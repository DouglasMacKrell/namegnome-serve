"""Rollback manifest writer for atomic filesystem operations.

This module provides functionality to write rollback manifests in JSONL format,
capturing all filesystem operations for potential rollback.
"""

import json
import os
import platform
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from namegnome_serve.utils.debug import debug


class RollbackWriter:
    """Writes rollback manifests in JSONL format for filesystem operations.

    Each manifest file contains:
    - Header line with metadata (type: "header")
    - One JSON object per operation (rename, skip, etc.)
    """

    def __init__(
        self,
        report_id: str,
        root: Path,
        mode: str,
        collision_strategy: str,
        plan_id: str | None = None,
    ) -> None:
        """Initialize rollback writer.

        Args:
            report_id: Unique identifier for this apply session
            root: Root directory for the apply operation
            mode: Apply mode (transactional, continue_on_error, dry_run)
            collision_strategy: Default collision strategy (backup, overwrite, skip)
            plan_id: Optional plan identifier
        """
        self.report_id = report_id
        self.root = root.resolve()
        self.mode = mode
        self.collision_strategy = collision_strategy
        self.plan_id = plan_id
        self._manifest_path: Path | None = None
        self._manifest_file: Any = None
        self._header_written = False

        # Ensure rollback directory exists and is writable
        self._ensure_rollback_directory()

    def _ensure_rollback_directory(self) -> None:
        """Ensure rollback directory exists and is writable."""
        rollback_dir = self.root / ".namegnome" / "rollbacks"

        try:
            rollback_dir.mkdir(parents=True, exist_ok=True)

            # Test write access
            test_file = rollback_dir / f".test_{uuid.uuid4().hex}"
            test_file.write_text("test")
            test_file.unlink()

        except (OSError, PermissionError) as e:
            raise OSError(
                f"Cannot create rollback directory {rollback_dir}: {e}. "
                "Ensure the directory is writable or choose a different root."
            ) from e

        self._manifest_path = rollback_dir / f"{self.report_id}.jsonl"
        debug(f"Rollback manifest will be written to: {self._manifest_path}")

    def write_header(self) -> None:
        """Write manifest header with session metadata."""
        if self._header_written:
            return

        header = {
            "type": "header",
            "schema_version": "1.0",
            "report_id": self.report_id,
            "plan_id": self.plan_id,
            "generated_at": datetime.now(UTC).isoformat(),
            "root": str(self.root),
            "mode": self.mode,
            "collision_strategy": self.collision_strategy,
            "system": {
                "os": platform.system(),
                "fs_case_insensitive": self._is_case_insensitive_fs(),
            },
        }

        self._write_line(header)
        self._header_written = True
        debug(f"Wrote manifest header for report {self.report_id}")

    def append(self, entry: dict[str, Any]) -> None:
        """Append an operation entry to the manifest.

        Args:
            entry: Operation data to append
        """
        if not self._header_written:
            self.write_header()

        self._write_line(entry)
        debug(
            f"Appended manifest entry: {entry.get('op', 'unknown')} - "
            f"{entry.get('status', 'unknown')}"
        )

    def _write_line(self, data: dict[str, Any]) -> None:
        """Write a JSON line to the manifest file."""
        if self._manifest_file is None:
            if self._manifest_path is None:
                raise RuntimeError("Manifest path not set")
            self._manifest_file = open(self._manifest_path, "w", encoding="utf-8")

        json_line = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        self._manifest_file.write(json_line + "\n")
        self._manifest_file.flush()
        os.fsync(self._manifest_file.fileno())

    def close(self) -> None:
        """Close the manifest file."""
        if self._manifest_file is not None:
            self._manifest_file.close()
            self._manifest_file = None
        debug(f"Closed manifest file: {self._manifest_path}")

    def _is_case_insensitive_fs(self) -> bool:
        """Check if the filesystem is case-insensitive."""
        try:
            # Create test files with different cases
            test_dir = self.root / ".namegnome" / "case_test"
            test_dir.mkdir(parents=True, exist_ok=True)

            test_file1 = test_dir / "test.txt"
            test_file2 = test_dir / "TEST.txt"

            test_file1.write_text("test")

            # If we can't create the second file, filesystem is case-insensitive
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

    def __enter__(self) -> "RollbackWriter":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.close()
