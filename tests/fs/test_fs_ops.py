"""Tests for atomic filesystem operations with rollback capability (T4-01)."""

import json
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

from namegnome_serve.fs.fs_ops import (
    ApplyOutcome,
    apply_plan_items,
    rename_with_rollback,
)
from namegnome_serve.fs.manifest import RollbackWriter
from namegnome_serve.routes.schemas import PlanItem


class TestRollbackWriter:
    """Test rollback manifest writer functionality."""

    def test_creates_rollback_directory(self, tmp_path: Path) -> None:
        """Test that rollback directory is created if it doesn't exist."""
        rollback_dir = tmp_path / ".namegnome" / "rollbacks"
        report_id = str(uuid.uuid4())

        RollbackWriter(
            report_id=report_id,
            root=tmp_path,
            mode="transactional",
            collision_strategy="backup",
            plan_id="test_plan",
        )

        # Should create directory
        assert rollback_dir.exists()
        assert rollback_dir.is_dir()

    def test_writes_header_correctly(self, tmp_path: Path) -> None:
        """Test that manifest header is written with correct format."""
        report_id = str(uuid.uuid4())
        writer = RollbackWriter(
            report_id=report_id,
            root=tmp_path,
            mode="transactional",
            collision_strategy="backup",
            plan_id="test_plan",
        )

        writer.write_header()
        writer.close()

        # Read and verify header
        manifest_file = tmp_path / ".namegnome" / "rollbacks" / f"{report_id}.jsonl"
        assert manifest_file.exists()

        with open(manifest_file) as f:
            header_line = f.readline().strip()
            header = json.loads(header_line)

        assert header["type"] == "header"
        assert header["schema_version"] == "1.0"
        assert header["report_id"] == report_id
        assert header["plan_id"] == "test_plan"
        assert header["mode"] == "transactional"
        assert header["collision_strategy"] == "backup"

    def test_appends_entries_correctly(self, tmp_path: Path) -> None:
        """Test that manifest entries are appended correctly."""
        report_id = str(uuid.uuid4())
        writer = RollbackWriter(
            report_id=report_id,
            root=tmp_path,
            mode="transactional",
            collision_strategy="backup",
            plan_id="test_plan",
        )

        writer.write_header()

        # Add test entry
        entry = {
            "ts": "2025-10-07T15:01:25Z",
            "op": "rename",
            "src_before": "/test/src.mp4",
            "dst_after": "/test/dst.mp4",
            "status": "applied",
            "collision_strategy": "backup",
        }
        writer.append(entry)
        writer.close()

        # Verify entries
        manifest_file = tmp_path / ".namegnome" / "rollbacks" / f"{report_id}.jsonl"
        with open(manifest_file) as f:
            lines = f.readlines()

        assert len(lines) == 2  # header + entry
        header = json.loads(lines[0])
        entry_data = json.loads(lines[1])

        assert header["type"] == "header"
        assert entry_data["op"] == "rename"
        assert entry_data["status"] == "applied"


