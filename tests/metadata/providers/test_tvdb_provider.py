"""Tests for TVDB v3 API provider with JWT authentication.

TVDB v3 API (legacy) specifics:
- Auth: POST /login with {"apikey": "KEY"} → JWT token
- Token cached for 24hrs
- All requests use Bearer {token} header
- Search: GET /search/series?name=...
- Episodes require series ID → season → episode lookups
"""

import os
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest


@pytest.mark.asyncio
async def test_tvdb_authenticates_and_caches_token():
    """Test that TVDB v3 authenticates and caches JWT token."""
    from namegnome_serve.metadata.providers.tvdb import TVDBProvider

    with patch.dict(os.environ, {"TVDB_API_KEY": "test_api_key"}):
        provider = TVDBProvider()

        # Mock authentication response
        mock_auth_response = AsyncMock()
        mock_auth_response.json = AsyncMock(
            return_value={"token": "test_jwt_token_12345"}
        )
        mock_auth_response.raise_for_status = Mock()

        with patch.object(
            provider._client, "post", return_value=mock_auth_response
        ) as mock_post:
            token = await provider._get_auth_token()

            # Should authenticate once
            assert token == "test_jwt_token_12345"
            mock_post.assert_called_once_with(
                f"{provider.BASE_URL}/login", json={"apikey": "test_api_key"}
            )

            # Second call should use cached token (no new POST)
            mock_post.reset_mock()
            token2 = await provider._get_auth_token()
            assert token2 == "test_jwt_token_12345"
            mock_post.assert_not_called()


@pytest.mark.asyncio
async def test_tvdb_uses_bearer_token_in_headers():
    """Test that TVDB uses Bearer token for all API requests."""
    from namegnome_serve.metadata.providers.tvdb import TVDBProvider

    with patch.dict(os.environ, {"TVDB_API_KEY": "test_api_key"}):
        provider = TVDBProvider()
        provider._auth_token = "cached_jwt_token"

        headers = await provider._get_auth_headers()

        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer cached_jwt_token"
        assert headers["Accept"] == "application/json"


@pytest.mark.asyncio
async def test_tvdb_search_series():
    """Test TV series search by name."""
    from namegnome_serve.metadata.providers.tvdb import TVDBProvider

    with patch.dict(os.environ, {"TVDB_API_KEY": "test_api_key"}):
        provider = TVDBProvider()
        provider._auth_token = "test_token"

        # Mock search response
        mock_response = AsyncMock()
        mock_response.json = AsyncMock(
            return_value={
                "data": [
                    {
                        "id": 305288,
                        "seriesName": "Firebuds",
                        "firstAired": "2022-09-21",
                        "network": "Disney Junior",
                    }
                ]
            }
        )
        mock_response.raise_for_status = Mock()

        with patch.object(
            provider._client, "get", return_value=mock_response
        ) as mock_get:
            results = await provider.search_series("Firebuds")

            assert len(results) == 1
            assert results[0]["id"] == 305288
            assert results[0]["seriesName"] == "Firebuds"

            # Verify API call
            mock_get.assert_called_once()
            call_args = mock_get.call_args
            assert "/search/series" in str(call_args[0][0])
            assert call_args[1]["params"]["name"] == "Firebuds"
            assert call_args[1]["headers"]["Authorization"] == "Bearer test_token"


