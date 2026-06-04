import re
from dataclasses import dataclass
from typing import Optional

import httpx

from app.api.schemas import TextToSqlMessage
from app.config import (
    ENHANCEMENT_KEYWORDS,
    REFINE_KEYWORDS,
    SQL_INTENT_CLASSIFIER_ENABLED,
    SQL_INTENT_ENHANCE,
    SQL_INTENT_FRESH,
    SQL_INTENT_REFINE,
    SQL_INTENT_USE_OLLAMA_CLASSIFIER,
    SQL_PROVIDER_OLLAMA,
    SqlIntent,
)
from app.services.ai.client import build_chat_payload, extract_ai_message_content, post_ai_completion
from app.services.ai.ollama import extract_ollama_message_content, post_ollama_chat_completion

# Phrases that refer to the previous SQL (should refine, not start fresh).
_REFINE_CONTEXT_PHRASES = (
    "that query",
    "this query",
    "the query",
    "previous query",
    "same query",
    "above sql",
    "current query",
    "that sql",
    "in that",
    "from that",
    "to that",
    "those results",
    "those symbols",
    "the above",
    "keep the",
    "still ",
)

INTENT_SOURCE_KEYWORD = "keyword"
INTENT_SOURCE_ENHANCEMENT = "enhancement"
INTENT_SOURCE_HEURISTIC = "heuristic"
INTENT_SOURCE_HEURISTIC_UNRELATED = "heuristic_unrelated"
INTENT_SOURCE_OLLAMA_CLASSIFIER = "ollama_classifier"
INTENT_SOURCE_DEEPSEEK_CLASSIFIER = "deepseek_classifier"
INTENT_SOURCE_CACHE = "cache"


@dataclass
class IntentResult:
    intent: SqlIntent
    source: str
    heuristic_intent: SqlIntent
    classifier_answer: str = ""


def keyword_intent(request: str) -> Optional[bool]:
    """Fast keyword pre-check. True=refine, False=fresh, None=ambiguous."""
    lower = request.lower()
    if any(kw in lower for kw in REFINE_KEYWORDS):
        return True
    return None


def is_enhancement_request(query: str) -> bool:
    lower = query.lower()
    return any(keyword in lower for keyword in ENHANCEMENT_KEYWORDS)


def looks_like_unrelated_follow_up(query: str) -> bool:
    """
    Detect a new topic that should not inherit the previous SQL.
    """
    lower = query.lower().strip()
    if any(phrase in lower for phrase in _REFINE_CONTEXT_PHRASES):
        return False
    if keyword_intent(query) is True:
        return False
    if is_enhancement_request(query):
        return False
    # Short standalone questions are usually new requests, not edits.
    if len(lower.split()) <= 18:
        return True
    return False


def _truncate_sql_for_classifier(sql: str, max_chars: int = 1200) -> str:
    cleaned = (sql or "").strip()
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 3] + "..."


def _build_classifier_prompt(last_sql: str, new_request: str) -> str:
    return (
        "Decide if the new request should REFINE the existing SQL or start as a NEW query.\n\n"
        f"Existing SQL:\n{_truncate_sql_for_classifier(last_sql)}\n\n"
        f"New request: {new_request}\n\n"
        "Rules:\n"
        "- REFINE: adds, removes, or changes something in the existing SQL (filters, columns, joins).\n"
        "- NEW: unrelated question, different report, or a new analysis that should not reuse the old SQL.\n"
        "Examples:\n"
        "- 'also include email' → REFINE\n"
        "- 'only last 30 days' → REFINE\n"
        "- 'the richest user' (after an unrelated prior query) → NEW\n"
        "- 'top customers by revenue' (new topic) → NEW\n\n"
        "Reply with exactly one word: REFINE or NEW.\n"
        "Answer:"
    )


