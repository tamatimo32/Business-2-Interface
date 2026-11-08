"""Runtime settings, local backup manifests, and content-free audit events."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, UUIDMixin
from app.db.types import JSONType, utcnow


class AppSetting(Base):
    __tablename__ = "app_settings"
    __table_args__ = (
        CheckConstraint("version >= 1", name="version"),
        Index("ix_app_settings_updated_at", "updated_at"),
    )

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[Any] = mapped_column(JSONType)
    version: Mapped[int] = mapped_column(default=1, server_default="1")
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)


class Backup(UUIDMixin, CreatedAtMixin, Base):
    __tablename__ = "backups"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'ready', 'failed', 'deleting')", name="status"
        ),
        CheckConstraint("size_bytes IS NULL OR size_bytes >= 0", name="size"),
        Index("ix_backups_status_created_at", "status", "created_at"),
        Index("ix_backups_expires_at", "expires_at"),
    )

    job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("jobs.id", ondelete="SET NULL"), unique=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(16), default="queued", server_default="queued")
    storage_key: Mapped[str] = mapped_column(String(512), unique=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    sha256: Mapped[str | None] = mapped_column(String(64))
    app_version: Mapped[str] = mapped_column(String(32))
    schema_revision: Mapped[str] = mapped_column(String(64))
    error_code: Mapped[str | None] = mapped_column(String(64))
    started_at: Mapped[datetime | None]
    completed_at: Mapped[datetime | None]
    expires_at: Mapped[datetime | None]


class AuditEvent(UUIDMixin, CreatedAtMixin, Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_created_at_id", "created_at", "id"),
        Index("ix_audit_events_actor_user_id_created_at", "actor_user_id", "created_at"),
        Index("ix_audit_events_action_created_at", "action", "created_at"),
        Index(
            "ix_audit_events_target_type_target_id_created_at",
            "target_type",
            "target_id",
            "created_at",
        ),
    )

    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(String(64))
    target_type: Mapped[str | None] = mapped_column(String(32))
    target_id: Mapped[uuid.UUID | None]
    request_id: Mapped[uuid.UUID]
    ip_hash: Mapped[str | None] = mapped_column(String(64))
    event_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSONType, default=dict)
