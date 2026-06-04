from datetime import datetime, timezone

import secrets
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.schemas import UserSchemaRequest, UserSchemaResponse
from app.database.models import SqlSchemaModel, ThreadModel, UserModel
from app.database.session import get_db
from app.dependencies import get_current_user
from app.services.schema_summary import get_schema_summary_cached, remove_schema_cache
from app.services.warmup import warm_sql_schema_context

router = APIRouter(prefix="/schemas", tags=["schemas"])


def schema_to_response(item: SqlSchemaModel) -> UserSchemaResponse:
    return UserSchemaResponse(
        id=item.id,
        title=item.title,
        schema=item.schema_text,
        faq=item.schema_faq or "",
        updatedAt=item.updated_at,
    )


@router.get("", response_model=list[UserSchemaResponse])
def list_user_schemas(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    items = (
        db.query(SqlSchemaModel)
        .filter(SqlSchemaModel.user_id == current_user.id)
        .order_by(SqlSchemaModel.updated_at.desc())
        .all()
    )
    return [schema_to_response(item) for item in items]


@router.post("", response_model=UserSchemaResponse, status_code=status.HTTP_201_CREATED)
def create_user_schema(
    body: UserSchemaRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    title = body.title.strip()
    cleaned = body.schema.strip()
    faq = (body.faq or "").strip()
    if len(title) < 2:
        raise HTTPException(status_code=400, detail="Title is too short")
    if len(cleaned) < 20:
        raise HTTPException(status_code=400, detail="Schema is too short")

    item = SqlSchemaModel(
        id=secrets.token_urlsafe(12),
        user_id=current_user.id,
        title=title,
        schema_text=cleaned,
        schema_faq=faq,
        updated_at=int(datetime.now(timezone.utc).timestamp() * 1000),
    )
    db.add(item)
    db.commit()
    summary = get_schema_summary_cached(item.id, item.schema_text)
    background_tasks.add_task(warm_sql_schema_context, item.id, summary)
    return schema_to_response(item)


@router.put("/{schema_id}", response_model=UserSchemaResponse)
def update_user_schema(
    schema_id: str,
    body: UserSchemaRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    item = (
        db.query(SqlSchemaModel)
        .filter(SqlSchemaModel.id == schema_id, SqlSchemaModel.user_id == current_user.id)
        .first()
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Schema not found")

    title = body.title.strip()
    cleaned = body.schema.strip()
    faq = (body.faq or "").strip()
    if len(title) < 2:
        raise HTTPException(status_code=400, detail="Title is too short")
    if len(cleaned) < 20:
        raise HTTPException(status_code=400, detail="Schema is too short")

    item.title = title
    item.schema_text = cleaned
    item.schema_faq = faq
    item.updated_at = int(datetime.now(timezone.utc).timestamp() * 1000)
    db.commit()
    remove_schema_cache(item.id)
    summary = get_schema_summary_cached(item.id, item.schema_text)
    background_tasks.add_task(warm_sql_schema_context, item.id, summary)
    return schema_to_response(item)


@router.delete("/{schema_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user_schema(
    schema_id: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    item = (
        db.query(SqlSchemaModel)
        .filter(SqlSchemaModel.id == schema_id, SqlSchemaModel.user_id == current_user.id)
        .first()
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Schema not found")
    in_use_count = (
        db.query(ThreadModel)
        .filter(
            ThreadModel.user_id == current_user.id,
            ThreadModel.mode == "sql",
            ThreadModel.schema_id == schema_id,
        )
        .count()
    )
    if in_use_count > 0:
        raise HTTPException(
            status_code=409,
            detail="Schema is used by one or more SQL threads and cannot be deleted",
        )
    db.delete(item)
    db.commit()
    remove_schema_cache(schema_id)
