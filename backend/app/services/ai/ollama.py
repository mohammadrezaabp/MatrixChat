import asyncio
from typing import Optional

import httpx
from fastapi import HTTPException

from app.config import (
    OLLAMA_BASE_URL,
    OLLAMA_INITIAL_RETRY_DELAY_SECONDS,
    OLLAMA_MAX_RETRIES,
    RETRIABLE_STATUS_CODES,
)


def build_ollama_chat_url() -> str:
    return f"{OLLAMA_BASE_URL.rstrip('/')}/api/chat"


def extract_ollama_message_content(payload: dict) -> str:
    message = payload.get("message") or {}
    if isinstance(message, dict) and message.get("content"):
        return message.get("content", "")
    return ""


def compact_prompt_text(text: str, max_chars: int) -> str:
    cleaned = (text or "").strip()
    if max_chars <= 0 or len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 3].rstrip() + "..."


async def post_ollama_chat_completion(client: httpx.AsyncClient, payload: dict) -> httpx.Response:
    url = build_ollama_chat_url()
    last_error: Exception | None = None

    for attempt in range(max(OLLAMA_MAX_RETRIES, 1)):
        try:
            response = await client.post(url, json=payload)
            if response.status_code not in RETRIABLE_STATUS_CODES or attempt >= OLLAMA_MAX_RETRIES - 1:
                return response
            last_error = HTTPException(status_code=response.status_code, detail=response.text)
        except httpx.RequestError as exc:
            last_error = exc
            if attempt >= OLLAMA_MAX_RETRIES - 1:
                raise

        await asyncio.sleep(OLLAMA_INITIAL_RETRY_DELAY_SECONDS * (2**attempt))

    if last_error is not None:
        raise last_error
    raise RuntimeError("Ollama request failed")
