"""Private document metadata and extracted chunks; vectors live in Chroma."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, TimestampMixin, UUIDMixin


class Document(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("id", "user_id", name="id_owner"),
        UniqueConstraint("user_id", "sha256", name="owner_hash"),
        CheckConstraint(
            "status IN ('queued', 'processing', 'ready', 'failed', 'deleting')", name="status"
        ),
        CheckConstraint("size_bytes > 0", name="size"),
        CheckConstraint("chunk_count >= 0", name="chunk_count"),
        CheckConstraint("page_count IS NULL OR page_count >= 0", name="page_count"),
        CheckConstraint(
            "embedding_dimensions IS NULL OR embedding_dimensions > 0", name="dimensions"
        ),
        Index("ix_documents_user_id_created_at_id", "user_id", "created_at", "id"),
        Index("ix_documents_user_id_status", "user_id", "status"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    filename: Mapped[str] = mapped_column(String(255))
    media_type: Mapped[str] = mapped_column(String(128))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64))
    storage_key: Mapped[str] = mapped_column(String(512), unique=True)
    status: Mapped[str] = mapped_column(String(16), default="queued", server_default="queued")
    page_count: Mapped[int | None]
    chunk_count: Mapped[int] = mapped_column(default=0, server_default="0")
    embedding_model: Mapped[str | None] = mapped_column(String(200))
    embedding_dimensions: Mapped[int | None]
    chroma_collection: Mapped[str | None] = mapped_column(String(128))
    error_code: Mapped[str | None] = mapped_column(String(64))
    indexed_at: Mapped[datetime | None]

    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="DocumentChunk.ordinal",
    )


class DocumentChunk(UUIDMixin, CreatedAtMixin, Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "ordinal", name="ordinal"),
        CheckConstraint("ordinal >= 0 AND token_count >= 0", name="counters"),
        CheckConstraint(
            "(page_start IS NULL OR page_start >= 1) AND "
            "(page_end IS NULL OR page_start IS NOT NULL AND page_end >= page_start)",
            name="pages",
        ),
        CheckConstraint(
            "(char_start IS NULL OR char_start >= 0) AND "
            "(char_end IS NULL OR char_start IS NOT NULL AND char_end >= char_start)",
            name="characters",
        ),
        Index("ix_document_chunks_document_id_page_start", "document_id", "page_start"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    ordinal: Mapped[int]
    text: Mapped[str]
    token_count: Mapped[int]
    page_start: Mapped[int | None]
    page_end: Mapped[int | None]
    char_start: Mapped[int | None]
    char_end: Mapped[int | None]
    content_hash: Mapped[str] = mapped_column(String(64))
    chroma_id: Mapped[str] = mapped_column(String(128), unique=True)

    document: Mapped["Document"] = relationship(back_populates="chunks")
