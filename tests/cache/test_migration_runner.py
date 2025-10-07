"""Tests for the cache migration runner."""

from __future__ import annotations

from pathlib import Path

import aiosqlite
import pytest

from namegnome_serve.cache.migrations import apply_migrations, get_migration_files


@pytest.mark.asyncio
async def test_migrations_create_expected_tables(tmp_path: Path) -> None:
    """Running migrations should create the initial schema."""
    db_path = tmp_path / "namegnome.db"

    await apply_migrations(db_path)

    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type='table' AND name IN (
                'migrations','kv','entities','episodes','tracks','decisions','locks','cache_entries'
            )
            ORDER BY name
            """
        )
        tables = [row[0] for row in await cursor.fetchall()]

        assert tables == [
            "cache_entries",
            "decisions",
            "entities",
            "episodes",
            "kv",
            "locks",
            "migrations",
            "tracks",
        ]


@pytest.mark.asyncio
async def test_migrations_are_idempotent(tmp_path: Path) -> None:
    """Applying migrations twice should not raise errors."""
    db_path = tmp_path / "namegnome.db"

    await apply_migrations(db_path)
    await apply_migrations(db_path)

    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM migrations")
        (count,) = await cursor.fetchone()
        assert count == len(get_migration_files())
