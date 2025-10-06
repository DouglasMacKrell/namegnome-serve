"""Tests for enhanced retry/backoff logic for 429 and 5xx errors.

Providers should automatically retry on:
- 429 Too Many Requests (rate limit)
- 500 Internal Server Error
- 502 Bad Gateway
- 503 Service Unavailable
- 504 Gateway Timeout

With exponential backoff and max retries.
"""

from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest


@pytest.mark.asyncio
async def test_provider_retries_on_429_rate_limit():
    """Test that provider retries automatically on 429 rate limit errors."""
    import os

    from namegnome_serve.metadata.providers.tmdb import TMDBProvider

    with patch.dict(os.environ, {"TMDB_API_KEY": "test_key"}):
        provider = TMDBProvider()

        # Mock 429 error on first call, success on second
        call_count = 0

        async def mock_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1

            if call_count == 1:
                # First call: 429 rate limit
                mock_resp = AsyncMock()
                mock_resp.status_code = 429
                raise httpx.HTTPStatusError(
                    "Rate limited", request=AsyncMock(), response=mock_resp
                )
            else:
                # Second call: success
                mock_resp = Mock()
                mock_resp.json.return_value = {"results": []}
                mock_resp.raise_for_status = Mock()
                return mock_resp

        with patch.object(provider._client, "get", side_effect=mock_get):
            # Should retry and succeed
            results = await provider.search_movie("test")
            assert results == []
            assert call_count == 2  # Initial + 1 retry


@pytest.mark.asyncio
async def test_provider_retries_on_500_server_error():
    """Test that provider retries on 500 Internal Server Error."""
    import os

    from namegnome_serve.metadata.providers.tmdb import TMDBProvider

    with patch.dict(os.environ, {"TMDB_API_KEY": "test_key"}):
        provider = TMDBProvider()

        call_count = 0

        async def mock_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1

            if call_count == 1:
                mock_resp = AsyncMock()
                mock_resp.status_code = 500
                raise httpx.HTTPStatusError(
                    "Server error", request=AsyncMock(), response=mock_resp
                )
            else:
                mock_resp = AsyncMock()
                mock_resp.json = Mock(return_value={"results": []})
                mock_resp.raise_for_status = AsyncMock()
                return mock_resp

        with patch.object(provider._client, "get", side_effect=mock_get):
            results = await provider.search_movie("test")
            assert results == []
            assert call_count == 2


@pytest.mark.asyncio
async def test_provider_retries_on_503_service_unavailable():
    """Test that provider retries on 503 Service Unavailable."""
    import os

    from namegnome_serve.metadata.providers.tmdb import TMDBProvider

    with patch.dict(os.environ, {"TMDB_API_KEY": "test_key"}):
        provider = TMDBProvider()

        call_count = 0

        async def mock_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1

            if call_count <= 2:
                mock_resp = AsyncMock()
                mock_resp.status_code = 503
                raise httpx.HTTPStatusError(
                    "Service unavailable", request=AsyncMock(), response=mock_resp
                )
            else:
                mock_resp = AsyncMock()
                mock_resp.json = Mock(return_value={"results": []})
                mock_resp.raise_for_status = AsyncMock()
                return mock_resp

        with patch.object(provider._client, "get", side_effect=mock_get):
            results = await provider.search_movie("test")
            assert results == []
            assert call_count == 3  # Initial + 2 retries


@pytest.mark.asyncio
async def test_provider_respects_max_retries():
    """Test that provider stops after max retries."""
    import os

    from namegnome_serve.metadata.providers.base import ProviderError
    from namegnome_serve.metadata.providers.tmdb import TMDBProvider

    with patch.dict(os.environ, {"TMDB_API_KEY": "test_key"}):
        provider = TMDBProvider()

        # Always fail with 500
        async def mock_get(*args, **kwargs):
            mock_resp = AsyncMock()
            mock_resp.status_code = 500
            raise httpx.HTTPStatusError(
                "Server error", request=AsyncMock(), response=mock_resp
            )

        with patch.object(provider._client, "get", side_effect=mock_get):
            # Should raise after max_retries attempts
            with pytest.raises(ProviderError):
                await provider.search_movie("test")


@pytest.mark.asyncio
async def test_provider_does_not_retry_on_404():
    """Test that provider does NOT retry on 404 (client error)."""
    import os

    from namegnome_serve.metadata.providers.tmdb import TMDBProvider

    with patch.dict(os.environ, {"TMDB_API_KEY": "test_key"}):
        provider = TMDBProvider()

        call_count = 0

        async def mock_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1

            mock_resp = AsyncMock()
            mock_resp.status_code = 404
            raise httpx.HTTPStatusError(
                "Not found", request=AsyncMock(), response=mock_resp
            )

        with patch.object(provider._client, "get", side_effect=mock_get):
            # Should return empty, not retry (404 is expected)
            results = await provider.search_movie("test")
            assert results == []
            assert call_count == 1  # No retries


@pytest.mark.asyncio
async def test_provider_exponential_backoff():
    """Test that retry delays use exponential backoff."""
    import os
    import time

    from namegnome_serve.metadata.providers.tmdb import TMDBProvider

    with patch.dict(os.environ, {"TMDB_API_KEY": "test_key"}):
        provider = TMDBProvider()

        call_times = []

        async def mock_get(*args, **kwargs):
            call_times.append(time.time())

            if len(call_times) <= 2:
                mock_resp = AsyncMock()
                mock_resp.status_code = 500
                raise httpx.HTTPStatusError(
                    "Server error", request=AsyncMock(), response=mock_resp
                )
            else:
                mock_resp = AsyncMock()
                mock_resp.json = Mock(return_value={"results": []})
                mock_resp.raise_for_status = AsyncMock()
                return mock_resp

        with patch.object(provider._client, "get", side_effect=mock_get):
            await provider.search_movie("test")

            # Check delays between calls (should be exponential: ~1s, ~2s)
            if len(call_times) >= 3:
                delay1 = call_times[1] - call_times[0]
                delay2 = call_times[2] - call_times[1]

                # First retry ~1s, second retry ~2s (exponential)
                assert delay1 >= 0.9  # At least 1 second
                assert delay2 >= 1.8  # At least 2 seconds
                assert delay2 > delay1  # Exponential growth


@pytest.mark.asyncio
async def test_provider_retries_on_network_timeout():
    """Test that provider retries on network timeouts."""
    import os

    from namegnome_serve.metadata.providers.tmdb import TMDBProvider

    with patch.dict(os.environ, {"TMDB_API_KEY": "test_key"}):
        provider = TMDBProvider()

        call_count = 0

        async def mock_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1

            if call_count == 1:
                raise httpx.TimeoutException("Request timed out")
            else:
                mock_resp = AsyncMock()
                mock_resp.json = Mock(return_value={"results": []})
                mock_resp.raise_for_status = AsyncMock()
                return mock_resp

        with patch.object(provider._client, "get", side_effect=mock_get):
            results = await provider.search_movie("test")
            assert results == []
            assert call_count == 2  # Retried after timeout
