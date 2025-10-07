"""Tests for TMDB provider with dual auth and English filtering.

Based on battle-tested patterns from mpv-scraper project.
"""

import os
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest


@pytest.mark.asyncio
async def test_tmdb_detects_bearer_token():
    """Test that TMDB auto-detects Bearer token vs API key."""
    from namegnome_serve.metadata.providers.tmdb import TMDBProvider

    # Bearer token format (starts with "eyJ" and is long)
    bearer_token = "eyJhbGciOiJIUzI1NiJ9." + "x" * 200
    with patch.dict(os.environ, {"TMDB_API_KEY": bearer_token}):
        provider = TMDBProvider()
        headers, params = provider._get_auth()

        assert "Authorization" in headers
        assert headers["Authorization"] == f"Bearer {bearer_token}"
        assert "api_key" not in params


@pytest.mark.asyncio
async def test_tmdb_uses_api_key_in_params():
    """Test that TMDB uses API key as query parameter when not Bearer token."""
    from namegnome_serve.metadata.providers.tmdb import TMDBProvider

    api_key = "regular_api_key_12345"
    with patch.dict(os.environ, {"TMDB_API_KEY": api_key}):
        provider = TMDBProvider()
        headers, params = provider._get_auth()

        assert "Authorization" not in headers
        assert params["api_key"] == api_key
        assert params["language"] == "en-US"


@pytest.mark.asyncio
async def test_tmdb_search_movie_with_year():
    """Test movie search with year filter."""
    from namegnome_serve.metadata.providers.tmdb import TMDBProvider

    with patch.dict(os.environ, {"TMDB_API_KEY": "test_key"}):
        provider = TMDBProvider()

    # Mock httpx response
    mock_response = Mock()
    mock_response.json = Mock(
        return_value={
            "results": [{"id": 12345, "title": "Moana", "release_date": "2016-11-23"}]
        }
    )
    mock_response.raise_for_status = Mock()

    with patch.object(provider._client, "get", return_value=mock_response) as mock_get:
        results = await provider.search_movie("Moana", year=2016)

        assert len(results) == 1
        assert results[0]["id"] == 12345
        assert results[0]["title"] == "Moana"

        # Verify API call
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert "search/movie" in str(call_args[0][0])
        assert call_args[1]["params"]["query"] == "Moana"
        assert call_args[1]["params"]["year"] == 2016


@pytest.mark.asyncio
async def test_tmdb_filters_english_posters():
    """Test English poster filtering (US > en > all)."""
    from namegnome_serve.metadata.providers.tmdb import TMDBProvider

    posters = [
        {"file_path": "/ru_poster.jpg", "iso_3166_1": "RU", "vote_average": 8.0},
        {"file_path": "/us_poster.jpg", "iso_3166_1": "US", "vote_average": 7.5},
        {"file_path": "/en_poster.jpg", "iso_639_1": "en", "vote_average": 9.0},
    ]

    with patch.dict(os.environ, {"TMDB_API_KEY": "test_key"}):
        provider = TMDBProvider()
        best = provider._filter_english_images(posters)

        # Should prefer US region even with lower vote
        assert best["iso_3166_1"] == "US"
        assert "us_poster.jpg" in best["file_path"]


@pytest.mark.asyncio
async def test_tmdb_get_movie_details():
    """Test fetching movie details with images."""
    from namegnome_serve.metadata.providers.tmdb import TMDBProvider

    with patch.dict(os.environ, {"TMDB_API_KEY": "test_key"}):
        provider = TMDBProvider()

        # Mock movie details response
        mock_details = Mock()
        mock_details.json = Mock(
            return_value={
                "id": 12345,
                "title": "Test Movie",
                "overview": "A test movie",
                "vote_average": 7.5,
                "genres": [{"name": "Action"}],
            }
        )
        mock_details.raise_for_status = Mock()

        # Mock images response
        mock_images = Mock()
        mock_images.json = Mock(
            return_value={
                "posters": [
                    {
                        "file_path": "/poster.jpg",
                        "iso_3166_1": "US",
                        "vote_average": 8.0,
                    }
                ],
                "logos": [
                    {
                        "file_path": "/logo.png",
                        "iso_3166_1": "US",
                        "vote_average": 7.0,
                    }
                ],
            }
        )
        mock_images.raise_for_status = Mock()

        with patch.object(
            provider._client, "get", side_effect=[mock_details, mock_images]
        ):
            details = await provider.get_movie_details(12345)

            assert details["id"] == 12345
            assert details["title"] == "Test Movie"
            assert "poster_url" in details
            assert "logo_url" in details
            assert "https://image.tmdb.org/t/p/original" in details["poster_url"]


