"""Tests for FanartTV provider (artwork fallback).

FanartTV specifics:
- Requires API key (free tier available)
- Provides high-quality artwork: posters, logos, backgrounds
- Movies: https://webservice.fanart.tv/v3/movies/{tmdb_id}
- TV: https://webservice.fanart.tv/v3/tv/{tvdb_id}
- Rate limit: Not specified, use conservative 40 req/min
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
async def test_fanarttv_requires_api_key():
    """Test that FanartTV requires API key from environment."""
    import os

    from namegnome_serve.metadata.providers.fanarttv import FanartTVProvider

    # Should raise if API key not in environment
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match="API key.*environment"):
            FanartTVProvider()


@pytest.mark.asyncio
async def test_fanarttv_enforces_rate_limit():
    """Test that FanartTV enforces conservative rate limit."""
    import os

    from namegnome_serve.metadata.providers.fanarttv import FanartTVProvider

    with patch.dict(os.environ, {"FANARTTV_API_KEY": "test_key"}):
        provider = FanartTVProvider()
        # Conservative rate limit
        assert provider.rate_limit_per_minute == 40


@pytest.mark.asyncio
async def test_fanarttv_get_movie_artwork():
    """Test fetching movie artwork by TMDB ID."""
    import os

    from namegnome_serve.metadata.providers.fanarttv import FanartTVProvider

    with patch.dict(os.environ, {"FANARTTV_API_KEY": "test_key"}):
        provider = FanartTVProvider()

        # Mock movie artwork response
        mock_response = AsyncMock()
        mock_response.json = Mock(
            return_value={
                "name": "Moana",
                "tmdb_id": "277834",
                "movieposter": [
                    {"url": "https://example.com/poster.jpg", "lang": "en"}
                ],
                "movielogo": [{"url": "https://example.com/logo.png", "lang": "en"}],
                "moviebackground": [
                    {"url": "https://example.com/bg.jpg", "lang": "en"}
                ],
            }
        )
        mock_response.raise_for_status = Mock()

        with patch.object(provider._client, "get", return_value=mock_response):
            artwork = await provider.get_movie_artwork("277834")

            assert artwork is not None
            assert "movieposter" in artwork
            assert "movielogo" in artwork
            assert "moviebackground" in artwork


@pytest.mark.asyncio
async def test_fanarttv_get_tv_artwork():
    """Test fetching TV artwork by TVDB ID."""
    import os

    from namegnome_serve.metadata.providers.fanarttv import FanartTVProvider

    with patch.dict(os.environ, {"FANARTTV_API_KEY": "test_key"}):
        provider = FanartTVProvider()

        # Mock TV artwork response
        mock_response = AsyncMock()
        mock_response.json = Mock(
            return_value={
                "name": "Firebuds",
                "thetvdb_id": "414000",
                "tvposter": [{"url": "https://example.com/poster.jpg", "lang": "en"}],
                "clearlogo": [{"url": "https://example.com/logo.png", "lang": "en"}],
                "showbackground": [{"url": "https://example.com/bg.jpg", "lang": "en"}],
            }
        )
        mock_response.raise_for_status = Mock()

        with patch.object(provider._client, "get", return_value=mock_response):
            artwork = await provider.get_tv_artwork("414000")

            assert artwork is not None
            assert "tvposter" in artwork
            assert "clearlogo" in artwork
            assert "showbackground" in artwork


@pytest.mark.asyncio
async def test_fanarttv_filters_english_artwork():
    """Test that FanartTV prefers English artwork."""
    import os

    from namegnome_serve.metadata.providers.fanarttv import FanartTVProvider

    with patch.dict(os.environ, {"FANARTTV_API_KEY": "test_key"}):
        provider = FanartTVProvider()

        artwork = [
            {"url": "https://example.com/de.jpg", "lang": "de"},
            {"url": "https://example.com/en.jpg", "lang": "en"},
            {"url": "https://example.com/fr.jpg", "lang": "fr"},
        ]

        best = provider._filter_english(artwork)
        assert best is not None
        assert best["lang"] == "en"
        assert "en.jpg" in best["url"]


@pytest.mark.asyncio
async def test_fanarttv_handles_not_found():
    """Test that FanartTV returns None for missing artwork."""
    import os

    from namegnome_serve.metadata.providers.fanarttv import FanartTVProvider

    with patch.dict(os.environ, {"FANARTTV_API_KEY": "test_key"}):
        provider = FanartTVProvider()

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
            artwork = await provider.get_movie_artwork("0")
            assert artwork is None


@pytest.mark.asyncio
async def test_fanarttv_search_and_get_details():
    """Test that FanartTV implements BaseProvider interface."""
    import os

    from namegnome_serve.metadata.providers.fanarttv import FanartTVProvider

    with patch.dict(os.environ, {"FANARTTV_API_KEY": "test_key"}):
        provider = FanartTVProvider()

        # search() should raise NotImplementedError (artwork provider)
        with pytest.raises(NotImplementedError):
            await provider.search("test")

        # get_details() should work with movie_id
        mock_response = AsyncMock()
        mock_response.json = Mock(return_value={"name": "Test"})
        mock_response.raise_for_status = Mock()

        with patch.object(provider._client, "get", return_value=mock_response):
            details = await provider.get_details("123", media_type="movie")
            assert details is not None
