"""Durable generation state, idempotency, cancellation, and metrics."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, UUIDMixin
from app.db.types import JSONType


class GenerationRun(UUIDMixin, CreatedAtMixin, Base):
    __tablename__ = "generation_runs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["conversation_id", "user_id"],
            ["conversations.id", "conversations.user_id"],
            ondelete="CASCADE",
            name="conversation_owner",
        ),
        ForeignKeyConstraint(
            ["conversation_id", "user_id", "user_message_id"],
            ["messages.conversation_id", "messages.user_id", "messages.id"],
            ondelete="CASCADE",
            name="user_message_owner",
        ),
        ForeignKeyConstraint(
            ["conversation_id", "user_id", "assistant_message_id"],
            ["messages.conversation_id", "messages.user_id", "messages.id"],
            ondelete="CASCADE",
            name="assistant_message_owner",
        ),
        UniqueConstraint("user_id", "idempotency_key", name="idempotency"),
        CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'stopped', 'failed', 'interrupted')",
            name="status",
        ),
        CheckConstraint(
            "finish_reason IS NULL OR finish_reason IN ('stop', 'length', 'cancelled', 'error', 'interrupted')",
            name="finish_reason",
        ),
        CheckConstraint("prompt_tokens IS NULL OR prompt_tokens >= 0", name="prompt_tokens"),
        CheckConstraint(
            "completion_tokens IS NULL OR completion_tokens >= 0", name="completion_tokens"
        ),
        Index(
            "ix_generation_runs_active_conversation",
            "conversation_id",
            unique=True,
            sqlite_where=text("status IN ('queued', 'running')"),
            postgresql_where=text("status IN ('queued', 'running')"),
        ),
        Index("ix_generation_runs_user_id_created_at", "user_id", "created_at"),
        Index("ix_generation_runs_status_created_at", "status", "created_at"),
        Index(
            "ix_generation_runs_assistant_message_id_created_at",
            "assistant_message_id",
            "created_at",
        ),
    )

    conversation_id: Mapped[uuid.UUID]
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    user_message_id: Mapped[uuid.UUID]
    assistant_message_id: Mapped[uuid.UUID]
    status: Mapped[str] = mapped_column(String(16), default="queued", server_default="queued")
    requested_model: Mapped[str] = mapped_column(String(200))
    resolved_model: Mapped[str | None] = mapped_column(String(200))
    idempotency_key: Mapped[uuid.UUID]
    request_hash: Mapped[str] = mapped_column(String(64))
    options_json: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    context_manifest: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, default=list)
    cancel_requested_at: Mapped[datetime | None]
    error_code: Mapped[str | None] = mapped_column(String(64))
    finish_reason: Mapped[str | None] = mapped_column(String(32))
    prompt_tokens: Mapped[int | None]
    completion_tokens: Mapped[int | None]
    queue_duration_ms: Mapped[int | None] = mapped_column(BigInteger)
    total_duration_ms: Mapped[int | None] = mapped_column(BigInteger)
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]
