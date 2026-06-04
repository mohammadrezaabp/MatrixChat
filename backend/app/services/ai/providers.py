from typing import Optional

from app.config import OLLAMA_SQL_MODEL, SQL_PROVIDER_DEEPSEEK, SQL_PROVIDER_OLLAMA


def resolve_sql_provider(model_hint: Optional[str]) -> str:
    hint = (model_hint or "").strip().lower()
    if hint in {SQL_PROVIDER_OLLAMA, OLLAMA_SQL_MODEL.lower()}:
        return SQL_PROVIDER_OLLAMA
    return SQL_PROVIDER_DEEPSEEK
