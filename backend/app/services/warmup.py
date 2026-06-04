from app.config import SCHEMA_WARMUP_LIMIT
from app.database.models import SqlSchemaModel
from app.database.session import SessionLocal
from app.services.schema_summary import WARMED_SCHEMA_IDS, get_schema_summary_cached


async def warm_sql_schema_context(schema_id: str, schema_summary: str) -> None:
    if not schema_summary.strip():
        return
    WARMED_SCHEMA_IDS.add(schema_id)
    print(f"[warm] SQL schema context ready: {schema_id}")


async def warm_recent_schema_contexts() -> None:
    if SessionLocal is None:
        return
    db = SessionLocal()
    try:
        recent_schemas = (
            db.query(SqlSchemaModel)
            .order_by(SqlSchemaModel.updated_at.desc())
            .limit(max(SCHEMA_WARMUP_LIMIT, 0))
            .all()
        )
        for item in recent_schemas:
            summary = get_schema_summary_cached(item.id, item.schema_text)
            await warm_sql_schema_context(item.id, summary)
    except Exception as exc:
        print(f"[warm] Could not preload schema contexts: {exc}")
    finally:
        db.close()