@pytest.mark.asyncio
async def test_tvdb_get_series_episodes():
    """Test fetching all episodes for a series."""
    from namegnome_serve.metadata.providers.tvdb import TVDBProvider

    with patch.dict(os.environ, {"TVDB_API_KEY": "test_api_key"}):
        provider = TVDBProvider()
        provider._auth_token = "test_token"

        # Mock episodes response (paginated)
        mock_page1 = AsyncMock()
        mock_page1.json = AsyncMock(
            return_value={
                "data": [
                    {
                        "id": 8675309,
                        "airedSeason": 1,
                        "airedEpisodeNumber": 1,
                        "episodeName": "Pilot",
                    }
                ],
                "links": {"next": 2},
            }
        )
        mock_page1.raise_for_status = Mock()

        mock_page2 = AsyncMock()
        mock_page2.json = AsyncMock(
            return_value={
                "data": [
                    {
                        "id": 8675310,
                        "airedSeason": 1,
                        "airedEpisodeNumber": 2,
                        "episodeName": "Second Episode",
                    }
                ],
                "links": {},
            }
        )
        mock_page2.raise_for_status = Mock()

        with patch.object(
            provider._client, "get", side_effect=[mock_page1, mock_page2]
        ):
            episodes = await provider.get_series_episodes(305288)

            assert len(episodes) == 2
            assert episodes[0]["episodeName"] == "Pilot"
            assert episodes[1]["episodeName"] == "Second Episode"


@pytest.mark.asyncio
async def test_tvdb_handles_401_reauth():
    """Test that TVDB re-authenticates on 401 (expired token)."""
    from namegnome_serve.metadata.providers.tvdb import TVDBProvider

    with patch.dict(os.environ, {"TVDB_API_KEY": "test_api_key"}):
        provider = TVDBProvider()
        provider._auth_token = "expired_token"

        # Mock 401 error response
        mock_401_response = AsyncMock()
        mock_401_response.status_code = 401

        # Mock new auth
        mock_auth = AsyncMock()
        mock_auth.json = AsyncMock(return_value={"token": "fresh_token"})
        mock_auth.raise_for_status = Mock()

        # Mock successful retry
        mock_success = AsyncMock()
        mock_success.json = AsyncMock(return_value={"data": []})
        mock_success.raise_for_status = Mock()

        # First GET raises 401, second GET succeeds
        get_call_count = 0

        async def mock_get(*args: Any, **kwargs: Any) -> AsyncMock:
            nonlocal get_call_count
            get_call_count += 1
            if get_call_count == 1:
                raise httpx.HTTPStatusError(
                    "Unauthorized", request=AsyncMock(), response=mock_401_response
                )
            return mock_success

        with patch.object(provider._client, "get", side_effect=mock_get):
            with patch.object(provider._client, "post", return_value=mock_auth):
                results = await provider.search_series("test")

                # Should have re-authenticated and retried
                assert provider._auth_token == "fresh_token"
                assert results == []


@pytest.mark.asyncio
async def test_tvdb_search_returns_empty_on_404():
    """Test that TVDB returns empty list on 404 (not found)."""
    from namegnome_serve.metadata.providers.tvdb import TVDBProvider

    with patch.dict(os.environ, {"TVDB_API_KEY": "test_api_key"}):
        provider = TVDBProvider()
        provider._auth_token = "test_token"

        with patch.object(
            provider._client,
            "get",
            side_effect=httpx.HTTPStatusError(
                "Not Found", request=AsyncMock(), response=AsyncMock(status_code=404)
            ),
        ):
            results = await provider.search_series("NonExistentShow")
            assert results == []


@pytest.mark.asyncio
async def test_tvdb_formats_episode_details():
    """Test that episode details are formatted with all required fields."""
    from namegnome_serve.metadata.providers.tvdb import TVDBProvider

    with patch.dict(os.environ, {"TVDB_API_KEY": "test_api_key"}):
        provider = TVDBProvider()

        raw_episode = {
            "id": 123456,
            "airedSeason": 2,
            "airedEpisodeNumber": 5,
            "episodeName": "The Big Episode",
            "overview": "Something happens",
            "firstAired": "2023-05-15",
        }

        formatted = provider._format_episode(raw_episode)

        assert formatted["episode_id"] == 123456
        assert formatted["season"] == 2
        assert formatted["episode"] == 5
        assert formatted["title"] == "The Big Episode"
        assert formatted["overview"] == "Something happens"
        assert formatted["air_date"] == "2023-05-15"
