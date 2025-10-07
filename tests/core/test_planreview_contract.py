import json
import pathlib
from collections.abc import Iterable
from datetime import UTC, datetime

from jsonschema import validate

from namegnome_serve.core.plan_review import (
    PlanReviewSourceInput,
    build_plan_review,
)
from namegnome_serve.routes.schemas import MediaFile, PlanItem, SourceRef

SCHEMA = json.loads(pathlib.Path("schemas/plan_review.schema.json").read_text())
EXAMPLE = json.loads(
    pathlib.Path("tests/fixtures/plan_review_example.json").read_text()
)


def test_planreview_validates_against_schema():
    validate(instance=EXAMPLE, schema=SCHEMA)


def test_ordering_and_grouping_are_stable():
    items = EXAMPLE["items"]
    assert items == sorted(
        items, key=lambda i: (i["src"]["path"].lower(), i["dst"]["path"].lower())
    )


def test_summary_counts_match_items():
    s = EXAMPLE["summary"]
    by_origin = dict.fromkeys(("deterministic", "llm"), 0)
    by_bucket = dict.fromkeys(("high", "medium", "low"), 0)
    for it in EXAMPLE["items"]:
        by_origin[it["origin"]] += 1
        by_bucket[it["confidence_bucket"]] += 1
    assert s["by_origin"] == by_origin
    assert s["by_confidence"] == by_bucket
    assert s["total_items"] == len(EXAMPLE["items"])


def _media_file(
    path: str,
    *,
    size: int,
    hash: str | None,
    parsed_title: str | None,
    parsed_season: int | None = None,
    parsed_episode: int | None = None,
    needs_disambiguation: bool = False,
    anthology_candidate: bool = False,
) -> MediaFile:
    return MediaFile(
        path=pathlib.Path(path),
        size=size,
        hash=hash,
        parsed_title=parsed_title,
        parsed_season=parsed_season,
        parsed_episode=parsed_episode,
        needs_disambiguation=needs_disambiguation,
        anthology_candidate=anthology_candidate,
    )


def _plan_item(
    src_path: str,
    dst_path: str,
    *,
    confidence: float,
    provider: str,
    provider_id: str,
    reason: str,
    warnings: Iterable[str] | None = None,
) -> PlanItem:
    return PlanItem(
        src_path=pathlib.Path(src_path),
        dst_path=pathlib.Path(dst_path),
        reason=reason,
        confidence=confidence,
        sources=[SourceRef(provider=provider, id=provider_id)],
        warnings=list(warnings or []),
    )


def _sample_inputs() -> list[PlanReviewSourceInput]:
    src_a = "/library/in/ShowA - S01E01.mkv"
    dst_a = "/library/out/ShowA (2021)/Season 01/ShowA - S01E01 - Pilot.mkv"
    mf_a = _media_file(
        src_a,
        size=1024,
        hash="hash-a",
        parsed_title="ShowA",
        parsed_season=1,
        parsed_episode=1,
    )
    det_a = _plan_item(
        src_a,
        dst_a,
        confidence=1.0,
        provider="tvdb",
        provider_id="tvdb-001",
        reason="Matched deterministically",
    )

    src_b = "/library/in/ShowB - S02E05-E06.mkv"
    dst_b_det = (
        "/library/out/ShowB (2019)/Season 02/ShowB - S02E05-E06 - Double Episode.mkv"
    )
    dst_b_llm_alt = (
        "/library/out/ShowB (2019)/Season 02/ShowB - S02E07 - Bonus Mission.mkv"
    )

    mf_b = _media_file(
        src_b,
        size=2048,
        hash="hash-b",
        parsed_title="ShowB",
        parsed_season=2,
        parsed_episode=5,
        needs_disambiguation=True,
        anthology_candidate=True,
    )

    det_b = _plan_item(
        src_b,
        dst_b_det,
        confidence=0.92,
        provider="tvdb",
        provider_id="tvdb-055",
        reason="Deterministic range",
        warnings=["range_trimmed"],
    )
    llm_b_tie = _plan_item(
        src_b,
        dst_b_det,
        confidence=0.88,
        provider="tmdb",
        provider_id="tmdb-055",
        reason="LLM suggested same span",
        warnings=["requires_manual_review"],
    )
    llm_b_extra = _plan_item(
        src_b,
        dst_b_llm_alt,
        confidence=0.75,
        provider="tmdb",
        provider_id="tmdb-056",
        reason="LLM inferred follow-up segment",
        warnings=["anthology_guess"],
    )

    return [
        PlanReviewSourceInput(
            media_file=mf_a,
            deterministic=[det_a],
            llm=[],
        ),
        PlanReviewSourceInput(
            media_file=mf_b,
            deterministic=[det_b],
            llm=[llm_b_tie, llm_b_extra],
        ),
    ]


