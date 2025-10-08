"""Tests for plan chain orchestration returning PlanReview payloads."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import pytest

from namegnome_serve.core.plan_review import PlanReviewSourceInput
from namegnome_serve.routes.schemas import MediaFile, PlanItem, ScanResult, SourceRef


class StubPlanEngine:
    """Minimal engine stub returning deterministic or LLM outputs."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, Sequence[dict[str, object]] | None]] = []

    async def generate_plan_inputs(
        self,
        media_file: MediaFile,
        media_type: str,
        provider_candidates: Sequence[dict[str, object]] | None = None,
    ) -> PlanReviewSourceInput:
        self.calls.append((str(media_file.path), provider_candidates))

        if media_file.parsed_title == "Deterministic":
            return PlanReviewSourceInput(
                media_file=media_file,
                deterministic=[
                    PlanItem(
                        src_path=media_file.path,
                        dst_path=Path("/out/Deterministic.mkv"),
                        reason="deterministic",
                        confidence=1.0,
                        sources=[SourceRef(provider="tvdb", id="det-1")],
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
                    dst_path=Path("/out/LLM.mkv"),
                    reason="llm",
                    confidence=0.72,
                    sources=[SourceRef(provider="tmdb", id="llm-1")],
                    warnings=["anthology_guess"],
                )
            ],
        )


@pytest.fixture()
def sample_scan() -> ScanResult:
    media_files = [
        MediaFile(
            path=Path("/tv/d.mkv"),
            size=10,
            mtime=0,
            parsed_title="Deterministic",
        ),
        MediaFile(
            path=Path("/tv/l.mkv"),
            size=20,
            mtime=0,
            parsed_title="LLM",
            anthology_candidate=True,
        ),
    ]

    return ScanResult(
        root_path=Path("/tv"),
        media_type="tv",
        files=media_files,
        total_size=sum(item.size for item in media_files),
        file_count=len(media_files),
    )


@pytest.mark.asyncio
async def test_plan_chain_returns_plan_review(sample_scan: ScanResult) -> None:
    from namegnome_serve.chains.plan_chain import PlanChain

    engine = StubPlanEngine()
    chain = PlanChain(engine)

    review = await chain.plan(
        scan_result=sample_scan,
        plan_id="pln_chain",
        scan_id="scan_chain",
        generated_at=datetime(2025, 1, 5, tzinfo=UTC),
    )

    assert review["plan_id"] == "pln_chain"
    assert review["scan_id"] == "scan_chain"
    assert review["summary"]["by_origin"] == {"deterministic": 1, "llm": 1}
    assert len(review["items"]) == 2
    assert engine.calls[0][0] == "/tv/d.mkv"
    assert engine.calls[1][0] == "/tv/l.mkv"


@pytest.mark.asyncio
async def test_plan_chain_can_return_json(sample_scan: ScanResult) -> None:
    from namegnome_serve.chains.plan_chain import PlanChain

    engine = StubPlanEngine()
    chain = PlanChain(engine)

    payload = await chain.plan(
        scan_result=sample_scan,
        plan_id="pln_chain",
        generated_at=datetime(2025, 1, 5, tzinfo=UTC),
        as_json=True,
    )

    assert isinstance(payload, str)
    assert '"plan_id":"pln_chain"' in payload
