"""SQLite migration utilities for the cache database."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib import resources
from importlib.abc import Traversable
from pathlib import Path

import aiosqlite

__all__ = [
    "MigrationFile",
    "apply_migrations",
    "ensure_connection_migrated",
    "get_migration_files",
]


@dataclass(frozen=True)
class MigrationFile:
    """Metadata for a single SQL migration file."""

    name: str
    sql: str


def _iter_sql_resources() -> Iterable[Traversable]:
    """Iterate over SQL migration files bundled with the package."""

    package = resources.files(__name__)
    for entry in package.iterdir():
        if entry.name.endswith(".sql"):
            yield entry


def get_migration_files() -> list[MigrationFile]:
    """Load bundled migration files as `MigrationFile` objects."""

    files = [
        MigrationFile(name=entry.name, sql=entry.read_text(encoding="utf-8"))
        for entry in sorted(_iter_sql_resources(), key=lambda item: item.name)
    ]
    return files


async def ensure_connection_migrated(connection: aiosqlite.Connection) -> None:
    """Apply migrations to an existing SQLite connection."""

    await connection.execute("PRAGMA foreign_keys=ON")
    await connection.execute(
        """
        CREATE TABLE IF NOT EXISTS migrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            applied_at TEXT NOT NULL
        )
        """
    )
    await connection.commit()

    async with connection.execute("SELECT name FROM migrations") as cursor:
        applied = {row[0] for row in await cursor.fetchall()}

    for migration in get_migration_files():
        if migration.name in applied:
            continue

        await connection.executescript(migration.sql)
        applied_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        await connection.execute(
            "INSERT INTO migrations (name, applied_at) VALUES (?, ?)",
            (migration.name, applied_at),
        )
        await connection.commit()
        applied.add(migration.name)


async def apply_migrations(db_path: str | Path) -> None:
    """Apply cache migrations to the SQLite database at `db_path`."""

    if str(db_path) != ":memory:":
        path_obj = Path(db_path).expanduser()
        path_obj.parent.mkdir(parents=True, exist_ok=True)
        target_path = str(path_obj)
    else:
        target_path = ":memory:"

    async with aiosqlite.connect(target_path) as connection:
        await ensure_connection_migrated(connection)
