"""Recursive media file scanner.

This module provides functionality to scan directories for media files,
filter by extension based on media type, and collect filesystem metadata.
"""

import hashlib
from pathlib import Path
from typing import Literal

from namegnome_serve.core.constants import (
    MOVIE_EXTENSIONS,
    MUSIC_EXTENSIONS,
    TV_EXTENSIONS,
)
from namegnome_serve.core.parser import parse_filename
from namegnome_serve.routes.schemas import MediaFile, ScanResult


def scan(
    paths: list[Path],
    media_type: Literal["tv", "movie", "music"],
    with_hash: bool = False,
) -> ScanResult:
    """Scan directories for media files and collect metadata.

    Args:
        paths: List of directory paths to scan recursively
        media_type: Type of media to scan for ('tv', 'movie', or 'music')
        with_hash: Whether to compute SHA-256 hashes for files

    Returns:
        ScanResult containing discovered files and metadata

    Raises:
        FileNotFoundError: If any path doesn't exist
        ValueError: If any path is not a directory
    """
    # Determine which extensions to look for based on media type
    if media_type == "tv":
        extensions = set(TV_EXTENSIONS)
    elif media_type == "movie":
        extensions = set(MOVIE_EXTENSIONS)
    elif media_type == "music":
        extensions = set(MUSIC_EXTENSIONS)
    else:
        raise ValueError(f"Invalid media_type: {media_type}")

    # Validate all paths exist
    for path in paths:
        if not path.exists():
            raise FileNotFoundError(f"Path does not exist: {path}")
        if not path.is_dir():
            raise ValueError(f"Path is not a directory: {path}")

    # Collect all matching files
    media_files: list[MediaFile] = []
    total_size = 0

    for root_path in paths:
        for file_path in _walk_directory(root_path):
            # Skip hidden files (starting with .)
            if file_path.name.startswith("."):
                continue

            # Check if file extension matches media type
            if file_path.suffix.lower() in extensions:
                # Get file metadata
                file_size = file_path.stat().st_size
                total_size += file_size

                # Optionally compute hash
                file_hash: str | None = None
                if with_hash:
                    file_hash = _compute_sha256(file_path)

                # Parse filename to extract metadata
                parsed_data = parse_filename(file_path, media_type=media_type)

                # Extract and cast parsed values to proper types
                title = parsed_data.get("title")
                season = parsed_data.get("season")
                episode = parsed_data.get("episode")
                year = parsed_data.get("year")
                track = parsed_data.get("track")

                # Extract uncertainty flags
                needs_disambiguation = parsed_data.get("needs_disambiguation", False)
                anthology_candidate = parsed_data.get("anthology_candidate", False)

                # Create MediaFile entry with parsed metadata
                media_file = MediaFile(
                    path=file_path,
                    size=file_size,
                    hash=file_hash,
                    parsed_title=str(title) if title is not None else None,
                    parsed_season=int(season) if season is not None else None,
                    parsed_episode=int(episode) if episode is not None else None,
                    parsed_year=int(year) if year is not None else None,
                    parsed_track=int(track) if track is not None else None,
                    needs_disambiguation=bool(needs_disambiguation),
                    anthology_candidate=bool(anthology_candidate),
                )
                media_files.append(media_file)

    # Use first path as root_path for ScanResult
    # (or we could track multiple roots if needed)
    root_path = paths[0] if paths else Path(".")

    return ScanResult(
        root_path=root_path,
        media_type=media_type,
        files=media_files,
        total_size=total_size,
        file_count=len(media_files),
    )


def _walk_directory(path: Path) -> list[Path]:
    """Recursively walk a directory and return all file paths.

    Args:
        path: Directory path to walk

    Returns:
        List of file paths found recursively
    """
    files: list[Path] = []

    for item in path.rglob("*"):
        if item.is_file():
            files.append(item)

    return files


def _compute_sha256(file_path: Path) -> str:
    """Compute SHA-256 hash of a file.

    Args:
        file_path: Path to file

    Returns:
        Hexadecimal string of SHA-256 hash
    """
    sha256_hash = hashlib.sha256()

    with open(file_path, "rb") as f:
        # Read file in chunks to handle large files
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)

    return sha256_hash.hexdigest()
