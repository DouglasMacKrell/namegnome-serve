"""Integration tests for OMDb API with real API calls.

OMDb requires an API key (free tier: 1,000 req/day).
Tests skip if OMDB_API_KEY is not configured.
"""

import os

import pytest


def check_omdb_api_key_configured() -> bool:
    """Check if OMDb API key is set in environment."""
    api_key = os.environ.get("OMDB_API_KEY")
    return bool(api_key and api_key != "your_omdb_api_key_here")


@pytest.mark.asyncio
async def test_omdb_real_search():
    """Test real movie search against OMDb API."""
    if not check_omdb_api_key_configured():
        pytest.skip("OMDB_API_KEY not configured for integration tests.")

    from namegnome_serve.metadata.providers.omdb import OMDbProvider

    async with OMDbProvider() as provider:
        # Search for Moana (2016)
        results = await provider.search_movie("Moana", year=2016)

        assert isinstance(results, list)
        assert len(results) > 0

        # Find the Disney Moana
        moana = next((r for r in results if r.get("Year") == "2016"), None)
        assert moana is not None
        assert "Moana" in moana["Title"]
        assert moana["Type"] == "movie"
        assert "imdbID" in moana

        print("✅ OMDb search successful:")
        print(f"   Found: {moana['Title']} ({moana['Year']})")
        print(f"   IMDb ID: {moana['imdbID']}")


@pytest.mark.asyncio
async def test_omdb_real_movie_details():
    """Test fetching real movie details from OMDb API."""
    if not check_omdb_api_key_configured():
        pytest.skip("OMDB_API_KEY not configured for integration tests.")

    from namegnome_serve.metadata.providers.omdb import OMDbProvider

    async with OMDbProvider() as provider:
        # Fetch details for Moana using known IMDb ID
        details = await provider.get_movie_details("tt3521164")

        assert details is not None
        assert details["Title"] == "Moana"
        assert details["Year"] == "2016"
        assert details["Type"] == "movie"
        assert "imdbRating" in details
        assert "imdb_rating_normalized" in details

        # Check rating normalization
        rating = details["imdb_rating_normalized"]
        assert 0.0 <= rating <= 1.0

        print("✅ OMDb movie details fetch successful:")
        print(f"   Title: {details['Title']}")
        print(f"   IMDb Rating: {details['imdbRating']} (normalized: {rating:.2f})")
        print(f"   Plot: {details.get('Plot', 'N/A')[:50]}...")


@pytest.mark.asyncio
async def test_omdb_real_not_found_handling():
    """Test that OMDb handles non-existent movies gracefully."""
    if not check_omdb_api_key_configured():
        pytest.skip("OMDB_API_KEY not configured for integration tests.")

    from namegnome_serve.metadata.providers.omdb import OMDbProvider

    async with OMDbProvider() as provider:
        # Try to get details for non-existent IMDb ID
        details = await provider.get_movie_details("tt0000000")

        # Should return None, not raise error
        assert details is None

        print("✅ OMDb 404 handling successful (None returned)")


@pytest.mark.asyncio
async def test_omdb_real_rate_limiting():
    """Test that rate limiting is configured (don't spam the API!)."""
    if not check_omdb_api_key_configured():
        pytest.skip("OMDB_API_KEY not configured for integration tests.")

    from namegnome_serve.metadata.providers.omdb import OMDbProvider

    async with OMDbProvider() as provider:
        # Provider should have very conservative rate limit (free tier!)
        assert provider.rate_limit_per_minute <= 1  # ~1 per 2 minutes

        # Make one request
        results = await provider.search_movie("test", limit=1)
        assert isinstance(results, list)

        # Check rate limit would block rapid requests
        assert provider.check_rate_limit()  # Should still have capacity

        print("✅ OMDb rate limiting configured correctly:")
        print(f"   Rate limit: {provider.rate_limit_per_minute} req/min")
        print("   (VERY conservative for free tier: 1,000 req/day)")
