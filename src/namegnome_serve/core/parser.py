"""Deterministic filename and directory parser for media files.

Extracts metadata from filenames following MEDIA_CONVENTIONS.md:
- TV: Show Name - SxxEyy - Episode Title
- Movies: Movie Title (Year)
- Music: Track## - Track Title
"""

import re
from pathlib import Path
from typing import Any, Literal

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


def _tokenize_title(text: str) -> list[str]:
    """Tokenize a title into lowercase alphanumeric terms excluding stopwords."""

    tokens = re.findall(r"[A-Za-z0-9']+", text or "")
    return [
        token.lower() for token in tokens if token and token.lower() not in _STOPWORDS
    ]


def _split_title_segments(text: str) -> list[str]:
    """Split anthology title string into segments using common separators."""

    if not text:
        return []

    normalized = text.strip()
    if not normalized:
        return []

    if " & " in normalized:
        return [part.strip() for part in normalized.split(" & ") if part.strip()]

    # Fallback: return the entire title as a single segment
    return [normalized]


def _normalize_whitespace(text: str) -> str:
    """Normalize multiple spaces and special separators to single spaces."""
    # Replace dots, underscores with spaces
    text = text.replace(".", " ").replace("_", " ")
    # Collapse multiple spaces
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _extract_year(text: str) -> tuple[str | None, str]:
    """Extract year in parentheses from text. Returns (year, remaining_text)."""
    match = re.search(r"\((\d{4})\)", text)
    if match:
        year = match.group(1)
        # Remove the year from text
        remaining = text[: match.start()] + text[match.end() :]
        return year, remaining.strip()
    return None, text


def _extract_all_years(text: str) -> list[str]:
    """Extract all years in parentheses from text."""
    matches = re.findall(r"\((\d{4})\)", text)
    return matches


def _has_anthology_keywords(text: str) -> bool:
    """Check if text contains anthology-related keywords."""
    anthology_keywords = [
        "anthology",
        "collection",
        "compilation",
        "omnibus",
    ]
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in anthology_keywords)


