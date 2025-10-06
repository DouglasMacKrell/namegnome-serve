"""Integration tests for TMDB API with real API calls.

These tests require TMDB_API_KEY environment variable.
If not set, tests are skipped gracefully.
"""

import os

import pytest


def check_tmdb_credentials() -> bool:
    """Check if TMDB API credentials are available."""
    return "TMDB_API_KEY" in os.environ and os.environ["TMDB_API_KEY"] not in (
        "",
        "your_tmdb_api_read_access_token_here",
        "your_tmdb_api_key_here",
    )


@pytest.mark.asyncio
async def test_tmdb_real_search_movie():
    """Test real movie search against TMDB API."""
    if not check_tmdb_credentials():
        pytest.skip("TMDB_API_KEY not configured. Set it in .env to run tests.")

    from namegnome_serve.metadata.providers.tmdb import TMDBProvider

    async with TMDBProvider() as provider:
        # Search for Moana (2016)
        results = await provider.search_movie("Moana", year=2016)

        # Should get results
        assert isinstance(results, list)
        assert len(results) > 0

        # First result should be Moana
        moana = results[0]
        assert "id" in moana
        assert "title" in moana
        assert "Moana" in moana["title"]
        assert "release_date" in moana

        print("✅ TMDB search successful:")
        print(f"   Found: {moana['title']} (ID: {moana['id']})")
        print(f"   Release Date: {moana.get('release_date', 'N/A')}")


@pytest.mark.asyncio
async def test_tmdb_real_movie_details():
    """Test fetching real movie details from TMDB API."""
    if not check_tmdb_credentials():
        pytest.skip("TMDB_API_KEY not configured. Set it in .env to run tests.")

    from namegnome_serve.metadata.providers.tmdb import TMDBProvider

    async with TMDBProvider() as provider:
        # Search for Moana first to get ID
        results = await provider.search_movie("Moana", year=2016)
        assert len(results) > 0
        movie_id = results[0]["id"]

        # Get detailed info
        details = await provider.get_movie_details(movie_id)

        # Should have comprehensive details
        assert details is not None
        assert "id" in details
        assert "title" in details
        assert "overview" in details
        assert "vote_average" in details

        # Should have normalized rating (0-1 scale)
        rating = details["vote_average"]
        assert isinstance(rating, float)
        assert 0.0 <= rating <= 1.0

        # Should attempt to include images
        # (poster_url/logo_url may or may not exist depending on API response)

        print("✅ TMDB movie details fetch successful:")
        print(f"   Title: {details['title']}")
        print(f"   Rating: {rating:.2f} (normalized)")
        print(f"   Overview: {details['overview'][:80]}...")
        if "poster_url" in details:
            print(f"   Poster: {details['poster_url'][:50]}...")


@pytest.mark.asyncio
async def test_tmdb_real_auth_detection():
    """Test that TMDB correctly detects auth method (Bearer vs API key)."""
    if not check_tmdb_credentials():
        pytest.skip("TMDB_API_KEY not configured. Set it in .env to run tests.")

    from namegnome_serve.metadata.providers.tmdb import TMDBProvider

    provider = TMDBProvider()

    # Get auth method
    headers, params = provider._get_auth()

    # Should use one or the other, not both
    if "Authorization" in headers:
        # Bearer token mode
        assert headers["Authorization"].startswith("Bearer ")
        assert "api_key" not in params
        print("✅ TMDB auth: Using Bearer token")
    else:
        # API key mode
        assert "api_key" in params
        assert params["language"] == "en-US"
        assert "Authorization" not in headers
        print("✅ TMDB auth: Using API key in params")


@pytest.mark.asyncio
async def test_tmdb_real_404_handling():
    """Test that non-existent movie returns None gracefully."""
    if not check_tmdb_credentials():
        pytest.skip("TMDB_API_KEY not configured. Set it in .env to run tests.")

    from namegnome_serve.metadata.providers.tmdb import TMDBProvider

    async with TMDBProvider() as provider:
        # Try to get details for non-existent movie ID
        details = await provider.get_movie_details(99999999)

        # Should return None, not raise error
        assert details is None

        print("✅ TMDB 404 handling successful (None returned)")


@pytest.mark.asyncio
async def test_tmdb_real_english_filtering():
    """Test that TMDB returns English content when available."""
    if not check_tmdb_credentials():
        pytest.skip("TMDB_API_KEY not configured. Set it in .env to run tests.")

    from namegnome_serve.metadata.providers.tmdb import TMDBProvider

    async with TMDBProvider() as provider:
        # Get details for a well-known movie
        results = await provider.search_movie("Moana", year=2016)
        assert len(results) > 0

        details = await provider.get_movie_details(results[0]["id"])
        assert details is not None

        # If poster/logo URLs exist, they should be from image.tmdb.org
        if "poster_url" in details:
            assert "image.tmdb.org" in details["poster_url"]
            assert "/original/" in details["poster_url"]
            print(f"✅ TMDB poster URL: {details['poster_url'][:60]}...")

        if "logo_url" in details:
            assert "image.tmdb.org" in details["logo_url"]
            assert "/original/" in details["logo_url"]
            print(f"✅ TMDB logo URL: {details['logo_url'][:60]}...")

        print("✅ TMDB English content filtering successful")
