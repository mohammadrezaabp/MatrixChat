from datetime import datetime, timezone

import secrets
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.api.schemas import MessageSchema, SqlGenerationLogSchema, ThreadSchema, UpsertThreadRequest
from app.database.models import SqlGenerationLogModel
from app.services.thread_export import build_thread_sql_export
from app.utils.content_disposition import attachment_content_disposition
from app.config import OLLAMA_SQL_MODEL, SQL_MODEL_NAME, SQL_PROVIDER_DEEPSEEK, SQL_PROVIDER_OLLAMA
from app.database.models import MessageModel, PromptModel, SqlSchemaModel, ThreadModel, UserModel
from app.database.session import get_db
from app.dependencies import get_current_user

router = APIRouter(prefix="/threads", tags=["threads"])


def thread_to_schema(t: ThreadModel) -> ThreadSchema:
    prompt_by_message_id: dict[str, str] = {}
    for p in t.prompts:
        if p.message_id not in prompt_by_message_id:
            prompt_by_message_id[p.message_id] = p.prompt_text

    return ThreadSchema(
        id=t.id,
        title=t.title,
        mode=t.mode,
        schemaId=t.schema_id,
        sqlModel=t.sql_model,
        updatedAt=t.updated_at,
        messages=[
            MessageSchema(
                id=m.id,
                role=m.role,
                content=m.content,
                isSql=m.is_sql,
                prompt=prompt_by_message_id.get(m.id),
            )
            for m in t.messages
        ],
    )