class TestRenameWithRollback:
    """Test atomic rename operations with rollback manifest."""

    def test_happy_path_rename(self, tmp_path: Path) -> None:
        """Test successful rename operation."""
        src = tmp_path / "source.mp4"
        dst = tmp_path / "destination.mp4"
        src.write_text("test content")

        report_id = str(uuid.uuid4())
        writer = RollbackWriter(
            report_id=report_id,
            root=tmp_path,
            mode="transactional",
            collision_strategy="backup",
            plan_id="test_plan",
        )
        writer.write_header()

        outcome = rename_with_rollback(src, dst, writer)

        # Verify file was moved
        assert not src.exists()
        assert dst.exists()
        assert dst.read_text() == "test content"

        # Verify outcome
        assert outcome.status == "applied"
        assert outcome.src == src
        assert outcome.dst == dst
        assert outcome.reason is None

    def test_collision_backup_strategy(self, tmp_path: Path) -> None:
        """Test collision handling with backup strategy."""
        src = tmp_path / "source.mp4"
        dst = tmp_path / "destination.mp4"
        existing = tmp_path / "existing.mp4"

        src.write_text("source content")
        existing.write_text("existing content")

        # Create collision by moving existing to dst
        existing.rename(dst)

        report_id = str(uuid.uuid4())
        writer = RollbackWriter(
            report_id=report_id,
            root=tmp_path,
            mode="transactional",
            collision_strategy="backup",
            plan_id="test_plan",
        )
        writer.write_header()

        outcome = rename_with_rollback(src, dst, writer, on_collision="backup")

        # Verify backup was created
        assert outcome.status == "applied"
        assert outcome.backup_path is not None
        assert outcome.backup_path.exists()
        assert outcome.backup_path.read_text() == "existing content"

        # Verify final state
        assert not src.exists()
        assert dst.exists()
        assert dst.read_text() == "source content"

    def test_collision_skip_strategy(self, tmp_path: Path) -> None:
        """Test collision handling with skip strategy."""
        src = tmp_path / "source.mp4"
        dst = tmp_path / "destination.mp4"
        existing = tmp_path / "existing.mp4"

        src.write_text("source content")
        existing.write_text("existing content")
        existing.rename(dst)

        report_id = str(uuid.uuid4())
        writer = RollbackWriter(
            report_id=report_id,
            root=tmp_path,
            mode="transactional",
            collision_strategy="skip",
            plan_id="test_plan",
        )
        writer.write_header()

        outcome = rename_with_rollback(src, dst, writer, on_collision="skip")

        # Verify skip behavior
        assert outcome.status == "skipped_collision"
        assert outcome.reason == "destination exists"
        assert src.exists()  # Source unchanged
        assert dst.exists()  # Destination unchanged
        assert dst.read_text() == "existing content"

    def test_dry_run_mode(self, tmp_path: Path) -> None:
        """Test dry run mode doesn't modify filesystem."""
        src = tmp_path / "source.mp4"
        dst = tmp_path / "destination.mp4"
        src.write_text("test content")

        report_id = str(uuid.uuid4())
        writer = RollbackWriter(
            report_id=report_id,
            root=tmp_path,
            mode="dry_run",
            collision_strategy="backup",
            plan_id="test_plan",
        )
        writer.write_header()

        outcome = rename_with_rollback(src, dst, writer, dry_run=True)

        # Verify no filesystem changes
        assert src.exists()
        assert not dst.exists()
        assert outcome.status == "noop"
        assert outcome.op == "noop"

    def test_permission_denied_handling(self, tmp_path: Path) -> None:
        """Test handling of permission denied errors."""
        src = tmp_path / "source.mp4"
        dst = tmp_path / "destination.mp4"
        src.write_text("test content")

        report_id = str(uuid.uuid4())
        writer = RollbackWriter(
            report_id=report_id,
            root=tmp_path,
            mode="transactional",
            collision_strategy="backup",
            plan_id="test_plan",
        )
        writer.write_header()

        # Mock permission denied
        with patch("os.rename", side_effect=PermissionError("Permission denied")):
            outcome = rename_with_rollback(src, dst, writer)

        assert outcome.status == "failed"
        assert "Permission denied" in (outcome.reason or "")
        assert src.exists()  # Source unchanged on failure


