"""LLM-assisted fuzzy mapper for ambiguous scan results (Sprint T3-03)."""

from __future__ import annotations

import json
from typing import Any, Protocol

from langchain.prompts import ChatPromptTemplate
from langchain.schema.runnable import RunnableLambda

from namegnome_serve.core.deterministic_mapper import DeterministicMapper
from namegnome_serve.routes.schemas import MediaFile, PlanItem, SourceRef


class RunnableProtocol(Protocol):
    """Subset of LangChain runnable interface we depend on."""

    def invoke(self, payload: Any) -> Any: ...


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
            valid_providers = {
                "tmdb",
                "tvdb",
                "musicbrainz",
                "anilist",
                "omdb",
                "theaudiodb",
            }
            if provider_name and provider_id and provider_name in valid_providers:
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
                " and provider episodes, return JSON assignments describing"
                " how the file should be split. Always respond with valid JSON.",
            ),
            (
                "human",
                "Media file info:\n{media_json}\n\nCandidate episodes:\n"
                "{episodes_json}\n\nReturn JSON matching this schema:\n{schema}",
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
