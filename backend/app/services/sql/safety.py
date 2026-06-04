import re

from app.config import FORBIDDEN_SQL_KEYWORDS


def extract_sql_from_response(response: str) -> str:
    """Extract SQL (including leading -- comments) from LLM response."""
    response = re.sub(r"```sql\n?", "", response, flags=re.IGNORECASE)
    response = re.sub(r"```\n?", "", response)
    response = response.strip()

    pattern = re.compile(r"(?is)((?:\s*(?:--[^\n]*\n|/\*.*?\*/\s*))*\s*(?:WITH|SELECT)\b.*)")
    match = pattern.search(response)
    candidate = match.group(1).strip() if match else response

    semicolon_pos = candidate.find(";")
    if semicolon_pos >= 0:
        candidate = candidate[:semicolon_pos + 1]
    elif candidate:
        candidate = candidate + ";"

    return candidate.strip()


def is_select_only_sql(sql: str) -> tuple[bool, str]:
    """Validate that SQL is a single read-only SELECT statement."""
    if not sql or not sql.strip():
        return False, "Empty SQL response"

    without_block_comments = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    without_comments = re.sub(r"--.*?$", " ", without_block_comments, flags=re.MULTILINE).strip()

    if not re.match(r"^(WITH|SELECT)\b", without_comments, re.IGNORECASE):
        return False, "Query must begin with SELECT or WITH"

    sql_no_trailing = without_comments[:-1] if without_comments.endswith(";") else without_comments
    if ";" in sql_no_trailing:
        return False, "Only one SQL statement is allowed"

    for keyword in FORBIDDEN_SQL_KEYWORDS:
        if re.search(rf"\b{keyword}\b", without_comments, re.IGNORECASE):
            return False, f"Forbidden keyword detected: {keyword}"

    return True, ""


def ensure_sql_comments(sql: str, user_query: str) -> str:
    """Ensure output starts with reason SQL comments as required by UI."""
    body = (sql or "").strip()
    lines = body.splitlines()
    has_reason = any(line.strip().lower().startswith("-- reason:") for line in lines[:3])
    if has_reason:
        return body

    compact_query = re.sub(r"\s+", " ", user_query).strip()
    if len(compact_query) > 140:
        compact_query = compact_query[:137] + "..."

    comment_prefix = (
        f"-- Reason: This SELECT query is generated to answer: {compact_query}\n"
    )
    return f"{comment_prefix}\n{body}"
