"""Plan review builder producing human-reviewable JSON payloads (T3-04)."""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from namegnome_serve.routes.schemas import MediaFile, PlanItem

Origin = Literal["deterministic", "llm"]
ConfidenceBucket = Literal["high", "medium", "low"]
MediaType = Literal["tv", "movie", "music"]


@dataclass(slots=True)
class PlanReviewSourceInput:
    """Input bundle for plan review assembly (per scanned media file)."""

    media_file: MediaFile
    deterministic: Sequence[PlanItem]
    llm: Sequence[PlanItem]


@dataclass
class _PlanEntry:
    """Internal representation binding a PlanItem with its origin."""

    origin: Origin
    plan_item: PlanItem


TV_PATTERN = re.compile(r"S(\d{1,2})E(\d{1,2})(?:-?E(\d{1,2}))?", re.IGNORECASE)
MOVIE_PATTERN = re.compile(r"\((\d{4})\)")
TRACK_PATTERN = re.compile(r"/(\d{2})\s*[-_]")


def build_plan_review(
    *,
    media_type: MediaType,
    sources: Sequence[PlanReviewSourceInput],
    plan_id: str | None = None,
    scan_id: str | None = None,
    source_fingerprint: str | None = None,
    generated_at: datetime | None = None,
    schema_version: str = "1.0",
) -> dict[str, Any]:
    """Construct a PlanReview payload merging deterministic/LLM outputs."""

    materialized_time = _format_generated_at(generated_at)
    resolved_plan_id = plan_id or _generate_plan_id()

    media_by_src = {
        str(input_bundle.media_file.path): input_bundle.media_file
        for input_bundle in sources
    }

    grouped_entries: dict[tuple[str, str], list[_PlanEntry]] = {}
    for bundle in sources:
        src_path = str(bundle.media_file.path)
        for item in bundle.deterministic:
            key = (src_path, str(item.dst_path))
            grouped_entries.setdefault(key, []).append(
                _PlanEntry("deterministic", item)
            )
        for item in bundle.llm:
            key = (src_path, str(item.dst_path))
            grouped_entries.setdefault(key, []).append(_PlanEntry("llm", item))

    final_items: list[dict[str, Any]] = []
    next_id = 1
    tie_paths: set[str] = set()

    for key, entries in grouped_entries.items():
        src_path, _dst_path = key
        winner, alternatives, tie_flag = _select_winner(entries)
        plan_item = winner.plan_item

        item_dict = _plan_item_to_dict(
            item_id=_format_item_id(next_id),
            origin=winner.origin,
            plan_item=plan_item,
            media_file=media_by_src.get(src_path),
            media_type=media_type,
            alternatives=alternatives,
            tie_flag=tie_flag,
        )
        next_id += 1
        final_items.append(item_dict)
        if tie_flag:
            tie_paths.add(src_path)

    final_items.sort(key=lambda item: _item_sort_key(media_type, item))

    groups = _build_groups(final_items, media_by_src)
    summary = _build_summary(final_items)

    return {
        "plan_id": resolved_plan_id,
        "schema_version": schema_version,
        "generated_at": materialized_time,
        "scan_id": scan_id,
        "source_fingerprint": source_fingerprint,
        "media_type": media_type,
        "summary": summary,
        "groups": groups,
        "items": final_items,
        "notes": _build_notes(tie_paths),
    }


def _generate_plan_id() -> str:
    from uuid import uuid4

    return f"pln_{uuid4().hex}"


def _format_generated_at(value: datetime | None) -> str:
    timestamp = value.astimezone(UTC) if value else datetime.now(UTC)
    timestamp = timestamp.replace(microsecond=0)
    return timestamp.isoformat().replace("+00:00", "Z")


def _format_item_id(seq: int) -> str:
    return f"pli_{seq:04d}"


def _select_winner(
    entries: Sequence[_PlanEntry],
) -> tuple[_PlanEntry, list[_PlanEntry], bool]:
    if not entries:
        raise ValueError("Cannot select winner from empty entry list")

    best_det = _best_by_origin(entries, "deterministic")
    best_llm = _best_by_origin(entries, "llm")

    tie_flag = False
    if best_det and best_llm:
        diff = abs(best_det.plan_item.confidence - best_llm.plan_item.confidence)
        if diff < 0.1:
            winner = best_det
            tie_flag = True
        else:
            winner = (
                best_det
                if best_det.plan_item.confidence > best_llm.plan_item.confidence
                else best_llm
            )
    else:
        winner = max(entries, key=lambda entry: entry.plan_item.confidence)

    alternatives = [entry for entry in entries if entry is not winner]
    return winner, alternatives, tie_flag


def _best_by_origin(entries: Sequence[_PlanEntry], origin: Origin) -> _PlanEntry | None:
    filtered = [entry for entry in entries if entry.origin == origin]
    if not filtered:
        return None
    return max(filtered, key=lambda entry: entry.plan_item.confidence)


