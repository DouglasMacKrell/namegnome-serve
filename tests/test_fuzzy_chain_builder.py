"""Tests for default fuzzy mapper builder wiring."""

from __future__ import annotations

from pathlib import Path

import pytest

from namegnome_serve.chains.fuzzy import create_fuzzy_tv_mapper
from namegnome_serve.routes.schemas import MediaFile


class StubChatModel:
    """Minimal chat model stub returning deterministic JSON."""

    def __init__(self) -> None:
        self.calls: list[list[object]] = []

    def invoke(self, messages: list[object], **_: object) -> object:
        self.calls.append(messages)
        return type(
            "StubResponse",
            (),
            {
                "content": """{
                    "assignments": [
                        {
                            "season": 1,
                            "episode_start": 1,
                            "episode_end": 1,
                            "episode_title": "Pilot",
                            "provider": {"provider": "tvdb", "id": "ep1"},
                            "confidence": 0.62
                        }
                    ]
                }"""
            },
        )()


def test_create_fuzzy_tv_mapper_uses_supplied_llm() -> None:
    """Builder should wrap supplied LLM and return working mapper."""

    stub_model = StubChatModel()
    mapper = create_fuzzy_tv_mapper(llm=stub_model)

    media_file = MediaFile(
        path=Path("/tv/Show/S01E01.mkv"),
        size=1,
        mtime=0,
        parsed_title="Show",
        parsed_season=1,
        parsed_episode=1,
    )
    provider_candidates = [
        {"id": "ep1", "name": "Pilot", "seasonNumber": 1, "number": 1},
    ]

    plan_items = mapper.generate_tv_plan(media_file, provider_candidates)

    assert len(plan_items) == 1
    assert str(plan_items[0].dst_path) == "/tv/Show/Season 01/Show - S01E01 - Pilot.mkv"
    assert plan_items[0].confidence == pytest.approx(0.62)
    assert stub_model.calls, "LLM should receive prompt messages"
