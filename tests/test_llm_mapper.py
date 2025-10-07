"""TDD suite for fuzzy LLM-assisted mapper (Sprint T3-03)."""

from __future__ import annotations

from typing import Any

import pytest

from namegnome_serve.core.llm_mapper import FuzzyLLMMapper, build_tv_fuzzy_chain
from namegnome_serve.routes.schemas import MediaFile


class FakeRunnable:
    """Simple stub that captures prompt payloads and returns fixed output."""

    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(payload)
        return self.response


@pytest.fixture()
def mapper() -> FuzzyLLMMapper:
    """Fuzzy mapper wired with fake LLM and deterministic helper."""

    fake_llm = FakeRunnable(
        {
            "assignments": [
                {
                    "season": 1,
                    "episode_start": 1,
                    "episode_end": 1,
                    "episode_title": "Ready to Roll",
                    "provider": {"provider": "tvdb", "id": "ep1"},
                    "confidence": 0.72,
                    "warnings": ["LLM fuzzy match"],
                },
                {
                    "season": 1,
                    "episode_start": 2,
                    "episode_end": 3,
                    "episode_title": "Double Feature",
                    "provider": {"provider": "tvdb", "id": "ep2"},
                    "confidence": 0.65,
                    "warnings": [],
                },
            ]
        }
    )
    return FuzzyLLMMapper(fake_llm)


def test_llm_mapper_returns_plan_items(mapper: FuzzyLLMMapper) -> None:
    """LLM mapper should emit PlanItems per LLM response."""

    media_file = MediaFile(
        path="/tv/Firebuds/Firebuds - S01E01-E03.mkv",
        size=1024,
        mtime=1234567890,
        parsed_title="Firebuds",
        parsed_season=1,
        parsed_episode=1,
        anthology_candidate=True,
    )

    provider_episodes = [
        {"id": "ep1", "name": "Ready to Roll", "seasonNumber": 1, "number": 1},
        {"id": "ep2", "name": "Double Delight", "seasonNumber": 1, "number": 2},
        {"id": "ep3", "name": "Lights Out", "seasonNumber": 1, "number": 3},
    ]

    plan_items = mapper.generate_tv_plan(media_file, provider_episodes)

    assert len(plan_items) == 2

    first, second = plan_items
    assert (
        str(first.dst_path)
        == "/tv/Firebuds/Season 01/Firebuds - S01E01 - Ready to Roll.mkv"
    )
    assert first.confidence == pytest.approx(0.72)
    assert first.sources[0].provider == "tvdb"
    assert first.sources[0].id == "ep1"
    assert "LLM fuzzy match" in first.warnings[0]

    assert (
        str(second.dst_path)
        == "/tv/Firebuds/Season 01/Firebuds - S01E02-E03 - Double Feature.mkv"
    )
    assert second.sources[0].id == "ep2"


def test_llm_mapper_handles_empty_assignments() -> None:
    """Gracefully return empty list when LLM yields no assignments."""

    mapper = FuzzyLLMMapper(FakeRunnable({"assignments": []}))
    media_file = MediaFile(
        path="/tv/Show/S01E01.mkv",
        size=10,
        mtime=0,
        parsed_title="Show",
        parsed_season=1,
        parsed_episode=1,
    )

    result = mapper.generate_tv_plan(media_file, [])
    assert result == []


def test_llm_mapper_validates_response_structure() -> None:
    """Invalid LLM payload should raise ValueError to callers."""

    mapper = FuzzyLLMMapper(FakeRunnable({"unexpected": []}))
    media_file = MediaFile(
        path="/tv/Show/S01E01.mkv",
        size=10,
        mtime=0,
        parsed_title="Show",
        parsed_season=1,
        parsed_episode=1,
    )

    with pytest.raises(ValueError, match="assignments"):
        mapper.generate_tv_plan(media_file, [])


class FakeChatModel:
    """Minimal chat model stub that records messages and returns JSON."""

    def __init__(self) -> None:
        self.calls: list[list[Any]] = []

    def invoke(self, messages: list[Any], **_: Any) -> str:
        self.calls.append(messages)
        return '{"assignments": []}'


