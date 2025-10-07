"""Tests for default plan engine factory wiring (Sprint T3-03)."""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

from namegnome_serve.core.plan_engine import PlanEngine
from namegnome_serve.core.plan_review import PlanReviewSourceInput
from namegnome_serve.routes.schemas import MediaFile, PlanItem, ScanResult, SourceRef


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


@pytest.mark.asyncio
async def test_plan_scan_result_returns_plan_review() -> None:
    from namegnome_serve.core.plan_service import plan_scan_result

    class FakePlanEngine:
        def __init__(self) -> None:
            self.calls: list[tuple[str, Sequence[dict[str, object]] | None]] = []

        async def generate_plan_inputs(
            self,
            media_file: MediaFile,
            media_type: str,
            provider_candidates: Sequence[dict[str, object]] | None = None,
        ) -> PlanReviewSourceInput:
            self.calls.append((str(media_file.path), provider_candidates))

            if "S01E01" in str(media_file.path):
                return PlanReviewSourceInput(
                    media_file=media_file,
                    deterministic=[
                        PlanItem(
                            src_path=media_file.path,
                            dst_path=Path(
                                "/library/ShowA/Season 01/ShowA - S01E01.mkv"
                            ),
                            reason="deterministic",
                            confidence=1.0,
                            sources=[SourceRef(provider="tvdb", id="a1")],
                        )
                    ],
                    llm=[],
                )

            return PlanReviewSourceInput(
                media_file=media_file,
                deterministic=[],
                llm=[
                    PlanItem(
                        src_path=media_file.path,
                        dst_path=Path(
                            "/library/ShowB/Season 02/"
                            "ShowB - S02E05-E06 - Double Episode.mkv"
                        ),
                        reason="llm",
                        confidence=0.72,
                        sources=[SourceRef(provider="tmdb", id="b1")],
                        warnings=["anthology_guess"],
                    )
                ],
            )

    engine = FakePlanEngine()

    media_files = [
        MediaFile(
            path=Path("/tv/ShowA/S01E01.mkv"),
            size=1024,
            mtime=0,
            parsed_title="ShowA",
            parsed_season=1,
            parsed_episode=1,
        ),
        MediaFile(
            path=Path("/tv/ShowB/S02E05-E06.mkv"),
            size=2048,
            mtime=0,
            parsed_title="ShowB",
            parsed_season=2,
            parsed_episode=5,
            anthology_candidate=True,
        ),
    ]

    scan_result = ScanResult(
        root_path=Path("/tv"),
        media_type="tv",
        files=media_files,
        total_size=sum(file.size for file in media_files),
        file_count=len(media_files),
    )

    candidates = {
        "/tv/ShowB/S02E05-E06.mkv": [
            {"id": "cand1", "seasonNumber": 2, "number": 5},
            {"id": "cand2", "seasonNumber": 2, "number": 6},
        ]
    }

    review = await plan_scan_result(
        engine=engine,
        scan_result=scan_result,
        plan_id="pln_scan",
        scan_id="scan_input",
        candidate_map=candidates,
        generated_at=datetime(2025, 1, 3, tzinfo=UTC),
    )

    assert review["plan_id"] == "pln_scan"
    assert review["scan_id"] == "scan_input"
    assert review["summary"]["by_origin"] == {"deterministic": 1, "llm": 1}
    assert review["summary"]["total_items"] == 2
    assert engine.calls[0][0] == "/tv/ShowA/S01E01.mkv"
    assert engine.calls[1][0] == "/tv/ShowB/S02E05-E06.mkv"
    assert len(engine.calls[0][1] or []) == 0
    assert len(engine.calls[1][1] or []) == 2


@pytest.mark.asyncio
async def test_plan_scan_result_json_is_stable() -> None:
    from namegnome_serve.core.plan_service import plan_scan_result_json

    class NoopEngine:
        async def generate_plan_inputs(
            self,
            media_file: MediaFile,
            media_type: str,
            provider_candidates: Sequence[dict[str, object]] | None = None,
        ) -> PlanReviewSourceInput:
            return PlanReviewSourceInput(
                media_file=media_file,
                deterministic=[
                    PlanItem(
                        src_path=media_file.path,
                        dst_path=media_file.path,
                        reason="noop",
                        confidence=1.0,
                        sources=[SourceRef(provider="tvdb", id="noop")],
                    )
                ],
                llm=[],
            )

    scan_result = ScanResult(
        root_path=Path("/tv"),
        media_type="tv",
        files=[
            MediaFile(path=Path("/tv/file.mkv"), size=1, mtime=0, parsed_title="Show")
        ],
        total_size=1,
        file_count=1,
    )

    payload_1 = await plan_scan_result_json(
        engine=NoopEngine(),
        scan_result=scan_result,
        plan_id="pln_json",
        generated_at=datetime(2025, 1, 4, tzinfo=UTC),
    )

    payload_2 = await plan_scan_result_json(
        engine=NoopEngine(),
        scan_result=scan_result,
        plan_id="pln_json",
        generated_at=datetime(2025, 1, 4, tzinfo=UTC),
    )

    assert payload_1 == payload_2
    parsed = json.loads(payload_1)
    assert parsed["plan_id"] == "pln_json"
