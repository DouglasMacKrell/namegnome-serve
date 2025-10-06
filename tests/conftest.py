"""Pytest configuration and fixtures for NameGnome Serve tests."""

import pytest


@pytest.fixture
def sample_media_files() -> list[dict[str, str]]:
    """Sample media file test data."""
    return [
        {
            "path": "Paw Patrol - S07E04.mp4",
            "media_type": "tv",
            "season": "07",
            "episode": "04",
        },
        {
            "path": "The Matrix (1999).mkv",
            "media_type": "movie",
            "year": "1999",
        },
        {
            "path": "Daft Punk/Discovery (2001)/Track01 - One More Time.mp3",
            "media_type": "music",
            "track": "01",
        },
    ]
