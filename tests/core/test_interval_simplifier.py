"""Unit tests for deterministic anthology interval simplification."""

from __future__ import annotations

from pathlib import Path

import pytest

from namegnome_serve.core.anthology import SimplifyResult, interval_simplify
from namegnome_serve.routes.schemas import MediaFile


def _media_file_with_segments(
    segments: list[dict[str, object]],
    *,
    season: int = 7,
    episode: int = 1,
) -> MediaFile:
    """Helper to build a MediaFile with predefined segments."""

    return MediaFile(
        path=Path("/tv/Show/Show - S07E01.mkv"),
        size=1,
        parsed_title="Show",
        parsed_season=season,
        parsed_episode=episode,
        anthology_candidate=True,
        segments=segments,
    )


def _provider_episodes() -> list[dict[str, object]]:
    """Return a default provider episode list for tests."""

    return [
        {"seasonNumber": 7, "number": 1, "name": "Opening Adventure"},
        {"seasonNumber": 7, "number": 2, "name": "Second Mission"},
        {"seasonNumber": 7, "number": 3, "name": "The New Pup"},
        {"seasonNumber": 7, "number": 4, "name": "Lighthouse Rescue"},
        {"seasonNumber": 7, "number": 5, "name": "Mighty Pups Save The Day"},
        {"seasonNumber": 7, "number": 6, "name": "Closing Ceremony"},
    ]


def test_interval_simplify_singleton_collapse() -> None:
    """A single range with a unique title should collapse to one episode."""

    media_file = _media_file_with_segments(
        [
            {
                "start": 3,
                "end": 4,
                "title_tokens": ["new", "pup"],
                "raw_span": "E03-E04",
                "source": "filename",
            }
        ],
        episode=3,
    )

    result = interval_simplify(media_file, _provider_episodes())

    assert isinstance(result, SimplifyResult)
    assert [segment.model_dump() for segment in result.segments] == [
        {
            "start": 3,
            "end": 3,
            "title_tokens": ["new", "pup"],
            "raw_span": "E03",
            "source": "filename",
        }
    ]
    assert "singleton_collapse" in result.warnings
    assert result.confidence == pytest.approx(0.95, abs=1e-6)
    assert result.punt_to_llm is False


def test_interval_simplify_overlap_boundary_resolved() -> None:
    """Boundary overlap should be trimmed deterministically."""

    media_file = _media_file_with_segments(
        [
            {
                "start": 3,
                "end": 4,
                "title_tokens": ["mighty"],
                "raw_span": "E03-E04",
                "source": "filename",
            },
            {
                "start": 4,
                "end": 5,
                "title_tokens": ["rescue"],
                "raw_span": "E04-E05",
                "source": "filename",
            },
        ],
        episode=3,
    )

    result = interval_simplify(media_file, _provider_episodes())

    segments = [segment.model_dump() for segment in result.segments]
    assert segments == [
        {
            "start": 3,
            "end": 3,
            "title_tokens": ["mighty"],
            "raw_span": "E03",
            "source": "filename",
        },
        {
            "start": 4,
            "end": 5,
            "title_tokens": ["rescue"],
            "raw_span": "E04-E05",
            "source": "filename",
        },
    ]
    assert "overlap_resolved" in result.warnings
    assert result.confidence == pytest.approx(0.9, abs=1e-6)
    assert result.punt_to_llm is False


def test_interval_simplify_clamps_out_of_bounds() -> None:
    """Segments outside provider bounds should clamp and reduce confidence."""

    media_file = _media_file_with_segments(
        [
            {
                "start": 0,
                "end": 2,
                "title_tokens": ["opening"],
                "raw_span": "E00-E02",
                "source": "filename",
            }
        ],
        episode=1,
    )

    result = interval_simplify(media_file, _provider_episodes())

    assert [segment.model_dump() for segment in result.segments] == [
        {
            "start": 1,
            "end": 2,
            "title_tokens": ["opening"],
            "raw_span": "E01-E02",
            "source": "filename",
        }
    ]
    assert "out_of_bounds" in result.warnings
    assert result.confidence == pytest.approx(0.9, abs=1e-6)
    assert result.punt_to_llm is False


def test_interval_simplify_detects_gap_and_punts() -> None:
    """Gaps between segments should trigger LLM punt."""

    media_file = _media_file_with_segments(
        [
            {
                "start": 1,
                "end": 1,
                "title_tokens": ["opening"],
                "raw_span": "E01",
                "source": "filename",
            },
            {
                "start": 3,
                "end": 3,
                "title_tokens": ["mission"],
                "raw_span": "E03",
                "source": "filename",
            },
        ],
        episode=1,
    )

    result = interval_simplify(media_file, _provider_episodes())

    assert "gap_unresolved" in result.warnings
    assert result.punt_to_llm is True
    assert result.confidence <= 0.7


def test_interval_simplify_unresolved_overlap_sets_punt() -> None:
    """Complex overlaps that cannot be resolved deterministically should punt."""

    media_file = _media_file_with_segments(
        [
            {
                "start": 3,
                "end": 5,
                "title_tokens": ["multi"],
                "raw_span": "E03-E05",
                "source": "filename",
            },
            {
                "start": 4,
                "end": 6,
                "title_tokens": ["overlap"],
                "raw_span": "E04-E06",
                "source": "filename",
            },
        ],
        episode=3,
    )

    result = interval_simplify(media_file, _provider_episodes())

    assert "overlap_unresolved" in result.warnings
    assert result.punt_to_llm is True
    assert result.confidence <= 0.7
