from fastapi import FastAPI, HTTPException, Depends, Request, Response, status, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import asyncio
import httpx
import json
import os
from typing import Optional
import re
from datetime import datetime, timezone
import base64
import hashlib
import hmac
import secrets

from sqlalchemy import (
    create_engine, Column, String, Boolean, Integer, Text, BigInteger,
    ForeignKey, text, inspect
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Session, relationship, sessionmaker

# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL", "")

engine = None
SessionLocal = None

if DATABASE_URL:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


class UserModel(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True)
    username = Column(String, nullable=False, unique=True, index=True)
    password_hash = Column(String, nullable=False)
    created_at = Column(BigInteger, nullable=False)
    threads = relationship("ThreadModel", back_populates="user", cascade="all, delete-orphan")
    schemas = relationship("SqlSchemaModel", back_populates="user", cascade="all, delete-orphan")


class SqlSchemaModel(Base):
    __tablename__ = "sql_schemas"
    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String, nullable=False)
    schema_text = Column(Text, nullable=False)
    updated_at = Column(BigInteger, nullable=False)
    user = relationship("UserModel", back_populates="schemas")
    threads = relationship("ThreadModel", back_populates="schema")


class ThreadModel(Base):
    __tablename__ = "threads"
    id        = Column(String, primary_key=True)
    user_id   = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    schema_id = Column(String, ForeignKey("sql_schemas.id", ondelete="SET NULL"), nullable=True, index=True)
    title     = Column(String, nullable=False)
    mode      = Column(String, nullable=False)          # 'chat' | 'sql'
    updated_at = Column(BigInteger, nullable=False)     # epoch ms
    user      = relationship("UserModel", back_populates="threads")
    schema    = relationship("SqlSchemaModel", back_populates="threads")
    messages  = relationship("MessageModel", back_populates="thread",
                             cascade="all, delete-orphan",
                             order_by="MessageModel.position")


