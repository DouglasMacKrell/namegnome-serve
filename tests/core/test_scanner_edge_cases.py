"""Edge case tests for scanner module to achieve 100% coverage.

These tests cover error conditions and boundary cases not covered by
the main scanner tests.
"""

from pathlib import Path

import pytest

from namegnome_serve.core.scanner import scan


def test_scan_invalid_media_type(tmp_path: Path) -> None:
    """Test that scan raises ValueError for invalid media_type."""
    media_dir = tmp_path / "media"
    media_dir.mkdir()

    with pytest.raises(ValueError, match="Invalid media_type"):
        scan(paths=[media_dir], media_type="invalid")  # type: ignore


def test_scan_non_directory_path(tmp_path: Path) -> None:
    """Test that scan raises ValueError when given a file instead of directory."""
    # Create a file, not a directory
    file_path = tmp_path / "file.txt"
    file_path.write_text("content")

    with pytest.raises(ValueError, match="Path is not a directory"):
        scan(paths=[file_path], media_type="tv")


def test_scan_nonexistent_path() -> None:
    """Test that scan raises FileNotFoundError for nonexistent path."""
    nonexistent = Path("/nonexistent/path/that/does/not/exist")

    with pytest.raises(FileNotFoundError, match="Path does not exist"):
        scan(paths=[nonexistent], media_type="tv")
