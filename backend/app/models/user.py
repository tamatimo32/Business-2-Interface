"""Local appliance accounts."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.conversation import Conversation
    from app.models.session import AuthSession


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('user', 'admin')", name="role"),
        CheckConstraint("locale IN ('nl', 'fr', 'de', 'en')", name="locale"),
        CheckConstraint("theme IN ('system', 'light', 'dark')", name="theme"),
        CheckConstraint("username <> '' AND username = lower(username)", name="username"),
        CheckConstraint("display_name <> ''", name="display_name"),
        CheckConstraint("storage_quota_bytes IS NULL OR storage_quota_bytes >= 0", name="quota"),
        CheckConstraint("failed_login_count >= 0", name="failed_login_count"),
        CheckConstraint("version >= 1", name="version"),
        Index("ix_users_role_is_active", "role", "is_active"),
    )

    username: Mapped[str] = mapped_column(String(64), unique=True)
    display_name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(512))
    role: Mapped[str] = mapped_column(String(16), default="user", server_default="user")
    locale: Mapped[str] = mapped_column(String(2), default="en", server_default="en")
    theme: Mapped[str] = mapped_column(String(16), default="system", server_default="system")
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true")
    must_change_password: Mapped[bool] = mapped_column(default=True, server_default="true")
    storage_quota_bytes: Mapped[int | None] = mapped_column(BigInteger)
    failed_login_count: Mapped[int] = mapped_column(default=0, server_default="0")
    locked_until: Mapped[datetime | None]
    password_changed_at: Mapped[datetime]
    last_login_at: Mapped[datetime | None]
    version: Mapped[int] = mapped_column(default=1, server_default="1")

    sessions: Mapped[list["AuthSession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