def test_plan_review_builder_combines_sources_and_summaries():
    review = build_plan_review(
        media_type="tv",
        sources=_sample_inputs(),
        plan_id="pln_test",
        scan_id="scan_test",
        generated_at=datetime(2025, 1, 1, tzinfo=UTC),
    )

    validate(instance=review, schema=SCHEMA)

    assert review["plan_id"] == "pln_test"
    assert review["schema_version"] == "1.0"
    assert review["generated_at"] == "2025-01-01T00:00:00Z"
    assert review["summary"]["total_items"] == len(review["items"])
    assert review["summary"]["by_origin"] == {"deterministic": 2, "llm": 1}
    assert review["summary"]["by_confidence"] == {
        "high": 2,
        "medium": 1,
        "low": 0,
    }
    assert review["summary"]["warnings"] == 3
    assert review["summary"]["anthology_candidates"] == 2
    assert review["summary"]["disambiguations_required"] == 2

    item_ids = [item["id"] for item in review["items"]]
    assert item_ids == sorted(item_ids)

    paths = [item["src"]["path"] for item in review["items"]]
    assert paths == sorted(paths, key=str.lower)

    groups = review["groups"]
    assert len(groups) == 2
    group_keys = [group["group_key"] for group in groups]
    assert group_keys == sorted(group_keys, key=str.lower)

    group_b = next(
        g for g in groups if g["group_key"].endswith("ShowB - S02E05-E06.mkv")
    )
    assert group_b["rollup"]["count"] == 2
    assert "tie_breaker_deterministic_preferred" in " ".join(
        group_b["rollup"]["warnings"]
    )

    det_b_item = next(
        item
        for item in review["items"]
        if item["dst"]["path"].endswith("Double Episode.mkv")
    )
    assert det_b_item["origin"] == "deterministic"
    assert "tie_breaker_deterministic_preferred" in det_b_item["warnings"]
    assert det_b_item["confidence_bucket"] == "high"
    assert det_b_item["alternatives"]
    alt = det_b_item["alternatives"][0]
    assert alt["origin"] == "llm"
    assert alt["confidence"] == 0.88
    assert alt["dst"]["path"].endswith("Double Episode.mkv")

    llm_item = next(item for item in review["items"] if item["origin"] == "llm")
    assert llm_item["confidence_bucket"] == "medium"
    assert "anthology_guess" in llm_item["warnings"]
    assert llm_item["anthology"] is True
    assert llm_item["disambiguation"] is not None


def test_plan_review_builder_is_byte_stable():
    sources = _sample_inputs()
    fixed = datetime(2025, 1, 1, tzinfo=UTC)
    review_1 = build_plan_review(
        media_type="tv",
        sources=sources,
        plan_id="pln_test",
        scan_id="scan_test",
        generated_at=fixed,
    )
    review_2 = build_plan_review(
        media_type="tv",
        sources=_sample_inputs(),
        plan_id="pln_test",
        scan_id="scan_test",
        generated_at=fixed,
    )

    encoded_1 = json.dumps(review_1, sort_keys=True)
    encoded_2 = json.dumps(review_2, sort_keys=True)
    assert encoded_1 == encoded_2
