"""Planning orchestrator combining deterministic mapping and fuzzy LLM logic."""

from __future__ import annotations

from typing import Any, cast

from namegnome_serve.core.episode_fetcher import EpisodeCandidateFetcher
from namegnome_serve.core.plan_review import PlanReviewSourceInput
from namegnome_serve.routes.schemas import MediaFile, PlanItem


class PlanEngine:
    """Coordinator that prefers deterministic mapping but falls back to LLM."""

    def __init__(
        self,
        deterministic_mapper: Any,
        fuzzy_mapper: Any,
        episode_fetcher: EpisodeCandidateFetcher | None = None,
    ) -> None:
        self._deterministic = deterministic_mapper
        self._fuzzy = fuzzy_mapper

        tvdb = getattr(deterministic_mapper, "tvdb", None)
        self._episode_fetcher: EpisodeCandidateFetcher | None = (
            episode_fetcher
            if episode_fetcher is not None
            else (EpisodeCandidateFetcher(tvdb) if tvdb is not None else None)
        )

    async def generate_plan(
        self,
        media_file: MediaFile,
        media_type: str,
        provider_candidates: list[dict[str, Any]] | None = None,
    ) -> list[PlanItem]:
        inputs = await self.generate_plan_inputs(
            media_file, media_type, provider_candidates=provider_candidates
        )

        if inputs.deterministic:
            return list(inputs.deterministic)
        return list(inputs.llm)

    async def generate_plan_inputs(
        self,
        media_file: MediaFile,
        media_type: str,
        provider_candidates: list[dict[str, Any]] | None = None,
    ) -> PlanReviewSourceInput:
        if media_type == "tv":
            anthology_mapper = getattr(
                self._deterministic, "map_anthology_segments", None
            )
            if callable(anthology_mapper):
                anthology_plan = await anthology_mapper(media_file)
                if anthology_plan:
                    return PlanReviewSourceInput(
                        media_file=media_file,
                        deterministic=list(anthology_plan),
                        llm=[],
                    )

        deterministic_plan = await self._deterministic.map_media_file(
            media_file, media_type
        )

        if deterministic_plan is not None:
            return PlanReviewSourceInput(
                media_file=media_file,
                deterministic=[deterministic_plan],
                llm=[],
            )

        if media_type != "tv":
            return PlanReviewSourceInput(
                media_file=media_file,
                deterministic=[],
                llm=[],
            )

        candidates = provider_candidates
        if not candidates and self._episode_fetcher:
            candidates = await self._episode_fetcher.fetch(media_file)

        if not candidates:
            return PlanReviewSourceInput(
                media_file=media_file,
                deterministic=[],
                llm=[],
            )

        normalized_candidates = self._prepare_tv_candidates(list(candidates))
        plans = self._fuzzy.generate_tv_plan(media_file, normalized_candidates)
        return PlanReviewSourceInput(
            media_file=media_file,
            deterministic=[],
            llm=cast(list[PlanItem], plans),
        )

    @staticmethod
    def _prepare_tv_candidates(
        candidates: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Sort and deduplicate episode candidates for LLM consumption."""

        seen_ids: set[str] = set()
        cleaned: list[dict[str, Any]] = []

        for candidate in candidates:
            identifier = candidate.get("id")
            if identifier is None:
                cleaned.append(dict(candidate))
                continue

            identifier_str = str(identifier)
            if identifier_str in seen_ids:
                continue

            seen_ids.add(identifier_str)
            cleaned.append(dict(candidate))

        def sort_key(item: dict[str, Any]) -> tuple[int, int]:
            season_raw = (
                item.get("seasonNumber")
                or item.get("SeasonNumber")
                or item.get("season")
                or 0
            )
            episode_raw = (
                item.get("number")
                or item.get("episodeNumber")
                or item.get("EpisodeNumber")
                or 0
            )

            try:
                season_val = int(season_raw)
            except (TypeError, ValueError):
                season_val = 0

            try:
                episode_val = int(episode_raw)
            except (TypeError, ValueError):
                episode_val = 0

            return (season_val, episode_val)

        cleaned.sort(key=sort_key)
        return cleaned
