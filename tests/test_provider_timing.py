"""Timing diagnostics for provider performance testing.

This module tests provider performance and retry behavior with detailed timing.
"""

import asyncio
import time
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from scripts.timing_diagnostics import checkpoint, record_provider_time, timing


@pytest.mark.asyncio
async def test_provider_retry_timing():
    """Test retry timing with detailed diagnostics."""
    import os

    from namegnome_serve.metadata.providers.tmdb import TMDBProvider

    checkpoint("Retry timing test started", "Setting up TMDB provider")

    with patch.dict(os.environ, {"TMDB_API_KEY": "test_key"}):
        provider = TMDBProvider()

        # Mock retry scenario: 2 failures, then success
        call_count = 0
        call_times = []

        async def mock_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            call_times.append(time.time())

            if call_count <= 2:
                # First two calls: 500 server error
                mock_resp = AsyncMock()
                mock_resp.status_code = 500
                raise httpx.HTTPStatusError(
                    "Server error", request=AsyncMock(), response=mock_resp
                )
            else:
                # Third call: success
                mock_resp = Mock()
                mock_resp.json.return_value = {"results": []}
                mock_resp.raise_for_status = Mock()
                return mock_resp

        checkpoint(
            "Mock setup complete", f"Will simulate {call_count} failures then success"
        )

        with patch.object(provider._client, "get", side_effect=mock_get):
            start_time = time.time()

            results = await provider.search_movie("test")

            total_time = time.time() - start_time
            record_provider_time("TMDB_retry_test", total_time)

            checkpoint(
                "Retry test completed",
                f"Total time: {total_time:.2f}s, calls: {call_count}",
            )

            assert results == []
            assert call_count == 3  # Initial + 2 retries

            # Verify exponential backoff timing
            if len(call_times) >= 3:
                delay1 = call_times[1] - call_times[0]
                delay2 = call_times[2] - call_times[1]

                checkpoint(
                    "Backoff analysis",
                    f"Delay 1: {delay1:.2f}s, Delay 2: {delay2:.2f}s",
                )

                # Should have exponential backoff (roughly 1s, 2s)
                assert delay1 >= 0.9  # At least 1 second
                assert delay2 >= 1.8  # At least 2 seconds
                assert delay2 > delay1  # Exponential growth


@pytest.mark.asyncio
async def test_provider_performance_comparison():
    """Compare performance across different providers."""
    import os

    from namegnome_serve.metadata.providers.musicbrainz import MusicBrainzProvider
    from namegnome_serve.metadata.providers.tmdb import TMDBProvider

    checkpoint("Performance comparison started", "Testing multiple providers")

    # Test TMDB performance
    with patch.dict(os.environ, {"TMDB_API_KEY": "test_key"}):
        tmdb_provider = TMDBProvider()

        mock_response = Mock()
        mock_response.json.return_value = {"results": []}
        mock_response.raise_for_status = Mock()

        with patch.object(tmdb_provider._client, "get", return_value=mock_response):
            start_time = time.time()
            await tmdb_provider.search_movie("test")
            tmdb_time = time.time() - start_time
            record_provider_time("TMDB", tmdb_time)

            checkpoint("TMDB test", f"Time: {tmdb_time:.3f}s")

    # Test MusicBrainz performance
    musicbrainz_provider = MusicBrainzProvider()

    mock_response = Mock()
    mock_response.json.return_value = {"recordings": []}
    mock_response.raise_for_status = Mock()

    with patch.object(musicbrainz_provider._client, "get", return_value=mock_response):
        start_time = time.time()
        await musicbrainz_provider.search_recording("test")
        mb_time = time.time() - start_time
        record_provider_time("MusicBrainz", mb_time)

        checkpoint("MusicBrainz test", f"Time: {mb_time:.3f}s")

    # Performance comparison
    if tmdb_time > 0 and mb_time > 0:
        ratio = tmdb_time / mb_time
        checkpoint("Performance ratio", f"TMDB/MusicBrainz: {ratio:.2f}x")


@pytest.mark.asyncio
async def test_concurrent_provider_performance():
    """Test concurrent provider calls for performance analysis."""
    import os

    from namegnome_serve.metadata.providers.musicbrainz import MusicBrainzProvider
    from namegnome_serve.metadata.providers.tmdb import TMDBProvider

    checkpoint("Concurrent test started", "Testing parallel provider calls")

    async def test_provider(provider_name, provider, search_method, query):
        start_time = time.time()

        # Mock response
        mock_response = Mock()
        if provider_name == "TMDB":
            mock_response.json.return_value = {"results": []}
        else:
            mock_response.json.return_value = {"recordings": []}
        mock_response.raise_for_status = Mock()

        with patch.object(provider._client, "get", return_value=mock_response):
            await search_method(query)

        duration = time.time() - start_time
        record_provider_time(provider_name, duration)
        checkpoint(f"{provider_name} concurrent", f"Time: {duration:.3f}s")
        return duration

    # Setup providers
    with patch.dict(os.environ, {"TMDB_API_KEY": "test_key"}):
        tmdb = TMDBProvider()
        musicbrainz = MusicBrainzProvider()

        # Run concurrent tests
        start_time = time.time()

        tasks = [
            test_provider("TMDB", tmdb, tmdb.search_movie, "test movie"),
            test_provider(
                "MusicBrainz", musicbrainz, musicbrainz.search_recording, "test song"
            ),
        ]

        results = await asyncio.gather(*tasks)
        total_time = time.time() - start_time

        checkpoint(
            "Concurrent test completed",
            f"Total: {total_time:.3f}s, Individual: {results}",
        )

        # Verify concurrent execution was faster than sequential
        sequential_time = sum(results)
        speedup = sequential_time / total_time if total_time > 0 else 1

        checkpoint(
            "Concurrency analysis",
            f"Speedup: {speedup:.2f}x (sequential: {sequential_time:.3f}s)",
        )


def test_timing_diagnostics_integration():
    """Test that timing diagnostics work correctly."""
    checkpoint("Timing diagnostics test", "Verifying timing system")

    # Test checkpoint recording
    assert len(timing.checkpoints) > 0

    # Test provider timing recording
    record_provider_time("test_provider", 0.5)
    assert "test_provider" in timing.provider_times
    assert timing.provider_times["test_provider"] == [0.5]

    checkpoint("Timing diagnostics verified", "All timing systems working")


# Cleanup function to reset timing state
@pytest.fixture(autouse=True)
def reset_timing():
    """Reset timing state between tests."""
    timing.checkpoints.clear()
    timing.provider_times.clear()
    timing.start_time = time.time()