async def classify_intent_deepseek(
    client: httpx.AsyncClient,
    model: str,
    last_sql: str,
    new_request: str,
) -> tuple[bool, str]:
    try:
        resp = await post_ai_completion(
            client,
            build_chat_payload(
                [
                    {"role": "system", "content": "Reply with exactly one word: REFINE or NEW."},
                    {"role": "user", "content": _build_classifier_prompt(last_sql, new_request)},
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
            print(f"[sql] intent classifier (deepseek) answer: {answer!r}")
            return "REFINE" in answer, answer
    except Exception as exc:
        print(f"[sql] intent classifier (deepseek) failed: {exc}")
    return False, ""


async def classify_intent_ollama(
    client: httpx.AsyncClient,
    model: str,
    last_sql: str,
    new_request: str,
) -> tuple[bool, str]:
    try:
        resp = await post_ollama_chat_completion(
            client,
            {
                "model": model,
                "stream": False,
                "messages": [
                    {"role": "system", "content": "Reply with exactly one word: REFINE or NEW."},
                    {"role": "user", "content": _build_classifier_prompt(last_sql, new_request)},
                ],
                "options": {
                    "temperature": 0.0,
                    "num_ctx": 2048,
                    "num_predict": 8,
                    "num_gpu": -1,
                },
            },
        )
        if resp.status_code == 200:
            answer = extract_ollama_message_content(resp.json()).strip().upper()
            print(f"[sql] intent classifier (ollama) answer: {answer!r}")
            return "REFINE" in answer, answer
    except Exception as exc:
        print(f"[sql] intent classifier (ollama) failed: {exc}")
    return False, ""


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


def resolve_sql_intent_heuristic(query: str, last_sql: Optional[str]) -> SqlIntent:
    """Fast local intent detection (no network)."""
    if not last_sql:
        return SQL_INTENT_FRESH
    if is_enhancement_request(query):
        return SQL_INTENT_ENHANCE
    if keyword_intent(query) is True:
        return SQL_INTENT_REFINE
    if looks_like_unrelated_follow_up(query):
        return SQL_INTENT_FRESH
    # Ambiguous: default to fresh so unrelated follow-ups do not inherit old SQL.
    return SQL_INTENT_FRESH


def is_ambiguous_follow_up(query: str, last_sql: Optional[str]) -> bool:
    if not last_sql:
        return False
    if is_enhancement_request(query):
        return False
    if keyword_intent(query) is True:
        return False
    if looks_like_unrelated_follow_up(query):
        return False
    return True


async def resolve_sql_intent(
    client: httpx.AsyncClient,
    classifier_model: str,
    query: str,
    last_sql: Optional[str],
    sql_provider: str,
    ollama_model: str,
) -> IntentResult:
    heuristic = resolve_sql_intent_heuristic(query, last_sql)

    if not last_sql:
        return IntentResult(SQL_INTENT_FRESH, INTENT_SOURCE_HEURISTIC, heuristic)
    if is_enhancement_request(query):
        return IntentResult(SQL_INTENT_ENHANCE, INTENT_SOURCE_ENHANCEMENT, heuristic)
    if keyword_intent(query) is True:
        return IntentResult(SQL_INTENT_REFINE, INTENT_SOURCE_KEYWORD, heuristic)
    if looks_like_unrelated_follow_up(query):
        return IntentResult(SQL_INTENT_FRESH, INTENT_SOURCE_HEURISTIC_UNRELATED, heuristic)

    if not is_ambiguous_follow_up(query, last_sql):
        return IntentResult(heuristic, INTENT_SOURCE_HEURISTIC, heuristic)

    if sql_provider == SQL_PROVIDER_OLLAMA and SQL_INTENT_USE_OLLAMA_CLASSIFIER:
        is_refine, answer = await classify_intent_ollama(client, ollama_model, last_sql, query)
        intent = SQL_INTENT_REFINE if is_refine else SQL_INTENT_FRESH
        return IntentResult(intent, INTENT_SOURCE_OLLAMA_CLASSIFIER, heuristic, answer)

    if SQL_INTENT_CLASSIFIER_ENABLED:
        is_refine, answer = await classify_intent_deepseek(client, classifier_model, last_sql, query)
        intent = SQL_INTENT_REFINE if is_refine else SQL_INTENT_FRESH
        return IntentResult(intent, INTENT_SOURCE_DEEPSEEK_CLASSIFIER, heuristic, answer)

    return IntentResult(heuristic, INTENT_SOURCE_HEURISTIC, heuristic)
