import asyncio
from datetime import datetime, timezone

import httpx
import secrets
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import TextToSqlRequest, TextToSqlResponse
from app.config import (
    AI_SERVICE_BASE_URL,
    AI_SERVICE_TIMEOUT_SECONDS,
    OLLAMA_BASE_URL,
    OLLAMA_KEEP_ALIVE,
    OLLAMA_NUM_GPU,
    OLLAMA_SQL_MODEL,
    OLLAMA_SQL_NUM_BATCH,
    OLLAMA_SQL_NUM_CTX,
    OLLAMA_SQL_NUM_PREDICT,
    OLLAMA_TIMEOUT_SECONDS,
    SQL_MODEL_NAME,
    SQL_PROVIDER_OLLAMA,
    SQL_RULES,
    SQL_SYSTEM_PROMPT,
    SQL_TEMPERATURE,
)
from app.database.models import PromptModel, SqlSchemaModel, ThreadModel, UserModel
from app.services.ai.client import (
    build_chat_payload,
    extract_ai_message_content,
    format_ai_error,
    post_ai_completion,
)
from app.services.ai.ollama import extract_ollama_message_content, post_ollama_chat_completion
from app.services.ai.providers import resolve_sql_provider
from app.services.schema_summary import WARMED_SCHEMA_IDS, get_schema_summary_cached
from app.services.sql.audit import persist_sql_generation_log
from app.services.sql.cache import (
    build_sql_cache_fuzzy_bucket,
    build_sql_cache_key,
    lookup_cached_sql,
    normalize_query_for_cache,
    sql_response_cache,
)
from app.services.sql.intent import (
    IntentResult,
    extract_last_sql,
    resolve_sql_intent,
)
from app.services.sql.intent import INTENT_SOURCE_CACHE
from app.services.sql.prompts import build_sql_prompt
from app.services.sql.safety import (
    ensure_sql_comments,
    extract_sql_from_response,
    is_select_only_sql,
)
from app.services.warmup import warm_sql_schema_context


def persist_prompt(
    db: Session,
    thread_id: str,
    message_id: str,
    user_id: str,
    prompt_text: str,
) -> None:
    thread = (
        db.query(ThreadModel)
        .filter(ThreadModel.id == thread_id, ThreadModel.user_id == user_id)
        .first()
    )
    if thread is None:
        return
    existing_prompt = (
        db.query(PromptModel)
        .filter(
            PromptModel.thread_id == thread_id,
            PromptModel.message_id == message_id,
        )
        .first()
    )
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    if existing_prompt is None:
        db.add(
            PromptModel(
                id=secrets.token_urlsafe(12),
                thread_id=thread_id,
                message_id=message_id,
                prompt_text=prompt_text,
                created_at=now_ms,
            )
        )
    else:
        existing_prompt.prompt_text = prompt_text
        existing_prompt.created_at = now_ms
    db.commit()


def _finish_response(
    *,
    sql: str,
    request: TextToSqlRequest,
    model: str,
    prompt: str,
    intent_result: IntentResult,
    cached: bool,
    db: Session,
    current_user: UserModel,
    sql_provider: str,
    raw_response: str = "",
) -> TextToSqlResponse:
    if request.threadId and request.assistantMessageId:
        persist_sql_generation_log(
            db,
            thread_id=request.threadId,
            user_id=current_user.id,
            user_message_id=request.userMessageId,
            assistant_message_id=request.assistantMessageId,
            user_query=request.query,
            intent_result=intent_result,
            sql_provider=sql_provider,
            model=model,
            cached=cached,
            prompt_text=prompt,
            raw_response=raw_response,
            generated_sql=sql,
        )

    log_source = INTENT_SOURCE_CACHE if cached else intent_result.source
    return TextToSqlResponse(
        sql=sql,
        query=request.query,
        model=model,
        prompt=prompt,
        cached=cached,
        intent=intent_result.intent,
        intentSource=log_source,
        classifierAnswer=intent_result.classifier_answer or None,
        heuristicIntent=intent_result.heuristic_intent,
    )


