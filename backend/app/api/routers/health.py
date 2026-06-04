from fastapi import APIRouter

from app.config import (
    AI_SERVICE_MODEL,
    CHAT_MODEL_NAME,
    OLLAMA_SQL_MODEL,
    SQL_CACHE_ENABLED,
    SQL_INTENT_CLASSIFIER_ENABLED,
    SQL_MODEL_NAME,
)
from app.services.ai.ollama_warmup import ollama_runtime_info

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    ollama = await ollama_runtime_info()
    return {
        "status": "ok",
        "chat_model": CHAT_MODEL_NAME,
        "sql_model": SQL_MODEL_NAME,
        "ai_service_model": AI_SERVICE_MODEL,
        "ollama_sql_model": OLLAMA_SQL_MODEL,
        "sql_cache_enabled": SQL_CACHE_ENABLED,
        "sql_intent_classifier_enabled": SQL_INTENT_CLASSIFIER_ENABLED,
        "ollama": ollama,
    }