@pytest.mark.asyncio
async def test_tmdb_handles_404():
    """Test that 404 returns None gracefully."""
    from namegnome_serve.metadata.providers.tmdb import TMDBProvider

    with patch.dict(os.environ, {"TMDB_API_KEY": "test_key"}):
        provider = TMDBProvider()

        # Mock 404 response
        with patch.object(
            provider._client,
            "get",
            side_effect=httpx.HTTPStatusError(
                "Not Found", request=AsyncMock(), response=AsyncMock(status_code=404)
            ),
        ):
            details = await provider.get_movie_details(99999)
            assert details is None


@pytest.mark.asyncio
async def test_tmdb_normalizes_rating():
    """Test that vote_average is normalized to 0-1 range."""
    from namegnome_serve.metadata.providers.tmdb import TMDBProvider

    with patch.dict(os.environ, {"TMDB_API_KEY": "test_key"}):
        provider = TMDBProvider()

        # Mock response with 10-point scale rating
        mock_response = Mock()
        mock_response.json = Mock(
            return_value={
                "id": 12345,
                "title": "Test",
                "vote_average": 7.5,  # 0-10 scale
                "overview": "Test movie",
            }
        )
        mock_response.raise_for_status = Mock()

        with patch.object(provider._client, "get", return_value=mock_response):
            details = await provider.get_movie_details(12345)

            # Should be normalized to 0-1
            assert details["vote_average"] == 0.75
            assert 0.0 <= details["vote_average"] <= 1.0


@pytest.mark.asyncio
async def test_tmdb_search_tv_with_year_filter():
    """TV search should pass first_air_date_year parameter."""
    from namegnome_serve.metadata.providers.tmdb import TMDBProvider

    with patch.dict(os.environ, {"TMDB_API_KEY": "test_key"}):
        provider = TMDBProvider()

    mock_response = Mock()
    mock_response.json = Mock(
        return_value={
            "results": [
                {"id": 2468, "name": "Firebuds", "first_air_date": "2022-09-21"}
            ]
        }
    )
    mock_response.raise_for_status = Mock()

    with patch.object(provider._client, "get", return_value=mock_response) as mock_get:
        results = await provider.search_tv("Firebuds", year=2022)

    assert len(results) == 1
    assert results[0]["id"] == 2468
    call_args = mock_get.call_args
    assert "search/tv" in call_args.args[0]
    params = call_args.kwargs["params"]
    assert params["query"] == "Firebuds"
    assert params["first_air_date_year"] == 2022


@pytest.mark.asyncio
async def test_tmdb_get_tv_episodes_for_season():
    """Fetching episodes for a specific season should return parsed list."""
    from namegnome_serve.metadata.providers.tmdb import TMDBProvider

    with patch.dict(os.environ, {"TMDB_API_KEY": "test_key"}):
        provider = TMDBProvider()

    mock_response = AsyncMock()
    mock_response.json = Mock(
        return_value={
            "episodes": [
                {"id": 1, "season_number": 1, "episode_number": 1, "name": "Pilot"}
            ]
        }
    )
    mock_response.raise_for_status = Mock()

    with patch.object(provider._client, "get", return_value=mock_response) as mock_get:
        episodes = await provider.get_tv_episodes(101, season=1)

    assert episodes == [
        {"id": 1, "season_number": 1, "episode_number": 1, "name": "Pilot"}
    ]
    mock_get.assert_called_once()
    assert "/tv/101/season/1" in mock_get.call_args.args[0]


@pytest.mark.asyncio
async def test_tmdb_get_tv_episodes_all_seasons():
    """Fetching episodes without season should iterate non-zero seasons."""
    from namegnome_serve.metadata.providers.tmdb import TMDBProvider

    with patch.dict(os.environ, {"TMDB_API_KEY": "test_key"}):
        provider = TMDBProvider()

    detail_response = AsyncMock()
    detail_response.json = Mock(
        return_value={
            "seasons": [
                {"season_number": 1},
                {"season_number": 0},  # specials should be skipped
                {"season_number": 2},
            ]
        }
    )
    detail_response.raise_for_status = Mock()

    season1_response = AsyncMock()
    season1_response.json = Mock(
        return_value={
            "episodes": [
                {"id": 11, "season_number": 1, "episode_number": 1, "name": "S1E1"}
            ]
        }
    )
    season1_response.raise_for_status = Mock()

    season2_response = AsyncMock()
    season2_response.json = Mock(
        return_value={
            "episodes": [
                {"id": 21, "season_number": 2, "episode_number": 1, "name": "S2E1"}
            ]
        }
    )
    season2_response.raise_for_status = Mock()

    with patch.object(
        provider._client,
        "get",
        side_effect=[detail_response, season1_response, season2_response],
    ) as mock_get:
        episodes = await provider.get_tv_episodes(202)

    assert len(episodes) == 2
    assert episodes[0]["season_number"] == 1
    assert episodes[1]["season_number"] == 2
    # First call should be details endpoint
    assert "/tv/202" in mock_get.call_args_list[0].args[0]
