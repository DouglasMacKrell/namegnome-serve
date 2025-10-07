"""Helpers for resolving cache database paths."""

from __future__ import annotations

import os
from pathlib import Path

__all__ = ["resolve_cache_db_path"]


def resolve_cache_db_path(db_path: str | Path | None = None) -> str:
    """Resolve the on-disk path for the cache database.

    Args:
        db_path: Optional explicit path or `\":memory:\"` for in-memory usage.

    Returns:
        Absolute string path suitable for sqlite3.
    """

    chosen: str | Path | None = db_path
    env_path = os.getenv("NAMEGNOME_CACHE_PATH")
    if chosen is None and env_path:
        chosen = env_path
    if chosen is None:
        chosen = Path(".cache") / "namegnome.db"

    if str(chosen) == ":memory:":
        return ":memory:"

    resolved = Path(chosen).expanduser()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    return str(resolved)
