"""SQLite-based cache for provider responses with TTL support.

This cache layer:
- Stores API responses to reduce redundant requests
- Respects TTL (Time To Live) for automatic expiration
- Provides thread-safe async operations
- Tracks cache statistics (hits, misses)
- Persists to disk for durability across restarts
"""

import hashlib
import json
import time
from typing import Any

import aiosqlite


class ProviderCache:
    """Async SQLite cache for provider API responses."""

    def __init__(self, db_path: str = ".cache/providers.db", default_ttl: int = 3600):
        """Initialize the provider cache.

        Args:
            db_path: Path to SQLite database file (":memory:" for in-memory)
            default_ttl: Default TTL in seconds (default: 1 hour)
        """
        self.db_path = db_path
        self.default_ttl = default_ttl
        self._db: aiosqlite.Connection | None = None
        self._hits = 0
        self._misses = 0

    async def _get_connection(self) -> aiosqlite.Connection:
        """Get or create database connection."""
        if self._db is None:
            self._db = await aiosqlite.connect(self.db_path)
            await self._create_tables()
        return self._db

    async def _create_tables(self) -> None:
        """Create cache tables if they don't exist."""
        if self._db is None:
            return

        await self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS cache (
                cache_key TEXT PRIMARY KEY,
                provider TEXT NOT NULL,
                data TEXT NOT NULL,
                expires_at REAL NOT NULL,
                created_at REAL NOT NULL
            )
            """
        )
        await self._db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_provider ON cache(provider)
            """
        )
        await self._db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_expires ON cache(expires_at)
            """
        )
        await self._db.commit()

    def _generate_key(self, provider: str, params: dict[str, Any]) -> str:
        """Generate consistent cache key from provider and params.

        Args:
            provider: Provider name
            params: Query parameters (will be sorted for consistency)

        Returns:
            Cache key (hex digest)
        """
        # Sort params for consistency
        sorted_params = json.dumps(params, sort_keys=True)
        key_string = f"{provider}:{sorted_params}"
        return hashlib.sha256(key_string.encode()).hexdigest()

    async def get(self, provider: str, key: str) -> dict[str, Any] | None:
        """Get cached data if available and not expired.

        Args:
            provider: Provider name
            key: Cache key (or use _generate_key for params)

        Returns:
            Cached data dict, or None if not found/expired
        """
        db = await self._get_connection()
        current_time = time.time()

        cursor = await db.execute(
            """
            SELECT data, expires_at FROM cache
            WHERE cache_key = ? AND provider = ? AND expires_at > ?
            """,
            (key, provider, current_time),
        )
        row = await cursor.fetchone()

        if row is None:
            self._misses += 1
            return None

        self._hits += 1
        data_json, _ = row
        result: dict[str, Any] = json.loads(data_json)
        return result

    async def set(
        self,
        provider: str,
        key: str,
        data: dict[str, Any],
        ttl: int | None = None,
    ) -> None:
        """Store data in cache with TTL.

        Args:
            provider: Provider name
            key: Cache key
            data: Data to cache (must be JSON-serializable)
            ttl: Time to live in seconds (None = use default_ttl)
        """
        db = await self._get_connection()
        ttl = ttl if ttl is not None else self.default_ttl

        current_time = time.time()
        expires_at = current_time + ttl
        data_json = json.dumps(data)

        await db.execute(
            """
            INSERT OR REPLACE INTO cache
            (cache_key, provider, data, expires_at, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (key, provider, data_json, expires_at, current_time),
        )
        await db.commit()

    async def clear(self) -> None:
        """Clear all cache entries."""
        db = await self._get_connection()
        await db.execute("DELETE FROM cache")
        await db.commit()

    async def cleanup_expired(self) -> None:
        """Remove expired cache entries."""
        db = await self._get_connection()
        current_time = time.time()
        await db.execute("DELETE FROM cache WHERE expires_at <= ?", (current_time,))
        await db.commit()

    def get_stats(self) -> dict[str, int | float]:
        """Get cache statistics.

        Returns:
            Dict with hits, misses, total (int), and hit_rate (float)
        """
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

    async def __aenter__(self) -> "ProviderCache":
        """Async context manager entry."""
        await self._get_connection()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()
