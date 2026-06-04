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
from app.services.sql.cache import (
    build_sql_cache_fuzzy_bucket,
    build_sql_cache_key,
    normalize_query_for_cache,
    sql_response_cache,
)
from app.services.sql.intent import extract_last_sql, resolve_sql_intent
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
            intent = await resolve_sql_intent(
                client, SQL_MODEL_NAME, request.query, last_sql
            )
            print(f"[sql] intent={intent}")

            prompt = build_sql_prompt(
                intent=intent,
                query=request.query,
                schema_summary=schema_summary,
                schema_faq=schema_faq,
                schema_text=user_schema.schema_text,
                last_sql=last_sql,
                messages=request.messages,
                compact_for_ollama=(sql_provider == SQL_PROVIDER_OLLAMA),
            )

            cache_key = build_sql_cache_key(
                user_schema.id,
                user_schema.updated_at,
                sql_provider,
                model,
                intent,
                normalized_query,
                last_sql,
            )
            fuzzy_bucket = build_sql_cache_fuzzy_bucket(
                user_schema.id,
                user_schema.updated_at,
                sql_provider,
                model,
                intent,
                last_sql,
            )
            cached_sql = sql_response_cache.get(cache_key, normalized_query, fuzzy_bucket)
            if cached_sql:
                if request.threadId and request.assistantMessageId:
                    persist_prompt(
                        db,
                        request.threadId,
                        request.assistantMessageId,
                        current_user.id,
                        prompt,
                    )
                return TextToSqlResponse(
                    sql=cached_sql,
                    query=request.query,
                    model=model,
                    prompt=prompt,
                    cached=True,
                    intent=intent,
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

            sql_response_cache.put(cache_key, sql_query, normalized_query, fuzzy_bucket)

            if request.threadId and request.assistantMessageId:
                persist_prompt(
                    db,
                    request.threadId,
                    request.assistantMessageId,
                    current_user.id,
                    prompt,
                )

            return TextToSqlResponse(
                sql=sql_query,
                query=request.query,
                model=model,
                prompt=prompt,
                cached=False,
                intent=intent,
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
