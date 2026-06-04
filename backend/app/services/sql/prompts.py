import re
from typing import Optional

from app.api.schemas import TextToSqlMessage
from app.config import (
    ENHANCEMENT_KEYWORDS,
    OLLAMA_SCHEMA_FAQ_MAX_CHARS,
    OLLAMA_SCHEMA_SUMMARY_MAX_CHARS,
    SQL_ENHANCEMENT_INSTRUCTIONS,
    SQL_FAQ_EXAMPLES_MAX_CHARS,
    SQL_FEW_SHOT_EXAMPLES,
    SQL_INTENT_ENHANCE,
    SQL_INTENT_FRESH,
    SQL_INTENT_REFINE,
    SQL_RULES,
    SQL_SYSTEM_PROMPT,
    SqlIntent,
)
from app.services.ai.ollama import compact_prompt_text


def infer_sql_dialect(schema_text: str) -> str:
    """Infer SQL dialect from CREATE TABLE / DDL cues in the schema."""
    upper = (schema_text or "").upper()
    if "IDENTITY" in upper or re.search(r"\bTOP\s+\d+\b", upper) or "NVARCHAR" in upper:
        return "Microsoft SQL Server (T-SQL)"
    if "`" in schema_text or "AUTO_INCREMENT" in upper or "ENGINE=INNODB" in upper:
        return "MySQL"
    if "SERIAL" in upper or "::" in schema_text:
        return "PostgreSQL"
    return "ANSI SQL (prefer LIMIT for row caps unless SCHEMA uses TOP)"


def extract_faq_examples(schema_faq: str, max_chars: int = SQL_FAQ_EXAMPLES_MAX_CHARS) -> str:
    """Surface FAQ snippets that look like examples or business rules."""
    faq = (schema_faq or "").strip()
    if not faq:
        return ""
    has_examples = (
        "REQUEST:" in faq.upper()
        or "SQL:" in faq.upper()
        or re.search(r"^[\s]*[-*]", faq, re.MULTILINE)
    )
    if not has_examples:
        return ""
    return compact_prompt_text(faq, max_chars)


def extract_recent_user_requests(
    messages: Optional[list[TextToSqlMessage]],
    current_query: str,
    limit: int = 3,
) -> list[str]:
    """Last N user messages before the current turn (for refine context)."""
    if not messages:
        return []
    cleaned: list[str] = []
    for m in messages:
        if m.role == "user" and m.content and m.content.strip():
            cleaned.append(m.content.strip())
    if cleaned and cleaned[-1].strip() == current_query.strip():
        cleaned = cleaned[:-1]
    return cleaned[-limit:] if cleaned else []


def build_sql_task_block(
    intent: SqlIntent,
    query: str,
    last_sql: Optional[str],
    prior_user_requests: list[str],
) -> str:
    if intent == SQL_INTENT_FRESH or not last_sql:
        return f"### Task\nREQUEST: {query}\nSQL:"

    prior_block = ""
    if prior_user_requests:
        lines = "\n".join(f"- {req}" for req in prior_user_requests)
        prior_block = f"### Prior user requests (context)\n{lines}\n\n"

    if intent == SQL_INTENT_ENHANCE:
        instructions = (
            "Take the Current query above as the base. Optimize it for performance and clarity "
            "while preserving the same logical result.\n"
            f"{SQL_ENHANCEMENT_INSTRUCTIONS}\n"
            "Return '-- Reason', then the full updated SQL ending with ';'.\n"
        )
    else:
        instructions = (
            "Take the Current query above as the base. Apply ONLY the modification "
            "described. Keep every existing SELECT column, JOIN, WHERE condition, "
            "ORDER BY and LIMIT from the base query. Only add or change what the "
            "modification asks for. Keep it read-only (SELECT or WITH...SELECT only). "
            "Return '-- Reason', then the full updated SQL ending with ';'.\n"
        )

    return (
        f"### Current query\n{last_sql}\n\n"
        f"{prior_block}"
        f"### Modification request\n{query}\n\n"
        f"### Instructions\n{instructions}"
        "SQL:"
    )


def build_sql_prompt(
    *,
    intent: SqlIntent,
    query: str,
    schema_summary: str,
    schema_faq: str,
    schema_text: str,
    last_sql: Optional[str],
    messages: Optional[list[TextToSqlMessage]],
    compact_for_ollama: bool = False,
) -> str:
    dialect = infer_sql_dialect(schema_text)
    summary = schema_summary
    faq_body = schema_faq or "N/A"
    if compact_for_ollama:
        summary = compact_prompt_text(schema_summary, OLLAMA_SCHEMA_SUMMARY_MAX_CHARS)
        faq_body = compact_prompt_text(schema_faq or "N/A", OLLAMA_SCHEMA_FAQ_MAX_CHARS)

    faq_examples = extract_faq_examples(
        schema_faq,
        OLLAMA_SCHEMA_FAQ_MAX_CHARS if compact_for_ollama else SQL_FAQ_EXAMPLES_MAX_CHARS,
    )
    faq_examples_block = ""
    if faq_examples:
        faq_examples_block = f"### Schema-specific examples\n{faq_examples}\n\n"

    prior_requests = (
        extract_recent_user_requests(messages, query)
        if intent in (SQL_INTENT_REFINE, SQL_INTENT_ENHANCE)
        else []
    )
    task_block = build_sql_task_block(intent, query, last_sql, prior_requests)

    return (
        f"{SQL_SYSTEM_PROMPT}\n\n"
        f"SQL dialect: {dialect}\n\n"
        f"SCHEMA (table: columns):\n{summary}\n\n"
        f"SCHEMA FAQ (markdown):\n{faq_body}\n\n"
        f"{faq_examples_block}"
        f"{SQL_RULES}\n\n"
        f"{SQL_FEW_SHOT_EXAMPLES}"
        f"{task_block}"
    )
