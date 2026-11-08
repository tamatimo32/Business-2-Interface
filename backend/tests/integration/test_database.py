"""Migration, SQLite connection policy, and ownership-integration tests."""

import asyncio
from uuid import uuid4

import pytest
from alembic import command
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import IntegrityError

from app.db.base import Base
from app.db.session import Database
from app.db.types import UTCDateTime, utcnow
from app.models import (
    Conversation,
    ConversationDocument,
    Document,
    DocumentChunk,
    GenerationRun,
    Message,
    MessageSource,
    User,
)
from tests.conftest import alembic_config

EXPECTED_TABLES = {
    "users",
    "auth_sessions",
    "app_settings",
    "conversations",
    "messages",
    "generation_runs",
    "conversation_documents",
    "documents",
    "document_chunks",
    "web_search_requests",
    "web_search_results",
    "message_sources",
    "jobs",
    "backups",
    "audit_events",
}


def make_user(username: str = "employee") -> User:
    return User(
        username=username,
        display_name="Employee",
        password_hash="test-only-not-a-password-hash",
        password_changed_at=utcnow(),
    )


async def test_initial_migration_contains_every_planned_table(database: Database) -> None:
    async with database.engine.connect() as connection:
        names = await connection.run_sync(lambda sync: set(inspect(sync).get_table_names()))
        revision = (
            await connection.execute(text("SELECT version_num FROM alembic_version"))
        ).scalar_one()
        indexes = await connection.run_sync(
            lambda sync: inspect(sync).get_indexes("generation_runs")
        )
    assert names == EXPECTED_TABLES | {"alembic_version"}
    assert set(Base.metadata.tables) == EXPECTED_TABLES
    assert revision == "0001_initial_schema"
    active = next(
        index for index in indexes if index["name"] == "ix_generation_runs_active_conversation"
    )
    assert active["unique"] == 1
    assert active["dialect_options"]["sqlite_where"] is not None


async def test_pragmas_apply_to_each_new_connection(database: Database) -> None:
    await database.engine.dispose()

    async def read_pragmas() -> tuple:
        async with database.session_factory() as session:
            return (
                (await session.execute(text("PRAGMA journal_mode"))).scalar_one(),
                (await session.execute(text("PRAGMA foreign_keys"))).scalar_one(),
                (await session.execute(text("PRAGMA synchronous"))).scalar_one(),
                (await session.execute(text("PRAGMA busy_timeout"))).scalar_one(),
            )

    assert await asyncio.gather(read_pragmas(), read_pragmas()) == [
        ("wal", 1, 1, 5000),
        ("wal", 1, 1, 5000),
    ]


async def test_migration_round_trip_and_no_model_drift(database: Database) -> None:
    await asyncio.to_thread(command.check, alembic_config())
    await asyncio.to_thread(command.downgrade, alembic_config(), "base")
    async with database.engine.connect() as connection:
        names = await connection.run_sync(lambda sync: set(inspect(sync).get_table_names()))
    assert names == {"alembic_version"}
    await asyncio.to_thread(command.upgrade, alembic_config(), "head")
    await asyncio.to_thread(command.check, alembic_config())


async def test_foreign_keys_reject_unknown_owner(database: Database) -> None:
    async with database.session_factory() as session:
        session.add(Conversation(user_id=uuid4(), model="chat:latest"))
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()


