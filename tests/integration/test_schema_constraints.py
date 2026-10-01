"""Database-level enforcement of tenant isolation and data integrity."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

pytestmark = pytest.mark.integration

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "services" / "api" / "alembic.ini"


async def _user(conn: AsyncConnection, email: str) -> uuid.UUID:
    return (
        await conn.execute(
            text("INSERT INTO users (email, status) VALUES (:e, 'active') RETURNING id"),
            {"e": email},
        )
    ).scalar_one()


async def _connection(conn: AsyncConnection, user_id: uuid.UUID) -> uuid.UUID:
    return (
        await conn.execute(
            text(
                "INSERT INTO storage_connections "
                "(user_id, provider, provider_account_id, status, token_key_version, scopes) "
                "VALUES (:u, 'google_drive', :acct, 'active', 1, '{}') RETURNING id"
            ),
            {"u": user_id, "acct": uuid.uuid4().hex},
        )
    ).scalar_one()


async def _file(conn: AsyncConnection, user_id: uuid.UUID, connection_id: uuid.UUID) -> uuid.UUID:
    return (
        await conn.execute(
            text(
                "INSERT INTO files (user_id, storage_provider, storage_connection_id, "
                "storage_file_id, name, mime_type, size_bytes, visibility, is_starred, "
                "is_favorite, access_count, document_type, processing_status, ocr_status, "
                "extraction_status, embedding_status, is_ai_indexed) VALUES "
                "(:u, 'google_drive', :c, :sid, 'Resume.pdf', 'application/pdf', 1024, "
                "'private', false, false, 0, 'unclassified', 'pending', 'pending', "
                "'pending', 'pending', false) RETURNING id"
            ),
            {"u": user_id, "c": connection_id, "sid": uuid.uuid4().hex},
        )
    ).scalar_one()


async def test_cannot_reference_another_users_storage_connection(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        trans = await conn.begin()
        try:
            alice = await _user(conn, f"alice-{uuid.uuid4().hex}@example.test")
            mallory = await _user(conn, f"mallory-{uuid.uuid4().hex}@example.test")
            alice_conn = await _connection(conn, alice)
            with pytest.raises(IntegrityError):
                async with conn.begin_nested():
                    await _file(conn, mallory, alice_conn)
        finally:
            await trans.rollback()


async def test_cannot_tag_another_users_file(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        trans = await conn.begin()
        try:
            alice = await _user(conn, f"alice-{uuid.uuid4().hex}@example.test")
            mallory = await _user(conn, f"mallory-{uuid.uuid4().hex}@example.test")
            alice_file = await _file(conn, alice, await _connection(conn, alice))
            mallory_tag = (
                await conn.execute(
                    text(
                        "INSERT INTO tags (user_id, name, normalized_name, is_sensitive) "
                        "VALUES (:u, 'cv', 'cv', false) RETURNING id"
                    ),
                    {"u": mallory},
                )
            ).scalar_one()
            with pytest.raises(IntegrityError):
                async with conn.begin_nested():
                    await conn.execute(
                        text(
                            "INSERT INTO file_tags (file_id, tag_id, user_id, source, status) "
                            "VALUES (:f, :t, :u, 'user', 'confirmed')"
                        ),
                        {"f": alice_file, "t": mallory_tag, "u": mallory},
                    )
        finally:
            await trans.rollback()


async def test_deleting_folder_clears_reference_but_keeps_user_id(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        trans = await conn.begin()
        try:
            alice = await _user(conn, f"alice-{uuid.uuid4().hex}@example.test")
            conn_id = await _connection(conn, alice)
            folder = (
                await conn.execute(
                    text(
                        "INSERT INTO folders (user_id, storage_connection_id, storage_folder_id, "
                        "name) VALUES (:u, :c, 'drive-folder', 'Career') RETURNING id"
                    ),
                    {"u": alice, "c": conn_id},
                )
            ).scalar_one()
            file_id = await _file(conn, alice, conn_id)
            await conn.execute(
                text("UPDATE files SET parent_folder_id = :f WHERE id = :id"),
                {"f": folder, "id": file_id},
            )
            await conn.execute(text("DELETE FROM folders WHERE id = :f"), {"f": folder})
            row = (
                await conn.execute(
                    text("SELECT parent_folder_id, user_id FROM files WHERE id = :id"),
                    {"id": file_id},
                )
            ).one()
            assert row.parent_folder_id is None
            assert row.user_id == alice
        finally:
            await trans.rollback()


async def test_email_uniqueness_is_case_insensitive(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        trans = await conn.begin()
        try:
            token = uuid.uuid4().hex
            await _user(conn, f"Person-{token}@Example.test")
            with pytest.raises(IntegrityError):
                async with conn.begin_nested():
                    await _user(conn, f"person-{token}@example.TEST")
        finally:
            await trans.rollback()


async def test_enum_check_constraint_rejects_unknown_values(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        trans = await conn.begin()
        try:
            with pytest.raises(IntegrityError):
                async with conn.begin_nested():
                    await conn.execute(
                        text("INSERT INTO users (email, status) VALUES ('x@example.test', 'root')")
                    )
        finally:
            await trans.rollback()


async def test_migration_is_at_head(engine: AsyncEngine) -> None:
    head = ScriptDirectory.from_config(Config(str(ALEMBIC_INI))).get_current_head()
    async with engine.connect() as conn:
        version = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar()
    assert version == head