@router.get("", response_model=list[ThreadSchema])
def list_threads(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    threads = (
        db.query(ThreadModel)
        .filter(ThreadModel.user_id == current_user.id)
        .order_by(ThreadModel.updated_at.desc())
        .all()
    )
    return [thread_to_schema(t) for t in threads]


@router.get("/{thread_id}", response_model=ThreadSchema)
def get_thread(
    thread_id: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    t = (
        db.query(ThreadModel)
        .filter(ThreadModel.id == thread_id, ThreadModel.user_id == current_user.id)
        .first()
    )
    if not t:
        raise HTTPException(status_code=404, detail="Thread not found")
    return thread_to_schema(t)


@router.get("/{thread_id}/sql-generation-logs", response_model=list[SqlGenerationLogSchema])
def list_sql_generation_logs(
    thread_id: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    thread = (
        db.query(ThreadModel)
        .filter(ThreadModel.id == thread_id, ThreadModel.user_id == current_user.id)
        .first()
    )
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")
    if thread.mode != "sql":
        raise HTTPException(status_code=400, detail="Only SQL threads have generation logs")

    logs = (
        db.query(SqlGenerationLogModel)
        .filter(SqlGenerationLogModel.thread_id == thread_id)
        .order_by(SqlGenerationLogModel.created_at.asc())
        .all()
    )
    return [
        SqlGenerationLogSchema(
            id=item.id,
            assistantMessageId=item.assistant_message_id,
            userMessageId=item.user_message_id,
            userQuery=item.user_query,
            intent=item.intent,
            intentSource=item.intent_source,
            heuristicIntent=item.heuristic_intent,
            classifierAnswer=item.classifier_answer or "",
            sqlProvider=item.sql_provider,
            model=item.model,
            cached=item.cached,
            createdAt=item.created_at,
        )
        for item in logs
    ]


@router.get("/{thread_id}/export")
def export_thread_queries(
    thread_id: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    t = (
        db.query(ThreadModel)
        .options(joinedload(ThreadModel.messages))
        .filter(ThreadModel.id == thread_id, ThreadModel.user_id == current_user.id)
        .first()
    )
    if not t:
        raise HTTPException(status_code=404, detail="Thread not found")
    if t.mode != "sql":
        raise HTTPException(status_code=400, detail="Only SQL threads can be exported")

    schema_title = None
    if t.schema_id:
        schema = (
            db.query(SqlSchemaModel)
            .filter(
                SqlSchemaModel.id == t.schema_id,
                SqlSchemaModel.user_id == current_user.id,
            )
            .first()
        )
        if schema is not None:
            schema_title = schema.title

    filename, body = build_thread_sql_export(t, schema_title)
    return Response(
        content=body.encode("utf-8"),
        media_type="application/sql; charset=utf-8",
        headers={
            "Content-Disposition": attachment_content_disposition(filename),
        },
    )


@router.put("/{thread_id}", response_model=ThreadSchema)
def upsert_thread(
    thread_id: str,
    body: UpsertThreadRequest,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    t = (
        db.query(ThreadModel)
        .filter(ThreadModel.id == thread_id, ThreadModel.user_id == current_user.id)
        .first()
    )
    data = body.thread
    if thread_id != data.id:
        raise HTTPException(status_code=400, detail="Thread id mismatch")

    schema_id = data.schemaId if data.mode == "sql" else None
    sql_model = data.sqlModel if data.mode == "sql" else None
    if data.mode == "sql" and not schema_id:
        raise HTTPException(status_code=400, detail="SQL threads require a schema")
    if data.mode == "sql" and not sql_model:
        sql_model = SQL_PROVIDER_DEEPSEEK

    if sql_model and sql_model not in {
        SQL_PROVIDER_DEEPSEEK,
        SQL_PROVIDER_OLLAMA,
        SQL_MODEL_NAME,
        OLLAMA_SQL_MODEL,
    }:
        raise HTTPException(status_code=400, detail="Invalid SQL model")
    if schema_id is not None:
        schema_exists = (
            db.query(SqlSchemaModel)
            .filter(SqlSchemaModel.id == schema_id, SqlSchemaModel.user_id == current_user.id)
            .first()
        )
        if schema_exists is None:
            raise HTTPException(status_code=400, detail="Invalid schema id")

    if t is not None and t.mode == "sql" and t.schema_id is not None and schema_id != t.schema_id:
        raise HTTPException(status_code=400, detail="Schema cannot be changed for an existing SQL thread")
    if t is not None and t.mode == "sql" and t.sql_model is not None and sql_model != t.sql_model:
        raise HTTPException(status_code=400, detail="SQL model cannot be changed for an existing SQL thread")

    def apply_messages() -> None:
        for pos, msg in enumerate(data.messages):
            db.add(
                MessageModel(
                    id=msg.id,
                    thread_id=data.id,
                    role=msg.role,
                    content=msg.content,
                    is_sql=msg.isSql,
                    position=pos,
                )
            )
            if msg.prompt:
                db.add(
                    PromptModel(
                        id=secrets.token_urlsafe(12),
                        thread_id=data.id,
                        message_id=msg.id,
                        prompt_text=msg.prompt,
                        created_at=int(datetime.now(timezone.utc).timestamp() * 1000),
                    )
                )

    next_message_ids = [msg.id for msg in data.messages]

    def cleanup_stale_prompts() -> None:
        stale_query = db.query(PromptModel).filter(PromptModel.thread_id == thread_id)
        if next_message_ids:
            stale_query = stale_query.filter(~PromptModel.message_id.in_(next_message_ids))
        stale_query.delete(synchronize_session=False)

    if t is None:
        existing_other = db.query(ThreadModel).filter(ThreadModel.id == thread_id).first()
        if existing_other is not None:
            raise HTTPException(status_code=404, detail="Thread not found")
        t = ThreadModel(
            id=data.id,
            user_id=current_user.id,
            schema_id=schema_id,
            sql_model=sql_model,
            title=data.title,
            mode=data.mode,
            updated_at=data.updatedAt,
        )
        db.add(t)
        apply_messages()
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            t = (
                db.query(ThreadModel)
                .filter(ThreadModel.id == thread_id, ThreadModel.user_id == current_user.id)
                .first()
            )
            if t is None:
                raise HTTPException(status_code=409, detail="Thread id already exists")
            t.title = data.title
            t.mode = data.mode
            t.schema_id = schema_id
            t.sql_model = sql_model
            t.updated_at = data.updatedAt
            db.query(MessageModel).filter(MessageModel.thread_id == thread_id).delete()
            apply_messages()
            cleanup_stale_prompts()
            db.commit()
    else:
        t.title = data.title
        t.mode = data.mode
        t.schema_id = schema_id
        t.sql_model = sql_model
        t.updated_at = data.updatedAt
        db.query(MessageModel).filter(MessageModel.thread_id == thread_id).delete()
        apply_messages()
        cleanup_stale_prompts()
        db.commit()

    db.refresh(t)
    return thread_to_schema(t)


@router.delete("/{thread_id}", status_code=204)
def delete_thread(
    thread_id: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    t = (
        db.query(ThreadModel)
        .filter(ThreadModel.id == thread_id, ThreadModel.user_id == current_user.id)
        .first()
    )
    if not t:
        raise HTTPException(status_code=404, detail="Thread not found")
    db.delete(t)
    db.commit()
