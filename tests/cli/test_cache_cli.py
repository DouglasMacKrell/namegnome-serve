"""CLI tests for cache management commands."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from namegnome_serve.cli.cache import app

runner = CliRunner()


def test_cache_migrate_creates_database(tmp_path: Path) -> None:
    db_path = tmp_path / "cache" / "custom.db"
    result = runner.invoke(app, ["--db-path", str(db_path)])

    assert result.exit_code == 0
    assert "Migrations applied" in result.stdout
    assert db_path.exists()
