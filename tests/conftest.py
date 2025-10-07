"""Pytest configuration and fixtures for NameGnome Serve tests."""

import os
from pathlib import Path

import pytest


def _load_project_dotenv() -> None:
    """Load environment variables from the project .env file if present."""

    repo_root = Path(__file__).resolve().parents[1]
    env_path = repo_root / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if "#" in value:
            value = value.split("#", 1)[0].strip()

        if key and value and key not in os.environ:
            os.environ[key] = value


_load_project_dotenv()


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
