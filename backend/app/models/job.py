"""Durable background work that can survive resource and user deletion."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.db.types import JSONType


class Job(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('document_ingest', 'document_delete', 'document_reindex', "
            "'user_purge', 'backup', 'backup_delete')",
            name="kind",
        ),
        CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')", name="status"
        ),
        CheckConstraint(
            "attempt >= 0 AND max_attempts >= 1 AND attempt <= max_attempts", name="attempts"
        ),
        CheckConstraint(
            "progress_current IS NULL OR progress_current >= 0", name="progress_current"
        ),
        CheckConstraint("progress_total IS NULL OR progress_total >= 0", name="progress_total"),
        Index("ix_jobs_dispatch", "status", "run_after", "priority", "created_at"),
        Index("ix_jobs_owner_id_created_at", "owner_id", "created_at"),
        Index("ix_jobs_resource_type_resource_id", "resource_type", "resource_id"),
        Index("ix_jobs_lease_expires_at", "lease_expires_at"),
    )

    kind: Mapped[str] = mapped_column(String(32))
    owner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    resource_type: Mapped[str | None] = mapped_column(String(32))
    resource_id: Mapped[uuid.UUID | None]
    status: Mapped[str] = mapped_column(String(16), default="queued", server_default="queued")
    dedupe_key: Mapped[str | None] = mapped_column(String(200), unique=True)
    priority: Mapped[int] = mapped_column(default=0, server_default="0")
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    stage: Mapped[str] = mapped_column(String(32), default="queued", server_default="queued")
    progress_current: Mapped[int | None]
    progress_total: Mapped[int | None]
    attempt: Mapped[int] = mapped_column(default=0, server_default="0")
    max_attempts: Mapped[int] = mapped_column(default=3, server_default="3")
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_detail: Mapped[str | None]
    run_after: Mapped[datetime]
    lease_expires_at: Mapped[datetime | None]
    worker_id: Mapped[str | None] = mapped_column(String(64))
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]
