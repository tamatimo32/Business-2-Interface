"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-11-08 16:25:20.945406+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial_schema"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("password_hash", sa.String(length=512), nullable=False),
        sa.Column("role", sa.String(length=16), server_default="user", nullable=False),
        sa.Column("locale", sa.String(length=2), server_default="en", nullable=False),
        sa.Column("theme", sa.String(length=16), server_default="system", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("must_change_password", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("storage_quota_bytes", sa.BigInteger(), nullable=True),
        sa.Column("failed_login_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("display_name <> ''", name=op.f("ck_users_display_name")),
        sa.CheckConstraint("locale IN ('nl', 'fr', 'de', 'en')", name=op.f("ck_users_locale")),
        sa.CheckConstraint("role IN ('user', 'admin')", name=op.f("ck_users_role")),
        sa.CheckConstraint("theme IN ('system', 'light', 'dark')", name=op.f("ck_users_theme")),
        sa.CheckConstraint(
            "username <> '' AND username = lower(username)", name=op.f("ck_users_username")
        ),
        sa.CheckConstraint("failed_login_count >= 0", name=op.f("ck_users_failed_login_count")),
        sa.CheckConstraint(
            "storage_quota_bytes IS NULL OR storage_quota_bytes >= 0", name=op.f("ck_users_quota")
        ),
        sa.CheckConstraint("version >= 1", name=op.f("ck_users_version")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("username", name=op.f("uq_users_username")),
    )
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.create_index("ix_users_role_is_active", ["role", "is_active"], unique=False)

    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column(
            "value", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=False
        ),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("version >= 1", name=op.f("ck_app_settings_version")),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["users.id"],
            name=op.f("fk_app_settings_updated_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_app_settings")),
    )
    with op.batch_alter_table("app_settings", schema=None) as batch_op:
        batch_op.create_index("ix_app_settings_updated_at", ["updated_at"], unique=False)

    op.create_table(
        "audit_events",
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=True),
        sa.Column("target_id", sa.Uuid(), nullable=True),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("ip_hash", sa.String(length=64), nullable=True),
        sa.Column(
            "metadata", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=False
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_audit_events_actor_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_events")),
    )
    with op.batch_alter_table("audit_events", schema=None) as batch_op:
        batch_op.create_index(
            "ix_audit_events_action_created_at", ["action", "created_at"], unique=False
        )
        batch_op.create_index(
            "ix_audit_events_actor_user_id_created_at",
            ["actor_user_id", "created_at"],
            unique=False,
        )
        batch_op.create_index("ix_audit_events_created_at_id", ["created_at", "id"], unique=False)
        batch_op.create_index(
            "ix_audit_events_target_type_target_id_created_at",
            ["target_type", "target_id", "created_at"],
            unique=False,
        )

    op.create_table(
        "auth_sessions",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idle_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("ip_hash", sa.String(length=64), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("expires_at > created_at", name=op.f("ck_auth_sessions_expiry")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_auth_sessions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_sessions")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_auth_sessions_token_hash")),
    )
    with op.batch_alter_table("auth_sessions", schema=None) as batch_op:
        batch_op.create_index("ix_auth_sessions_expires_at", ["expires_at"], unique=False)
        batch_op.create_index(
            "ix_auth_sessions_user_id_revoked_at", ["user_id", "revoked_at"], unique=False
        )

    op.create_table(
        "conversations",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("title_is_manual", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("model", sa.String(length=200), nullable=False),
        sa.Column("system_prompt", sa.String(), nullable=True),
        sa.Column(
            "generation_options",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
        ),
        sa.Column("is_archived", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("is_pinned", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("version >= 1", name=op.f("ck_conversations_version")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_conversations_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_conversations")),
        sa.UniqueConstraint("id", "user_id", name="id_owner"),
    )
    with op.batch_alter_table("conversations", schema=None) as batch_op:
        batch_op.create_index(
            "ix_conversations_sidebar",
            ["user_id", "is_archived", "is_pinned", "last_message_at", "id"],
            unique=False,
        )

    op.create_table(
        "documents",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("media_type", sa.String(length=128), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="queued", nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("chunk_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("embedding_model", sa.String(length=200), nullable=True),
        sa.Column("embedding_dimensions", sa.Integer(), nullable=True),
        sa.Column("chroma_collection", sa.String(length=128), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('queued', 'processing', 'ready', 'failed', 'deleting')",
            name=op.f("ck_documents_status"),
        ),
        sa.CheckConstraint("chunk_count >= 0", name=op.f("ck_documents_chunk_count")),
        sa.CheckConstraint(
            "embedding_dimensions IS NULL OR embedding_dimensions > 0",
            name=op.f("ck_documents_dimensions"),
        ),
        sa.CheckConstraint(
            "page_count IS NULL OR page_count >= 0", name=op.f("ck_documents_page_count")
        ),
        sa.CheckConstraint("size_bytes > 0", name=op.f("ck_documents_size")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_documents_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_documents")),
        sa.UniqueConstraint("id", "user_id", name="id_owner"),
        sa.UniqueConstraint("storage_key", name=op.f("uq_documents_storage_key")),
        sa.UniqueConstraint("user_id", "sha256", name="owner_hash"),
    )
    with op.batch_alter_table("documents", schema=None) as batch_op:
        batch_op.create_index(
            "ix_documents_user_id_created_at_id", ["user_id", "created_at", "id"], unique=False
        )
        batch_op.create_index("ix_documents_user_id_status", ["user_id", "status"], unique=False)

    op.create_table(
        "jobs",
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("resource_type", sa.String(length=32), nullable=True),
        sa.Column("resource_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=16), server_default="queued", nullable=False),
        sa.Column("dedupe_key", sa.String(length=200), nullable=True),
        sa.Column("priority", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "payload", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=False
        ),
        sa.Column("stage", sa.String(length=32), server_default="queued", nullable=False),
        sa.Column("progress_current", sa.Integer(), nullable=True),
        sa.Column("progress_total", sa.Integer(), nullable=True),
        sa.Column("attempt", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="3", nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_detail", sa.String(), nullable=True),
        sa.Column("run_after", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("worker_id", sa.String(length=64), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('document_ingest', 'document_delete', 'document_reindex', 'user_purge', 'backup', 'backup_delete')",
            name=op.f("ck_jobs_kind"),
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')",
            name=op.f("ck_jobs_status"),
        ),
        sa.CheckConstraint(
            "attempt >= 0 AND max_attempts >= 1 AND attempt <= max_attempts",
            name=op.f("ck_jobs_attempts"),
        ),
        sa.CheckConstraint(
            "progress_current IS NULL OR progress_current >= 0",
            name=op.f("ck_jobs_progress_current"),
        ),
        sa.CheckConstraint(
            "progress_total IS NULL OR progress_total >= 0", name=op.f("ck_jobs_progress_total")
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("fk_jobs_created_by_users"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], name=op.f("fk_jobs_owner_id_users"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jobs")),
        sa.UniqueConstraint("dedupe_key", name=op.f("uq_jobs_dedupe_key")),
    )
    with op.batch_alter_table("jobs", schema=None) as batch_op:
        batch_op.create_index(
            "ix_jobs_dispatch", ["status", "run_after", "priority", "created_at"], unique=False
        )
        batch_op.create_index("ix_jobs_lease_expires_at", ["lease_expires_at"], unique=False)
        batch_op.create_index(
            "ix_jobs_owner_id_created_at", ["owner_id", "created_at"], unique=False
        )
        batch_op.create_index(
            "ix_jobs_resource_type_resource_id", ["resource_type", "resource_id"], unique=False
        )

    op.create_table(
        "backups",
        sa.Column("job_id", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=16), server_default="queued", nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("app_version", sa.String(length=32), nullable=False),
        sa.Column("schema_revision", sa.String(length=64), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'ready', 'failed', 'deleting')",
            name=op.f("ck_backups_status"),
        ),
        sa.CheckConstraint("size_bytes IS NULL OR size_bytes >= 0", name=op.f("ck_backups_size")),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_backups_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name=op.f("fk_backups_job_id_jobs"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_backups")),
        sa.UniqueConstraint("job_id", name=op.f("uq_backups_job_id")),
        sa.UniqueConstraint("storage_key", name=op.f("uq_backups_storage_key")),
    )
    with op.batch_alter_table("backups", schema=None) as batch_op:
        batch_op.create_index("ix_backups_expires_at", ["expires_at"], unique=False)
        batch_op.create_index(
            "ix_backups_status_created_at", ["status", "created_at"], unique=False
        )

    op.create_table(
        "conversation_documents",
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["conversation_id", "user_id"],
            ["conversations.id", "conversations.user_id"],
            name="conversation_owner",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["document_id", "user_id"],
            ["documents.id", "documents.user_id"],
            name="document_owner",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_conversation_documents_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "conversation_id", "document_id", name=op.f("pk_conversation_documents")
        ),
    )
    with op.batch_alter_table("conversation_documents", schema=None) as batch_op:
        batch_op.create_index(
            "ix_conversation_documents_document_id", ["document_id"], unique=False
        )
        batch_op.create_index(
            "ix_conversation_documents_user_id_created_at", ["user_id", "created_at"], unique=False
        )

    op.create_table(
        "document_chunks",
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("text", sa.String(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("page_start", sa.Integer(), nullable=True),
        sa.Column("page_end", sa.Integer(), nullable=True),
        sa.Column("char_start", sa.Integer(), nullable=True),
        sa.Column("char_end", sa.Integer(), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("chroma_id", sa.String(length=128), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(char_start IS NULL OR char_start >= 0) AND (char_end IS NULL OR char_start IS NOT NULL AND char_end >= char_start)",
            name=op.f("ck_document_chunks_characters"),
        ),
        sa.CheckConstraint(
            "(page_start IS NULL OR page_start >= 1) AND (page_end IS NULL OR page_start IS NOT NULL AND page_end >= page_start)",
            name=op.f("ck_document_chunks_pages"),
        ),
        sa.CheckConstraint(
            "ordinal >= 0 AND token_count >= 0", name=op.f("ck_document_chunks_counters")
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_document_chunks_document_id_documents"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document_chunks")),
        sa.UniqueConstraint("chroma_id", name=op.f("uq_document_chunks_chroma_id")),
        sa.UniqueConstraint("document_id", "ordinal", name="ordinal"),
    )
    with op.batch_alter_table("document_chunks", schema=None) as batch_op:
        batch_op.create_index(
            "ix_document_chunks_document_id_page_start", ["document_id", "page_start"], unique=False
        )

    op.create_table(
        "messages",
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="pending", nullable=False),
        sa.Column("model", sa.String(length=200), nullable=True),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
        sa.Column("finish_reason", sa.String(length=32), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "finish_reason IS NULL OR finish_reason IN ('stop', 'length', 'cancelled', 'error', 'interrupted')",
            name=op.f("ck_messages_finish_reason"),
        ),
        sa.CheckConstraint("role IN ('user', 'assistant')", name=op.f("ck_messages_role")),
        sa.CheckConstraint(
            "status IN ('pending', 'streaming', 'completed', 'stopped', 'failed', 'interrupted')",
            name=op.f("ck_messages_status"),
        ),
        sa.CheckConstraint(
            "seq >= 1 AND revision >= 1", name=op.f("ck_messages_positive_counters")
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id", "user_id"],
            ["conversations.id", "conversations.user_id"],
            name="conversation_owner",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_messages")),
        sa.UniqueConstraint("conversation_id", "seq", name="sequence"),
        sa.UniqueConstraint("conversation_id", "user_id", "id", name="owner_identity"),
    )
    with op.batch_alter_table("messages", schema=None) as batch_op:
        batch_op.create_index(
            "ix_messages_conversation_id_seq", ["conversation_id", "seq"], unique=False
        )

    op.create_table(
        "generation_runs",
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("user_message_id", sa.Uuid(), nullable=False),
        sa.Column("assistant_message_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="queued", nullable=False),
        sa.Column("requested_model", sa.String(length=200), nullable=False),
        sa.Column("resolved_model", sa.String(length=200), nullable=True),
        sa.Column("idempotency_key", sa.Uuid(), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "options_json", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=False
        ),
        sa.Column(
            "context_manifest",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
        ),
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("finish_reason", sa.String(length=32), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("queue_duration_ms", sa.BigInteger(), nullable=True),
        sa.Column("total_duration_ms", sa.BigInteger(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "finish_reason IS NULL OR finish_reason IN ('stop', 'length', 'cancelled', 'error', 'interrupted')",
            name=op.f("ck_generation_runs_finish_reason"),
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'stopped', 'failed', 'interrupted')",
            name=op.f("ck_generation_runs_status"),
        ),
        sa.CheckConstraint(
            "completion_tokens IS NULL OR completion_tokens >= 0",
            name=op.f("ck_generation_runs_completion_tokens"),
        ),
        sa.CheckConstraint(
            "prompt_tokens IS NULL OR prompt_tokens >= 0",
            name=op.f("ck_generation_runs_prompt_tokens"),
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id", "user_id", "assistant_message_id"],
            ["messages.conversation_id", "messages.user_id", "messages.id"],
            name="assistant_message_owner",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id", "user_id", "user_message_id"],
            ["messages.conversation_id", "messages.user_id", "messages.id"],
            name="user_message_owner",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id", "user_id"],
            ["conversations.id", "conversations.user_id"],
            name="conversation_owner",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_generation_runs_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_generation_runs")),
        sa.UniqueConstraint("user_id", "idempotency_key", name="idempotency"),
    )
    with op.batch_alter_table("generation_runs", schema=None) as batch_op:
        batch_op.create_index(
            "ix_generation_runs_active_conversation",
            ["conversation_id"],
            unique=True,
            sqlite_where=sa.text("status IN ('queued', 'running')"),
            postgresql_where=sa.text("status IN ('queued', 'running')"),
        )
        batch_op.create_index(
            "ix_generation_runs_assistant_message_id_created_at",
            ["assistant_message_id", "created_at"],
            unique=False,
        )
        batch_op.create_index(
            "ix_generation_runs_status_created_at", ["status", "created_at"], unique=False
        )
        batch_op.create_index(
            "ix_generation_runs_user_id_created_at", ["user_id", "created_at"], unique=False
        )

    op.create_table(
        "web_search_requests",
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("query", sa.String(), nullable=False),
        sa.Column("provider", sa.String(length=32), server_default="searxng", nullable=False),
        sa.Column("consent_version", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="pending", nullable=False),
        sa.Column("result_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'succeeded', 'failed')",
            name=op.f("ck_web_search_requests_status"),
        ),
        sa.CheckConstraint("result_count >= 0", name=op.f("ck_web_search_requests_result_count")),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["generation_runs.id"],
            name=op.f("fk_web_search_requests_run_id_generation_runs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_web_search_requests_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_web_search_requests")),
        sa.UniqueConstraint("run_id", name=op.f("uq_web_search_requests_run_id")),
    )
    with op.batch_alter_table("web_search_requests", schema=None) as batch_op:
        batch_op.create_index(
            "ix_web_search_requests_status_created_at", ["status", "created_at"], unique=False
        )
        batch_op.create_index(
            "ix_web_search_requests_user_id_created_at", ["user_id", "created_at"], unique=False
        )

    op.create_table(
        "web_search_results",
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("snippet", sa.String(), nullable=False),
        sa.Column("engine", sa.String(length=64), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("rank >= 1", name=op.f("ck_web_search_results_positive_rank")),
        sa.ForeignKeyConstraint(
            ["request_id"],
            ["web_search_requests.id"],
            name=op.f("fk_web_search_results_request_id_web_search_requests"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_web_search_results")),
        sa.UniqueConstraint("request_id", "rank", name="rank"),
    )
    with op.batch_alter_table("web_search_results", schema=None) as batch_op:
        batch_op.create_index("ix_web_search_results_request_id", ["request_id"], unique=False)

    op.create_table(
        "message_sources",
        sa.Column("message_id", sa.Uuid(), nullable=False),
        sa.Column("label", sa.String(length=16), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=True),
        sa.Column("chunk_id", sa.Uuid(), nullable=True),
        sa.Column("web_result_id", sa.Uuid(), nullable=True),
        sa.Column("title_snapshot", sa.String(), nullable=False),
        sa.Column("url_snapshot", sa.String(), nullable=True),
        sa.Column("excerpt_snapshot", sa.String(), nullable=False),
        sa.Column(
            "locator", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=False
        ),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(kind = 'document' AND web_result_id IS NULL) OR (kind = 'web' AND document_id IS NULL AND chunk_id IS NULL)",
            name=op.f("ck_message_sources_reference_kind"),
        ),
        sa.CheckConstraint("kind IN ('document', 'web')", name=op.f("ck_message_sources_kind")),
        sa.CheckConstraint("position >= 1", name=op.f("ck_message_sources_positive_position")),
        sa.ForeignKeyConstraint(
            ["chunk_id"],
            ["document_chunks.id"],
            name=op.f("fk_message_sources_chunk_id_document_chunks"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_message_sources_document_id_documents"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["messages.id"],
            name=op.f("fk_message_sources_message_id_messages"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["web_result_id"],
            ["web_search_results.id"],
            name=op.f("fk_message_sources_web_result_id_web_search_results"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_message_sources")),
        sa.UniqueConstraint("message_id", "label", name="label"),
        sa.UniqueConstraint("message_id", "position", name="position"),
    )
    with op.batch_alter_table("message_sources", schema=None) as batch_op:
        batch_op.create_index("ix_message_sources_chunk_id", ["chunk_id"], unique=False)
        batch_op.create_index("ix_message_sources_document_id", ["document_id"], unique=False)
        batch_op.create_index("ix_message_sources_web_result_id", ["web_result_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("message_sources", schema=None) as batch_op:
        batch_op.drop_index("ix_message_sources_web_result_id")
        batch_op.drop_index("ix_message_sources_document_id")
        batch_op.drop_index("ix_message_sources_chunk_id")

    op.drop_table("message_sources")
    with op.batch_alter_table("web_search_results", schema=None) as batch_op:
        batch_op.drop_index("ix_web_search_results_request_id")

    op.drop_table("web_search_results")
    with op.batch_alter_table("web_search_requests", schema=None) as batch_op:
        batch_op.drop_index("ix_web_search_requests_user_id_created_at")
        batch_op.drop_index("ix_web_search_requests_status_created_at")

    op.drop_table("web_search_requests")
    with op.batch_alter_table("generation_runs", schema=None) as batch_op:
        batch_op.drop_index("ix_generation_runs_user_id_created_at")
        batch_op.drop_index("ix_generation_runs_status_created_at")
        batch_op.drop_index("ix_generation_runs_assistant_message_id_created_at")
        batch_op.drop_index(
            "ix_generation_runs_active_conversation",
            sqlite_where=sa.text("status IN ('queued', 'running')"),
            postgresql_where=sa.text("status IN ('queued', 'running')"),
        )

    op.drop_table("generation_runs")
    with op.batch_alter_table("messages", schema=None) as batch_op:
        batch_op.drop_index("ix_messages_conversation_id_seq")

    op.drop_table("messages")
    with op.batch_alter_table("document_chunks", schema=None) as batch_op:
        batch_op.drop_index("ix_document_chunks_document_id_page_start")

    op.drop_table("document_chunks")
    with op.batch_alter_table("conversation_documents", schema=None) as batch_op:
        batch_op.drop_index("ix_conversation_documents_user_id_created_at")
        batch_op.drop_index("ix_conversation_documents_document_id")

    op.drop_table("conversation_documents")
    with op.batch_alter_table("backups", schema=None) as batch_op:
        batch_op.drop_index("ix_backups_status_created_at")
        batch_op.drop_index("ix_backups_expires_at")

    op.drop_table("backups")
    with op.batch_alter_table("jobs", schema=None) as batch_op:
        batch_op.drop_index("ix_jobs_resource_type_resource_id")
        batch_op.drop_index("ix_jobs_owner_id_created_at")
        batch_op.drop_index("ix_jobs_lease_expires_at")
        batch_op.drop_index("ix_jobs_dispatch")

    op.drop_table("jobs")
    with op.batch_alter_table("documents", schema=None) as batch_op:
        batch_op.drop_index("ix_documents_user_id_status")
        batch_op.drop_index("ix_documents_user_id_created_at_id")

    op.drop_table("documents")
    with op.batch_alter_table("conversations", schema=None) as batch_op:
        batch_op.drop_index("ix_conversations_sidebar")

    op.drop_table("conversations")
    with op.batch_alter_table("auth_sessions", schema=None) as batch_op:
        batch_op.drop_index("ix_auth_sessions_user_id_revoked_at")
        batch_op.drop_index("ix_auth_sessions_expires_at")

    op.drop_table("auth_sessions")
    with op.batch_alter_table("audit_events", schema=None) as batch_op:
        batch_op.drop_index("ix_audit_events_target_type_target_id_created_at")
        batch_op.drop_index("ix_audit_events_created_at_id")
        batch_op.drop_index("ix_audit_events_actor_user_id_created_at")
        batch_op.drop_index("ix_audit_events_action_created_at")

    op.drop_table("audit_events")
    with op.batch_alter_table("app_settings", schema=None) as batch_op:
        batch_op.drop_index("ix_app_settings_updated_at")

    op.drop_table("app_settings")
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_index("ix_users_role_is_active")

    op.drop_table("users")