async def generate_sql(
    request: TextToSqlRequest,
    current_user: UserModel,
    db: Session,
) -> TextToSqlResponse:
    """Convert natural language query to SQL using the database schema."""
    if not request.schemaId:
        raise HTTPException(status_code=400, detail="Schema is required")

    user_schema = (
        db.query(SqlSchemaModel)
        .filter(
            SqlSchemaModel.id == request.schemaId,
            SqlSchemaModel.user_id == current_user.id,
        )
        .first()
    )
    if user_schema is None:
        raise HTTPException(status_code=400, detail="Schema not found")

    schema_summary = get_schema_summary_cached(user_schema.id, user_schema.schema_text)
    schema_faq = (user_schema.schema_faq or "").strip()
    sql_provider = resolve_sql_provider(request.model)
    model = OLLAMA_SQL_MODEL if sql_provider == SQL_PROVIDER_OLLAMA else SQL_MODEL_NAME
    last_sql = extract_last_sql(request.messages, request.query)

    if user_schema.id not in WARMED_SCHEMA_IDS:
        asyncio.create_task(warm_sql_schema_context(user_schema.id, schema_summary))

    provider_timeout = (
        OLLAMA_TIMEOUT_SECONDS if sql_provider == SQL_PROVIDER_OLLAMA else AI_SERVICE_TIMEOUT_SECONDS
    )
    normalized_query = normalize_query_for_cache(request.query)

    try:
        async with httpx.AsyncClient(timeout=provider_timeout) as client:
            intent_result = await resolve_sql_intent(
                client,
                SQL_MODEL_NAME,
                request.query,
                last_sql,
                sql_provider,
                model,
            )
            print(
                f"[sql] intent={intent_result.intent} source={intent_result.source} "
                f"heuristic={intent_result.heuristic_intent} "
                f"classifier={intent_result.classifier_answer!r}"
            )

            prompt = build_sql_prompt(
                intent=intent_result.intent,
                query=request.query,
                schema_summary=schema_summary,
                schema_faq=schema_faq,
                schema_text=user_schema.schema_text,
                last_sql=last_sql,
                messages=request.messages,
                compact_for_ollama=(sql_provider == SQL_PROVIDER_OLLAMA),
            )

            cached_sql = lookup_cached_sql(
                schema_id=user_schema.id,
                schema_updated_at=user_schema.updated_at,
                sql_provider=sql_provider,
                model=model,
                intent=intent_result.intent,
                normalized_query=normalized_query,
                last_sql=last_sql,
            )
            if cached_sql:
                print("[sql] cache hit")
                if request.threadId and request.assistantMessageId:
                    persist_prompt(
                        db,
                        request.threadId,
                        request.assistantMessageId,
                        current_user.id,
                        prompt,
                    )
                return _finish_response(
                    sql=cached_sql,
                    request=request,
                    model=model,
                    prompt=prompt,
                    intent_result=intent_result,
                    cached=True,
                    db=db,
                    current_user=current_user,
                    sql_provider=sql_provider,
                )

            if sql_provider == SQL_PROVIDER_OLLAMA:
                response = await post_ollama_chat_completion(
                    client,
                    {
                        "model": model,
                        "stream": False,
                        "keep_alive": OLLAMA_KEEP_ALIVE,
                        "messages": [
                            {
                                "role": "system",
                                "content": f"{SQL_SYSTEM_PROMPT}\n\n{SQL_RULES}",
                            },
                            {"role": "user", "content": prompt},
                        ],
                        "options": {
                            "temperature": max(0.0, min(SQL_TEMPERATURE, 0.3)),
                            "num_ctx": max(256, OLLAMA_SQL_NUM_CTX),
                            "num_predict": max(64, OLLAMA_SQL_NUM_PREDICT),
                            "num_batch": max(32, OLLAMA_SQL_NUM_BATCH),
                            "num_gpu": OLLAMA_NUM_GPU,
                        },
                    },
                )
            else:
                response = await post_ai_completion(
                    client,
                    build_chat_payload(
                        [
                            {"role": "system", "content": f"{SQL_SYSTEM_PROMPT}\n\n{SQL_RULES}"},
                            {"role": "user", "content": prompt},
                        ],
                        model,
                        temperature=max(0.0, min(SQL_TEMPERATURE, 0.3)),
                    ),
                )

            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"AI service error: {format_ai_error(response)}",
                )

            result = response.json()
            if sql_provider == SQL_PROVIDER_OLLAMA:
                raw_response = extract_ollama_message_content(result).strip()
            else:
                raw_response = extract_ai_message_content(result).strip()
            print(f"[sql] raw model response: {raw_response!r}")
            sql_query = extract_sql_from_response(raw_response)
            sql_query = ensure_sql_comments(sql_query, request.query)

            is_safe, reason = is_select_only_sql(sql_query)
            if not is_safe:
                raise HTTPException(status_code=422, detail=f"Unsafe SQL blocked: {reason}")

            cache_key = build_sql_cache_key(
                user_schema.id,
                user_schema.updated_at,
                sql_provider,
                model,
                intent_result.intent,
                normalized_query,
                last_sql,
            )
            fuzzy_bucket = build_sql_cache_fuzzy_bucket(
                user_schema.id,
                user_schema.updated_at,
                sql_provider,
                model,
                intent_result.intent,
                last_sql,
            )
            sql_response_cache.put(cache_key, sql_query, normalized_query, fuzzy_bucket)

            if request.threadId and request.assistantMessageId:
                persist_prompt(
                    db,
                    request.threadId,
                    request.assistantMessageId,
                    current_user.id,
                    prompt,
                )

            return _finish_response(
                sql=sql_query,
                request=request,
                model=model,
                prompt=prompt,
                intent_result=intent_result,
                cached=False,
                db=db,
                current_user=current_user,
                sql_provider=sql_provider,
                raw_response=raw_response,
            )

    except httpx.ConnectError:
        if resolve_sql_provider(request.model) == SQL_PROVIDER_OLLAMA:
            raise HTTPException(
                status_code=503,
                detail=f"Cannot connect to Ollama service at {OLLAMA_BASE_URL}.",
            )
        raise HTTPException(
            status_code=503,
            detail=f"Cannot connect to AI service at {AI_SERVICE_BASE_URL}.",
        )
    except httpx.ReadTimeout:
        if resolve_sql_provider(request.model) == SQL_PROVIDER_OLLAMA:
            raise HTTPException(
                status_code=504,
                detail=(
                    "Ollama timed out while generating SQL. "
                    "Try a shorter request or smaller schema/FAQ."
                ),
            )
        raise HTTPException(status_code=504, detail="AI service timed out")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e) or "Unexpected server error")
