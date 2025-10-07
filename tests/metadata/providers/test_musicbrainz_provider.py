"""Tests for MusicBrainz provider with strict rate limiting.

MusicBrainz specifics:
- NO API key required (free, open data)
- STRICT rate limit: 1 request per second
- MUST include User-Agent header
- Search: /ws/2/recording?query=...
- Release groups for albums
"""

from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest


@pytest.mark.asyncio
async def test_musicbrainz_requires_user_agent():
    """Test that MusicBrainz includes required User-Agent header."""
    from namegnome_serve.metadata.providers.musicbrainz import MusicBrainzProvider

    provider = MusicBrainzProvider()

    headers = provider._get_headers()

    assert "User-Agent" in headers
    assert "namegnome" in headers["User-Agent"].lower()
    assert headers["Accept"] == "application/json"


@pytest.mark.asyncio
async def test_musicbrainz_enforces_rate_limit():
    """Test that MusicBrainz enforces 1 req/sec rate limit."""
    from namegnome_serve.metadata.providers.musicbrainz import MusicBrainzProvider

    provider = MusicBrainzProvider()

    # Rate limit should be 50 per minute (1 per ~1.2 seconds)
    assert provider.rate_limit_per_minute == 50


@pytest.mark.asyncio
async def test_musicbrainz_search_recording():
    """Test searching for a music recording."""
    from namegnome_serve.metadata.providers.musicbrainz import MusicBrainzProvider

    provider = MusicBrainzProvider()

    # Mock search response
    mock_response = AsyncMock()
    # httpx .json() is synchronous, not async - use Mock, not AsyncMock
    mock_response.json = Mock(
        return_value={
            "recordings": [
                {
                    "id": "abc-123",
                    "title": "We Know the Way",
                    "artist-credit": [{"artist": {"name": "Lin-Manuel Miranda"}}],
                    "length": 180000,  # milliseconds
                }
            ]
        }
    )
    mock_response.raise_for_status = Mock()

    with patch.object(provider._client, "get", return_value=mock_response) as mock_get:
        results = await provider.search_recording("We Know the Way")

        assert len(results) == 1
        assert results[0]["id"] == "abc-123"
        assert results[0]["title"] == "We Know the Way"

        # Verify API call
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert "/ws/2/recording" in str(call_args[0][0])
        assert call_args[1]["params"]["query"] == "We Know the Way"
        assert call_args[1]["params"]["fmt"] == "json"


@pytest.mark.asyncio
async def test_musicbrainz_search_artist():
    """Test searching for an artist."""
    from namegnome_serve.metadata.providers.musicbrainz import MusicBrainzProvider

    provider = MusicBrainzProvider()

    # Mock artist search response
    mock_response = AsyncMock()
    # httpx .json() is synchronous, not async - use Mock, not AsyncMock
    mock_response.json = Mock(
        return_value={
            "artists": [
                {
                    "id": "artist-456",
                    "name": "Lin-Manuel Miranda",
                    "type": "Person",
                    "country": "US",
                }
            ]
        }
    )
    mock_response.raise_for_status = Mock()

    with patch.object(provider._client, "get", return_value=mock_response):
        results = await provider.search_artist("Lin-Manuel Miranda")

        assert len(results) == 1
        assert results[0]["id"] == "artist-456"
        assert results[0]["name"] == "Lin-Manuel Miranda"


@pytest.mark.asyncio
async def test_musicbrainz_get_release_group():
    """Test fetching release group (album) details."""
    from namegnome_serve.metadata.providers.musicbrainz import MusicBrainzProvider

    provider = MusicBrainzProvider()

    # Mock release group response
    mock_response = AsyncMock()
    # httpx .json() is synchronous, not async - use Mock, not AsyncMock
    mock_response.json = Mock(
        return_value={
            "id": "rg-789",
            "title": "Moana Soundtrack",
            "first-release-date": "2016-11-18",
            "primary-type": "Album",
        }
    )
    mock_response.raise_for_status = Mock()

    with patch.object(provider._client, "get", return_value=mock_response):
        details = await provider.get_release_group("rg-789")

        assert details is not None
        assert details["id"] == "rg-789"
        assert details["title"] == "Moana Soundtrack"
        assert details["first-release-date"] == "2016-11-18"


@pytest.mark.asyncio
async def test_musicbrainz_formats_recording_data():
    """Test that recording data is formatted correctly."""
    from namegnome_serve.metadata.providers.musicbrainz import MusicBrainzProvider

    provider = MusicBrainzProvider()

    raw_recording = {
        "id": "rec-123",
        "title": "How Far I'll Go",
        "length": 165000,  # 2:45 in milliseconds
        "artist-credit": [{"artist": {"name": "Auli'i Cravalho"}}],
    }

    formatted = provider._format_recording(raw_recording)

    assert formatted["recording_id"] == "rec-123"
    assert formatted["title"] == "How Far I'll Go"
    assert formatted["duration_ms"] == 165000
    assert formatted["artist"] == "Auli'i Cravalho"


@pytest.mark.asyncio
async def test_musicbrainz_handles_404():
    """Test that 404 returns None gracefully."""
    from namegnome_serve.metadata.providers.musicbrainz import MusicBrainzProvider

    provider = MusicBrainzProvider()

    with patch.object(
        provider._client,
        "get",
        side_effect=httpx.HTTPStatusError(
            "Not Found", request=AsyncMock(), response=AsyncMock(status_code=404)
        ),
    ):
        details = await provider.get_release_group("nonexistent")
        assert details is None


@pytest.mark.asyncio
async def test_musicbrainz_handles_503_rate_limit():
    """Test that 503 (rate limit) is handled with retry."""
    from namegnome_serve.metadata.providers.musicbrainz import MusicBrainzProvider

    provider = MusicBrainzProvider()

    # Mock 503 error response
    mock_503_response = AsyncMock()
    mock_503_response.status_code = 503

    # Mock successful retry
    mock_success = AsyncMock()
    # httpx .json() is synchronous, not async - use Mock, not AsyncMock
    mock_success.json = Mock(return_value={"artists": []})
    mock_success.raise_for_status = Mock()

    call_count = 0

    async def mock_get(*args: Any, **kwargs: Any) -> AsyncMock:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise httpx.HTTPStatusError(
                "Service Unavailable",
                request=AsyncMock(),
                response=mock_503_response,
            )
        return mock_success

    with patch.object(provider._client, "get", side_effect=mock_get):
        # Should retry and succeed
        results = await provider.search_artist("test")
        assert results == []
        assert call_count == 2  # Initial + 1 retry