class TestApplyPlanItems:
    """Test high-level plan application orchestration."""

    def test_apply_plan_items_happy_path(self, tmp_path: Path) -> None:
        """Test applying plan items successfully."""
        # Create test files
        src1 = tmp_path / "show" / "S01E01.mp4"
        src2 = tmp_path / "show" / "S01E02.mp4"
        src1.parent.mkdir()
        src1.write_text("episode 1")
        src2.write_text("episode 2")

        # Create plan items
        plan_items = [
            PlanItem(
                src_path=src1,
                dst_path=tmp_path / "show" / "S01E01 - Episode 1.mp4",
                reason="Test rename 1",
                confidence=1.0,
                sources=[],
            ),
            PlanItem(
                src_path=src2,
                dst_path=tmp_path / "show" / "S01E02 - Episode 2.mp4",
                reason="Test rename 2",
                confidence=1.0,
                sources=[],
            ),
        ]

        report = apply_plan_items(
            plan_items,
            root=tmp_path,
            plan_id="test_plan",
            mode="transactional",
            on_collision="backup",
        )

        # Verify results
        assert report.total_items == 2
        assert report.applied_count == 2
        assert report.skipped_count == 0
        assert report.failed_count == 0

        # Verify files were renamed
        assert not src1.exists()
        assert not src2.exists()
        assert (tmp_path / "show" / "S01E01 - Episode 1.mp4").exists()
        assert (tmp_path / "show" / "S01E02 - Episode 2.mp4").exists()

    def test_apply_plan_items_continue_on_error(self, tmp_path: Path) -> None:
        """Test continue-on-error mode."""
        # Create test files
        src1 = tmp_path / "good.mp4"
        src2 = tmp_path / "bad.mp4"
        src1.write_text("good content")
        src2.write_text("bad content")

        # Create plan items
        plan_items = [
            PlanItem(
                src_path=src1,
                dst_path=tmp_path / "good_renamed.mp4",
                reason="Good rename",
                confidence=1.0,
                sources=[],
            ),
            PlanItem(
                src_path=src2,
                dst_path=tmp_path / "bad_renamed.mp4",
                reason="Bad rename",
                confidence=1.0,
                sources=[],
            ),
        ]

        # Mock one failure
        with patch("namegnome_serve.fs.fs_ops.rename_with_rollback") as mock_rename:
            mock_rename.side_effect = [
                ApplyOutcome(src1, tmp_path / "good_renamed.mp4", "applied"),
                ApplyOutcome(
                    src2, tmp_path / "bad_renamed.mp4", "failed", reason="Test failure"
                ),
            ]

            report = apply_plan_items(
                plan_items,
                root=tmp_path,
                plan_id="test_plan",
                mode="continue_on_error",
                on_collision="backup",
            )

        # Verify results
        assert report.total_items == 2
        assert report.applied_count == 1
        assert report.failed_count == 1
        assert report.skipped_count == 0


class TestPathNormalization:
    """Test path normalization and edge cases."""

    def test_normalize_path_absolute(self, tmp_path: Path) -> None:
        """Test that paths are normalized to absolute."""
        from namegnome_serve.fs.paths import normalize_path

        relative_path = Path("test.mp4")
        normalized = normalize_path(relative_path, tmp_path)

        assert normalized.is_absolute()
        assert normalized == tmp_path / "test.mp4"

    def test_case_insensitive_handling(self, tmp_path: Path) -> None:
        """Test case-insensitive filesystem handling."""
        # This test would be platform-specific
        # On case-insensitive systems, we need temp hop for case-only changes
        pass  # Implementation will handle this in fs_ops.py


class TestManifestWriteFailure:
    """Test handling of manifest write failures."""

    def test_preflight_rollback_directory_failure(self, tmp_path: Path) -> None:
        """Test failure when rollback directory cannot be created."""
        # Make parent directory read-only
        rollback_parent = tmp_path / ".namegnome"
        rollback_parent.mkdir()
        rollback_parent.chmod(0o444)  # Read-only

        try:
            with pytest.raises(OSError, match="Cannot create rollback directory"):
                RollbackWriter(
                    report_id=str(uuid.uuid4()),
                    root=tmp_path,
                    mode="transactional",
                    collision_strategy="backup",
                    plan_id="test_plan",
                )
        finally:
            rollback_parent.chmod(0o755)  # Restore permissions

    def test_mid_run_manifest_write_failure(self, tmp_path: Path) -> None:
        """Test handling of mid-run manifest write failures."""
        src = tmp_path / "source.mp4"
        dst = tmp_path / "destination.mp4"
        src.write_text("test content")

        report_id = str(uuid.uuid4())
        writer = RollbackWriter(
            report_id=report_id,
            root=tmp_path,
            mode="transactional",
            collision_strategy="backup",
            plan_id="test_plan",
        )
        writer.write_header()

        # Mock write failure after header
        with patch.object(writer, "append", side_effect=OSError("Write failed")):
            with pytest.raises(OSError, match="Write failed"):
                rename_with_rollback(src, dst, writer)