def test_build_tv_fuzzy_chain_formats_prompt() -> None:
    """Builder should format prompt, forward to model, and parse JSON."""

    fake_model = FakeChatModel()
    chain = build_tv_fuzzy_chain(fake_model)

    payload = {
        "media": {"title": "Firebuds", "season": 1, "episode": None},
        "candidates": [{"id": "ep1", "name": "Ready"}],
    }

    output = chain.invoke(payload)

    assert output == {"assignments": []}
    assert len(fake_model.calls) == 1
    messages = fake_model.calls[0]
    contents = [msg.content if hasattr(msg, "content") else msg[1] for msg in messages]
    combined = "\n".join(str(text) for text in contents)
    assert "Firebuds" in combined
    assert "assignments" in combined
    assert "adjacency" in combined
    assert "contiguous" in combined


def test_llm_mapper_sorts_assignments_and_backfills_titles() -> None:
    """Assignments should be normalized and ordered."""

    mapper = FuzzyLLMMapper(
        FakeRunnable(
            {
                "assignments": [
                    {
                        "season": 2,
                        "episode_start": 3,
                        "episode_end": 4,
                        "provider": {"provider": "tvdb", "id": "ep34"},
                        "confidence": 0.4,
                    },
                    {
                        "season": 1,
                        "episode_start": 5,
                        "episode_end": 5,
                        "episode_title": "Finale",
                        "provider": {"provider": "tvdb", "id": "ep5"},
                        "confidence": 0.6,
                    },
                ]
            }
        )
    )

    media_file = MediaFile(
        path="/tv/Show/mixed.mkv",
        size=1,
        mtime=0,
        parsed_title="Show",
    )
    provider_candidates = [
        {"id": "ep34", "name": "The Double Act", "seasonNumber": 2, "number": 3},
        {"id": "ep5", "name": "Finale", "seasonNumber": 1, "number": 5},
    ]

    plan_items = mapper.generate_tv_plan(media_file, provider_candidates)

    assert [str(item.dst_path) for item in plan_items] == [
        "/tv/Show/Season 01/Show - S01E05 - Finale.mkv",
        "/tv/Show/Season 02/Show - S02E03-E04 - The Double Act.mkv",
    ]
    assert [item.confidence for item in plan_items] == [0.6, 0.4]


def test_llm_mapper_trims_overlapping_ranges() -> None:
    """Overlapping spans are trimmed and warnings emitted."""

    mapper = FuzzyLLMMapper(
        FakeRunnable(
            {
                "assignments": [
                    {
                        "season": 1,
                        "episode_start": 1,
                        "episode_end": 2,
                        "provider": {"provider": "tvdb", "id": "ep12"},
                    },
                    {
                        "season": 1,
                        "episode_start": 3,
                        "episode_end": 4,
                        "provider": {"provider": "tvdb", "id": "ep34"},
                    },
                    {
                        "season": 1,
                        "episode_start": 4,
                        "episode_end": 5,
                        "provider": {"provider": "tvdb", "id": "ep45"},
                        "episode_title": "Night Rescue",
                    },
                ]
            }
        )
    )

    media_file = MediaFile(
        path="/tv/Show/anthology.mkv",
        size=1,
        mtime=0,
        parsed_title="Show",
        anthology_candidate=True,
    )
    provider_candidates = [
        {"id": "ep12", "name": "Mighty Quest", "seasonNumber": 1, "number": 2},
        {"id": "ep34", "name": "Into the Shadows", "seasonNumber": 1, "number": 3},
        {"id": "ep45", "name": "Night Rescue", "seasonNumber": 1, "number": 4},
        {"id": "ep46", "name": "Bonus", "seasonNumber": 1, "number": 5},
    ]

    plan_items = mapper.generate_tv_plan(media_file, provider_candidates)

    assert [str(item.dst_path) for item in plan_items] == [
        "/tv/Show/Season 01/Show - S01E01-E02 - Mighty Quest.mkv",
        "/tv/Show/Season 01/Show - S01E03 - Into the Shadows.mkv",
        "/tv/Show/Season 01/Show - S01E04-E05 - Night Rescue.mkv",
    ]
    assert any("Trimmed span" in warning for warning in plan_items[1].warnings)
    assert plan_items[1].confidence == pytest.approx(0.5)
