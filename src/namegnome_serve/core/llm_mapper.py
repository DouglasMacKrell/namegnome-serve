"""LLM-assisted fuzzy mapper for ambiguous scan results (Sprint T3-03)."""

from __future__ import annotations

from typing import Any, Protocol

from namegnome_serve.core.deterministic_mapper import DeterministicMapper
from namegnome_serve.routes.schemas import MediaFile, PlanItem, SourceRef


class RunnableProtocol(Protocol):
    """Subset of LangChain runnable we rely on (duck-typed for tests)."""

    def invoke(self, payload: dict[str, Any]) -> dict[str, Any]: ...


class FuzzyLLMMapper:
    """Use an LLM to resolve ambiguous TV mappings and anthology episodes."""

    def __init__(self, llm: RunnableProtocol) -> None:
        self._llm = llm

    def generate_tv_plan(
        self,
        media_file: MediaFile,
        provider_candidates: list[dict[str, Any]],
    ) -> list[PlanItem]:
        """Produce plan items for ambiguous television inputs via LLM guidance."""

        if not media_file.parsed_title:
            return []

        prompt_payload = {
            "media": {
                "title": media_file.parsed_title,
                "season": media_file.parsed_season,
                "episode": media_file.parsed_episode,
                "anthology_candidate": media_file.anthology_candidate,
            },
            "candidates": provider_candidates,
        }

        response = self._llm.invoke(prompt_payload)
        assignments = (
            response.get("assignments") if isinstance(response, dict) else None
        )
        if assignments is None:
            raise ValueError("LLM response missing 'assignments' list")

        results: list[PlanItem] = []
        for assignment in assignments:
            if not isinstance(assignment, dict):
                raise ValueError("Each assignment must be a mapping")

            try:
                season = int(assignment["season"])
                episode_start = int(assignment["episode_start"])
                episode_end = int(assignment.get("episode_end", episode_start))
                episode_title = assignment.get("episode_title")
                confidence = float(assignment.get("confidence", 0.5))
                warnings = assignment.get("warnings", [])

                provider_info = assignment.get("provider", {})
                provider_name = provider_info.get("provider")
                provider_id = provider_info.get("id")
            except (
                KeyError,
                TypeError,
                ValueError,
            ) as exc:  # pragma: no cover - defensive
                raise ValueError(f"Invalid assignment payload: {assignment}") from exc

            dst_path = DeterministicMapper._build_tv_path(
                media_file.parsed_title,
                season,
                episode_start,
                episode_title,
                episode_end=episode_end,
            )

            sources: list[SourceRef] = []
            if (
                provider_name
                and provider_id
                and provider_name
                in {
                    "tmdb",
                    "tvdb",
                    "musicbrainz",
                    "anilist",
                    "omdb",
                    "theaudiodb",
                }
            ):
                sources.append(SourceRef(provider=provider_name, id=str(provider_id)))

            reason = assignment.get(
                "reason",
                (
                    f"LLM matched '{media_file.parsed_title}' to "
                    f"S{season:02d}E{episode_start:02d}"
                ),
            )

            plan_item = PlanItem(
                src_path=media_file.path,
                dst_path=dst_path,
                reason=reason,
                confidence=confidence,
                sources=sources,
                warnings=list(warnings),
            )
            results.append(plan_item)

        return results
