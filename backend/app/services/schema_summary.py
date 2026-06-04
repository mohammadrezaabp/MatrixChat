import re

SCHEMA_SUMMARY_CACHE: dict[str, str] = {}
WARMED_SCHEMA_IDS: set[str] = set()


def get_schema_summary(schema: str) -> str:
    """Build a compact table/column summary for faster text-to-SQL prompts."""
    tables: list[str] = []

    table_blocks = re.findall(
        r"CREATE TABLE\s+([A-Za-z0-9_]+)\s*\((.*?)\);",
        schema,
        re.IGNORECASE | re.DOTALL,
    )

    for table_name, block in table_blocks:
        column_names: list[str] = []
        for raw_line in block.splitlines():
            line = raw_line.strip().rstrip(",")
            if not line:
                continue
            upper_line = line.upper()
            if upper_line.startswith(("PRIMARY KEY", "UNIQUE", "FOREIGN KEY", "CONSTRAINT", "INDEX")):
                continue
            column_match = re.match(r"([A-Za-z0-9_]+)\s+", line)
            if column_match:
                column_names.append(column_match.group(1))

        if column_names:
            tables.append(f"- {table_name}: {', '.join(column_names)}")

    if not tables:
        return schema

    return "\n".join(tables)


def get_schema_summary_cached(schema_id: str, schema_text: str) -> str:
    cached = SCHEMA_SUMMARY_CACHE.get(schema_id)
    if cached is not None:
        return cached
    summary = get_schema_summary(schema_text)
    SCHEMA_SUMMARY_CACHE[schema_id] = summary
    return summary


def remove_schema_cache(schema_id: str) -> None:
    SCHEMA_SUMMARY_CACHE.pop(schema_id, None)
    WARMED_SCHEMA_IDS.discard(schema_id)