async def test_cross_owner_document_attachment_is_rejected(database: Database) -> None:
    async with database.session_factory() as session:
        owner = make_user("owner")
        other = make_user("other")
        session.add_all([owner, other])
        await session.flush()
        document = Document(
            user_id=owner.id,
            filename="private.txt",
            media_type="text/plain",
            size_bytes=10,
            sha256="a" * 64,
            storage_key="opaque/private",
        )
        conversation = Conversation(user_id=other.id, model="chat:latest")
        session.add_all([document, conversation])
        await session.flush()
        session.add(
            ConversationDocument(
                conversation_id=conversation.id,
                document_id=document.id,
                user_id=other.id,
                created_at=utcnow(),
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()


async def test_user_delete_cascades_private_data(database: Database) -> None:
    async with database.session_factory() as session:
        user = make_user()
        session.add(user)
        await session.flush()
        conversation = Conversation(user_id=user.id, model="chat:latest")
        document = Document(
            user_id=user.id,
            filename="private.txt",
            media_type="text/plain",
            size_bytes=10,
            sha256="b" * 64,
            storage_key="opaque/private-2",
        )
        session.add_all([conversation, document])
        await session.flush()
        session.add_all(
            [
                Message(
                    conversation_id=conversation.id,
                    user_id=user.id,
                    seq=1,
                    role="user",
                    content="private",
                ),
                DocumentChunk(
                    document_id=document.id,
                    ordinal=0,
                    text="private",
                    token_count=1,
                    content_hash="c" * 64,
                    chroma_id="vector-1",
                ),
                ConversationDocument(
                    conversation_id=conversation.id,
                    document_id=document.id,
                    user_id=user.id,
                    created_at=utcnow(),
                ),
            ]
        )
        await session.commit()
        await session.delete(user)
        await session.commit()
        for model in (Conversation, Message, Document, DocumentChunk, ConversationDocument):
            assert (
                await session.execute(select(func.count()).select_from(model))
            ).scalar_one() == 0


async def test_only_one_active_generation_per_conversation(database: Database) -> None:
    async with database.session_factory() as session:
        user = make_user()
        session.add(user)
        await session.flush()
        conversation = Conversation(user_id=user.id, model="chat:latest")
        session.add(conversation)
        await session.flush()
        prompt = Message(
            conversation_id=conversation.id,
            user_id=user.id,
            seq=1,
            role="user",
            content="test",
            status="completed",
        )
        answer = Message(conversation_id=conversation.id, user_id=user.id, seq=2, role="assistant")
        session.add_all([prompt, answer])
        await session.flush()

        conversation_id = conversation.id
        owner_id = user.id
        prompt_id = prompt.id
        answer_id = answer.id

        def run() -> GenerationRun:
            return GenerationRun(
                conversation_id=conversation_id,
                user_id=owner_id,
                user_message_id=prompt_id,
                assistant_message_id=answer_id,
                requested_model="chat:latest",
                idempotency_key=uuid4(),
                request_hash="d" * 64,
            )

        first = run()
        session.add(first)
        await session.commit()
        session.add(run())
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()
        await session.refresh(conversation)
        await session.refresh(prompt)
        await session.refresh(answer)
        await session.refresh(first)
        first.status = "completed"
        await session.commit()
        session.add(run())
        await session.commit()


async def test_document_deletion_preserves_citation_snapshot(database: Database) -> None:
    async with database.session_factory() as session:
        user = make_user()
        session.add(user)
        await session.flush()
        conversation = Conversation(user_id=user.id, model="chat:latest")
        document = Document(
            user_id=user.id,
            filename="private.txt",
            media_type="text/plain",
            size_bytes=10,
            sha256="e" * 64,
            storage_key="opaque/private-3",
        )
        session.add_all([conversation, document])
        await session.flush()
        message = Message(
            conversation_id=conversation.id,
            user_id=user.id,
            seq=1,
            role="assistant",
            status="completed",
        )
        chunk = DocumentChunk(
            document_id=document.id,
            ordinal=0,
            text="private chunk",
            token_count=2,
            content_hash="f" * 64,
            chroma_id="vector-2",
        )
        session.add_all([message, chunk])
        await session.flush()
        source = MessageSource(
            message_id=message.id,
            label="D1",
            position=1,
            kind="document",
            document_id=document.id,
            chunk_id=chunk.id,
            title_snapshot="private.txt",
            excerpt_snapshot="retained bounded excerpt",
        )
        session.add(source)
        await session.commit()
        await session.delete(document)
        await session.commit()
        await session.refresh(source)
        assert source.document_id is None
        assert source.chunk_id is None
        assert source.excerpt_snapshot == "retained bounded excerpt"


def test_utc_type_rejects_naive_datetime() -> None:
    from datetime import datetime

    with pytest.raises(ValueError, match="naive datetimes"):
        UTCDateTime().process_bind_param(datetime(2026, 1, 1), None)
