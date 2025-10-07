"""Plan engine tests for deterministic + LLM orchestration (Sprint T3-03)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest

from namegnome_serve.core.plan_engine import PlanEngine
from namegnome_serve.core.plan_review import PlanReviewSourceInput
from namegnome_serve.routes.schemas import MediaFile, PlanItem, SourceRef


def _dummy_plan() -> PlanItem:
    return PlanItem(
        src_path="/tv/show/file.mkv",
        dst_path="/tv/show/Season 01/show - S01E01.mkv",
        reason="deterministic",
        confidence=1.0,
        sources=[SourceRef(provider="tvdb", id="123")],
    )


@pytest.mark.asyncio
async def test_plan_engine_returns_deterministic_plan() -> None:
    deterministic = AsyncMock()
    deterministic.map_media_file.return_value = _dummy_plan()
    fuzzy = Mock()

    engine = PlanEngine(deterministic, fuzzy)

    media_file = MediaFile(path="/a.mkv", size=1, mtime=0, parsed_title="Show")
    result = await engine.generate_plan(media_file, "tv", provider_candidates=[])

    assert len(result) == 1
    assert result[0].reason == "deterministic"
    deterministic.map_media_file.assert_awaited_once_with(media_file, "tv")
    fuzzy.generate_tv_plan.assert_not_called()

    inputs = await engine.generate_plan_inputs(media_file, "tv", provider_candidates=[])
    assert isinstance(inputs, PlanReviewSourceInput)
    assert len(inputs.deterministic) == 1
    assert inputs.llm == []


@pytest.mark.asyncio
async def test_plan_engine_invokes_llm_for_anthology() -> None:
    deterministic = AsyncMock()
    deterministic.map_media_file.return_value = None
    fuzzy = Mock()
    fuzzy.generate_tv_plan.return_value = ["llm_result"]

    engine = PlanEngine(deterministic, fuzzy)

    media_file = MediaFile(
        path="/tv/Show/S01E01-E03.mkv",
        size=10,
        mtime=0,
        parsed_title="Show",
        anthology_candidate=True,
    )

    provider_candidates: list[dict[str, Any]] = [
        {"id": "dup", "seasonNumber": 1, "number": 2},
        {"id": "b", "seasonNumber": 2, "number": 1},
        {"id": "dup", "seasonNumber": 1, "number": 2, "name": "S1E2"},
        {"id": "a", "seasonNumber": 1, "number": 1, "name": "S1E1"},
    ]

    result = await engine.generate_plan(media_file, "tv", provider_candidates)

    assert result == ["llm_result"]
    deterministic.map_media_file.assert_awaited_once()
    fuzzy.generate_tv_plan.assert_called_once()
    _, llm_candidates = fuzzy.generate_tv_plan.call_args[0]
    assert [c["id"] for c in llm_candidates] == ["a", "dup", "b"]
    assert llm_candidates[0]["seasonNumber"] == 1
    assert llm_candidates[1]["number"] == 2

    inputs = await engine.generate_plan_inputs(
        media_file, "tv", provider_candidates=provider_candidates
    )
    assert isinstance(inputs, PlanReviewSourceInput)
    assert inputs.deterministic == []
    assert inputs.llm == ["llm_result"]


@pytest.mark.asyncio
async def test_plan_engine_handles_missing_candidates() -> None:
    deterministic = AsyncMock()
    deterministic.map_media_file.return_value = None
    fuzzy = Mock()
    engine = PlanEngine(deterministic, fuzzy)

    media_file = MediaFile(path="/tv/Show.mkv", size=1, mtime=0, parsed_title="Show")

    result = await engine.generate_plan(media_file, "tv", provider_candidates=None)

    assert result == []
    fuzzy.generate_tv_plan.assert_not_called()


@pytest.mark.asyncio
async def test_plan_engine_fetches_candidates_when_missing() -> None:
    """Plan engine should fetch provider candidates when none supplied."""

    deterministic = AsyncMock()
    deterministic.map_media_file.return_value = None

    episode_fetcher = AsyncMock()
    episode_fetcher.fetch.return_value = [
        {"id": "c1", "name": "Segment A", "seasonNumber": 1, "number": 1},
        {"id": "c2", "name": "Segment B", "seasonNumber": 1, "number": 2},
    ]

    fuzzy = Mock()
    fuzzy.generate_tv_plan.return_value = ["llm_result"]

    engine = PlanEngine(
        deterministic,
        fuzzy,
        episode_fetcher=episode_fetcher,
    )

    media_file = MediaFile(
        path="/tv/Show/S01E01-E02.mkv",
        size=1,
        mtime=0,
        parsed_title="Show",
        anthology_candidate=True,
    )

    result = await engine.generate_plan(media_file, "tv")

    assert result == ["llm_result"]
    episode_fetcher.fetch.assert_awaited_once_with(media_file)
    fuzzy.generate_tv_plan.assert_called_once()


@pytest.mark.asyncio
async def test_plan_engine_default_fetcher_end_to_end() -> None:
    """Default engine wiring should fetch from TVDB and route through LLM."""

    class FakeRunnable:
        def __init__(self, response: dict[str, Any]) -> None:
            self.response = response
            self.calls: list[dict[str, Any]] = []

        def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
            self.calls.append(payload)
            return self.response

    deterministic = AsyncMock()
    deterministic.map_media_file.return_value = None

    tvdb = AsyncMock()
    tvdb.search_series.return_value = [
        {"id": 42, "seriesName": "Paw Patrol", "year": "2013"}
    ]
    tvdb.get_series_episodes.return_value = [
        {
            "id": "ep701",
            "episodeName": "Mighty Pups Part 1",
            "airedSeason": 7,
            "airedEpisodeNumber": 1,
        },
        {
            "id": "ep702",
            "episodeName": "Mighty Pups Part 2",
            "airedSeason": 7,
            "airedEpisodeNumber": 2,
        },
        {
            "id": "ep703",
            "episodeName": "Third Segment",
            "airedSeason": 7,
            "airedEpisodeNumber": 3,
        },
    ]
    deterministic.tvdb = tvdb

    fake_llm = FakeRunnable(
        {
            "assignments": [
                {
                    "season": 7,
                    "episode_start": 1,
                    "episode_end": 2,
                    "episode_title": "Mighty Pups",
                    "provider": {"provider": "tvdb", "id": "ep701"},
                    "confidence": 0.68,
                    "warnings": ["Needs anthology review"],
                }
            ]
        }
    )

    from namegnome_serve.core.llm_mapper import FuzzyLLMMapper

    fuzzy = FuzzyLLMMapper(fake_llm)
    engine = PlanEngine(deterministic, fuzzy)

    media_file = MediaFile(
        path="/tv/Paw Patrol/Paw Patrol - S07E01-E02.mkv",
        size=1,
        mtime=0,
        parsed_title="Paw Patrol",
        parsed_season=7,
        anthology_candidate=True,
    )

    result = await engine.generate_plan(media_file, "tv")

    assert len(result) == 1
    plan_item = result[0]
    assert "S07E01-E02" in str(plan_item.dst_path)
    assert plan_item.confidence == pytest.approx(0.68)
    assert any("anthology" in warning.lower() for warning in plan_item.warnings)
    assert fake_llm.calls, "LLM should receive payload"
    tvdb.search_series.assert_awaited_once()
    tvdb.get_series_episodes.assert_awaited_once_with(42)
