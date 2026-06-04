from typing import Optional

from pydantic import BaseModel


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
    threadId: Optional[str] = None
    assistantMessageId: Optional[str] = None


class TextToSqlResponse(BaseModel):
    sql: str
    query: str
    model: str
    prompt: Optional[str] = None
    cached: bool = False
    intent: Optional[str] = None


class MessageSchema(BaseModel):
    id: str
    role: str
    content: str
    isSql: bool = False
    prompt: Optional[str] = None


class ThreadSchema(BaseModel):
    id: str
    title: str
    mode: str
    schemaId: Optional[str] = None
    sqlModel: Optional[str] = None
    updatedAt: int
    messages: list[MessageSchema] = []


class UpsertThreadRequest(BaseModel):
    thread: ThreadSchema


class UserSchemaRequest(BaseModel):
    title: str
    schema: str
    faq: Optional[str] = ""


class UserSchemaResponse(BaseModel):
    id: str
    title: str
    schema: str
    faq: str
    updatedAt: int
