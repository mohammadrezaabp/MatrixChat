import re
from datetime import datetime, timezone

from app.database.models import ThreadModel


def _sanitize_filename(title: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", (title or "thread").strip())
    cleaned = re.sub(r"\s+", "-", cleaned)
    return (cleaned[:80] or "thread").strip("-") or "thread"


def _is_exportable_sql(content: str, is_sql: bool) -> bool:
    text = (content or "").strip()
    if not text or text.startswith("[Error]"):
        return False
    if is_sql:
        return True
    return bool(re.match(r"^\s*(SELECT|WITH)\b", text, re.IGNORECASE))


def build_thread_sql_export(thread: ThreadModel, schema_title: str | None = None) -> tuple[str, str]:
    """
    Build .sql file body and a safe download filename from thread messages.
    Returns (filename_without_ext, sql_body).
    """
    filename = _sanitize_filename(thread.title)
    exported_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = [
        f"-- Thread: {thread.title}",
        f"-- Exported: {exported_at}",
    ]
    if schema_title:
        lines.append(f"-- Schema: {schema_title}")
    if thread.sql_model:
        lines.append(f"-- Model: {thread.sql_model}")
    lines.append("")

    messages = sorted(thread.messages, key=lambda m: m.position)
    query_index = 0

    for i, msg in enumerate(messages):
        if msg.role != "assistant":
            continue
        if not _is_exportable_sql(msg.content, msg.is_sql):
            continue

        user_request = ""
        for j in range(i - 1, -1, -1):
            if messages[j].role == "user" and messages[j].content.strip():
                user_request = messages[j].content.strip()
                break

        query_index += 1
        lines.append(f"-- {'=' * 60}")
        lines.append(f"-- Query {query_index}")
        if user_request:
            for user_line in user_request.splitlines():
                lines.append(f"-- User: {user_line}")
        lines.append("")

        sql_body = msg.content.strip()
        if not sql_body.endswith(";"):
            sql_body += ";"
        lines.append(sql_body)
        lines.append("")

    if query_index == 0:
        lines.append("-- No generated SQL queries in this thread yet.")
        lines.append("")

    return filename, "\n".join(lines).rstrip() + "\n"
