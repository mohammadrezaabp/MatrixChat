import asyncio
import json
import random
from typing import AsyncIterator

import httpx
from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from app.api.schemas import ChatRequest, ChatResponse
from app.config import (
    AI_SERVICE_BASE_URL,
    AI_SERVICE_INITIAL_RETRY_DELAY_SECONDS,
    AI_SERVICE_MAX_RETRIES,
    AI_SERVICE_TIMEOUT_SECONDS,
    CHAT_MODEL_NAME,
    CHAT_SYSTEM_PROMPT,
    MAX_CHAT_HISTORY,
    RETRIABLE_STATUS_CODES,
)
from app.services.ai.client import (
    build_ai_completion_url,
    build_ai_headers,
    build_chat_payload,
    extract_ai_message_content,
    format_ai_error,
    post_ai_completion,
)


def _trim_history(request: ChatRequest) -> list[dict[str, str]]:
    history = [
        {"role": msg.role, "content": msg.content}
        for msg in request.messages
        if msg.role in ("user", "assistant") and msg.content
    ]
    if len(history) > MAX_CHAT_HISTORY:
        history = history[-MAX_CHAT_HISTORY:]
    return history


def _stream_retry_delay(attempt: int) -> float:
    """Exponential backoff with full jitter for streaming retries."""
    base = AI_SERVICE_INITIAL_RETRY_DELAY_SECONDS * (2 ** attempt)
    return random.uniform(0, base)


async def chat_completion(request: ChatRequest) -> ChatResponse:
    model = request.model or CHAT_MODEL_NAME
    messages = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}] + _trim_history(request)

    try:
        async with httpx.AsyncClient(timeout=AI_SERVICE_TIMEOUT_SECONDS) as client:
            response = await post_ai_completion(
                client,
                build_chat_payload(
                    messages,
                    model,
                    temperature=request.temperature or 0.7,
                ),
            )

        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"AI service error: {format_ai_error(response)}",
            )

        result = response.json()
        return ChatResponse(
            response=extract_ai_message_content(result),
            model=model,
        )
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail=f"Cannot connect to AI service at {AI_SERVICE_BASE_URL}.",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def chat_stream_response(request: ChatRequest) -> StreamingResponse:
    model = request.model or CHAT_MODEL_NAME
    messages = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}] + _trim_history(request)
    payload = {
        **build_chat_payload(
            messages,
            model,
            temperature=request.temperature or 0.7,
            stream=True,
        )
    }

    async def event_iter() -> AsyncIterator[str]:
        url = build_ai_completion_url()
        headers = build_ai_headers()

        for attempt in range(max(AI_SERVICE_MAX_RETRIES, 1)):
            try:
                async with httpx.AsyncClient(timeout=None) as client:
                    async with client.stream(
                        "POST",
                        url,
                        headers=headers,
                        json=payload,
                        follow_redirects=True,
                    ) as response:
                        if response.status_code == 200:
                            async for line in response.aiter_lines():
                                if not line:
                                    continue
                                if line.startswith("data:"):
                                    line = line.removeprefix("data:").strip()
                                if line == "[DONE]":
                                    yield json.dumps({"done": True}) + "\n"
                                    return
                                try:
                                    obj = json.loads(line)
                                except json.JSONDecodeError:
                                    continue
                                delta = extract_ai_message_content(obj)
                                if delta:
                                    yield json.dumps({"delta": delta}) + "\n"
                            return

                        if response.status_code not in RETRIABLE_STATUS_CODES or attempt >= AI_SERVICE_MAX_RETRIES - 1:
                            body = await response.aread()
                            error_text = body.decode("utf-8", "ignore").strip()
                            if not error_text:
                                location = response.headers.get("location")
                                if location:
                                    error_text = f"redirected to {location}"
                            if not error_text:
                                error_text = "no response body"
                            yield json.dumps(
                                {"error": f"{response.status_code} {response.reason_phrase}: {error_text}"}
                            ) + "\n"
                            return

                        # Rate-limited or other retriable error - wait and retry
                        await asyncio.sleep(_stream_retry_delay(attempt))

            except httpx.ConnectError:
                yield json.dumps({"error": f"Cannot connect to AI service at {AI_SERVICE_BASE_URL}."}) + "\n"
                return
            except Exception as exc:
                if attempt >= AI_SERVICE_MAX_RETRIES - 1:
                    yield json.dumps({"error": str(exc)}) + "\n"
                    return
                await asyncio.sleep(_stream_retry_delay(attempt))

    return StreamingResponse(event_iter(), media_type="application/x-ndjson")