"""Provider episode candidate fetching utilities for fuzzy planning."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from namegnome_serve.routes.schemas import MediaFile


def _extract_year(value: Any) -> int | None:
    """Best-effort extraction of a four-digit year from provider fields."""

    if value is None:
        return None

    if isinstance(value, int):
        return value

    text = str(value).strip()
    if not text:
        return None

    digits = "".join(ch for ch in text[:4] if ch.isdigit())
    if len(digits) == 4:
        return int(digits)
    return None


def _coerce_int(value: Any) -> int | None:
    """Convert provider season/episode values into integers when possible."""

    if value is None:
        return None

    if isinstance(value, int):
        return value

    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


@dataclass
class EpisodeCandidateFetcher:
    """Fetch TV episode candidates from a provider for LLM planning."""

    tvdb: Any

    async def fetch(self, media_file: MediaFile) -> list[dict[str, Any]]:
        """Fetch and normalize potential episode matches for the given media file."""

        if not self.tvdb or not media_file.parsed_title:
            return []

        series_candidates = await self.tvdb.search_series(media_file.parsed_title)
        if not series_candidates:
            return []

        series_choice = self._select_series(series_candidates, media_file)
        if not series_choice:
            return []

        series_id = series_choice.get("id")
        if series_id is None:
            return []

        episodes = await self.tvdb.get_series_episodes(series_id)
        normalized: list[dict[str, Any]] = []
        for raw_episode in episodes:
            normalized_ep = self._normalize_episode(raw_episode)
            if normalized_ep is not None:
                normalized.append(normalized_ep)

        if media_file.parsed_season:
            normalized = [
                ep
                for ep in normalized
                if ep["seasonNumber"] == media_file.parsed_season
            ]

        normalized.sort(key=lambda ep: (ep["seasonNumber"], ep["number"]))
        return normalized

    def _select_series(
        self, candidates: list[dict[str, Any]], media_file: MediaFile
    ) -> dict[str, Any] | None:
        """Pick the best matching series candidate for the media file."""

        if not candidates:
            return None

        if media_file.parsed_year:
            for candidate in candidates:
                year = (
                    _extract_year(candidate.get("year"))
                    or _extract_year(candidate.get("firstAired"))
                    or _extract_year(candidate.get("releaseYear"))
                )
                if year == media_file.parsed_year:
                    return candidate

        return candidates[0]

    @staticmethod
    def _normalize_episode(raw: dict[str, Any]) -> dict[str, Any] | None:
        """Convert provider episode payload to the structure expected by the planner."""

        identifier = raw.get("id") or raw.get("episode_id")
        if identifier is None:
            return None

        name = raw.get("name") or raw.get("episodeName") or raw.get("title")
        season_number = (
            _coerce_int(raw.get("seasonNumber"))
            or _coerce_int(raw.get("airedSeason"))
            or _coerce_int(raw.get("season"))
        )
        episode_number = (
            _coerce_int(raw.get("number"))
            or _coerce_int(raw.get("airedEpisodeNumber"))
            or _coerce_int(raw.get("episode"))
        )

        if season_number is None or episode_number is None:
            return None

        return {
            "id": str(identifier),
            "name": str(name) if name is not None else "",
            "seasonNumber": season_number,
            "number": episode_number,
        }
