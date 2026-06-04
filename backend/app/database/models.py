from sqlalchemy import (
    Column, String, Boolean, Integer, Text, BigInteger, ForeignKey,
)
from sqlalchemy.orm import DeclarativeBase, relationship


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
    schema_faq = Column(Text, nullable=False, default="")
    updated_at = Column(BigInteger, nullable=False)
    user = relationship("UserModel", back_populates="schemas")
    threads = relationship("ThreadModel", back_populates="schema")


class ThreadModel(Base):
    __tablename__ = "threads"
    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    schema_id = Column(String, ForeignKey("sql_schemas.id", ondelete="SET NULL"), nullable=True, index=True)
    sql_model = Column(String, nullable=True)
    title = Column(String, nullable=False)
    mode = Column(String, nullable=False)
    updated_at = Column(BigInteger, nullable=False)
    user = relationship("UserModel", back_populates="threads")
    schema = relationship("SqlSchemaModel", back_populates="threads")
    messages = relationship(
        "MessageModel",
        back_populates="thread",
        cascade="all, delete-orphan",
        order_by="MessageModel.position",
    )
    prompts = relationship(
        "PromptModel",
        back_populates="thread",
        cascade="all, delete-orphan",
        order_by="PromptModel.created_at",
    )
    sql_generation_logs = relationship(
        "SqlGenerationLogModel",
        back_populates="thread",
        cascade="all, delete-orphan",
        order_by="SqlGenerationLogModel.created_at",
    )


class MessageModel(Base):
    __tablename__ = "messages"
    id = Column(String, primary_key=True)
    thread_id = Column(String, ForeignKey("threads.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False, default="")
    is_sql = Column(Boolean, nullable=False, default=False)
    position = Column(Integer, nullable=False, default=0)
    thread = relationship("ThreadModel", back_populates="messages")


class PromptModel(Base):
    __tablename__ = "prompts"
    id = Column(String, primary_key=True)
    thread_id = Column(String, ForeignKey("threads.id", ondelete="CASCADE"), nullable=False, index=True)
    message_id = Column(String, nullable=False, index=True)
    prompt_text = Column(Text, nullable=False, default="")
    created_at = Column(BigInteger, nullable=False)
    thread = relationship("ThreadModel", back_populates="prompts")


class SqlGenerationLogModel(Base):
    """Audit trail for SQL generation: intent decision, prompt, and model output."""
    __tablename__ = "sql_generation_logs"
    id = Column(String, primary_key=True)
    thread_id = Column(String, ForeignKey("threads.id", ondelete="CASCADE"), nullable=False, index=True)
    user_message_id = Column(String, nullable=True, index=True)
    assistant_message_id = Column(String, nullable=False, index=True)
    user_query = Column(Text, nullable=False, default="")
    intent = Column(String, nullable=False)
    intent_source = Column(String, nullable=False)
    heuristic_intent = Column(String, nullable=False, default="")
    classifier_answer = Column(Text, nullable=False, default="")
    sql_provider = Column(String, nullable=False, default="")
    model = Column(String, nullable=False, default="")
    cached = Column(Boolean, nullable=False, default=False)
    prompt_text = Column(Text, nullable=False, default="")
    raw_response = Column(Text, nullable=False, default="")
    generated_sql = Column(Text, nullable=False, default="")
    created_at = Column(BigInteger, nullable=False)
    thread = relationship("ThreadModel", back_populates="sql_generation_logs")