def _parse_tv_episode(
    filename: str, full_path: Path
) -> dict[str, str | int | bool | None]:
    """Parse TV episode filename."""
    result: dict[str, Any] = {
        "title": None,
        "season": None,
        "episode": None,
        "episode_end": None,
        "episode_title": None,
        "year": None,
        "needs_disambiguation": False,
        "anthology_candidate": False,
        "segments": [],
    }

    # Normalize separators
    normalized = _normalize_whitespace(filename)

    # Try to extract from directory structure
    parts = full_path.parts
    show_name_from_dir = None
    for part in parts:
        # Check if directory contains (Year) - likely show name
        year_match = re.search(r"^(.+?)\s*\((\d{4})\)", part)
        if year_match:
            show_name_from_dir = year_match.group(1).strip()
            result["year"] = int(year_match.group(2))
            break

    # Extract season/episode pattern: SxxEyy or SxxEyy-Eyy
    season_ep_match = re.search(
        r"S(\d{1,2})E(\d{1,2})(?:-?E(\d{1,2}))?", normalized, re.IGNORECASE
    )

    if season_ep_match:
        result["season"] = int(season_ep_match.group(1))
        result["episode"] = int(season_ep_match.group(2))
        if season_ep_match.group(3):  # Multi-episode
            result["episode_end"] = int(season_ep_match.group(3))

        # Extract show name (before SxxEyy)
        before_season = normalized[: season_ep_match.start()].strip()
        # Remove trailing separators like " - "
        before_season = re.sub(r"[\s\-]+$", "", before_season)

        if before_season:
            # Extract year if present
            year_str, title_clean = _extract_year(before_season)
            if year_str:
                result["year"] = int(year_str)
            result["title"] = title_clean.strip() if title_clean else None
        elif show_name_from_dir:
            result["title"] = show_name_from_dir

        # Extract episode title (after SxxEyy)
        after_season = normalized[season_ep_match.end() :].strip()
        # Remove leading separators like " - "
        after_season = re.sub(r"^[\s\-]+", "", after_season)
        if after_season:
            result["episode_title"] = after_season

    # If no SxxEyy found but we have directory info, use that
    elif show_name_from_dir:
        result["title"] = show_name_from_dir

    # Fallback: use filename as title if nothing else worked
    if not result["title"]:
        result["title"] = normalized

    # Detect uncertainty flags

    # Check for multiple years in filename
    all_years_in_filename = _extract_all_years(filename)
    if len(all_years_in_filename) > 1:
        result["needs_disambiguation"] = True

    # Check for conflicting year info between directory and filename
    year_from_dir = None
    for part in full_path.parts:
        year_match = re.search(r"\((\d{4})\)", part)
        if year_match:
            year_from_dir = int(year_match.group(1))
            break

    if year_from_dir and result["year"] and year_from_dir != result["year"]:
        result["needs_disambiguation"] = True

    # Check for multi-episode range (anthology candidate)
    if result["episode_end"] is not None:
        result["anthology_candidate"] = True

    # Check for anthology keywords (only in filename and immediate parent dir)
    # Don't check the entire path to avoid false positives from temp directories
    immediate_parent = full_path.parent.name if full_path.parent else ""
    check_text = filename + " " + immediate_parent
    if _has_anthology_keywords(check_text):
        result["anthology_candidate"] = True

    # Note: We don't use title length as a heuristic because many shows
    # (like Paw Patrol) naturally have long, descriptive episode titles
    # without being multi-segment anthology episodes. We rely on explicit
    # multi-episode ranges (E01-E02) or anthology keywords instead.

    segments: list[dict[str, Any]] = []

    start_episode = result.get("episode")
    end_episode = result.get("episode_end") or start_episode
    title_string = result.get("episode_title") or ""
    title_parts = _split_title_segments(title_string)

    if start_episode is not None and end_episode is not None:
        span_count = max(end_episode - start_episode + 1, 1)

        if title_parts and len(title_parts) == span_count:
            for index, part in enumerate(title_parts):
                episode_number = start_episode + index
                segments.append(
                    {
                        "start": episode_number,
                        "end": episode_number,
                        "title_tokens": _tokenize_title(part),
                        "raw_span": f"E{episode_number:02d}",
                        "source": "filename",
                    }
                )
        else:
            raw_span = (
                f"E{start_episode:02d}"
                if end_episode == start_episode
                else f"E{start_episode:02d}-E{end_episode:02d}"
            )
            segments.append(
                {
                    "start": start_episode,
                    "end": end_episode,
                    "title_tokens": _tokenize_title(title_string),
                    "raw_span": raw_span,
                    "source": "filename",
                }
            )
            if title_parts and len(title_parts) != span_count:
                result["needs_disambiguation"] = True
    else:
        inferred_source = (
            "dirname" if result.get("title") == show_name_from_dir else "unknown"
        )
        fallback_tokens = _tokenize_title(title_string or result.get("title", ""))
        segments.append(
            {
                "start": None,
                "end": None,
                "title_tokens": fallback_tokens,
                "raw_span": "",
                "source": inferred_source,
            }
        )

    result["segments"] = segments

    return result


