from datetime import datetime, timezone

import secrets
from sqlalchemy.orm import Session

from app.database.models import SqlGenerationLogModel, ThreadModel
from app.services.sql.intent import IntentResult


def persist_sql_generation_log(
    db: Session,
    *,
    thread_id: str,
    user_id: str,
    user_message_id: str | None,
    assistant_message_id: str,
    user_query: str,
    intent_result: IntentResult,
    sql_provider: str,
    model: str,
    cached: bool,
    prompt_text: str,
    raw_response: str,
    generated_sql: str,
) -> None:
    thread = (
        db.query(ThreadModel)
        .filter(ThreadModel.id == thread_id, ThreadModel.user_id == user_id)
        .first()
    )
    if thread is None:
        return

    existing = (
        db.query(SqlGenerationLogModel)
        .filter(
            SqlGenerationLogModel.thread_id == thread_id,
            SqlGenerationLogModel.assistant_message_id == assistant_message_id,
        )
        .first()
    )
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    payload = dict(
        user_message_id=user_message_id,
        user_query=user_query,
        intent=intent_result.intent,
        intent_source=intent_result.source,
        heuristic_intent=intent_result.heuristic_intent,
        classifier_answer=intent_result.classifier_answer or "",
        sql_provider=sql_provider,
        model=model,
        cached=cached,
        prompt_text=prompt_text,
        raw_response=raw_response,
        generated_sql=generated_sql,
        created_at=now_ms,
    )
    if existing is None:
        db.add(
            SqlGenerationLogModel(
                id=secrets.token_urlsafe(12),
                thread_id=thread_id,
                assistant_message_id=assistant_message_id,
                **payload,
            )
        )
    else:
        for key, value in payload.items():
            setattr(existing, key, value)
    db.commit()
