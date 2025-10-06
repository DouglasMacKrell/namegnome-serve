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
