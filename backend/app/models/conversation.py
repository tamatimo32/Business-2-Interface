"""Private conversations and explicit document selection."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.db.types import JSONType

if TYPE_CHECKING:
    from app.models.message import Message
    from app.models.user import User


class Conversation(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "conversations"
    __table_args__ = (
        UniqueConstraint("id", "user_id", name="id_owner"),
        CheckConstraint("version >= 1", name="version"),
        Index(
            "ix_conversations_sidebar",
            "user_id",
            "is_archived",
            "is_pinned",
            "last_message_at",
            "id",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str | None] = mapped_column(String(200))
    title_is_manual: Mapped[bool] = mapped_column(default=False, server_default="false")
    model: Mapped[str] = mapped_column(String(200))
    system_prompt: Mapped[str | None]
    generation_options: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    is_archived: Mapped[bool] = mapped_column(default=False, server_default="false")
    is_pinned: Mapped[bool] = mapped_column(default=False, server_default="false")
    version: Mapped[int] = mapped_column(default=1, server_default="1")
    last_message_at: Mapped[datetime | None]

    user: Mapped["User"] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        foreign_keys="[Message.conversation_id, Message.user_id]",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Message.seq",
    )


class ConversationDocument(Base):
    __tablename__ = "conversation_documents"
    __table_args__ = (
        ForeignKeyConstraint(
            ["conversation_id", "user_id"],
            ["conversations.id", "conversations.user_id"],
            ondelete="CASCADE",
            name="conversation_owner",
        ),
        ForeignKeyConstraint(
            ["document_id", "user_id"],
            ["documents.id", "documents.user_id"],
            ondelete="CASCADE",
            name="document_owner",
        ),
        Index("ix_conversation_documents_document_id", "document_id"),
        Index("ix_conversation_documents_user_id_created_at", "user_id", "created_at"),
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    document_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    created_at: Mapped[datetime]
