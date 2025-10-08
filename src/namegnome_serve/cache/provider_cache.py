"""SQLite-backed provider cache with schema migrations."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, cast

import aiosqlite

from namegnome_serve.cache.migrations import ensure_connection_migrated
from namegnome_serve.cache.paths import resolve_cache_db_path


class ProviderCache:
    """Async SQLite cache for provider API responses."""

    def __init__(
        self,
        db_path: str | Path | None = None,
        default_ttl: int = 3600,
    ) -> None:
        """Initialize the provider cache.

        Args:
            db_path: Path to SQLite database file (\":memory:\" for in-memory). When
                omitted, resolves to `NAMEGNOME_CACHE_PATH` or `./.cache/namegnome.db`.
            default_ttl: Default TTL in seconds (default: 1 hour).
        """

        self.default_ttl = default_ttl
        self._db_path = resolve_cache_db_path(db_path)
        self._db: aiosqlite.Connection | None = None
        self._hits = 0
        self._misses = 0

    async def _get_connection(self) -> aiosqlite.Connection:
        """Get or create the cache database connection."""

        if self._db is None:
            self._db = await aiosqlite.connect(self._db_path)
            await ensure_connection_migrated(self._db)
        return self._db

    def _generate_key(self, provider: str, params: dict[str, Any]) -> str:
        """Generate consistent cache key from provider and params."""

        sorted_params = json.dumps(params, sort_keys=True)
        key_string = f"{provider}:{sorted_params}"
        return hashlib.sha256(key_string.encode()).hexdigest()

    async def get(self, provider: str, key: str) -> dict[str, Any] | None:
        """Get cached data if available and not expired."""

        db = await self._get_connection()
        current_time = time.time()

        async with db.execute(
            """
            SELECT data FROM cache_entries
            WHERE cache_key = ? AND provider = ? AND expires_at > ?
            """,
            (key, provider, current_time),
        ) as cursor:
            row = await cursor.fetchone()

        if row is None:
            self._misses += 1
            return None

        self._hits += 1
        data_json = row[0]
        return cast(dict[str, Any], json.loads(data_json))

    async def set(
        self,
        provider: str,
        key: str,
        data: dict[str, Any],
        ttl: int | None = None,
    ) -> None:
        """Store data in cache with TTL."""

        db = await self._get_connection()
        ttl_seconds = ttl if ttl is not None else self.default_ttl

        current_time = time.time()
        expires_at = current_time + ttl_seconds
        data_json = json.dumps(data)

        await db.execute(
            """
            INSERT OR REPLACE INTO cache_entries
            (cache_key, provider, data, expires_at, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (key, provider, data_json, expires_at, current_time),
        )
        await db.commit()

    async def clear(self) -> None:
        """Clear all cache entries."""

        db = await self._get_connection()
        await db.execute("DELETE FROM cache_entries")
        await db.commit()

    async def cleanup_expired(self) -> None:
        """Remove expired cache entries."""

        db = await self._get_connection()
        current_time = time.time()
        await db.execute(
            "DELETE FROM cache_entries WHERE expires_at <= ?", (current_time,)
        )
        await db.commit()

    def get_stats(self) -> dict[str, int | float]:
        """Get cache statistics."""

        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0.0

        return {
            "hits": self._hits,
            "misses": self._misses,
            "total": total,
            "hit_rate": round(hit_rate, 2),
        }

    async def close(self) -> None:
        """Close database connection."""

        if self._db is not None:
            await self._db.close()
            self._db = None

    async def __aenter__(self) -> ProviderCache:
        """Async context manager entry."""

        await self._get_connection()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""

        await self.close()