def _plan_item_to_dict(
    *,
    item_id: str,
    origin: Origin,
    plan_item: PlanItem,
    media_file: MediaFile | None,
    media_type: MediaType,
    alternatives: Iterable[_PlanEntry],
    tie_flag: bool,
) -> dict[str, Any]:
    base_warnings = list(plan_item.warnings)
    if tie_flag and "tie_breaker_deterministic_preferred" not in base_warnings:
        base_warnings.append("tie_breaker_deterministic_preferred")

    item_dict: dict[str, Any] = {
        "id": item_id,
        "origin": origin,
        "confidence": float(plan_item.confidence),
        "confidence_bucket": _confidence_bucket(plan_item.confidence),
        "src": {
            "path": str(plan_item.src_path),
            "segment": None,
        },
        "dst": {
            "path": str(plan_item.dst_path),
            "episode": None,
            "movie": None,
            "track": None,
        },
        "sources": [
            {
                "provider": ref.provider,
                "id": ref.id,
                "type": _source_type(media_type),
            }
            for ref in plan_item.sources
        ],
        "warnings": base_warnings,
        "anthology": bool(media_file.anthology_candidate) if media_file else False,
        "disambiguation": _build_disambiguation(media_file),
        "alternatives": [
            {
                "origin": alt.origin,
                "confidence": float(alt.plan_item.confidence),
                "dst": {"path": str(alt.plan_item.dst_path)},
                "reason": alt.plan_item.reason or None,
            }
            for alt in alternatives
        ],
        "explain": {"reason": plan_item.reason} if plan_item.reason else None,
    }

    return item_dict


def _build_disambiguation(media_file: MediaFile | None) -> dict[str, Any] | None:
    if not media_file or not media_file.needs_disambiguation:
        return None
    payload: dict[str, Any] = {"status": "needs_user_confirmation"}
    if media_file.parsed_title:
        payload["title"] = media_file.parsed_title
    if media_file.parsed_year:
        payload["year"] = media_file.parsed_year
    return payload


def _confidence_bucket(value: float) -> ConfidenceBucket:
    if value >= 0.90:
        return "high"
    if value >= 0.70:
        return "medium"
    return "low"


def _source_type(media_type: MediaType) -> str:
    if media_type == "tv":
        return "episode"
    if media_type == "movie":
        return "movie"
    return "track"


def _item_sort_key(media_type: MediaType, item: dict[str, Any]) -> tuple[Any, ...]:
    src_path = item["src"]["path"].lower()
    dst_path = item["dst"]["path"].lower()

    if media_type == "tv":
        match = TV_PATTERN.search(dst_path)
        if match:
            season = int(match.group(1))
            episode = int(match.group(2))
            episode_end = int(match.group(3)) if match.group(3) else episode
            return (src_path, season, episode, episode_end, dst_path)
    elif media_type == "movie":
        match = MOVIE_PATTERN.search(dst_path)
        if match:
            year = int(match.group(1))
            return (src_path, year, dst_path)
    elif media_type == "music":
        match = TRACK_PATTERN.search(dst_path)
        if match:
            track = int(match.group(1))
            return (src_path, track, dst_path)

    return (src_path, dst_path)


def _build_groups(
    items: Sequence[dict[str, Any]],
    media_by_src: dict[str, MediaFile],
) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    order: list[str] = []

    for item in items:
        src_path = item["src"]["path"]
        if src_path not in groups:
            media_file = media_by_src.get(src_path)
            groups[src_path] = {
                "group_key": src_path,
                "src_file": {
                    "path": src_path,
                    "size": media_file.size if media_file else None,
                    "mtime": None,
                    "hash": media_file.hash if media_file else None,
                },
                "items": [],
            }
            order.append(src_path)
        groups[src_path]["items"].append(item)

    sorted_paths = sorted(order, key=str.lower)

    group_payloads: list[dict[str, Any]] = []
    for path in sorted_paths:
        group = groups[path]
        warnings = sorted(
            {warning for item in group["items"] for warning in item["warnings"]}
        )
        confidences = [item["confidence"] for item in group["items"]]
        group["rollup"] = {
            "count": len(group["items"]),
            "confidence_min": min(confidences) if confidences else 0.0,
            "confidence_max": max(confidences) if confidences else 0.0,
            "warnings": warnings,
        }
        group_payloads.append(group)

    return group_payloads


def _build_summary(items: Sequence[dict[str, Any]]) -> dict[str, Any]:
    by_origin = {"deterministic": 0, "llm": 0}
    by_confidence = {"high": 0, "medium": 0, "low": 0}
    warnings_total = 0
    anthology_count = 0
    disambiguation_count = 0

    for item in items:
        origin = item["origin"]
        by_origin[origin] = by_origin.get(origin, 0) + 1
        bucket = item["confidence_bucket"]
        by_confidence[bucket] = by_confidence.get(bucket, 0) + 1
        warnings_total += len(item["warnings"])
        if item.get("anthology"):
            anthology_count += 1
        if item.get("disambiguation"):
            disambiguation_count += 1

    return {
        "total_items": len(items),
        "by_origin": by_origin,
        "by_confidence": by_confidence,
        "warnings": warnings_total,
        "anthology_candidates": anthology_count,
        "disambiguations_required": disambiguation_count,
    }


def _build_notes(tie_paths: set[str]) -> list[str]:
    if not tie_paths:
        return []
    sorted_paths = sorted(tie_paths, key=str.lower)
    return [
        "Deterministic results preferred for near-ties at: " + ", ".join(sorted_paths)
    ]
