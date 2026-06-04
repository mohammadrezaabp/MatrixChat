import os
from typing import Literal

AI_SERVICE_BASE_URL = os.getenv("AI_SERVICE_BASE_URL", "https://gpu1-llm.emofid.com/")
AI_SERVICE_API_KEY = os.getenv("AI_SERVICE_API_KEY", "")
AI_SERVICE_MODEL = os.getenv("AI_SERVICE_MODEL", "DeepSeek-V4-Pro")
AI_SERVICE_COMPLETIONS_PATH = os.getenv("AI_SERVICE_COMPLETIONS_PATH", "v1/chat/completions")
AI_SERVICE_MAX_RETRIES = int(os.getenv("AI_SERVICE_MAX_RETRIES", "3"))
AI_SERVICE_INITIAL_RETRY_DELAY_SECONDS = float(os.getenv("AI_SERVICE_INITIAL_RETRY_DELAY_SECONDS", "2"))
AI_SERVICE_TIMEOUT_SECONDS = float(os.getenv("AI_SERVICE_TIMEOUT_SECONDS", "120"))
RETRIABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}

CHAT_MODEL_NAME = os.getenv("CHAT_MODEL_NAME", AI_SERVICE_MODEL)
SQL_MODEL_NAME = os.getenv("SQL_MODEL_NAME", AI_SERVICE_MODEL)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
OLLAMA_SQL_MODEL = os.getenv("OLLAMA_SQL_MODEL", "qwen2.5-coder:7b-instruct-q4_K_M")
OLLAMA_SQL_NUM_CTX = int(os.getenv("OLLAMA_SQL_NUM_CTX", "1024"))
OLLAMA_SQL_NUM_PREDICT = int(os.getenv("OLLAMA_SQL_NUM_PREDICT", "256"))
OLLAMA_SQL_NUM_BATCH = int(os.getenv("OLLAMA_SQL_NUM_BATCH", "128"))
OLLAMA_KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "30m")
OLLAMA_MAX_RETRIES = int(os.getenv("OLLAMA_MAX_RETRIES", "1"))
OLLAMA_INITIAL_RETRY_DELAY_SECONDS = float(os.getenv("OLLAMA_INITIAL_RETRY_DELAY_SECONDS", "0.5"))
OLLAMA_TIMEOUT_SECONDS = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "120"))
OLLAMA_SCHEMA_SUMMARY_MAX_CHARS = int(os.getenv("OLLAMA_SCHEMA_SUMMARY_MAX_CHARS", "2200"))
OLLAMA_SCHEMA_FAQ_MAX_CHARS = int(os.getenv("OLLAMA_SCHEMA_FAQ_MAX_CHARS", "1200"))
SQL_PROVIDER_DEEPSEEK = "deepseek"
SQL_PROVIDER_OLLAMA = "ollama"

CHAT_NUM_CTX = int(os.getenv("CHAT_NUM_CTX", "2048"))
SQL_NUM_CTX = int(os.getenv("SQL_NUM_CTX", "4096"))
SQL_WARMUP_NUM_CTX = int(os.getenv("SQL_WARMUP_NUM_CTX", str(min(SQL_NUM_CTX, 2048))))
SCHEMA_WARMUP_LIMIT = int(os.getenv("SCHEMA_WARMUP_LIMIT", "6"))
SQL_TEMPERATURE = float(os.getenv("SQL_TEMPERATURE", "0.1"))

SQL_CACHE_ENABLED = os.getenv("SQL_CACHE_ENABLED", "true").lower() in ("1", "true", "yes")
SQL_CACHE_MAX_ENTRIES = int(os.getenv("SQL_CACHE_MAX_ENTRIES", "256"))
SQL_CACHE_TTL_SECONDS = int(os.getenv("SQL_CACHE_TTL_SECONDS", "3600"))
SQL_CACHE_FUZZY_THRESHOLD = float(os.getenv("SQL_CACHE_FUZZY_THRESHOLD", "0.92"))
SQL_FAQ_EXAMPLES_MAX_CHARS = int(os.getenv("SQL_FAQ_EXAMPLES_MAX_CHARS", "800"))

MAX_CHAT_HISTORY = int(os.getenv("MAX_CHAT_HISTORY", "8"))

SQL_INTENT_FRESH = "fresh"
SQL_INTENT_REFINE = "refine"
SQL_INTENT_ENHANCE = "enhance"
SqlIntent = Literal["fresh", "refine", "enhance"]

CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:3001").split(",")
    if origin.strip()
]

