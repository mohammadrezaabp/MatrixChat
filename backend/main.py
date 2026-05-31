from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import asyncio
import httpx
import json
import os
from functools import lru_cache
from typing import Optional
import re

app = FastAPI()

# Enable CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://host.docker.internal:11434")

# Use small, fast models tuned for CPU / 8GB RAM laptops.
# Override via env if you want to try bigger ones.
CHAT_MODEL_NAME = os.getenv("CHAT_MODEL_NAME", os.getenv("MODEL_NAME", "llama3.2:1b"))
SQL_MODEL_NAME = os.getenv("SQL_MODEL_NAME", "qwen2.5-coder:1.5b")

# Keep models hot in RAM so the next request doesn't pay the cold-load tax.
KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "60m")

# Context windows: smaller = much faster prompt processing on CPU.
CHAT_NUM_CTX = int(os.getenv("CHAT_NUM_CTX", "2048"))
SQL_NUM_CTX = int(os.getenv("SQL_NUM_CTX", "2560"))

# Cap how many prior messages we forward (older turns rarely matter and slow CPU inference a lot).
MAX_CHAT_HISTORY = int(os.getenv("MAX_CHAT_HISTORY", "8"))

# Optional thread count override.
NUM_THREAD_ENV = os.getenv("OLLAMA_NUM_THREAD")
NUM_THREAD: Optional[int] = int(NUM_THREAD_ENV) if NUM_THREAD_ENV else None

SCHEMA_FILE = os.path.join(os.path.dirname(__file__), "MySqlSchema.sql")

CHAT_SYSTEM_PROMPT = (
    "You are a concise English assistant. Answer directly in 1-3 short paragraphs. "
    "Skip pleasantries and disclaimers unless asked."
)

SQL_SYSTEM_PROMPT = (
    "You are a senior database engineer. Convert the user request into ONE valid "
    "SQL SELECT/INSERT/UPDATE/DELETE statement that runs against the given schema. "
    "Output ONLY the SQL, terminated with a single semicolon. No prose, no markdown, "
    "no comments, no explanations, no code fences."
)

# Keywords that strongly signal the user wants to MODIFY the previous query.
_REFINE_KEYWORDS = {
    "also", "add", "include", "remove", "exclude", "change", "modify",
    "update", "additionally", "besides", "along with", "as well",
    "instead", "replace", "without", "and show", "and get", "and add",
    "now filter", "now only", "now sort", "now order", "now group",
    "but only", "but filter", "but add", "but also",
}

SQL_RULES = (
    "Rules:\n"
    "1. Use ONLY tables and columns that appear in the SCHEMA. Never invent names.\n"
    "2. Match the exact casing of table and column names from the SCHEMA.\n"
    "3. Prefer explicit JOIN ... ON syntax over comma joins. Qualify columns with table "
    "aliases when joining.\n"
    "4. Use clear short aliases (c for Customers, a for BankAccounts, s for Symbols, etc.).\n"
    "5. Add WHERE / GROUP BY / ORDER BY / LIMIT only when the request asks for them.\n"
    "6. Use the SQL dialect that matches the SCHEMA syntax. If the schema uses IDENTITY, "
    "GETDATE(), BIT, NVARCHAR (T-SQL / SQL Server) then use TOP N and DATEADD/GETDATE for dates. "
    "If the schema looks like MySQL then use LIMIT N and CURDATE() / INTERVAL.\n"
    "7. For aggregate questions use COUNT/SUM/AVG/MIN/MAX with GROUP BY as needed.\n"
    "8. Use single quotes for string and date literals. Dates as 'YYYY-MM-DD'.\n"
    "9. When refining a prior query, KEEP its existing SELECT columns, filters, joins, "
    "ordering and limits unless the new request explicitly changes them. Only add or "
    "adjust what was asked. To add a column from another table, ADD a JOIN and ADD the "
    "column to the SELECT list \u2014 do NOT replace the original query.\n"
    "10. Return exactly one statement ending with ';'. No trailing text."
)

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    model: Optional[str] = None
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = 0.9

class ChatResponse(BaseModel):
    response: str
    model: str

class TextToSqlMessage(BaseModel):
    role: str
    content: str
    isSql: Optional[bool] = False

class TextToSqlRequest(BaseModel):
    query: str
    model: Optional[str] = None
    messages: Optional[list[TextToSqlMessage]] = None

class TextToSqlResponse(BaseModel):
    sql: str
    query: str
    model: str