class MessageModel(Base):
    __tablename__ = "messages"
    id         = Column(String, primary_key=True)
    thread_id  = Column(String, ForeignKey("threads.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    role       = Column(String, nullable=False)          # 'user' | 'assistant'
    content    = Column(Text, nullable=False, default="")
    is_sql     = Column(Boolean, nullable=False, default=False)
    position   = Column(Integer, nullable=False, default=0)  # ordering within thread
    thread     = relationship("ThreadModel", back_populates="messages")


def get_db():
    if SessionLocal is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    if engine is not None:
        Base.metadata.create_all(bind=engine)
        ensure_auth_schema()
        ensure_thread_schema_column()
        print("[db] tables ready")
    else:
        print("[db] DATABASE_URL not set, skipping DB init")

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
SQL_MODEL_NAME = os.getenv("SQL_MODEL_NAME", "qwen2.5-coder:7b-instruct-q4_K_M")

# Keep models hot in RAM so the next request doesn't pay the cold-load tax.
KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "60m")

# Context windows: smaller = much faster prompt processing on CPU.
CHAT_NUM_CTX = int(os.getenv("CHAT_NUM_CTX", "2048"))
SQL_NUM_CTX = int(os.getenv("SQL_NUM_CTX", "4096"))
SQL_WARMUP_NUM_CTX = int(os.getenv("SQL_WARMUP_NUM_CTX", str(min(SQL_NUM_CTX, 2048))))
SCHEMA_WARMUP_LIMIT = int(os.getenv("SCHEMA_WARMUP_LIMIT", "6"))
SQL_TEMPERATURE = float(os.getenv("SQL_TEMPERATURE", "0.1"))

# Cap how many prior messages we forward (older turns rarely matter and slow CPU inference a lot).
MAX_CHAT_HISTORY = int(os.getenv("MAX_CHAT_HISTORY", "8"))

# Optional thread count override.
NUM_THREAD_ENV = os.getenv("OLLAMA_NUM_THREAD")
NUM_THREAD: Optional[int] = int(NUM_THREAD_ENV) if NUM_THREAD_ENV else None

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

# Keywords that strongly signal the user wants to MODIFY the previous query.
_REFINE_KEYWORDS = {
    "also", "add", "include", "remove", "exclude", "change", "modify",
    "update", "additionally", "besides", "along with", "as well",
    "instead", "replace", "without", "and show", "and get", "and add",
    "now filter", "now only", "now sort", "now order", "now group",
    "but only", "but filter", "but add", "but also",
}

_ENHANCEMENT_KEYWORDS = {
    "enhance", "enhancement", "improve", "improvement", "optimize", "optimization",
    "faster", "speed", "performance", "tune", "better",
}

SQL_RULES = (
    "Rules:\n"
    "1. Use ONLY tables and columns that exist in SCHEMA. Never invent names.\n"
    "2. Match the SQL dialect shown by SCHEMA and never mix dialect syntax.\n"
    "3. Output must stay read-only: SELECT or WITH...SELECT only. Never write DML/DDL.\n"
    "4. Use explicit JOIN ... ON and qualify columns with aliases in multi-table queries.\n"
    "5. Never use SELECT *. Return only needed columns.\n"
    "6. Push filters into WHERE early, avoid unnecessary subqueries, and use LIMIT/TOP when user asks for samples or top N.\n"
    "7. Avoid functions on indexed filter columns; prefer sargable ranges.\n"
    "8. Use IS NULL / IS NOT NULL for null checks and single quotes for literals.\n"
    "9. For refinements, keep existing logic and change only what the new request asks.\n"
    "10. Return exactly two leading comments (-- Reason) then one SQL statement ending with ';'.\n"
)

FORBIDDEN_SQL_KEYWORDS = {
    "INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "TRUNCATE", "ALTER",
    "MERGE", "REPLACE", "GRANT", "REVOKE", "EXEC", "CALL",
}

# In-memory schema summary cache to avoid repeated parsing and support schema warmups.
SCHEMA_SUMMARY_CACHE: dict[str, str] = {}
WARMED_SCHEMA_IDS: set[str] = set()

AUTH_SECRET = os.getenv("AUTH_SECRET", "matrixchat-dev-secret-change-me")
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", "604800"))
SESSION_COOKIE_NAME = "mc_session"


class AuthUserSchema(BaseModel):
    id: str
    username: str


class RegisterRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class UpdateProfileRequest(BaseModel):
    currentPassword: str
    username: Optional[str] = None
    newPassword: Optional[str] = None

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
    schemaId: Optional[str] = None
    model: Optional[str] = None
    messages: Optional[list[TextToSqlMessage]] = None

class TextToSqlResponse(BaseModel):
    sql: str
    query: str
    model: str

# ---------------------------------------------------------------------------
# Thread / Message API Pydantic schemas
# ---------------------------------------------------------------------------
class MessageSchema(BaseModel):
    id: str
    role: str
    content: str
    isSql: bool = False

class ThreadSchema(BaseModel):
    id: str
    title: str
    mode: str
    schemaId: Optional[str] = None
    updatedAt: int
    messages: list[MessageSchema] = []

class UpsertThreadRequest(BaseModel):
    thread: ThreadSchema


class UserSchemaRequest(BaseModel):
    title: str
    schema: str


class UserSchemaResponse(BaseModel):
    id: str
    title: str
    schema: str
    updatedAt: int


def now_epoch() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * ((4 - len(data) % 4) % 4)
    return base64.urlsafe_b64decode(data + padding)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    rounds = 200_000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds)
    return f"pbkdf2_sha256${rounds}${_b64url_encode(salt)}${_b64url_encode(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, rounds_str, salt_b64, digest_b64 = stored.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        rounds = int(rounds_str)
        salt = _b64url_decode(salt_b64)
        expected = _b64url_decode(digest_b64)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds)
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def create_session_token(user_id: str) -> str:
    exp = now_epoch() + SESSION_TTL_SECONDS
    payload = f"{user_id}:{exp}".encode("utf-8")
    signature = hmac.new(AUTH_SECRET.encode("utf-8"), payload, hashlib.sha256).digest()
    return f"{_b64url_encode(payload)}.{_b64url_encode(signature)}"


def parse_session_token(token: str) -> Optional[str]:
    try:
        payload_b64, sig_b64 = token.split(".", 1)
        payload = _b64url_decode(payload_b64)
        expected_sig = hmac.new(AUTH_SECRET.encode("utf-8"), payload, hashlib.sha256).digest()
        provided_sig = _b64url_decode(sig_b64)
        if not hmac.compare_digest(provided_sig, expected_sig):
            return None
        raw = payload.decode("utf-8")
        user_id, exp_str = raw.rsplit(":", 1)
        if now_epoch() > int(exp_str):
            return None
        return user_id
    except Exception:
        return None


def set_session_cookie(response: Response, user_id: str) -> None:
    token = create_session_token(user_id)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")


