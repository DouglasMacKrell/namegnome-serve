"""Integration tests for anthology planning pipeline (Sprint T3-03)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

from namegnome_serve.core.llm_mapper import FuzzyLLMMapper
from namegnome_serve.routes.schemas import MediaFile


class FakeLLM:
    """LLM stub returning predetermined anthology assignments."""

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def invoke(self, payload: dict[str, object]) -> dict[str, object]:
        self.calls.append(payload)
        return {
            "assignments": [
                {
                    "season": 7,
                    "episode_start": 1,
                    "episode_end": 2,
                    "episode_title": "Mighty Pups",
                    "provider": {"provider": "tvdb", "id": "ep701"},
                    "confidence": 0.68,
                    "warnings": ["Anthology segments inferred"],
                },
                {
                    "season": 7,
                    "episode_start": 3,
                    "episode_end": 3,
                    "episode_title": "Pups Save the Day",
                    "provider": {"provider": "tvdb", "id": "ep703"},
                    "confidence": 0.6,
                },
            ]
        }


class StubDeterministic:
    """Stub deterministic mapper that forces LLM fallback for anthology files."""

    def __init__(self) -> None:
        self.map_media_file = AsyncMock(return_value=None)
        self.tvdb = Mock()
        self.tvdb.search_series = AsyncMock(
            return_value=[{"id": 1234, "name": "Paw Patrol"}]
        )
        self.tvdb.get_series_episodes = AsyncMock(
            return_value=[
                {
                    "id": "ep701",
                    "name": "Mighty Pups Part 1",
                    "seasonNumber": 7,
                    "number": 1,
                },
                {
                    "id": "ep702",
                    "name": "Mighty Pups Part 2",
                    "seasonNumber": 7,
                    "number": 2,
                },
                {
                    "id": "ep703",
                    "name": "Pups Save the Day",
                    "seasonNumber": 7,
                    "number": 3,
                },
            ]
        )


@pytest.mark.asyncio
async def test_anthology_plan_pipeline_produces_contiguous_groups() -> None:
    """Full pipeline should emit anthology plan items with sub-1 confidence."""

    from namegnome_serve.core.plan_service import create_plan_engine

    deterministic = StubDeterministic()
    fake_llm = FakeLLM()
    fuzzy = FuzzyLLMMapper(fake_llm)

    engine = create_plan_engine(deterministic=deterministic, fuzzy=fuzzy)

    media_file = MediaFile(
        path=Path("/fixtures/Paw Patrol - S07E01-E03.mkv"),
        size=42,
        mtime=0,
        parsed_title="Paw Patrol",
        parsed_season=7,
        parsed_episode=1,
        anthology_candidate=True,
    )

    plans = await engine.generate_plan(media_file, "tv")

    assert len(plans) == 2
    first, second = plans
    assert first.confidence < 1.0 and second.confidence < 1.0
    assert "S07E01-E02" in str(first.dst_path)
    assert "S07E03" in str(second.dst_path)
    assert any("Anthology" in warning for warning in first.warnings)
    assert fake_llm.calls, "LLM should have been invoked for anthology pipeline"
