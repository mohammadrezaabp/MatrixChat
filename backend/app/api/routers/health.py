from fastapi import APIRouter

from app.config import AI_SERVICE_MODEL, CHAT_MODEL_NAME, SQL_MODEL_NAME

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    return {
        "status": "ok",
        "chat_model": CHAT_MODEL_NAME,
        "sql_model": SQL_MODEL_NAME,
        "ai_service_model": AI_SERVICE_MODEL,
    }
