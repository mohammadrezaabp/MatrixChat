from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from app.config import DATABASE_URL
from app.database.models import Base
from app.services.auth import hash_password

engine = None
SessionLocal = None

if DATABASE_URL:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    if SessionLocal is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_auth_schema() -> None:
    if engine is None:
        return
    insp = inspect(engine)
    if not insp.has_table("threads"):
        return
    thread_columns = {col["name"] for col in insp.get_columns("threads")}
    if "user_id" in thread_columns:
        return

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO users (id, username, password_hash, created_at)
                VALUES (:id, :username, :password_hash, :created_at)
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {
                "id": "legacy",
                "username": "legacy",
                "password_hash": hash_password("legacy-migration-account"),
                "created_at": int(datetime.now(timezone.utc).timestamp() * 1000),
            },
        )
        conn.execute(text("ALTER TABLE threads ADD COLUMN user_id VARCHAR NOT NULL DEFAULT 'legacy'"))
        conn.execute(
            text(
                "ALTER TABLE threads ADD CONSTRAINT fk_threads_user_id "
                "FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE"
            )
        )


def ensure_thread_schema_column() -> None:
    if engine is None:
        return
    insp = inspect(engine)
    if not insp.has_table("threads"):
        return
    thread_columns = {col["name"] for col in insp.get_columns("threads")}
    if "schema_id" in thread_columns:
        return
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE threads ADD COLUMN schema_id VARCHAR NULL"))


def ensure_thread_sql_model_column() -> None:
    if engine is None:
        return
    insp = inspect(engine)
    if not insp.has_table("threads"):
        return
    thread_columns = {col["name"] for col in insp.get_columns("threads")}
    if "sql_model" in thread_columns:
        return
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE threads ADD COLUMN sql_model VARCHAR NULL"))


def ensure_schema_faq_column() -> None:
    if engine is None:
        return
    insp = inspect(engine)
    if not insp.has_table("sql_schemas"):
        return
    schema_columns = {col["name"] for col in insp.get_columns("sql_schemas")}
    if "schema_faq" in schema_columns:
        return
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE sql_schemas ADD COLUMN schema_faq TEXT NOT NULL DEFAULT ''"))


def init_db() -> None:
    if engine is not None:
        Base.metadata.create_all(bind=engine)
        ensure_auth_schema()
        ensure_thread_schema_column()
        ensure_thread_sql_model_column()
        ensure_schema_faq_column()
        print("[db] tables ready")
    else:
        print("[db] DATABASE_URL not set, skipping DB init")
