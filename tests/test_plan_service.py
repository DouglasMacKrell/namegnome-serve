"""Tests for default plan engine factory wiring (Sprint T3-03)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

from namegnome_serve.core.plan_engine import PlanEngine
from namegnome_serve.routes.schemas import MediaFile, PlanItem, SourceRef


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


@pytest.mark.asyncio
async def test_build_plan_review_payload_aggregates_origins() -> None:
    from namegnome_serve.core.plan_service import build_plan_review_payload

    deterministic = AsyncMock()
    deterministic.map_media_file.side_effect = [
        PlanItem(
            src_path=Path("/tv/ShowA/S01E01.mkv"),
            dst_path=Path("/library/ShowA/Season 01/ShowA - S01E01.mkv"),
            reason="deterministic",
            confidence=1.0,
            sources=[SourceRef(provider="tvdb", id="a1")],
        ),
        None,
    ]

    fuzzy = Mock()
    fuzzy.generate_tv_plan.return_value = [
        PlanItem(
            src_path=Path("/tv/ShowB/S02E05-E06.mkv"),
            dst_path=Path(
                "/library/ShowB/Season 02/ShowB - S02E05-E06 - Double Episode.mkv"
            ),
            reason="llm",
            confidence=0.78,
            sources=[SourceRef(provider="tmdb", id="b1")],
            warnings=["anthology_guess"],
        )
    ]

    engine = PlanEngine(deterministic, fuzzy)

    media_items: Sequence[tuple[MediaFile, Sequence[dict[str, object]] | None]] = [
        (
            MediaFile(
                path=Path("/tv/ShowA/S01E01.mkv"),
                size=1024,
                mtime=0,
                parsed_title="ShowA",
                parsed_season=1,
                parsed_episode=1,
            ),
            [],
        ),
        (
            MediaFile(
                path=Path("/tv/ShowB/S02E05-E06.mkv"),
                size=2048,
                mtime=0,
                parsed_title="ShowB",
                parsed_season=2,
                parsed_episode=5,
                anthology_candidate=True,
            ),
            [
                {"id": "cand1", "seasonNumber": 2, "number": 5},
                {"id": "cand2", "seasonNumber": 2, "number": 6},
            ],
        ),
    ]

    review = await build_plan_review_payload(
        engine=engine,
        media_type="tv",
        items=media_items,
        plan_id="pln_unit",
        scan_id="scan_unit",
        generated_at=datetime(2025, 1, 2, tzinfo=UTC),
    )

    assert review["plan_id"] == "pln_unit"
    assert review["scan_id"] == "scan_unit"
    assert review["summary"]["by_origin"] == {"deterministic": 1, "llm": 1}
    assert review["summary"]["by_confidence"] == {"high": 1, "medium": 1, "low": 0}
    assert review["summary"]["warnings"] == 1
    assert len(review["groups"]) == 2
    assert {group["group_key"] for group in review["groups"]} == {
        "/tv/ShowA/S01E01.mkv",
        "/tv/ShowB/S02E05-E06.mkv",
    }