def ensure_auth_schema() -> None:
    if engine is None:
        return
    insp = inspect(engine)
    if not insp.has_table("threads"):
        return
    thread_columns = {col["name"] for col in insp.get_columns("threads")}
    if "user_id" in thread_columns:
        return

    # Backfill legacy rows under a system user before enforcing ownership.
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO users (id, username, password_hash, created_at)
                VALUES (:id, :username, :password_hash, :created_at)
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {
                "id": "legacy",
                "username": "legacy",
                "password_hash": hash_password("legacy-migration-account"),
                "created_at": int(datetime.now(timezone.utc).timestamp() * 1000),
            },
        )
        conn.execute(text("ALTER TABLE threads ADD COLUMN user_id VARCHAR NOT NULL DEFAULT 'legacy'"))
        conn.execute(
            text(
                "ALTER TABLE threads ADD CONSTRAINT fk_threads_user_id "
                "FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE"
            )
        )


def ensure_thread_schema_column() -> None:
    if engine is None:
        return
    insp = inspect(engine)
    if not insp.has_table("threads"):
        return
    thread_columns = {col["name"] for col in insp.get_columns("threads")}
    if "schema_id" in thread_columns:
        return
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE threads ADD COLUMN schema_id VARCHAR NULL"))


def get_current_user(request: Request, db: Session = Depends(get_db)) -> UserModel:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    user_id = parse_session_token(token)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")
    user = db.get(UserModel, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")
    return user


@app.post("/auth/register", response_model=AuthUserSchema, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, response: Response, db: Session = Depends(get_db)):
    username = body.username.strip().lower()
    if len(username) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters")
    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    existing = db.query(UserModel).filter(UserModel.username == username).first()
    if existing:
        raise HTTPException(status_code=409, detail="Username already exists")

    user = UserModel(
        id=secrets.token_urlsafe(18),
        username=username,
        password_hash=hash_password(body.password),
        created_at=int(datetime.now(timezone.utc).timestamp() * 1000),
    )
    db.add(user)
    db.commit()
    set_session_cookie(response, user.id)
    return AuthUserSchema(id=user.id, username=user.username)


@app.post("/auth/login", response_model=AuthUserSchema)
def login(body: LoginRequest, response: Response, db: Session = Depends(get_db)):
    username = body.username.strip().lower()
    user = db.query(UserModel).filter(UserModel.username == username).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    set_session_cookie(response, user.id)
    return AuthUserSchema(id=user.id, username=user.username)


@app.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response):
    clear_session_cookie(response)


@app.get("/auth/me", response_model=AuthUserSchema)
def me(current_user: UserModel = Depends(get_current_user)):
    return AuthUserSchema(id=current_user.id, username=current_user.username)


