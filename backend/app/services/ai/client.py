import asyncio
import random
from typing import Optional

import httpx
from fastapi import HTTPException

from app.config import (
    AI_SERVICE_API_KEY,
    AI_SERVICE_BASE_URL,
    AI_SERVICE_COMPLETIONS_PATH,
    AI_SERVICE_INITIAL_RETRY_DELAY_SECONDS,
    AI_SERVICE_MAX_RETRIES,
    RETRIABLE_STATUS_CODES,
)


def build_ai_completion_url() -> str:
    return f"{AI_SERVICE_BASE_URL.rstrip('/')}/{AI_SERVICE_COMPLETIONS_PATH.lstrip('/')}"


def build_ai_headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if AI_SERVICE_API_KEY:
        headers["Authorization"] = f"Bearer {AI_SERVICE_API_KEY}"
    return headers


def build_chat_payload(
    messages: list[dict[str, str]],
    model: str,
    *,
    temperature: float,
    stream: Optional[bool] = None,
    top_p: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> dict:
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    if stream is not None:
        payload["stream"] = stream
    if top_p is not None:
        payload["top_p"] = top_p
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    return payload


def extract_ai_message_content(payload: dict) -> str:
    choices = payload.get("choices") or []
    if not choices:
        return ""
    choice = choices[0] or {}
    message = choice.get("message") or {}
    if message.get("content"):
        return message.get("content", "")
    delta = choice.get("delta") or {}
    if delta.get("content"):
        return delta.get("content", "")
    if choice.get("text"):
        return choice.get("text", "")
    return ""


def format_ai_error(response: httpx.Response) -> str:
    body = (response.text or "").strip()
    if not body:
        location = response.headers.get("location")
        if location:
            body = f"redirected to {location}"
    if not body:
        body = "no response body"
    return f"{response.status_code} {response.reason_phrase}: {body}"


def _retry_delay(attempt: int) -> float:
    """Exponential backoff with full jitter to avoid thundering herd."""
    base = AI_SERVICE_INITIAL_RETRY_DELAY_SECONDS * (2 ** attempt)
    return random.uniform(0, base)


async def post_ai_completion(client: httpx.AsyncClient, payload: dict) -> httpx.Response:
    url = build_ai_completion_url()
    headers = build_ai_headers()
    last_error: Exception | None = None

    for attempt in range(max(AI_SERVICE_MAX_RETRIES, 1)):
        try:
            response = await client.post(url, headers=headers, json=payload, follow_redirects=True)
            if response.status_code not in RETRIABLE_STATUS_CODES or attempt >= AI_SERVICE_MAX_RETRIES - 1:
                return response
            last_error = HTTPException(status_code=response.status_code, detail=response.text)
        except httpx.RequestError as exc:
            last_error = exc
            if attempt >= AI_SERVICE_MAX_RETRIES - 1:
                raise

        await asyncio.sleep(_retry_delay(attempt))

    if last_error is not None:
        raise last_error
    raise RuntimeError("AI service request failed")