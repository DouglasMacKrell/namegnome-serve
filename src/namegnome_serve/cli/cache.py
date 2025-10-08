"""CLI commands for cache management."""

from __future__ import annotations

import asyncio
import importlib
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any

if TYPE_CHECKING:  # pragma: no cover - typing only
    import typer
    from typer import Typer as TyperType
else:  # pragma: no cover - runtime fallback for typing
    typer = importlib.import_module("typer")
    TyperType = Any

from namegnome_serve.cache.migrations import apply_migrations
from namegnome_serve.cache.paths import resolve_cache_db_path

app: TyperType = typer.Typer(help="Manage the NameGnome cache database.")

DbPathOption = Annotated[
    Path | None,
    typer.Option(
        "--db-path",
        help="Optional override for the cache database location.",
    ),
]


def migrate(db_path: DbPathOption = None) -> None:
    """Apply cache migrations to ensure schema is up-to-date."""

    resolved_path = resolve_cache_db_path(db_path)
    asyncio.run(apply_migrations(resolved_path))
    typer.secho(f"Migrations applied to {resolved_path}", fg=typer.colors.GREEN)


app.command("migrate")(migrate)
