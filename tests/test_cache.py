"""Tests for SQLite cache layer with TTL support.

The cache layer provides:
- Persistent storage of API responses
- TTL (Time To Live) expiration
- Thread-safe operations
- Cache stats (hits, misses)
- Key generation based on provider + params
"""

import time
from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_cache_stores_and_retrieves_data():
    """Test basic cache storage and retrieval."""
    from namegnome_serve.cache.provider_cache import ProviderCache

    async with ProviderCache(":memory:") as cache:  # In-memory for testing
        # Store data
        await cache.set("test_provider", "test_key", {"result": "test_data"})

        # Retrieve data
        result = await cache.get("test_provider", "test_key")
        assert result is not None
        assert result["result"] == "test_data"


@pytest.mark.asyncio
async def test_cache_respects_ttl():
    """Test that cache entries expire after TTL."""
    from namegnome_serve.cache.provider_cache import ProviderCache

    async with ProviderCache(":memory:") as cache:
        # Store with 1 second TTL
        await cache.set("test_provider", "test_key", {"data": "expires"}, ttl=1)

        # Should be available immediately
        result = await cache.get("test_provider", "test_key")
        assert result is not None

        # Wait for expiration
        time.sleep(1.1)

        # Should be expired
        result = await cache.get("test_provider", "test_key")
        assert result is None


@pytest.mark.asyncio
async def test_cache_returns_none_for_missing_key():
    """Test that cache returns None for missing keys."""
    from namegnome_serve.cache.provider_cache import ProviderCache

    async with ProviderCache(":memory:") as cache:
        result = await cache.get("test_provider", "nonexistent_key")
        assert result is None


@pytest.mark.asyncio
async def test_cache_generates_consistent_keys():
    """Test that cache key generation is consistent."""
    from namegnome_serve.cache.provider_cache import ProviderCache

    async with ProviderCache(":memory:") as cache:
        # Same params should generate same key
        key1 = cache._generate_key("tmdb", {"query": "moana", "year": 2016})
        key2 = cache._generate_key("tmdb", {"query": "moana", "year": 2016})
        assert key1 == key2

        # Different params should generate different keys
        key3 = cache._generate_key("tmdb", {"query": "frozen", "year": 2013})
        assert key1 != key3

        # Different providers should generate different keys
        key4 = cache._generate_key("tvdb", {"query": "moana", "year": 2016})
        assert key1 != key4


@pytest.mark.asyncio
async def test_cache_handles_complex_data():
    """Test that cache can store/retrieve complex data structures."""
    from namegnome_serve.cache.provider_cache import ProviderCache

    async with ProviderCache(":memory:") as cache:
        complex_data = {
            "title": "Moana",
            "year": 2016,
            "ratings": [7.6, 8.0, 7.5],
            "metadata": {"director": "Ron Clements", "runtime": 107},
            "cast": ["Auli'i Cravalho", "Dwayne Johnson"],
        }

        await cache.set("test_provider", "complex_key", complex_data)
        result = await cache.get("test_provider", "complex_key")

        assert result == complex_data
        assert result["ratings"] == [7.6, 8.0, 7.5]
        assert result["metadata"]["director"] == "Ron Clements"


@pytest.mark.asyncio
async def test_cache_tracks_hits_and_misses():
    """Test that cache tracks hit/miss statistics."""
    from namegnome_serve.cache.provider_cache import ProviderCache

    async with ProviderCache(":memory:") as cache:
        # Initial stats
        stats = cache.get_stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 0

        # Store and retrieve (hit)
        await cache.set("test_provider", "key1", {"data": "test"})
        await cache.get("test_provider", "key1")

        stats = cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 0

        # Try to get nonexistent key (miss)
        await cache.get("test_provider", "nonexistent")

        stats = cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1


@pytest.mark.asyncio
async def test_cache_clear_removes_all_entries():
    """Test that cache.clear() removes all entries."""
    from namegnome_serve.cache.provider_cache import ProviderCache

    async with ProviderCache(":memory:") as cache:
        # Store multiple entries
        await cache.set("provider1", "key1", {"data": "test1"})
        await cache.set("provider2", "key2", {"data": "test2"})
        await cache.set("provider3", "key3", {"data": "test3"})

        # Verify they exist
        assert await cache.get("provider1", "key1") is not None
        assert await cache.get("provider2", "key2") is not None

        # Clear cache
        await cache.clear()

        # Verify all gone
        assert await cache.get("provider1", "key1") is None
        assert await cache.get("provider2", "key2") is None
        assert await cache.get("provider3", "key3") is None


@pytest.mark.asyncio
async def test_cache_clears_expired_entries():
    """Test that cache automatically clears expired entries."""
    from namegnome_serve.cache.provider_cache import ProviderCache

    async with ProviderCache(":memory:") as cache:
        # Store entries with different TTLs
        await cache.set("provider", "expires_fast", {"data": "fast"}, ttl=1)
        await cache.set("provider", "expires_slow", {"data": "slow"}, ttl=10)

        # Wait for first to expire
        time.sleep(1.1)

        # Trigger cleanup
        await cache.cleanup_expired()

        # Fast should be gone, slow should remain
        assert await cache.get("provider", "expires_fast") is None
        assert await cache.get("provider", "expires_slow") is not None


@pytest.mark.asyncio
async def test_cache_persists_to_file():
    """Test that cache persists data to file."""
    import tempfile

    from namegnome_serve.cache.provider_cache import ProviderCache

    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
        db_path = tmp.name

    try:
        # Create cache and store data
        async with ProviderCache(db_path) as cache1:
            await cache1.set("provider", "key", {"data": "persisted"})

        # Open new cache instance with same file
        async with ProviderCache(db_path) as cache2:
            result = await cache2.get("provider", "key")

        assert result is not None
        assert result["data"] == "persisted"

    finally:
        # Cleanup
        Path(db_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_cache_default_ttl():
    """Test that cache uses default TTL when not specified."""
    from namegnome_serve.cache.provider_cache import ProviderCache

    async with ProviderCache(":memory:", default_ttl=3600) as cache:  # 1 hour
        # Store without explicit TTL
        await cache.set("provider", "key", {"data": "test"})

        # Should still be available (default TTL not expired)
        result = await cache.get("provider", "key")
        assert result is not None
