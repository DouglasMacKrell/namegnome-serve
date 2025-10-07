"""Tests for fetching provider episode candidates prior to LLM mapping."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from namegnome_serve.core.episode_fetcher import EpisodeCandidateFetcher
from namegnome_serve.routes.schemas import MediaFile


@pytest.mark.asyncio
async def test_fetcher_requires_title() -> None:
    """Fetcher should short-circuit when no parsed title available."""

    tvdb = AsyncMock()
    fetcher = EpisodeCandidateFetcher(tvdb)

    media_file = MediaFile(path=Path("/tv/unknown.mkv"), size=1, mtime=0)

    result = await fetcher.fetch(media_file)

    assert result == []
    tvdb.search_series.assert_not_called()


@pytest.mark.asyncio
async def test_fetcher_prefers_year_match_and_normalizes() -> None:
    """Fetcher selects series matching parsed year and normalizes episodes."""

    tvdb = AsyncMock()
    tvdb.search_series.return_value = [
        {"id": 10, "seriesName": "Show Redux", "year": "2023"},
        {"id": 7, "seriesName": "Show Classic", "year": "2015"},
    ]
    tvdb.get_series_episodes.return_value = [
        {
            "id": "ep-01",
            "episodeName": "Pilot",
            "airedSeason": 2,
            "airedEpisodeNumber": 3,
        },
        {
            "id": "ep-02",
            "episodeName": "Second Act",
            "airedSeason": 2,
            "airedEpisodeNumber": 4,
        },
    ]

    fetcher = EpisodeCandidateFetcher(tvdb)
    media_file = MediaFile(
        path=Path("/tv/Show/partial.mkv"),
        size=1,
        mtime=0,
        parsed_title="Show",
        parsed_year=2015,
    )

    result = await fetcher.fetch(media_file)

    tvdb.search_series.assert_awaited_once_with("Show")
    tvdb.get_series_episodes.assert_awaited_once_with(7)
    assert result == [
        {"id": "ep-01", "name": "Pilot", "seasonNumber": 2, "number": 3},
        {"id": "ep-02", "name": "Second Act", "seasonNumber": 2, "number": 4},
    ]


@pytest.mark.asyncio
async def test_fetcher_filters_to_parsed_season() -> None:
    """Only episodes from the parsed season should be returned when available."""

    tvdb = AsyncMock()
    tvdb.search_series.return_value = [{"id": 12, "seriesName": "Show"}]
    tvdb.get_series_episodes.return_value = [
        {
            "id": "s1-1",
            "episodeName": "S1E1",
            "airedSeason": 1,
            "airedEpisodeNumber": 1,
        },
        {
            "id": "s2-1",
            "episodeName": "S2E1",
            "airedSeason": 2,
            "airedEpisodeNumber": 1,
        },
    ]

    fetcher = EpisodeCandidateFetcher(tvdb)
    media_file = MediaFile(
        path=Path("/tv/Show/season2.mkv"),
        size=1,
        mtime=0,
        parsed_title="Show",
        parsed_season=2,
    )

    result = await fetcher.fetch(media_file)

    assert result == [
        {"id": "s2-1", "name": "S2E1", "seasonNumber": 2, "number": 1},
    ]


@pytest.mark.asyncio
async def test_fetcher_uses_first_aired_year_when_available() -> None:
    """Fallback to firstAired metadata when explicit year missing."""

    tvdb = AsyncMock()
    tvdb.search_series.return_value = [
        {"id": 30, "seriesName": "Show", "firstAired": "2011-05-01"},
        {"id": 31, "seriesName": "Show", "firstAired": "2019-04-01"},
    ]
    tvdb.get_series_episodes.return_value = [
        {"id": "ep", "episodeName": "Launch", "airedSeason": 1, "airedEpisodeNumber": 1}
    ]

    fetcher = EpisodeCandidateFetcher(tvdb)
    media_file = MediaFile(
        path=Path("/tv/Show/file.mkv"),
        size=1,
        mtime=0,
        parsed_title="Show",
        parsed_year=2011,
    )

    result = await fetcher.fetch(media_file)

    tvdb.get_series_episodes.assert_awaited_once_with(30)
    assert result[0]["id"] == "ep"


def test_normalize_episode_handles_missing_fields() -> None:
    """Normalization should drop invalid payloads gracefully."""

    raw_missing_numbers = {"id": "x1", "episodeName": "Test"}
    assert EpisodeCandidateFetcher._normalize_episode(raw_missing_numbers) is None

    raw_valid = {
        "episode_id": 42,
        "name": "Special",
        "seasonNumber": "3",
        "number": "7",
    }
    normalized = EpisodeCandidateFetcher._normalize_episode(raw_valid)
    assert normalized == {
        "id": "42",
        "name": "Special",
        "seasonNumber": 3,
        "number": 7,
    }
