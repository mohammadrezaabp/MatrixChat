import re
from typing import Optional

import httpx

from app.api.schemas import TextToSqlMessage
from app.config import (
    ENHANCEMENT_KEYWORDS,
    REFINE_KEYWORDS,
    SQL_INTENT_ENHANCE,
    SQL_INTENT_FRESH,
    SQL_INTENT_REFINE,
    SqlIntent,
)
from app.services.ai.client import build_chat_payload, extract_ai_message_content, post_ai_completion


def keyword_intent(request: str) -> Optional[bool]:
    """Fast keyword pre-check. True=refine, False=fresh, None=ambiguous."""
    lower = request.lower()
    if any(kw in lower for kw in REFINE_KEYWORDS):
        return True
    return None


def is_enhancement_request(query: str) -> bool:
    lower = query.lower()
    return any(keyword in lower for keyword in ENHANCEMENT_KEYWORDS)


async def classify_intent(
    client: httpx.AsyncClient,
    model: str,
    last_sql: str,
    new_request: str,
) -> bool:
    """
    Ask the model whether new_request is a REFINEMENT of last_sql or a NEW query.
    Returns True if REFINE, False if NEW.
    """
    prompt = (
        "Decide if the new database request should REFINE the existing SQL or start as a NEW query.\n\n"
        f"Existing SQL: {last_sql}\n"
        f"New request: {new_request}\n\n"
        "Reply with exactly one word.\n"
        "- If the request adds/changes/removes something in the existing SQL → REFINE\n"
        "- If the request is about completely different data or a new unrelated question → NEW\n"
        "Answer:"
    )
    try:
        resp = await post_ai_completion(
            client,
            build_chat_payload(
                [
                    {"role": "system", "content": "Reply with exactly one word: REFINE or NEW."},
                    {"role": "user", "content": prompt},
                ],
                model,
                stream=False,
                temperature=0.0,
                top_p=1.0,
                max_tokens=4,
            ),
        )
        if resp.status_code == 200:
            answer = extract_ai_message_content(resp.json()).strip().upper()
            print(f"[sql] intent classifier answer: {answer!r}")
            return "REFINE" in answer
    except Exception as exc:
        print(f"[sql] intent classifier failed: {exc}")
    return False


def extract_last_sql(
    messages: Optional[list[TextToSqlMessage]],
    current_query: str,
) -> Optional[str]:
    """Return the most recent valid SQL from the conversation history, or None."""
    if not messages:
        return None

    cleaned: list[TextToSqlMessage] = []
    for m in messages:
        if not m.content or m.role not in ("user", "assistant"):
            continue
        cleaned.append(m)

    if cleaned and cleaned[-1].role == "user" and cleaned[-1].content.strip() == current_query.strip():
        cleaned = cleaned[:-1]

    for m in reversed(cleaned):
        if m.role != "assistant":
            continue
        text = m.content.strip()
        if not text or text == ";":
            continue
        if m.isSql or re.match(r"^\s*(SELECT|INSERT|UPDATE|DELETE|WITH)\b", text, re.IGNORECASE):
            return text if text.endswith(";") else text + ";"
    return None


async def resolve_sql_intent(
    client: httpx.AsyncClient,
    classifier_model: str,
    query: str,
    last_sql: Optional[str],
) -> SqlIntent:
    if not last_sql:
        return SQL_INTENT_FRESH
    if is_enhancement_request(query):
        return SQL_INTENT_ENHANCE
    kw = keyword_intent(query)
    if kw is True:
        return SQL_INTENT_REFINE
    is_refine = await classify_intent(client, classifier_model, last_sql, query)
    return SQL_INTENT_REFINE if is_refine else SQL_INTENT_FRESH
