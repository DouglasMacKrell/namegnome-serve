"""Integration tests for TVMaze API (public, no authentication required)."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_tvmaze_real_search() -> None:
    """Search for a known series and verify response structure."""

    from namegnome_serve.metadata.providers.tvmaze import TVMazeProvider

    async with TVMazeProvider() as provider:
        results = await provider.search_series("Firebuds")

        assert isinstance(results, list)
        assert len(results) > 0

        top = results[0]
        assert "id" in top
        assert "name" in top
        assert isinstance(top["id"], int)
        assert isinstance(top["name"], str)

        print(
            f"✅ TVMaze search returned {len(results)} results; first='{top['name']}'"
        )


@pytest.mark.asyncio
async def test_tvmaze_real_episode_lookup() -> None:
    """Fetch real episode data for a known series."""

    from namegnome_serve.metadata.providers.tvmaze import TVMazeProvider

    async with TVMazeProvider() as provider:
        shows = await provider.search_series("Firebuds")
        assert shows, "Expected at least one show"
        series_id = shows[0]["id"]

        episode = await provider.get_episode(series_id, season=1, episode=1)

        assert episode is not None
        assert episode.get("season") == 1
        assert episode.get("number") == 1
        assert "name" in episode

        print(
            "✅ TVMaze episode lookup succeeded:"
            f" S{episode['season']}E{episode['number']} - {episode['name']}"
        )


@pytest.mark.asyncio
async def test_tvmaze_real_missing_episode_returns_none() -> None:
    """A non-existent episode should return None instead of raising."""

    from namegnome_serve.metadata.providers.tvmaze import TVMazeProvider

    async with TVMazeProvider() as provider:
        shows = await provider.search_series("Firebuds")
        assert shows, "Expected at least one show"
        series_id = shows[0]["id"]

        missing = await provider.get_episode(series_id, season=99, episode=1)

        assert missing is None
        print("✅ TVMaze returns None when episode is not found")
