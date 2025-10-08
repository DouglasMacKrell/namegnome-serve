"""Deterministic helpers for anthology interval simplification (T3-06)."""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

from namegnome_serve.routes.schemas import EpisodeSegment, MediaFile

_STOPWORDS = {
    "the",
    "and",
    "a",
    "an",
    "of",
    "in",
    "to",
    "for",
    "with",
}


def _tokenize(text: str) -> set[str]:
    tokens = [token.lower() for token in _split_tokens(text)]
    return {token for token in tokens if token and token not in _STOPWORDS}


def _split_tokens(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9']+", text or "")


def _similarity(tokens_a: Iterable[str], tokens_b: Iterable[str]) -> float:
    set_a = set(tokens_a)
    set_b = set(tokens_b)
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union else 0.0


@dataclass(slots=True)
class SimplifyResult:
    """Result of deterministic anthology interval simplification."""

    segments: list[EpisodeSegment]
    warnings: list[str] = field(default_factory=list)
    confidence: float = 1.0
    punt_to_llm: bool = False


def interval_simplify(
    media_file: MediaFile,
    provider_episodes: Sequence[dict[str, Any]],
) -> SimplifyResult:
    """Simplify anthology episode segments before invoking the LLM."""

    original_segments = media_file.segments or []
    mutable_segments: list[dict[str, Any]] = [
        segment.model_dump() if hasattr(segment, "model_dump") else dict(segment)
        for segment in original_segments
    ]

    warnings: list[str] = []
    confidence = 1.0

    if not mutable_segments:
        return SimplifyResult(segments=list(original_segments), warnings=warnings)

    _normalise_segments(mutable_segments)

    season = media_file.parsed_season
    provider_map, season_bounds = _build_provider_lookup(provider_episodes, season)

    if season_bounds is not None:
        changed = _clamp_to_bounds(mutable_segments, season_bounds)
        if changed:
            warnings.append("out_of_bounds")
            confidence = _deduct(confidence, 0.1)

    has_unresolved_overlap, resolved_count = _resolve_simple_overlaps(
        mutable_segments,
        warnings,
    )
    if resolved_count:
        confidence = _deduct(confidence, 0.1 * resolved_count)
    if has_unresolved_overlap:
        warnings.append("overlap_unresolved")

    gap_detected = _detect_gaps(mutable_segments)
    if gap_detected:
        warnings.append("gap_unresolved")

    singleton_applied = _maybe_singleton_collapse(
        mutable_segments,
        provider_map,
        media_file,
    )
    if singleton_applied:
        warnings.append("singleton_collapse")
        confidence = _deduct(confidence, 0.05)

    ambiguous_segment = any(
        seg.get("start") is None or seg.get("end") is None for seg in mutable_segments
    )
    if ambiguous_segment:
        warnings.append("ambiguous_segment")

    punt = False
    if any(
        flag in warnings
        for flag in {"overlap_unresolved", "gap_unresolved", "ambiguous_segment"}
    ):
        punt = True

    if confidence < 0.9:
        punt = True

    if punt:
        confidence = min(confidence, 0.7)

    _update_raw_spans(mutable_segments)

    simplified_segments = [
        EpisodeSegment.model_validate(segment) for segment in mutable_segments
    ]

    if has_unresolved_overlap or gap_detected or ambiguous_segment:
        punt = True

    return SimplifyResult(
        segments=simplified_segments,
        warnings=_deduplicate_preserve_order(warnings),
        confidence=confidence,
        punt_to_llm=punt,
    )


def _normalise_segments(segments: list[dict[str, Any]]) -> None:
    segments.sort(
        key=lambda seg: (
            seg.get("start") if isinstance(seg.get("start"), int) else float("inf"),
            seg.get("end") if isinstance(seg.get("end"), int) else float("inf"),
        )
    )

    for segment in segments:
        start = segment.get("start")
        end = segment.get("end")

        if isinstance(start, int) and end is None:
            segment["end"] = start
        elif start is None and isinstance(end, int):
            segment["start"] = end
        elif isinstance(start, int) and isinstance(end, int) and end < start:
            segment["start"], segment["end"] = end, start


def _build_provider_lookup(
    provider_episodes: Sequence[dict[str, Any]],
    season: int | None,
) -> tuple[dict[int, set[str]], tuple[int, int] | None]:
    tokens_map: dict[int, set[str]] = {}
    episode_numbers: list[int] = []

    for episode in provider_episodes:
        season_value = (
            episode.get("seasonNumber")
            or episode.get("SeasonNumber")
            or episode.get("season")
            or episode.get("season_number")
        )
        if (
            season is not None
            and season_value is not None
            and int(season_value) != season
        ):
            continue

        number_value = (
            episode.get("number")
            or episode.get("episodeNumber")
            or episode.get("EpisodeNumber")
            or episode.get("episode")
        )
        if number_value is None:
            continue

        number = int(number_value)
        title = (
            episode.get("name")
            or episode.get("episodeName")
            or episode.get("title")
            or ""
        )
        tokens_map[number] = _tokenize(title)
        episode_numbers.append(number)

    bounds = None
    if episode_numbers:
        bounds = (min(episode_numbers), max(episode_numbers))

    return tokens_map, bounds


def _clamp_to_bounds(segments: list[dict[str, Any]], bounds: tuple[int, int]) -> bool:
    changed = False
    lower, upper = bounds

    for segment in segments:
        start = segment.get("start")
        end = segment.get("end")

        if isinstance(start, int) and start < lower:
            segment["start"] = lower
            changed = True
        if isinstance(end, int) and end > upper:
            segment["end"] = upper
            changed = True

        if (
            isinstance(segment.get("start"), int)
            and isinstance(segment.get("end"), int)
            and segment["end"] < segment["start"]
        ):
            segment["end"] = segment["start"]

    return changed


def _resolve_simple_overlaps(
    segments: list[dict[str, Any]],
    warnings: list[str],
) -> tuple[bool, int]:
    has_unresolved = False
    resolved_count = 0

    for idx in range(len(segments) - 1):
        current = segments[idx]
        nxt = segments[idx + 1]

        curr_start = current.get("start")
        curr_end = current.get("end")
        next_start = nxt.get("start")
        next_end = nxt.get("end")

        if not isinstance(curr_start, int) or not isinstance(curr_end, int):
            continue
        if not isinstance(next_start, int) or not isinstance(next_end, int):
            continue

        if curr_end < next_start:
            continue

        if curr_end == next_start:
            # Trim the boundary episode from the first segment.
            current["end"] = curr_end - 1
            if current["end"] < curr_start:
                current["end"] = curr_start
            warnings.append("overlap_resolved")
            resolved_count += 1
        else:
            has_unresolved = True

    return has_unresolved, resolved_count


def _detect_gaps(segments: list[dict[str, Any]]) -> bool:
    previous_end: int | None = None
    gap_detected = False

    for segment in segments:
        start = segment.get("start")
        end = segment.get("end")

        if not isinstance(start, int) or not isinstance(end, int):
            continue

        if previous_end is not None and start > previous_end + 1:
            gap_detected = True

        previous_end = max(previous_end or end, end)

    return gap_detected


def _maybe_singleton_collapse(
    segments: list[dict[str, Any]],
    provider_tokens: dict[int, set[str]],
    media_file: MediaFile,
) -> bool:
    if len(segments) != 1:
        return False

    segment = segments[0]
    start = segment.get("start")
    end = segment.get("end")
    tokens = segment.get("title_tokens") or []

    if not isinstance(start, int) or not isinstance(end, int) or start == end:
        return False

    if not tokens:
        return False

    matched_episode = _match_unique_episode(tokens, provider_tokens, start, end)

    if matched_episode is None:
        return False

    segment["start"] = matched_episode
    segment["end"] = matched_episode
    segment["raw_span"] = f"E{matched_episode:02d}"
    return True


def _match_unique_episode(
    tokens: Iterable[str],
    provider_tokens: dict[int, set[str]],
    range_start: int,
    range_end: int,
) -> int | None:
    matches: list[tuple[float, int]] = []
    for episode_number, candidate_tokens in provider_tokens.items():
        similarity = _similarity(tokens, candidate_tokens)
        if similarity >= 0.85:
            matches.append((similarity, episode_number))

    if not matches:
        return None

    in_range = [match for match in matches if range_start <= match[1] <= range_end]
    if len(in_range) == 1:
        return in_range[0][1]

    if len(matches) == 1:
        return matches[0][1]

    return None


def _update_raw_spans(segments: list[dict[str, Any]]) -> None:
    for segment in segments:
        start = segment.get("start")
        end = segment.get("end")

        if isinstance(start, int) and isinstance(end, int):
            if end == start:
                segment["raw_span"] = f"E{start:02d}"
            else:
                segment["raw_span"] = f"E{start:02d}-E{end:02d}"
        elif isinstance(start, int):
            segment["raw_span"] = f"E{start:02d}"
        else:
            segment["raw_span"] = segment.get("raw_span") or ""


def _deduct(confidence: float, amount: float) -> float:
    return max(confidence - amount, 0.0)


def _deduplicate_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            deduped.append(item)
    return deduped
