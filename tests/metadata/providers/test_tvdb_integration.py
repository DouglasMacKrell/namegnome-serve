"""Integration tests for TVDB v3 API with real API calls.

These tests require TVDB_API_KEY environment variable.
If not set, tests are skipped gracefully.
"""

import os

import pytest


def check_tvdb_credentials() -> bool:
    """Check if TVDB API credentials are available."""
    return "TVDB_API_KEY" in os.environ and os.environ["TVDB_API_KEY"] not in (
        "",
        "your_tvdb_v3_api_key_here",
    )


@pytest.mark.asyncio
async def test_tvdb_real_authentication():
    """Test that we can authenticate with real TVDB v3 API."""
    if not check_tvdb_credentials():
        pytest.skip(
            "TVDB_API_KEY not configured. Set it in .env to run integration tests."
        )

    from namegnome_serve.metadata.providers.tvdb import TVDBProvider

    async with TVDBProvider() as provider:
        # Should be able to get auth token
        token = await provider._get_auth_token()

        assert token is not None
        assert len(token) > 50  # JWT tokens are long
        assert isinstance(token, str)
        print(f"✅ TVDB authentication successful, token length: {len(token)}")


@pytest.mark.asyncio
async def test_tvdb_real_search():
    """Test real series search against TVDB v3 API."""
    if not check_tvdb_credentials():
        pytest.skip(
            "TVDB_API_KEY not configured. Set it in .env to run integration tests."
        )

    from namegnome_serve.metadata.providers.tvdb import TVDBProvider

    async with TVDBProvider() as provider:
        # Search for a well-known show
        results = await provider.search_series("Firebuds")

        # Should get results
        assert isinstance(results, list)
        assert len(results) > 0

        # First result should be Firebuds
        firebuds = results[0]
        assert "id" in firebuds
        assert "seriesName" in firebuds
        assert "Firebuds" in firebuds["seriesName"]

        print("✅ TVDB search successful:")
        print(f"   Found: {firebuds['seriesName']} (ID: {firebuds['id']})")
        if "firstAired" in firebuds:
            print(f"   First Aired: {firebuds['firstAired']}")


@pytest.mark.asyncio
async def test_tvdb_real_episodes():
    """Test fetching real episode data from TVDB v3 API."""
    if not check_tvdb_credentials():
        pytest.skip(
            "TVDB_API_KEY not configured. Set it in .env to run integration tests."
        )

    from namegnome_serve.metadata.providers.tvdb import TVDBProvider

    async with TVDBProvider() as provider:
        # First search for Firebuds
        results = await provider.search_series("Firebuds")
        assert len(results) > 0
        series_id = results[0]["id"]

        # Get episodes
        episodes = await provider.get_series_episodes(series_id)

        # Should have episodes
        assert isinstance(episodes, list)
        assert len(episodes) > 0

        # Check first episode structure
        first_ep = episodes[0]
        assert "id" in first_ep
        assert "airedSeason" in first_ep or "seasonNumber" in first_ep
        assert "airedEpisodeNumber" in first_ep or "episodeNumber" in first_ep

        print("✅ TVDB episodes fetch successful:")
        print(f"   Series ID: {series_id}")
        print(f"   Total episodes: {len(episodes)}")
        season = first_ep.get("airedSeason", "?")
        episode = first_ep.get("airedEpisodeNumber", "?")
        name = first_ep.get("episodeName", "N/A")
        print(f"   First episode: S{season}E{episode} - {name}")


@pytest.mark.asyncio
async def test_tvdb_real_404_handling():
    """Test that non-existent series returns empty list."""
    if not check_tvdb_credentials():
        pytest.skip(
            "TVDB_API_KEY not configured. Set it in .env to run integration tests."
        )

    from namegnome_serve.metadata.providers.tvdb import TVDBProvider

    async with TVDBProvider() as provider:
        # Search for something that definitely doesn't exist
        results = await provider.search_series("XYZ_NONEXISTENT_SHOW_12345")

        # Should return empty list, not raise error
        assert isinstance(results, list)
        assert len(results) == 0

        print("✅ TVDB 404 handling successful (empty list returned)")
