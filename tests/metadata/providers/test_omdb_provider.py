"""Tests for OMDb provider (movie fallback).

OMDb specifics:
- Requires API key (free tier: 1,000 req/day)
- Search: http://www.omdbapi.com/?s={query}&apikey={key}
- Details: http://www.omdbapi.com/?i={imdb_id}&apikey={key}
- Rate limit: 1,000 req/day on free tier
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.mark.asyncio
async def test_omdb_requires_api_key():
    """Test that OMDb requires API key from environment."""
    import os

    from namegnome_serve.metadata.providers.omdb import OMDbProvider

    # Should raise if API key not in environment
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match="API key.*environment"):
            OMDbProvider()


@pytest.mark.asyncio
async def test_omdb_enforces_rate_limit():
    """Test that OMDb enforces conservative rate limit."""
    import os

    from namegnome_serve.metadata.providers.omdb import OMDbProvider

    with patch.dict(os.environ, {"OMDB_API_KEY": "test_key"}):
        provider = OMDbProvider()
        # Conservative: 900 per day = ~37 per hour = ~1 per 2 minutes
        assert provider.rate_limit_per_minute <= 1


@pytest.mark.asyncio
async def test_omdb_search_movie():
    """Test searching for movies by title."""
    import os

    from namegnome_serve.metadata.providers.omdb import OMDbProvider

    with patch.dict(os.environ, {"OMDB_API_KEY": "test_key"}):
        provider = OMDbProvider()

        # Mock search response
        mock_response = AsyncMock()
        mock_response.json = Mock(
            return_value={
                "Search": [
                    {
                        "Title": "Moana",
                        "Year": "2016",
                        "imdbID": "tt3521164",
                        "Type": "movie",
                        "Poster": "https://example.com/poster.jpg",
                    }
                ],
                "totalResults": "1",
                "Response": "True",
            }
        )
        mock_response.raise_for_status = Mock()

        with patch.object(provider._client, "get", return_value=mock_response):
            results = await provider.search_movie("Moana", year=2016)

        assert len(results) == 1
        assert results[0]["Title"] == "Moana"
        assert results[0]["imdbID"] == "tt3521164"


@pytest.mark.asyncio
async def test_omdb_search_series():
    """Test searching for TV series by title."""
    import os

    from namegnome_serve.metadata.providers.omdb import OMDbProvider

    with patch.dict(os.environ, {"OMDB_API_KEY": "test_key"}):
        provider = OMDbProvider()

        mock_response = Mock()
        mock_response.json.return_value = {
            "Search": [
                {
                    "Title": "Firebuds",
                    "Year": "2022",
                    "imdbID": "tt12345",
                    "Type": "series",
                }
            ],
            "totalResults": "1",
            "Response": "True",
        }
        mock_response.raise_for_status.return_value = None

        provider._client.get = AsyncMock(return_value=mock_response)

        results = await provider.search_series("Firebuds")

        assert len(results) == 1
        assert results[0]["Title"] == "Firebuds"
        assert results[0]["imdbID"] == "tt12345"


@pytest.mark.asyncio
async def test_omdb_get_movie_details():
    """Test fetching movie details by IMDb ID."""
    import os

    from namegnome_serve.metadata.providers.omdb import OMDbProvider

    with patch.dict(os.environ, {"OMDB_API_KEY": "test_key"}):
        provider = OMDbProvider()

        # Mock details response
        mock_response = AsyncMock()
        mock_response.json = Mock(
            return_value={
                "Title": "Moana",
                "Year": "2016",
                "imdbID": "tt3521164",
                "Type": "movie",
                "Plot": "In Ancient Polynesia...",
                "imdbRating": "7.6",
                "Poster": "https://example.com/poster.jpg",
                "Response": "True",
            }
        )
        mock_response.raise_for_status = Mock()

        with patch.object(provider._client, "get", return_value=mock_response):
            details = await provider.get_movie_details("tt3521164")

            assert details is not None
        assert details["Title"] == "Moana"
        assert details["imdbRating"] == "7.6"
        assert details["imdb_rating_normalized"] == 0.76  # 7.6/10


@pytest.mark.asyncio
async def test_omdb_get_episode_details():
    """Test fetching a specific TV episode."""
    import os

    from namegnome_serve.metadata.providers.omdb import OMDbProvider

    with patch.dict(os.environ, {"OMDB_API_KEY": "test_key"}):
        provider = OMDbProvider()

        mock_response = Mock()
        mock_response.json.return_value = {
            "Title": "Pilot",
            "Season": "1",
            "Episode": "1",
            "SeriesID": "tt12345",
            "Response": "True",
        }
        mock_response.raise_for_status.return_value = None

        provider._client.get = AsyncMock(return_value=mock_response)

        details = await provider.get_episode("tt12345", 1, 1)

        assert details is not None
        assert details["Title"] == "Pilot"
        assert details["Season"] == "1"


@pytest.mark.asyncio
async def test_omdb_handles_not_found():
    """Test that OMDb returns None for movies not found."""
    import os

    from namegnome_serve.metadata.providers.omdb import OMDbProvider

    with patch.dict(os.environ, {"OMDB_API_KEY": "test_key"}):
        provider = OMDbProvider()

        # Mock not found response (OMDb returns Response: "False")
        mock_response = AsyncMock()
        mock_response.json = Mock(
            return_value={"Response": "False", "Error": "Movie not found!"}
        )
        mock_response.raise_for_status = Mock()

        with patch.object(provider._client, "get", return_value=mock_response):
            details = await provider.get_movie_details("tt0000000")
            assert details is None


@pytest.mark.asyncio
async def test_omdb_handles_search_no_results():
    """Test that OMDb returns empty list for no search results."""
    import os

    from namegnome_serve.metadata.providers.omdb import OMDbProvider

    with patch.dict(os.environ, {"OMDB_API_KEY": "test_key"}):
        provider = OMDbProvider()

        # Mock no results response
        mock_response = AsyncMock()
        mock_response.json = Mock(
            return_value={"Response": "False", "Error": "Movie not found!"}
        )
        mock_response.raise_for_status = Mock()

        with patch.object(provider._client, "get", return_value=mock_response):
            results = await provider.search_movie("NonexistentMovie12345")
            assert results == []


@pytest.mark.asyncio
async def test_omdb_normalizes_rating():
    """Test that OMDb normalizes IMDb ratings to 0-1 scale."""
    import os

    from namegnome_serve.metadata.providers.omdb import OMDbProvider

    with patch.dict(os.environ, {"OMDB_API_KEY": "test_key"}):
        provider = OMDbProvider()

        # Test various ratings
        assert provider._normalize_rating("8.5") == 0.85
        assert provider._normalize_rating("10.0") == 1.0
        assert provider._normalize_rating("0.0") == 0.0
        assert provider._normalize_rating("N/A") == 0.0
        assert provider._normalize_rating(None) == 0.0


@pytest.mark.asyncio
async def test_omdb_base_provider_interface():
    """Test that OMDb implements BaseProvider interface correctly."""
    import os

    from namegnome_serve.metadata.providers.omdb import OMDbProvider

    with patch.dict(os.environ, {"OMDB_API_KEY": "test_key"}):
        provider = OMDbProvider()

        # Should have search() and get_details() methods
        assert hasattr(provider, "search")
        assert hasattr(provider, "get_details")
