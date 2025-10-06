"""Tests for AniDB provider (anime fallback).

AniDB specifics:
- Requires API key (client registration required)
- VERY STRICT rate limits: 1 request per 2 seconds
- XML-based API: http://api.anidb.net:9001/httpapi
- Search by name: ?request=anime&aid={anime_id}
- Client name and version required in User-Agent
"""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_anidb_requires_api_key():
    """Test that AniDB requires API key from environment."""
    import os

    from namegnome_serve.metadata.providers.anidb import AniDBProvider

    # Should raise if API key not in environment
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match="API key.*environment"):
            AniDBProvider()


@pytest.mark.asyncio
async def test_anidb_enforces_strict_rate_limit():
    """Test that AniDB enforces VERY strict rate limit."""
    import os

    from namegnome_serve.metadata.providers.anidb import AniDBProvider

    with patch.dict(os.environ, {"ANIDB_API_KEY": "test_key"}):
        provider = AniDBProvider()
        # STRICT: 1 request per 2 seconds = 30 per minute
        assert provider.rate_limit_per_minute == 30


@pytest.mark.asyncio
async def test_anidb_includes_client_header():
    """Test that AniDB includes required client header."""
    import os

    from namegnome_serve.metadata.providers.anidb import AniDBProvider

    with patch.dict(os.environ, {"ANIDB_API_KEY": "test_key"}):
        provider = AniDBProvider()

        # Should include client name/version
        assert provider.CLIENT_NAME == "namegnomeserve"
        assert provider.CLIENT_VERSION == "1"


@pytest.mark.asyncio
async def test_anidb_get_anime_details():
    """Test fetching anime details by AniDB ID."""
    import os

    from namegnome_serve.metadata.providers.anidb import AniDBProvider

    with patch.dict(os.environ, {"ANIDB_API_KEY": "test_key"}):
        provider = AniDBProvider()

        # Mock XML response
        mock_response = AsyncMock()
        mock_response.text = """<?xml version="1.0" encoding="UTF-8"?>
<anime id="123" restricted="false">
    <type>TV Series</type>
    <episodecount>24</episodecount>
    <startdate>2016-10-01</startdate>
    <enddate>2017-03-31</enddate>
    <titles>
        <title type="official" xml:lang="en">My Hero Academia</title>
        <title type="main">Boku no Hero Academia</title>
    </titles>
    <ratings>
        <permanent count="1000">8.50</permanent>
    </ratings>
</anime>"""
        mock_response.raise_for_status = AsyncMock()

        with patch.object(provider._client, "get", return_value=mock_response):
            details = await provider.get_anime_details("123")

            assert details is not None
            assert "title" in details
            assert "episode_count" in details
            assert "rating_normalized" in details


@pytest.mark.asyncio
async def test_anidb_normalizes_rating():
    """Test that AniDB normalizes ratings (0-10) to 0-1 scale."""
    import os

    from namegnome_serve.metadata.providers.anidb import AniDBProvider

    with patch.dict(os.environ, {"ANIDB_API_KEY": "test_key"}):
        provider = AniDBProvider()

        # Test various ratings
        assert provider._normalize_rating("8.50") == 0.85
        assert provider._normalize_rating("10.0") == 1.0
        assert provider._normalize_rating("0.0") == 0.0
        assert provider._normalize_rating("") == 0.0
        assert provider._normalize_rating(None) == 0.0


@pytest.mark.asyncio
async def test_anidb_handles_not_found():
    """Test that AniDB returns None for missing anime."""
    import os

    from namegnome_serve.metadata.providers.anidb import AniDBProvider

    with patch.dict(os.environ, {"ANIDB_API_KEY": "test_key"}):
        provider = AniDBProvider()

        # Mock 404 response
        mock_response = AsyncMock()
        mock_response.status_code = 404

        import httpx

        with patch.object(
            provider._client,
            "get",
            side_effect=httpx.HTTPStatusError(
                "Not Found", request=AsyncMock(), response=mock_response
            ),
        ):
            details = await provider.get_anime_details("0")
            assert details is None


@pytest.mark.asyncio
async def test_anidb_search_not_implemented():
    """Test that AniDB search raises NotImplementedError."""
    import os

    from namegnome_serve.metadata.providers.anidb import AniDBProvider

    with patch.dict(os.environ, {"ANIDB_API_KEY": "test_key"}):
        provider = AniDBProvider()

        # AniDB API doesn't support text search (requires anime ID)
        with pytest.raises(NotImplementedError):
            await provider.search("test")
