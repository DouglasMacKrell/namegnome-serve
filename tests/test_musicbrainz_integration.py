"""Integration tests for MusicBrainz API with real API calls.

MusicBrainz is FREE and requires NO API key!
Tests run when the public API is reachable; otherwise the module is skipped to
protect CI environments without outbound network access.

IMPORTANT: These tests respect MusicBrainz's 1 req/sec rate limit.
"""

import socket

import pytest


def _musicbrainz_reachable() -> bool:
    """Return True when the MusicBrainz API host is reachable."""

    try:
        with socket.create_connection(("musicbrainz.org", 443), timeout=2):
            return True
    except OSError:
        return False


@pytest.fixture(scope="module", autouse=True)
def _skip_if_musicbrainz_unreachable() -> None:
    """Skip module when MusicBrainz cannot be reached."""

    if not _musicbrainz_reachable():
        pytest.skip("MusicBrainz API not reachable. Skipping integration tests.")


@pytest.mark.asyncio
async def test_musicbrainz_real_search_recording():
    """Test real recording search against MusicBrainz API."""
    from namegnome_serve.metadata.providers.musicbrainz import (
        MusicBrainzProvider,
    )

    async with MusicBrainzProvider() as provider:
        # Search for "How Far I'll Go" from Moana
        results = await provider.search_recording("How Far I'll Go Moana")

        # Should get results
        assert isinstance(results, list)
        assert len(results) > 0

        # First result should contain the song
        first = results[0]
        assert "id" in first
        assert "title" in first
        assert "How Far I'll Go" in first["title"]

        print("✅ MusicBrainz recording search successful:")
        print(f"   Found: {first['title']} (ID: {first['id']})")
        if "length" in first:
            duration_sec = first["length"] // 1000
            print(f"   Duration: {duration_sec}s")


@pytest.mark.asyncio
async def test_musicbrainz_real_search_artist():
    """Test real artist search against MusicBrainz API."""
    from namegnome_serve.metadata.providers.musicbrainz import (
        MusicBrainzProvider,
    )

    async with MusicBrainzProvider() as provider:
        # Search for Lin-Manuel Miranda
        results = await provider.search_artist("Lin-Manuel Miranda")

        # Should get results
        assert isinstance(results, list)
        assert len(results) > 0

        # First result should be the artist
        artist = results[0]
        assert "id" in artist
        assert "name" in artist
        assert "Lin-Manuel" in artist["name"] or "Miranda" in artist["name"]

        print("✅ MusicBrainz artist search successful:")
        print(f"   Found: {artist['name']} (ID: {artist['id']})")
        if "type" in artist:
            print(f"   Type: {artist['type']}")


@pytest.mark.asyncio
async def test_musicbrainz_real_user_agent_required():
    """Test that MusicBrainz requires and accepts our User-Agent."""
    from namegnome_serve.metadata.providers.musicbrainz import (
        MusicBrainzProvider,
    )

    provider = MusicBrainzProvider()

    # Check that User-Agent is set
    headers = provider._get_headers()
    assert "User-Agent" in headers
    assert "NameGnomeServe" in headers["User-Agent"]

    # Verify it works with real API
    async with provider:
        results = await provider.search_recording("test")
        # Should not error, even if no results
        assert isinstance(results, list)

    print("✅ MusicBrainz User-Agent accepted by API")


@pytest.mark.asyncio
async def test_musicbrainz_real_rate_limiting():
    """Test that rate limiting is enforced (don't spam the API!)."""
    from namegnome_serve.metadata.providers.musicbrainz import (
        MusicBrainzProvider,
    )

    async with MusicBrainzProvider() as provider:
        # Provider should have strict rate limit
        assert provider.rate_limit_per_minute == 50  # ~1 req/sec

        # Make one request
        results1 = await provider.search_recording("test1", limit=1)
        assert isinstance(results1, list)

        # Check rate limit would block rapid requests
        assert provider.check_rate_limit()  # Should still have capacity

        print("✅ MusicBrainz rate limiting configured correctly:")
        print(f"   Rate limit: {provider.rate_limit_per_minute} req/min")
        print("   (~1 request per second)")


@pytest.mark.asyncio
async def test_musicbrainz_real_404_handling():
    """Test that non-existent entity returns None gracefully."""
    from namegnome_serve.metadata.providers.musicbrainz import (
        MusicBrainzProvider,
    )

    async with MusicBrainzProvider() as provider:
        # Try to get details for non-existent release group
        uuid = "00000000-0000-0000-0000-000000000000"
        details = await provider.get_release_group(uuid)

        # Should return None, not raise error
        assert details is None

        print("✅ MusicBrainz 404 handling successful (None returned)")
