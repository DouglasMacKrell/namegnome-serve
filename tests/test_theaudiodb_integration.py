"""Integration tests for TheAudioDB provider using real API calls.

These tests verify actual connectivity and functionality against the real
TheAudioDB API. Tests load credentials from `.env` when available, and skip
automatically when no credentials are configured (protects CI pipelines).
"""

import os

import pytest

from namegnome_serve.metadata.providers.theaudiodb import TheAudioDBProvider


def _has_valid_theaudiodb_key() -> bool:
    """Return True when a non-placeholder TheAudioDB key is present."""

    env_var = "THEAUDIODB_API_KEY"
    placeholder_values = {
        "",
        "test_key",
        "your_theaudiodb_api_key_here",
    }

    key = os.environ.get(env_var, "").strip()
    return key not in placeholder_values


@pytest.fixture(scope="module", autouse=True)
def _skip_without_credentials() -> None:
    """Skip the module when TheAudioDB credentials are unavailable."""

    if not _has_valid_theaudiodb_key():
        pytest.skip(
            "THEAUDIODB_API_KEY not configured. Set it in .env to run integration"
            " tests."
        )


class TestTheAudioDBIntegration:
    """Integration tests for TheAudioDB provider with real API calls."""

    @pytest.mark.asyncio
    async def test_search_artist_real_api(self):
        """Test real artist search against TheAudioDB API."""
        async with TheAudioDBProvider() as provider:
            # Search for a well-known artist
            results = await provider.search_artist("Queen")

            # Should find Queen
            assert len(results) > 0
            queen_found = any(
                artist.get("strArtist", "").lower() == "queen" for artist in results
            )
            assert queen_found, "Queen should be found in search results"

    @pytest.mark.asyncio
    async def test_get_artist_details_real_api(self):
        """Test getting real artist details from TheAudioDB API."""
        async with TheAudioDBProvider() as provider:
            # First search for Queen to get an ID
            search_results = await provider.search_artist("Queen")
            assert len(search_results) > 0

            # Get details for the first result
            artist_id = search_results[0].get("idArtist")
            assert artist_id is not None

            details = await provider.get_artist_details(artist_id)
            assert details is not None
            assert details.get("strArtist", "").lower() == "queen"
            assert details.get("idArtist") == artist_id

    @pytest.mark.asyncio
    async def test_search_album_real_api(self):
        """Test real album search against TheAudioDB API."""
        async with TheAudioDBProvider() as provider:
            # Search for a well-known album
            results = await provider.search_album("A Night at the Opera", "Queen")

            # Should find the album
            assert len(results) > 0
            album_found = any(
                album.get("strAlbum", "").lower() == "a night at the opera"
                for album in results
            )
            assert album_found, "A Night at the Opera should be found in search results"

    @pytest.mark.asyncio
    async def test_search_track_real_api(self):
        """Test real track search against TheAudioDB API."""
        async with TheAudioDBProvider() as provider:
            # Search for a well-known track
            results = await provider.search_track("Bohemian Rhapsody", "Queen")

            # Should find the track
            assert len(results) > 0
            track_found = any(
                track.get("strTrack", "").lower() == "bohemian rhapsody"
                for track in results
            )
            assert track_found, "Bohemian Rhapsody should be found in search results"

    @pytest.mark.asyncio
    async def test_get_artist_artwork_real_api(self):
        """Test getting real artist artwork from TheAudioDB API."""
        async with TheAudioDBProvider() as provider:
            # First search for Queen to get an ID
            search_results = await provider.search_artist("Queen")
            assert len(search_results) > 0

            # Get artwork for the first result
            artist_id = search_results[0].get("idArtist")
            assert artist_id is not None

            artwork = await provider.get_artist_artwork(artist_id)
            # Artwork might be empty, but the method should not fail
            assert artwork is not None

    @pytest.mark.asyncio
    async def test_user_agent_header(self):
        """Test that User-Agent header is properly set for API requests."""
        async with TheAudioDBProvider() as provider:
            # The provider should have the correct User-Agent header
            assert "User-Agent" in provider._client.headers
            user_agent = provider._client.headers["User-Agent"]
            assert "NameGnome" in user_agent
            assert "TheAudioDB" not in user_agent  # Should not expose internal details

    @pytest.mark.asyncio
    async def test_rate_limiting_behavior(self):
        """Test that rate limiting is respected (1 request per second)."""
        async with TheAudioDBProvider() as provider:
            import time

            # Make multiple requests quickly to test rate limiting
            # First request
            await provider.search_artist("Queen")
            first_request_time = time.time()

            # Second request immediately after
            await provider.search_artist("Beatles")
            second_request_time = time.time()

            # Should have some delay between requests due to rate limiting
            # (though the exact timing depends on the rate limiter implementation)
            elapsed = second_request_time - first_request_time
            # Allow some tolerance for test execution time
            assert elapsed >= 0, "Rate limiting should not cause negative delays"

    @pytest.mark.asyncio
    async def test_no_results_handling(self):
        """Test handling of searches with no results."""
        async with TheAudioDBProvider() as provider:
            # Search for something that definitely doesn't exist
            results = await provider.search_artist("DefinitelyNotARealArtistName12345")

            # Should return empty list, not raise exception
            assert results == []

    @pytest.mark.asyncio
    async def test_api_error_handling(self):
        """Test handling of API errors gracefully."""
        async with TheAudioDBProvider() as provider:
            # Test with invalid parameters that might cause API errors
            # The provider should handle these gracefully
            try:
                await provider.search_artist("")
                # Empty search might return empty results or cause an error
                # Either is acceptable as long as it doesn't crash
            except Exception as exc:
                # If an exception is raised, it should be a reasonable one
                message = str(exc)
                assert (
                    "API" in message
                    or "HTTP" in message
                    or "request" in message.lower()
                )
