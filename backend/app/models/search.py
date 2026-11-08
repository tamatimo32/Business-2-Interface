"""Explicit outbound search requests and normalized results."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, UUIDMixin


class WebSearchRequest(UUIDMixin, CreatedAtMixin, Base):
    __tablename__ = "web_search_requests"
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'running', 'succeeded', 'failed')", name="status"),
        CheckConstraint("result_count >= 0", name="result_count"),
        Index("ix_web_search_requests_user_id_created_at", "user_id", "created_at"),
        Index("ix_web_search_requests_status_created_at", "status", "created_at"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("generation_runs.id", ondelete="CASCADE"), unique=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    query: Mapped[str]
    provider: Mapped[str] = mapped_column(String(32), default="searxng", server_default="searxng")
    consent_version: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default="pending", server_default="pending")
    result_count: Mapped[int] = mapped_column(default=0, server_default="0")
    error_code: Mapped[str | None] = mapped_column(String(64))
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]

    results: Mapped[list["WebSearchResult"]] = relationship(
        back_populates="request",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="WebSearchResult.rank",
    )


class WebSearchResult(UUIDMixin, Base):
    __tablename__ = "web_search_results"
    __table_args__ = (
        UniqueConstraint("request_id", "rank", name="rank"),
        CheckConstraint("rank >= 1", name="positive_rank"),
        Index("ix_web_search_results_request_id", "request_id"),
    )

    request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("web_search_requests.id", ondelete="CASCADE")
    )
    rank: Mapped[int]
    url: Mapped[str]
    title: Mapped[str]
    snippet: Mapped[str]
    engine: Mapped[str | None] = mapped_column(String(64))
    published_at: Mapped[datetime | None]
    content_hash: Mapped[str] = mapped_column(String(64))

    request: Mapped[WebSearchRequest] = relationship(back_populates="results")
