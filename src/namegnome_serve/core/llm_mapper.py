"""LLM-assisted fuzzy mapper for ambiguous scan results (Sprint T3-03)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, cast

from langchain.prompts import ChatPromptTemplate
from langchain.schema.runnable import RunnableLambda

from namegnome_serve.core.deterministic_mapper import DeterministicMapper
from namegnome_serve.routes.schemas import MediaFile, PlanItem, SourceRef


class RunnableProtocol(Protocol):
    """Subset of LangChain runnable interface we depend on."""

    def invoke(self, payload: Any) -> Any: ...


@dataclass
class _Assignment:
    """Internal representation of an LLM-suggested episode assignment."""

    season: int
    episode_start: int
    episode_end: int
    episode_title: str | None
    provider_name: str | None
    provider_id: str | None
    confidence: float
    warnings: list[str] = field(default_factory=list)
    reason: str | None = None


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

        provider_index = {
            str(candidate.get("id")): candidate for candidate in provider_candidates
        }

        response = self._llm.invoke(prompt_payload)
        assignments = (
            response.get("assignments") if isinstance(response, dict) else None
        )
        if assignments is None:
            raise ValueError("LLM response missing 'assignments' list")

        parsed: list[_Assignment] = []
        for assignment in assignments:
            if not isinstance(assignment, dict):
                raise ValueError("Each assignment must be a mapping")

            try:
                season = int(assignment["season"])
                episode_start = int(assignment["episode_start"])
                episode_end = int(assignment.get("episode_end", episode_start))
            except (
                KeyError,
                TypeError,
                ValueError,
            ) as exc:  # pragma: no cover - defensive
                raise ValueError(f"Invalid assignment payload: {assignment}") from exc

            episode_title_raw = assignment.get("episode_title")
            episode_title = (
                str(episode_title_raw) if episode_title_raw is not None else None
            )

            raw_confidence = assignment.get("confidence", 0.5)
            try:
                confidence = float(raw_confidence)
            except (TypeError, ValueError):
                confidence = 0.5

            # Clamp to inclusive [0, 0.99] to reflect LLM ambiguity.
            if confidence < 0.0:
                confidence = 0.0
            elif confidence >= 1.0:
                confidence = 0.99

            warnings_field = assignment.get("warnings", [])
            if isinstance(warnings_field, str):
                warnings_list = [warnings_field]
            elif isinstance(warnings_field, list):
                warnings_list = [str(item) for item in warnings_field if item]
            elif warnings_field:
                warnings_list = [str(warnings_field)]
            else:
                warnings_list = []

            provider_info = assignment.get("provider", {}) or {}
            provider_name_raw = provider_info.get("provider")
            provider_id = provider_info.get("id")
            provider_name = (
                str(provider_name_raw) if provider_name_raw is not None else None
            )

            if not episode_title and provider_id:
                candidate = provider_index.get(str(provider_id))
                if candidate:
                    candidate_name = candidate.get("name")
                    if candidate_name is not None:
                        episode_title = str(candidate_name)

            parsed.append(
                _Assignment(
                    season=season,
                    episode_start=episode_start,
                    episode_end=episode_end,
                    episode_title=episode_title,
                    provider_name=provider_name,
                    provider_id=str(provider_id) if provider_id is not None else None,
                    confidence=confidence,
                    warnings=warnings_list,
                    reason=assignment.get("reason"),
                )
            )

        self._normalize_assignments(parsed)

        ordered: list[tuple[int, int, PlanItem]] = []
        for assignment in parsed:
            dst_path = DeterministicMapper._build_tv_path(
                media_file.parsed_title,
                assignment.season,
                assignment.episode_start,
                assignment.episode_title,
                episode_end=assignment.episode_end,
            )

            sources: list[SourceRef] = []
            valid_providers = {
                "tmdb",
                "tvdb",
                "musicbrainz",
                "anilist",
                "omdb",
                "theaudiodb",
                "tvmaze",
            }
            if (
                assignment.provider_name
                and assignment.provider_id
                and assignment.provider_name in valid_providers
            ):
                provider_literal = cast(
                    Literal[
                        "tmdb",
                        "tvdb",
                        "musicbrainz",
                        "anilist",
                        "omdb",
                        "theaudiodb",
                        "tvmaze",
                    ],
                    assignment.provider_name,
                )
                sources.append(
                    SourceRef(
                        provider=provider_literal,
                        id=assignment.provider_id,
                    )
                )

            reason_value = assignment.reason
            if reason_value:
                reason_text = str(reason_value)
            else:
                reason_text = (
                    f"LLM matched '{media_file.parsed_title}' to "
                    f"S{assignment.season:02d}E{assignment.episode_start:02d}"
                )

            plan_item = PlanItem(
                src_path=media_file.path,
                dst_path=dst_path,
                reason=reason_text,
                confidence=assignment.confidence,
                sources=sources,
                warnings=list(assignment.warnings),
            )
            ordered.append((assignment.season, assignment.episode_start, plan_item))

        ordered.sort(key=lambda entry: (entry[0], entry[1]))
        return [plan for _, _, plan in ordered]

    @staticmethod
    def _normalize_assignments(assignments: list[_Assignment]) -> None:
        """Ensure episode ranges are contiguous and non-overlapping."""

        assignments.sort(
            key=lambda item: (item.season, item.episode_start, item.episode_end)
        )

        for idx in range(len(assignments) - 1):
            current = assignments[idx]
            nxt = assignments[idx + 1]

            if current.season != nxt.season:
                continue

            if current.episode_end < current.episode_start:
                current.episode_end = current.episode_start

            if nxt.episode_end < nxt.episode_start:
                nxt.episode_end = nxt.episode_start

            if current.episode_end < nxt.episode_start:
                continue

            new_end = nxt.episode_start - 1
            if new_end < current.episode_start:
                new_end = current.episode_start

            if new_end != current.episode_end:
                current.episode_end = new_end
                current_label = (
                    f"S{current.season:02d}E{current.episode_start:02d}"
                    if current.episode_start == current.episode_end
                    else (
                        f"S{current.season:02d}E{current.episode_start:02d}-"
                        f"E{current.episode_end:02d}"
                    )
                )
                overlap_label = f"S{nxt.season:02d}E{nxt.episode_start:02d}"
                warning_text = (
                    "Trimmed span to "
                    f"{current_label} to avoid overlap with {overlap_label}."
                )
                current.warnings.append(warning_text)

            desired_next_start = current.episode_end + 1
            if nxt.episode_start < desired_next_start:
                original_start = nxt.episode_start
                nxt.episode_start = desired_next_start
                if nxt.episode_end < nxt.episode_start:
                    nxt.episode_end = nxt.episode_start
                next_label = (
                    f"S{nxt.season:02d}E{nxt.episode_start:02d}"
                    if nxt.episode_start == nxt.episode_end
                    else (
                        f"S{nxt.season:02d}E{nxt.episode_start:02d}-"
                        f"E{nxt.episode_end:02d}"
                    )
                )
                prior_label = (
                    f"S{current.season:02d}E{current.episode_start:02d}"
                    if current.episode_start == current.episode_end
                    else (
                        f"S{current.season:02d}E{current.episode_start:02d}-"
                        f"E{current.episode_end:02d}"
                    )
                )
                nxt.warnings.append(
                    "Shifted start from "
                    f"E{original_start:02d} to build {next_label} after {prior_label}."
                )


TV_ASSIGNMENT_SCHEMA = {
    "type": "object",
    "properties": {
        "assignments": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "season",
                    "episode_start",
                    "episode_end",
                    "episode_title",
                    "provider",
                ],
                "properties": {
                    "season": {"type": "integer", "minimum": 1},
                    "episode_start": {"type": "integer", "minimum": 1},
                    "episode_end": {"type": "integer", "minimum": 1},
                    "episode_title": {"type": "string"},
                    "confidence": {"type": "number"},
                    "warnings": {"type": "array", "items": {"type": "string"}},
                    "provider": {
                        "type": "object",
                        "properties": {
                            "provider": {"type": "string"},
                            "id": {"type": "string"},
                        },
                    },
                },
            },
        }
    },
}


def build_tv_fuzzy_chain(llm: RunnableProtocol) -> Any:
    """Create runnable chain that formats prompts, calls LLM, parses JSON."""

    parser: RunnableLambda[Any, Any] = RunnableLambda(json.loads)
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are NameGnome's mapping assistant. Given media metadata"
                " and canonical provider episode lists, produce JSON assignments"
                " describing how the file should be split into contiguous episode"
                " spans. Prefer provider titles when input titles are fuzzy or"
                " truncated, never invent numbering, and include confidence and"
                " warnings whenever ambiguity remains. Your reply must be valid JSON.",
            ),
            (
                "human",
                "Media file info:\n{media_json}\n\nCandidate episodes:\n"
                "{episodes_json}\n\nInstructions:\n"
                "- Use fuzzy title similarity plus adjacency.\n"
                "- Group episodes into contiguous spans with no overlaps or gaps.\n"
                "- If unsure about a span, lower the confidence and add a warning.\n"
                "- Provide provider identifiers where possible.\n\n"
                "Return JSON matching this schema:\n{schema}",
            ),
        ]
    )

    formatter = RunnableLambda(
        lambda inputs: {
            "media_json": json.dumps(inputs["media"], indent=2, sort_keys=True),
            "episodes_json": json.dumps(inputs["candidates"], indent=2, sort_keys=True),
        }
    )

    schema_text = json.dumps(TV_ASSIGNMENT_SCHEMA, indent=2, sort_keys=True)

    model = RunnableLambda(lambda messages: llm.invoke(messages))
    to_text = RunnableLambda(
        lambda result: result.content if hasattr(result, "content") else result
    )

    chain = formatter | prompt.partial(schema=schema_text) | model | to_text | parser
    return chain