@app.put("/auth/profile", response_model=AuthUserSchema)
def update_profile(
    body: UpdateProfileRequest,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    if not verify_password(body.currentPassword, current_user.password_hash):
        raise HTTPException(status_code=401, detail="Current password is incorrect")

    next_username = body.username.strip().lower() if body.username is not None else current_user.username
    next_password = body.newPassword if body.newPassword is not None else None

    wants_username_change = next_username != current_user.username
    wants_password_change = bool(next_password)
    if not wants_username_change and not wants_password_change:
        raise HTTPException(status_code=400, detail="No profile changes were provided")

    if wants_username_change:
        if len(next_username) < 3:
            raise HTTPException(status_code=400, detail="Username must be at least 3 characters")
        existing = db.query(UserModel).filter(UserModel.username == next_username).first()
        if existing and existing.id != current_user.id:
            raise HTTPException(status_code=409, detail="Username already exists")
        current_user.username = next_username

    if wants_password_change:
        if len(next_password) < 6:
            raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
        current_user.password_hash = hash_password(next_password)

    db.commit()
    db.refresh(current_user)
    return AuthUserSchema(id=current_user.id, username=current_user.username)


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


def build_schema_warmup_prompt(schema_summary: str) -> str:
    return (
        f"{SQL_SYSTEM_PROMPT}\n\n"
        f"SCHEMA (table: columns):\n{schema_summary}\n\n"
        f"{SQL_RULES}\n\n"
        "Warmup task: acknowledge schema context with one token."
    )


async def warm_sql_schema_context(schema_id: str, schema_summary: str) -> None:
    """Warm SQL model using schema context so first real query responds faster."""
    if not schema_summary.strip():
        return
    try:
        prompt = build_schema_warmup_prompt(schema_summary)
        async with httpx.AsyncClient(timeout=300) as client:
            await client.post(
                f"{OLLAMA_API_URL}/api/generate",
                json={
                    "model": SQL_MODEL_NAME,
                    "prompt": prompt,
                    "stream": False,
                    "keep_alive": KEEP_ALIVE,
                    "options": build_options(
                        num_ctx=SQL_WARMUP_NUM_CTX,
                        num_predict=1,
                        temperature=0.0,
                    ),
                },
            )
        WARMED_SCHEMA_IDS.add(schema_id)
        print(f"[warm] SQL schema context ready: {schema_id}")
    except Exception as exc:
        print(f"[warm] Could not warm schema context {schema_id}: {exc}")


async def warm_recent_schema_contexts() -> None:
    if SessionLocal is None:
        return
    db = SessionLocal()
    try:
        recent_schemas = (
            db.query(SqlSchemaModel)
            .order_by(SqlSchemaModel.updated_at.desc())
            .limit(max(SCHEMA_WARMUP_LIMIT, 0))
            .all()
        )
        for item in recent_schemas:
            summary = get_schema_summary_cached(item.id, item.schema_text)
            await warm_sql_schema_context(item.id, summary)
    except Exception as exc:
        print(f"[warm] Could not preload schema contexts: {exc}")
    finally:
        db.close()


def _schema_to_response(item: SqlSchemaModel) -> UserSchemaResponse:
    return UserSchemaResponse(
        id=item.id,
        title=item.title,
        schema=item.schema_text,
        updatedAt=item.updated_at,
    )


@app.get("/schemas", response_model=list[UserSchemaResponse])
def list_user_schemas(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    items = (
        db.query(SqlSchemaModel)
        .filter(SqlSchemaModel.user_id == current_user.id)
        .order_by(SqlSchemaModel.updated_at.desc())
        .all()
    )
    return [_schema_to_response(item) for item in items]


@app.post("/schemas", response_model=UserSchemaResponse, status_code=status.HTTP_201_CREATED)
def create_user_schema(
    body: UserSchemaRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    title = body.title.strip()
    cleaned = body.schema.strip()
    if len(title) < 2:
        raise HTTPException(status_code=400, detail="Title is too short")
    if len(cleaned) < 20:
        raise HTTPException(status_code=400, detail="Schema is too short")

    item = SqlSchemaModel(
        id=secrets.token_urlsafe(12),
        user_id=current_user.id,
        title=title,
        schema_text=cleaned,
        updated_at=int(datetime.now(timezone.utc).timestamp() * 1000),
    )
    db.add(item)
    db.commit()
    summary = get_schema_summary_cached(item.id, item.schema_text)
    background_tasks.add_task(warm_sql_schema_context, item.id, summary)
    return _schema_to_response(item)


@app.put("/schemas/{schema_id}", response_model=UserSchemaResponse)
def update_user_schema(
    schema_id: str,
    body: UserSchemaRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    item = (
        db.query(SqlSchemaModel)
        .filter(SqlSchemaModel.id == schema_id, SqlSchemaModel.user_id == current_user.id)
        .first()
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Schema not found")

    title = body.title.strip()
    cleaned = body.schema.strip()
    if len(title) < 2:
        raise HTTPException(status_code=400, detail="Title is too short")
    if len(cleaned) < 20:
        raise HTTPException(status_code=400, detail="Schema is too short")

    item.title = title
    item.schema_text = cleaned
    item.updated_at = int(datetime.now(timezone.utc).timestamp() * 1000)
    db.commit()
    remove_schema_cache(item.id)
    summary = get_schema_summary_cached(item.id, item.schema_text)
    background_tasks.add_task(warm_sql_schema_context, item.id, summary)
    return _schema_to_response(item)


@app.delete("/schemas/{schema_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user_schema(
    schema_id: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    item = (
        db.query(SqlSchemaModel)
        .filter(SqlSchemaModel.id == schema_id, SqlSchemaModel.user_id == current_user.id)
        .first()
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Schema not found")
    db.query(ThreadModel).filter(ThreadModel.schema_id == schema_id).update({"schema_id": None})
    db.delete(item)
    db.commit()
    remove_schema_cache(schema_id)

def extract_sql_from_response(response: str) -> str:
    """Extract SQL (including leading -- comments) from LLM response."""
    response = re.sub(r"```sql\n?", "", response, flags=re.IGNORECASE)
    response = re.sub(r"```\n?", "", response)
    response = response.strip()

    # Keep optional leading SQL comments and capture the first SELECT/WITH statement.
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


def build_options(num_ctx: int, num_predict: Optional[int] = None,
                  temperature: float = 0.7, top_p: float = 0.9,
                  top_k: Optional[int] = None, repeat_penalty: Optional[float] = None,
                  stop: Optional[list[str]] = None) -> dict:
    opts: dict = {
        "temperature": temperature,
        "top_p": top_p,
        "num_ctx": num_ctx,
        "use_mmap": True,  # Add this
        "num_gpu": 0,      # Explicitly CPU-only
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
    init_db()
    # Minimal warmup - just load model weights, don't fill context
    asyncio.create_task(warm_model(CHAT_MODEL_NAME, 256))  # Minimal context
    asyncio.create_task(warm_model(SQL_MODEL_NAME, 256))
    # Schema warmups can wait a few seconds
    asyncio.create_task(delayed_schema_warmup())

async def delayed_schema_warmup():
    await asyncio.sleep(5)  # Let model loading finish first
    await warm_recent_schema_contexts()


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "ok",
        "chat_model": CHAT_MODEL_NAME,
        "sql_model": SQL_MODEL_NAME,
    }

# ---------------------------------------------------------------------------
# Thread CRUD endpoints
# ---------------------------------------------------------------------------

def _thread_to_schema(t: ThreadModel) -> ThreadSchema:
    return ThreadSchema(
        id=t.id,
        title=t.title,
        mode=t.mode,
        schemaId=t.schema_id,
        updatedAt=t.updated_at,
        messages=[
            MessageSchema(id=m.id, role=m.role, content=m.content, isSql=m.is_sql)
            for m in t.messages
        ],
    )


@app.get("/threads", response_model=list[ThreadSchema])
def list_threads(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    threads = (
        db.query(ThreadModel)
        .filter(ThreadModel.user_id == current_user.id)
        .order_by(ThreadModel.updated_at.desc())
        .all()
    )
    return [_thread_to_schema(t) for t in threads]


@app.get("/threads/{thread_id}", response_model=ThreadSchema)
def get_thread(
    thread_id: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    t = (
        db.query(ThreadModel)
        .filter(ThreadModel.id == thread_id, ThreadModel.user_id == current_user.id)
        .first()
    )
    if not t:
        raise HTTPException(status_code=404, detail="Thread not found")
    return _thread_to_schema(t)


@app.put("/threads/{thread_id}", response_model=ThreadSchema)
def upsert_thread(thread_id: str, body: UpsertThreadRequest,
                  db: Session = Depends(get_db),
                  current_user: UserModel = Depends(get_current_user)):
    t = (
        db.query(ThreadModel)
        .filter(ThreadModel.id == thread_id, ThreadModel.user_id == current_user.id)
        .first()
    )
    data = body.thread
    if thread_id != data.id:
        raise HTTPException(status_code=400, detail="Thread id mismatch")

    schema_id = data.schemaId if data.mode == "sql" else None
    if schema_id is not None:
        schema_exists = (
            db.query(SqlSchemaModel)
            .filter(SqlSchemaModel.id == schema_id, SqlSchemaModel.user_id == current_user.id)
            .first()
        )
        if schema_exists is None:
            raise HTTPException(status_code=400, detail="Invalid schema id")

    def apply_messages() -> None:
        for pos, msg in enumerate(data.messages):
            db.add(MessageModel(
                id=msg.id,
                thread_id=data.id,
                role=msg.role,
                content=msg.content,
                is_sql=msg.isSql,
                position=pos,
            ))

    if t is None:
        existing_other = db.query(ThreadModel).filter(ThreadModel.id == thread_id).first()
        if existing_other is not None:
            raise HTTPException(status_code=404, detail="Thread not found")
        t = ThreadModel(id=data.id, user_id=current_user.id, schema_id=schema_id,
                        title=data.title, mode=data.mode,
                        updated_at=data.updatedAt)
        db.add(t)
        apply_messages()
        try:
            db.commit()
        except IntegrityError:
            # Concurrent upserts can race on insert for the same thread id.
            db.rollback()
            t = (
                db.query(ThreadModel)
                .filter(ThreadModel.id == thread_id, ThreadModel.user_id == current_user.id)
                .first()
            )
            if t is None:
                raise HTTPException(status_code=409, detail="Thread id already exists")
            t.title = data.title
            t.mode = data.mode
            t.schema_id = schema_id
            t.updated_at = data.updatedAt
            db.query(MessageModel).filter(MessageModel.thread_id == thread_id).delete()
            apply_messages()
            db.commit()
    else:
        t.title = data.title
        t.mode = data.mode
        t.schema_id = schema_id
        t.updated_at = data.updatedAt
        # Delete existing messages; we replace them wholesale.
        db.query(MessageModel).filter(MessageModel.thread_id == thread_id).delete()
        apply_messages()
        db.commit()

    db.refresh(t)
    return _thread_to_schema(t)


@app.delete("/threads/{thread_id}", status_code=204)
def delete_thread(
    thread_id: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    t = (
        db.query(ThreadModel)
        .filter(ThreadModel.id == thread_id, ThreadModel.user_id == current_user.id)
        .first()
    )
    if not t:
        raise HTTPException(status_code=404, detail="Thread not found")
    db.delete(t)
    db.commit()

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


def _is_enhancement_request(query: str) -> bool:
    lower = query.lower()
    return any(keyword in lower for keyword in _ENHANCEMENT_KEYWORDS)


@app.post("/text-to-sql")
async def text_to_sql(
    request: TextToSqlRequest,
    _current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TextToSqlResponse:
    """Convert natural language query to SQL using the database schema"""
    try:
        if not request.schemaId:
            raise HTTPException(status_code=400, detail="Schema is required")

        user_schema = (
            db.query(SqlSchemaModel)
            .filter(
                SqlSchemaModel.id == request.schemaId,
                SqlSchemaModel.user_id == _current_user.id,
            )
            .first()
        )
        if user_schema is None:
            raise HTTPException(status_code=400, detail="Schema not found")

        schema_summary = get_schema_summary_cached(user_schema.id, user_schema.schema_text)
        model = request.model or SQL_MODEL_NAME
        last_sql = extract_last_sql(request.messages, request.query)
        is_enhancement = _is_enhancement_request(request.query)

        if user_schema.id not in WARMED_SCHEMA_IDS:
            asyncio.create_task(warm_sql_schema_context(user_schema.id, schema_summary))

        # Determine intent: refine the last SQL or generate a fresh one.
        is_refinement = False
        if last_sql:
            # Fast path: avoid extra model classification call for lower latency.
            kw = _keyword_intent(request.query)
            is_refinement = (kw is True) or is_enhancement
            print(f"[sql] intent={'REFINE' if is_refinement else 'NEW'} (fast heuristic)")

        if is_refinement and last_sql:
            print(f"[sql] refining prior SQL: {last_sql!r}")
            enhancement_block = ""
            task_block = (
                f"### Current query\n{last_sql}\n\n"
                f"### Modification request\n"
                f"{request.query}\n\n"
                "### Instructions\n"
                "Take the Current query above as the base. Apply ONLY the modification "
                "described. Keep every existing SELECT column, JOIN, WHERE condition, "
                "ORDER BY and LIMIT from the base query. Only add or change what the "
                "modification asks for. Keep it read-only (SELECT or WITH...SELECT only). "
                "Return '-- Reason', then the full updated SQL ending with ';'."
                f"{enhancement_block}\n"
                "SQL:"
            )
        else:
            print(f"[sql] fresh query: {request.query!r}")
            task_block = f"### Task\nREQUEST: {request.query}\nSQL:"

        prompt = (
            f"{SQL_SYSTEM_PROMPT}\n\n"
            f"SCHEMA (table: columns):\n{schema_summary}\n\n"
            f"{SQL_RULES}\n\n"
            "### Example\n"
            "REQUEST: list top 10 recent orders\n"
            "SQL:\n"
            "-- Reason: The query returns the most recent orders requested by the user.\n"
            "SELECT o.OrderID, o.OrderDate FROM Orders o ORDER BY o.OrderDate DESC LIMIT 10;\n\n"
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
                        num_ctx=min(SQL_NUM_CTX, 1600),
                        num_predict=180,
                        temperature=max(0.0, min(SQL_TEMPERATURE, 0.3)),
                        top_p=0.4,
                        top_k=12,
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
        sql_query = ensure_sql_comments(sql_query, request.query)

        is_safe, reason = is_select_only_sql(sql_query)
        if not is_safe:
            raise HTTPException(status_code=422, detail=f"Unsafe SQL blocked: {reason}")

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
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat")
async def chat(
    request: ChatRequest,
    _current_user: UserModel = Depends(get_current_user),
) -> ChatResponse:
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
async def chat_stream(
    request: ChatRequest,
    _current_user: UserModel = Depends(get_current_user),
):
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