def read_schema() -> str:
    """Read the MySQL schema from file"""
    try:
        with open(SCHEMA_FILE, 'r') as f:
            return f.read()
    except FileNotFoundError:
        return "Schema file not found"


@lru_cache(maxsize=1)
def get_schema() -> str:
    return read_schema()


@lru_cache(maxsize=1)
def get_schema_summary() -> str:
    """Build a compact table/column summary for faster text-to-SQL prompts."""
    schema = get_schema()
    tables: list[str] = []

    table_blocks = re.findall(
        r"CREATE TABLE\s+([A-Za-z0-9_]+)\s*\((.*?)\);",
        schema,
        re.IGNORECASE | re.DOTALL,
    )

    for table_name, block in table_blocks:
        column_names: list[str] = []
        for raw_line in block.splitlines():
            line = raw_line.strip().rstrip(',')
            if not line:
                continue
            upper_line = line.upper()
            if upper_line.startswith(("PRIMARY KEY", "UNIQUE", "FOREIGN KEY", "CONSTRAINT", "INDEX")):
                continue
            column_match = re.match(r'([A-Za-z0-9_]+)\s+', line)
            if column_match:
                column_names.append(column_match.group(1))

        if column_names:
            tables.append(f"- {table_name}: {', '.join(column_names)}")

    if not tables:
        return schema

    return "\n".join(tables)

def extract_sql_from_response(response: str) -> str:
    """Extract SQL query from LLM response"""
    response = re.sub(r'```sql\n?', '', response)
    response = re.sub(r'```\n?', '', response)

    sql_pattern = r'(?:SELECT|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER)[^;]*;?'
    matches = re.findall(sql_pattern, response, re.IGNORECASE)

    if matches:
        sql = matches[0].strip()
        if not sql.endswith(';'):
            sql += ';'
        return sql

    lines = response.strip().split('\n')
    sql_lines = []
    for line in lines:
        line = line.strip()
        if line and not any(word in line.lower() for word in ['explanation', 'note:', 'answer:', 'here', 'this', 'the query']):
            sql_lines.append(line)

    result = ' '.join(sql_lines).strip()
    if not result.endswith(';'):
        result += ';'
    return result


def build_options(num_ctx: int, num_predict: Optional[int] = None,
                  temperature: float = 0.7, top_p: float = 0.9,
                  top_k: Optional[int] = None, repeat_penalty: Optional[float] = None,
                  stop: Optional[list[str]] = None) -> dict:
    opts: dict = {
        "temperature": temperature,
        "top_p": top_p,
        "num_ctx": num_ctx,
    }
    if num_predict is not None:
        opts["num_predict"] = num_predict
    if top_k is not None:
        opts["top_k"] = top_k
    if repeat_penalty is not None:
        opts["repeat_penalty"] = repeat_penalty
    if NUM_THREAD is not None:
        opts["num_thread"] = NUM_THREAD
    if stop:
        opts["stop"] = stop
    return opts


async def warm_model(model: str, num_ctx: int) -> None:
    """Send a tiny request so Ollama loads the model into memory."""
    try:
        async with httpx.AsyncClient(timeout=600) as client:
            await client.post(
                f"{OLLAMA_API_URL}/api/generate",
                json={
                    "model": model,
                    "prompt": "ok",
                    "stream": False,
                    "keep_alive": KEEP_ALIVE,
                    "options": {"num_predict": 1, "num_ctx": num_ctx},
                },
            )
        print(f"[warm] Model ready: {model}")
    except Exception as exc:
        print(f"[warm] Could not warm {model}: {exc}")


@app.on_event("startup")
async def startup_warmup() -> None:
    # Don't block startup — warm in the background.
    asyncio.create_task(warm_model(CHAT_MODEL_NAME, CHAT_NUM_CTX))
    asyncio.create_task(warm_model(SQL_MODEL_NAME, SQL_NUM_CTX))


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "ok",
        "chat_model": CHAT_MODEL_NAME,
        "sql_model": SQL_MODEL_NAME,
    }

def _keyword_intent(request: str) -> Optional[bool]:
    """Fast keyword pre-check. True=refine, False=fresh, None=ambiguous."""
    lower = request.lower()
    if any(kw in lower for kw in _REFINE_KEYWORDS):
        return True
    return None


