"""Path utilities for filesystem operations.

This module provides path normalization and handling utilities for
cross-platform filesystem operations.
"""

import os
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def normalize_path(path: Path, root: Path | None = None) -> Path:
    """Normalize a path for consistent handling.

    Args:
        path: Path to normalize
        root: Optional root directory for relative paths

    Returns:
        Normalized absolute path
    """
    # Convert to Path if needed
    if not isinstance(path, Path):
        path = Path(path)

    # Make absolute using root if provided
    if not path.is_absolute():
        if root is None:
            path = path.resolve()
        else:
            path = (root / path).resolve()
    else:
        path = path.resolve()

    # Normalize Unicode (NFC on macOS, NFD handling)
    if os.name == "posix":  # Unix-like systems
        path = Path(unicodedata.normalize("NFC", str(path)))

    return path


def is_case_insensitive_fs(path: Path) -> bool:
    """Check if the filesystem containing the path is case-insensitive.

    Args:
        path: Path to check filesystem for

    Returns:
        True if filesystem is case-insensitive
    """
    try:
        # Create a temporary test file
        test_dir = path.parent / ".namegnome" / "case_test"
        test_dir.mkdir(parents=True, exist_ok=True)

        test_file1 = test_dir / "test.txt"
        test_file2 = test_dir / "TEST.txt"

        test_file1.write_text("test")

        try:
            test_file2.write_text("TEST")
            case_insensitive = False
        except OSError:
            case_insensitive = True

        # Cleanup
        if test_file1.exists():
            test_file1.unlink()
        if test_file2.exists():
            test_file2.unlink()
        test_dir.rmdir()

        return case_insensitive

    except Exception:
        # Default to False if we can't determine
        return False


def get_temp_path_for_case_change(dst: Path) -> Path:
    """Get a temporary path for case-only changes on case-insensitive filesystems.

    Args:
        dst: Destination path that might conflict due to case

    Returns:
        Temporary path to use for atomic case change
    """
    # Add a unique suffix to avoid conflicts
    import uuid

    temp_suffix = f".tmpcase_{uuid.uuid4().hex[:8]}"
    return dst.with_suffix(dst.suffix + temp_suffix)


def get_backup_path(original_path: Path, backup_dir: Path | None = None) -> Path:
    """Generate a backup path for collision handling.

    Args:
        original_path: Path that needs to be backed up
        backup_dir: Directory to store backup (defaults to .namegnome/backups)

    Returns:
        Path for the backup file
    """
    if backup_dir is None:
        backup_dir = original_path.parent / ".namegnome" / "backups"

    backup_dir.mkdir(parents=True, exist_ok=True)

    # Generate unique backup name
    import uuid

    stem = original_path.stem
    suffix = original_path.suffix
    unique_id = uuid.uuid4().hex[:8]

    backup_name = f"{stem}.bak{unique_id}{suffix}"
    return backup_dir / backup_name


def get_file_stats(path: Path) -> dict[str, Any]:
    """Get file statistics for manifest recording.

    Args:
        path: File path to get stats for

    Returns:
        Dictionary with file statistics
    """
    try:
        stat = path.stat()
        return {
            "size": stat.st_size,
            "mtime": datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat(),
            "inode": stat.st_ino,
        }
    except (OSError, FileNotFoundError):
        return {}


def ensure_parent_dir(path: Path) -> None:
    """Ensure parent directory exists for a path.

    Args:
        path: Path whose parent directory should exist

    Raises:
        OSError: If parent directory cannot be created
    """
    parent = path.parent
    if not parent.exists():
        parent.mkdir(parents=True, exist_ok=True)
