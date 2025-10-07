"""Factory helpers for constructing plan engines with default dependencies."""

from __future__ import annotations

from namegnome_serve.chains.fuzzy import create_fuzzy_tv_mapper
from namegnome_serve.core.deterministic_mapper import DeterministicMapper
from namegnome_serve.core.episode_fetcher import EpisodeCandidateFetcher
from namegnome_serve.core.llm_mapper import FuzzyLLMMapper, RunnableProtocol
from namegnome_serve.core.plan_engine import PlanEngine


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
