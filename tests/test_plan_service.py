"""Tests for default plan engine factory wiring (Sprint T3-03)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

from namegnome_serve.routes.schemas import MediaFile


class DummyDeterministic:
    """Deterministic mapper stub that always defers to LLM fallback."""

    def __init__(self) -> None:
        self.map_media_file = AsyncMock(return_value=None)
        self.tvdb = Mock()
        self.tvdb.search_series = AsyncMock(
            return_value=[{"id": 10, "name": "Show", "seriesName": "Show"}]
        )
        self.tvdb.get_series_episodes = AsyncMock(
            return_value=[
                {
                    "id": "ep1",
                    "name": "Episode One",
                    "seasonNumber": 1,
                    "number": 1,
                },
                {
                    "id": "ep2",
                    "name": "Episode Two",
                    "seasonNumber": 1,
                    "number": 2,
                },
            ]
        )


class DummyFuzzy:
    """Fuzzy mapper stub that records candidates provided by factory."""

    def __init__(self) -> None:
        self.generate_tv_plan = Mock(return_value=["fuzzy-plan"])


@pytest.mark.asyncio
async def test_create_plan_engine_fetches_candidates() -> None:
    """Factory wires episode fetcher and routes fallback to fuzzy mapper."""

    from namegnome_serve.core.plan_service import create_plan_engine

    deterministic = DummyDeterministic()
    fuzzy = DummyFuzzy()

    engine = create_plan_engine(deterministic=deterministic, fuzzy=fuzzy)

    media_file = MediaFile(
        path=Path("/tv/Show/Show - S01E01.mkv"),
        size=1,
        mtime=0,
        parsed_title="Show",
        parsed_season=1,
        parsed_episode=1,
        anthology_candidate=True,
    )

    plans = await engine.generate_plan(media_file, "tv")

    assert plans == ["fuzzy-plan"]
    deterministic.map_media_file.assert_awaited_once_with(media_file, "tv")
    deterministic.tvdb.search_series.assert_awaited_once_with("Show")
    fuzzy.generate_tv_plan.assert_called_once()
    _, provided_candidates = fuzzy.generate_tv_plan.call_args[0]
    assert [candidate["id"] for candidate in provided_candidates] == ["ep1", "ep2"]