AUTH_SECRET = os.getenv("AUTH_SECRET", "matrixchat-dev-secret-change-me")
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", "604800"))
SESSION_COOKIE_NAME = "mc_session"

DATABASE_URL = os.getenv("DATABASE_URL", "")

CHAT_SYSTEM_PROMPT = (
    "You are a concise English assistant. Answer directly in 1-3 short paragraphs. "
    "Skip pleasantries and disclaimers unless asked."
)

SQL_SYSTEM_PROMPT = (
    "You are a senior database engineer. Convert the user request into ONE valid "
    "and efficient SQL read-only query for the given schema. "
    "STRICT SAFETY: Generate SELECT-only SQL. Never generate INSERT, UPDATE, DELETE, "
    "CREATE, DROP, TRUNCATE, ALTER, MERGE, REPLACE, GRANT, REVOKE, EXEC, or CALL. "
    "Output format must be exactly: "
    "line 1 comment starting with '-- Reason:' explaining why this query answers the request; "
    "then one SQL SELECT/ WITH...SELECT statement ending with a single semicolon. "
    "No markdown fences."
)

REFINE_KEYWORDS = {
    "also", "add", "include", "remove", "exclude", "change", "modify",
    "update", "additionally", "besides", "along with", "as well",
    "instead", "replace", "without", "and show", "and get", "and add",
    "now filter", "now only", "now sort", "now order", "now group",
    "but only", "but filter", "but add", "but also",
}

ENHANCEMENT_KEYWORDS = {
    "enhance", "enhancement", "improve", "improvement", "optimize", "optimization",
    "faster", "speed", "performance", "tune", "better",
}

SQL_RULES = (
    "Rules:\n"
    "1. Use ONLY tables and columns that exist in SCHEMA. Never invent names.\n"
    "2. Match the SQL dialect line and SCHEMA syntax; never mix dialects.\n"
    "3. Output must stay read-only: SELECT or WITH...SELECT only. Never write DML/DDL.\n"
    "4. Use explicit JOIN ... ON and qualify columns with table aliases in multi-table queries.\n"
    "5. Never use SELECT *. Return only needed columns.\n"
    "6. Start FROM the main fact table, JOIN dimension/lookup tables; avoid cartesian products.\n"
    "7. When using aggregates, include every non-aggregated selected column in GROUP BY.\n"
    "8. Push filters into WHERE early; use sargable date ranges (column >= start AND column < end).\n"
    "9. Use LIMIT/TOP only when the user asks for samples, top N, or recent rows.\n"
    "10. If SCHEMA FAQ defines aliases, business terms, or join paths, prefer those.\n"
    "11. For refinements, keep existing logic and change only what the new request asks.\n"
    "12. Return a '-- Reason:' comment line then one SQL statement ending with ';'.\n"
)

SQL_FEW_SHOT_EXAMPLES = (
    "### Examples\n"
    "REQUEST: list top 10 recent orders\n"
    "SQL:\n"
    "-- Reason: Returns the 10 most recent orders as requested.\n"
    "SELECT o.OrderID, o.OrderDate FROM Orders o ORDER BY o.OrderDate DESC LIMIT 10;\n\n"
    "REQUEST: customers who placed orders in 2024 with total over 1000\n"
    "SQL:\n"
    "-- Reason: Joins customers to orders, filters by year and minimum total.\n"
    "SELECT c.CustomerID, c.Name, SUM(o.Amount) AS TotalAmount\n"
    "FROM Customers c\n"
    "INNER JOIN Orders o ON o.CustomerID = c.CustomerID\n"
    "WHERE o.OrderDate >= '2024-01-01' AND o.OrderDate < '2025-01-01'\n"
    "GROUP BY c.CustomerID, c.Name\n"
    "HAVING SUM(o.Amount) > 1000;\n\n"
)

SQL_ENHANCEMENT_INSTRUCTIONS = (
    "### Performance optimization\n"
    "Preserve the same logical result (same filters, joins, and output columns unless the user asked to change them). "
    "Improve structure: use sargable predicates, avoid SELECT *, reduce redundant subqueries, "
    "prefer explicit JOINs over correlated subqueries when equivalent. "
    "Add LIMIT/TOP only if already present or explicitly requested. "
    "Do not remove columns or filters unless explicitly asked.\n"
)

FORBIDDEN_SQL_KEYWORDS = {
    "INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "TRUNCATE", "ALTER",
    "MERGE", "REPLACE", "GRANT", "REVOKE", "EXEC", "CALL",
}
