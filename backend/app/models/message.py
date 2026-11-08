"""Linear conversation messages and durable source snapshots."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, TimestampMixin, UUIDMixin
from app.db.types import JSONType

if TYPE_CHECKING:
    from app.models.conversation import Conversation


class Message(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "messages"
    __table_args__ = (
        ForeignKeyConstraint(
            ["conversation_id", "user_id"],
            ["conversations.id", "conversations.user_id"],
            ondelete="CASCADE",
            name="conversation_owner",
        ),
        UniqueConstraint("conversation_id", "seq", name="sequence"),
        UniqueConstraint("conversation_id", "user_id", "id", name="owner_identity"),
        CheckConstraint("role IN ('user', 'assistant')", name="role"),
        CheckConstraint(
            "status IN ('pending', 'streaming', 'completed', 'stopped', 'failed', 'interrupted')",
            name="status",
        ),
        CheckConstraint(
            "finish_reason IS NULL OR finish_reason IN ('stop', 'length', 'cancelled', 'error', 'interrupted')",
            name="finish_reason",
        ),
        CheckConstraint("seq >= 1 AND revision >= 1", name="positive_counters"),
        Index("ix_messages_conversation_id_seq", "conversation_id", "seq"),
    )

    conversation_id: Mapped[uuid.UUID]
    user_id: Mapped[uuid.UUID]
    seq: Mapped[int]
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text, default="", server_default=text("''"))
    status: Mapped[str] = mapped_column(String(16), default="pending", server_default="pending")
    model: Mapped[str | None] = mapped_column(String(200))
    revision: Mapped[int] = mapped_column(default=1, server_default="1")
    finish_reason: Mapped[str | None] = mapped_column(String(32))
    error_code: Mapped[str | None] = mapped_column(String(64))

    conversation: Mapped["Conversation"] = relationship(
        back_populates="messages", foreign_keys="[Message.conversation_id, Message.user_id]"
    )
    sources: Mapped[list["MessageSource"]] = relationship(
        back_populates="message",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="MessageSource.position",
    )


class MessageSource(UUIDMixin, CreatedAtMixin, Base):
    __tablename__ = "message_sources"
    __table_args__ = (
        UniqueConstraint("message_id", "label", name="label"),
        UniqueConstraint("message_id", "position", name="position"),
        CheckConstraint("kind IN ('document', 'web')", name="kind"),
        CheckConstraint(
            # SQLite may null the two document references in separate FK actions.
            # Services require both on insertion; tombstones may have either/both null.
            "(kind = 'document' AND web_result_id IS NULL) OR "
            "(kind = 'web' AND document_id IS NULL AND chunk_id IS NULL)",
            name="reference_kind",
        ),
        CheckConstraint("position >= 1", name="positive_position"),
        Index("ix_message_sources_document_id", "document_id"),
        Index("ix_message_sources_chunk_id", "chunk_id"),
        Index("ix_message_sources_web_result_id", "web_result_id"),
    )

    message_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"))
    label: Mapped[str] = mapped_column(String(16))
    position: Mapped[int]
    kind: Mapped[str] = mapped_column(String(16))
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL")
    )
    chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("document_chunks.id", ondelete="SET NULL")
    )
    web_result_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("web_search_results.id", ondelete="SET NULL")
    )
    title_snapshot: Mapped[str]
    url_snapshot: Mapped[str | None]
    excerpt_snapshot: Mapped[str]
    locator: Mapped[dict] = mapped_column(JSONType, default=dict)
    score: Mapped[float | None]

    message: Mapped["Message"] = relationship(back_populates="sources")