def _parse_movie(filename: str, full_path: Path) -> dict[str, str | int | bool | None]:
    """Parse movie filename."""
    result: dict[str, Any] = {
        "title": None,
        "year": None,
        "part": None,
        "needs_disambiguation": False,
        "anthology_candidate": False,
    }

    # Normalize separators
    normalized = _normalize_whitespace(filename)

    # Extract year
    year_str, remaining = _extract_year(normalized)
    if year_str:
        result["year"] = int(year_str)

    # Extract part number if present
    part_match = re.search(r"-\s*Part\s*(\d+)", remaining, re.IGNORECASE)
    if part_match:
        result["part"] = int(part_match.group(1))
        # Remove part from title
        remaining = remaining[: part_match.start()].strip()

    # Remove extra metadata after year (e.g., " - 1080p - BluRay")
    remaining = re.sub(r"-\s*\d+p.*$", "", remaining, flags=re.IGNORECASE)
    remaining = re.sub(r"-\s*BluRay.*$", "", remaining, flags=re.IGNORECASE)

    # Title is what remains
    result["title"] = remaining.strip() if remaining else None

    # Try to extract from directory if title is empty
    if not result["title"]:
        parts = full_path.parts
        for part in reversed(parts):
            year_match = re.search(r"^(.+?)\s*\((\d{4})\)", part)
            if year_match:
                result["title"] = year_match.group(1).strip()
                if not result["year"]:
                    result["year"] = int(year_match.group(2))
                break

    # Detect uncertainty flags for movies

    # Check for multiple years in filename (remakes)
    all_years_in_filename = _extract_all_years(filename)
    if len(all_years_in_filename) > 1:
        result["needs_disambiguation"] = True

    # Movies don't have anthology concept in our system
    # (anthology_candidate remains False for movies)

    return result


def _parse_music(filename: str, full_path: Path) -> dict[str, str | int | bool | None]:
    """Parse music track filename."""
    result: dict[str, Any] = {
        "track": None,
        "title": None,
        "artist": None,
        "album": None,
        "year": None,
        "needs_disambiguation": False,
        "anthology_candidate": False,
    }

    # Normalize separators but keep hyphens for track separator
    normalized = filename.replace(".", " ").replace("_", " ")
    normalized = re.sub(r"\s+", " ", normalized).strip()

    # Extract track number: 01, 02, Track01, etc.
    track_match = re.search(r"^(?:Track\s*)?(\d{1,2})", normalized, re.IGNORECASE)
    if track_match:
        result["track"] = int(track_match.group(1))

        # Extract title after track number
        after_track = normalized[track_match.end() :].strip()
        # Remove leading hyphen or spaces
        after_track = re.sub(r"^[\s\-]+", "", after_track)
        if after_track:
            result["title"] = after_track

    # Try to extract from directory structure
    parts = full_path.parts
    if len(parts) >= 3:
        # Artist/Album (Year)/Track## - Title.ext
        artist_candidate = parts[-3] if len(parts) >= 3 else None
        album_part = parts[-2] if len(parts) >= 2 else None

        if artist_candidate:
            result["artist"] = artist_candidate

        if album_part:
            # Extract album and year
            year_match = re.search(r"^(.+?)\s*\((\d{4})\)", album_part)
            if year_match:
                result["album"] = year_match.group(1).strip()
                result["year"] = int(year_match.group(2))
            else:
                result["album"] = album_part

    # Music files typically don't need uncertainty flags
    # (both flags remain False for music in most cases)

    return result


def parse_filename(
    path: Path, media_type: Literal["tv", "movie", "music"]
) -> dict[str, str | int | None]:
    """Parse filename to extract media metadata.

    Args:
        path: Path to the media file (can be filename only or full path)
        media_type: Type of media ('tv', 'movie', or 'music')

    Returns:
        Dictionary with extracted metadata fields. Keys vary by media_type:
        - TV: title, season, episode, episode_end, episode_title, year
        - Movie: title, year, part
        - Music: track, title, artist, album, year

    Examples:
        >>> parse_filename(Path("Paw Patrol - S07E04.mp4"), "tv")
        {'title': 'Paw Patrol', 'season': 7, 'episode': 4, ...}

        >>> parse_filename(Path("The Matrix (1999).mkv"), "movie")
        {'title': 'The Matrix', 'year': 1999, 'part': None}

        >>> parse_filename(Path("01 - Track Title.mp3"), "music")
        {'track': 1, 'title': 'Track Title', ...}
    """
    # Get filename without extension
    filename = path.stem

    if media_type == "tv":
        return _parse_tv_episode(filename, path)
    elif media_type == "movie":
        return _parse_movie(filename, path)
    elif media_type == "music":
        return _parse_music(filename, path)
    else:
        # Fallback for unknown media type
        return {"title": filename}