async def classify_intent(client: httpx.AsyncClient, model: str,
                          last_sql: str, new_request: str) -> bool:
    """
    Ask the model whether new_request is a REFINEMENT of last_sql or a NEW query.
    Uses a tiny forced-choice prompt with num_predict=4 so it's very fast.
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
        resp = await client.post(
            f"{OLLAMA_API_URL}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "keep_alive": KEEP_ALIVE,
                "options": {
                    "num_predict": 4,
                    "temperature": 0.0,
                    "num_ctx": 512,
                },
            },
        )
        if resp.status_code == 200:
            answer = resp.json().get("response", "").strip().upper()
            print(f"[sql] intent classifier answer: {answer!r}")
            return "REFINE" in answer
    except Exception as exc:
        print(f"[sql] intent classifier failed: {exc}")
    # Default to fresh query on any error.
    return False


def extract_last_sql(messages: Optional[list[TextToSqlMessage]],
                     current_query: str) -> Optional[str]:
    """Return the most recent valid SQL from the conversation history, or None."""
    if not messages:
        return None

    cleaned: list[TextToSqlMessage] = []
    for m in messages:
        if not m.content or m.role not in ("user", "assistant"):
            continue
        cleaned.append(m)

    # Remove the trailing user message if it duplicates the current query.
    if cleaned and cleaned[-1].role == "user" and cleaned[-1].content.strip() == current_query.strip():
        cleaned = cleaned[:-1]

    # Walk backwards and find the last assistant turn that looks like SQL.
    for m in reversed(cleaned):
        if m.role != "assistant":
            continue
        text = m.content.strip()
        if not text or text == ";":
            continue
        if m.isSql or re.match(r"^\s*(SELECT|INSERT|UPDATE|DELETE|WITH)\b", text, re.IGNORECASE):
            return text if text.endswith(";") else text + ";"
    return None


@app.post("/text-to-sql")
async def text_to_sql(request: TextToSqlRequest) -> TextToSqlResponse:
    """Convert natural language query to SQL using the database schema"""
    try:
        schema_summary = get_schema_summary()
        model = request.model or SQL_MODEL_NAME
        last_sql = extract_last_sql(request.messages, request.query)

        # Determine intent: refine the last SQL or generate a fresh one.
        is_refinement = False
        if last_sql:
            kw = _keyword_intent(request.query)
            if kw is True:
                is_refinement = True
                print(f"[sql] intent=REFINE (keyword match)")
            elif kw is False:
                is_refinement = False
                print(f"[sql] intent=NEW (keyword match)")
            else:
                # Ambiguous — ask the model.
                async with httpx.AsyncClient(timeout=60) as clf_client:
                    is_refinement = await classify_intent(clf_client, model, last_sql, request.query)

        if is_refinement and last_sql:
            print(f"[sql] refining prior SQL: {last_sql!r}")
            task_block = (
                f"### Current query\n{last_sql}\n\n"
                f"### Modification request\n"
                f"{request.query}\n\n"
                "### Instructions\n"
                "Take the Current query above as the base. Apply ONLY the modification "
                "described. Keep every existing SELECT column, JOIN, WHERE condition, "
                "ORDER BY and LIMIT from the base query. Only add or change what the "
                "modification asks for. Output the full updated SQL ending with ';':\n"
                "SQL:"
            )
        else:
            print(f"[sql] fresh query: {request.query!r}")
            task_block = f"### Task\nREQUEST: {request.query}\nSQL:"

        prompt = (
            f"{SQL_SYSTEM_PROMPT}\n\n"
            f"SCHEMA (table: columns):\n{schema_summary}\n\n"
            f"{SQL_RULES}\n\n"
            "### Example (fresh query)\n"
            "REQUEST: list all trades from the past week\n"
            "SQL: SELECT t.* FROM Trades t WHERE t.TradeDate >= DATEADD(day, -7, CAST(GETDATE() AS DATE));\n\n"
            "### Example (refinement)\n"
            "Current query: SELECT t.* FROM Trades t WHERE t.TradeDate >= DATEADD(day, -7, CAST(GETDATE() AS DATE));\n"
            "Modification request: also include the customer name\n"
            "SQL: SELECT t.*, c.FullName FROM Trades t "
            "JOIN TradingCodes tc ON tc.TradingCodeID = t.TradingCodeID "
            "JOIN Customers c ON c.CustomerID = tc.CustomerID "
            "WHERE t.TradeDate >= DATEADD(day, -7, CAST(GETDATE() AS DATE));\n\n"
            f"{task_block}"
        )

        async def call_ollama(use_model: str):
            return await client.post(
                f"{OLLAMA_API_URL}/api/generate",
                json={
                    "model": use_model,
                    "prompt": prompt,
                    "stream": False,
                    "keep_alive": KEEP_ALIVE,
                    "options": build_options(
                        num_ctx=SQL_NUM_CTX,
                        num_predict=256,
                        temperature=0.0,
                        top_p=0.5,
                        top_k=20,
                        repeat_penalty=1.05,
                        stop=["###", "REQUEST:", "Explanation:", "Note:", "```"],
                        # No ';' stop — let model output the full statement;
                        # extract_sql_from_response handles trimming.
                        # No '\n\n' stop — code models often prefix with a blank line.
                    ),
                },
            )

        async with httpx.AsyncClient(timeout=300) as client:
            response = await call_ollama(model)

            # Fallback: if the SQL model isn't installed, retry with the chat model.
            if (
                response.status_code == 404
                and model != CHAT_MODEL_NAME
                and "not found" in response.text.lower()
            ):
                print(f"[sql] Model '{model}' missing, falling back to '{CHAT_MODEL_NAME}'")
                model = CHAT_MODEL_NAME
                response = await call_ollama(model)

        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Ollama error: {response.text}"
            )

        result = response.json()
        raw_response = result.get("response", "").strip()
        print(f"[sql] raw model response: {raw_response!r}")
        sql_query = extract_sql_from_response(raw_response)

        return TextToSqlResponse(
            sql=sql_query,
            query=request.query,
            model=model,
        )

    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail=f"Cannot connect to Ollama at {OLLAMA_API_URL}. Make sure it's running."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat")
async def chat(request: ChatRequest) -> ChatResponse:
    """Chat endpoint that connects to Ollama"""
    try:
        model = request.model or CHAT_MODEL_NAME

        # Trim history to last N turns to keep prompts short on CPU.
        history = [
            {"role": msg.role, "content": msg.content}
            for msg in request.messages
            if msg.role in ("user", "assistant") and msg.content
        ]
        if len(history) > MAX_CHAT_HISTORY:
            history = history[-MAX_CHAT_HISTORY:]

        messages = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}] + history

        async with httpx.AsyncClient(timeout=300) as client:
            response = await client.post(
                f"{OLLAMA_API_URL}/api/chat",
                json={
                    "model": model,
                    "messages": messages,
                    "stream": False,
                    "keep_alive": KEEP_ALIVE,
                    "options": build_options(
                        num_ctx=CHAT_NUM_CTX,
                        num_predict=512,
                        temperature=request.temperature or 0.7,
                        top_p=request.top_p or 0.9,
                    ),
                },
            )

        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Ollama error: {response.text}"
            )

        result = response.json()
        return ChatResponse(
            response=result.get("message", {}).get("content", ""),
            model=model,
        )

    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail=f"Cannot connect to Ollama at {OLLAMA_API_URL}. Make sure it's running."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat-stream")
async def chat_stream(request: ChatRequest):
    """Streaming chat endpoint. Emits NDJSON lines: {"delta": "..."} ... {"done": true}."""
    model = request.model or CHAT_MODEL_NAME

    history = [
        {"role": msg.role, "content": msg.content}
        for msg in request.messages
        if msg.role in ("user", "assistant") and msg.content
    ]
    if len(history) > MAX_CHAT_HISTORY:
        history = history[-MAX_CHAT_HISTORY:]

    messages = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}] + history

    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "keep_alive": KEEP_ALIVE,
        "options": build_options(
            num_ctx=CHAT_NUM_CTX,
            num_predict=512,
            temperature=request.temperature or 0.7,
            top_p=request.top_p or 0.9,
        ),
    }

    async def event_iter():
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream(
                    "POST", f"{OLLAMA_API_URL}/api/chat", json=payload
                ) as response:
                    if response.status_code != 200:
                        body = await response.aread()
                        yield json.dumps({"error": body.decode("utf-8", "ignore")}) + "\n"
                        return
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        try:
                            obj = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        delta = obj.get("message", {}).get("content", "")
                        if delta:
                            yield json.dumps({"delta": delta}) + "\n"
                        if obj.get("done"):
                            yield json.dumps({"done": True}) + "\n"
                            return
        except httpx.ConnectError:
            yield json.dumps({"error": f"Cannot connect to Ollama at {OLLAMA_API_URL}."}) + "\n"
        except Exception as exc:
            yield json.dumps({"error": str(exc)}) + "\n"

    return StreamingResponse(event_iter(), media_type="application/x-ndjson")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
