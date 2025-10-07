"""Factory helpers for constructing plan engines with default dependencies."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from namegnome_serve.chains.fuzzy import create_fuzzy_tv_mapper
from namegnome_serve.core.deterministic_mapper import DeterministicMapper
from namegnome_serve.core.episode_fetcher import EpisodeCandidateFetcher
from namegnome_serve.core.llm_mapper import FuzzyLLMMapper, RunnableProtocol
from namegnome_serve.core.plan_engine import PlanEngine
from namegnome_serve.core.plan_review import (
    MediaType,
    PlanReviewSourceInput,
    build_plan_review,
)
from namegnome_serve.routes.schemas import MediaFile


def create_plan_engine(
    *,
    deterministic: DeterministicMapper | None = None,
    fuzzy: FuzzyLLMMapper | None = None,
    llm: RunnableProtocol | None = None,
) -> PlanEngine:
    """Build a plan engine with deterministic + fuzzy strategies wired together."""

    deterministic_mapper = deterministic or DeterministicMapper()

    fuzzy_mapper = fuzzy or create_fuzzy_tv_mapper(llm=llm)

    tvdb_client = getattr(deterministic_mapper, "tvdb", None)
    episode_fetcher = EpisodeCandidateFetcher(tvdb_client)

    return PlanEngine(
        deterministic_mapper,
        fuzzy_mapper,
        episode_fetcher=episode_fetcher,
    )


async def build_plan_review_payload(
    *,
    engine: PlanEngine,
    media_type: MediaType,
    items: Sequence[tuple[MediaFile, Sequence[dict[str, Any]] | None]],
    plan_id: str | None = None,
    scan_id: str | None = None,
    source_fingerprint: str | None = None,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Assemble a PlanReview payload for a batch of media files."""

    sources: list[PlanReviewSourceInput] = []
    for media_file, raw_candidates in items:
        prepared_candidates = (
            [dict(candidate) for candidate in raw_candidates]
            if raw_candidates
            else None
        )
        inputs = await engine.generate_plan_inputs(
            media_file,
            media_type,
            provider_candidates=prepared_candidates,
        )
        sources.append(inputs)

    return build_plan_review(
        media_type=media_type,
        sources=sources,
        plan_id=plan_id,
        scan_id=scan_id,
        source_fingerprint=source_fingerprint,
        generated_at=generated_at,
    )
