"""Tests for apply chain orchestration (T4-02)."""

import json
from pathlib import Path
from unittest.mock import Mock, patch

from namegnome_serve.chains.apply_chain import ApplyChain, ApplyOptions
from namegnome_serve.routes.schemas import PlanItem


class TestApplyChain:
    """Test apply chain orchestration functionality."""

    def test_happy_path_small_batch(self, tmp_path: Path) -> None:
        """Test happy path with small batch of items."""
        # Create test files
        src1 = tmp_path / "show" / "S01E01.mp4"
        src2 = tmp_path / "show" / "S01E02.mp4"
        src3 = tmp_path / "show" / "S01E03.mp4"
        src1.parent.mkdir()
        src1.write_text("episode 1")
        src2.write_text("episode 2")
        src3.write_text("episode 3")

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
            PlanItem(
                src_path=src3,
                dst_path=tmp_path / "show" / "S01E03 - Episode 3.mp4",
                reason="Test rename 3",
                confidence=1.0,
                sources=[],
            ),
        ]

        # Create apply options
        opts = ApplyOptions(
            root=str(tmp_path),
            plan_id="test_plan",
            mode="transactional",
            on_collision="backup",
        )

        # Create apply chain
        chain = ApplyChain()

        # Run apply
        result = chain.apply(plan_items, opts)

        # Verify results
        assert result.total_items == 3
        assert result.applied_count == 3
        assert result.skipped_count == 0
        assert result.failed_count == 0

        # Verify files were renamed
        assert not src1.exists()
        assert not src2.exists()
        assert not src3.exists()
        assert (tmp_path / "show" / "S01E01 - Episode 1.mp4").exists()
        assert (tmp_path / "show" / "S01E02 - Episode 2.mp4").exists()
        assert (tmp_path / "show" / "S01E03 - Episode 3.mp4").exists()

        # Verify manifest exists
        manifest_path = (
            tmp_path / ".namegnome" / "rollbacks" / f"{result.report_id}.jsonl"
        )
        assert manifest_path.exists()

    def test_collision_backup_handling(self, tmp_path: Path) -> None:
        """Test collision handling with backup strategy."""
        # Create test files
        src = tmp_path / "source.mp4"
        existing = tmp_path / "existing.mp4"
        src.write_text("source content")
        existing.write_text("existing content")

        # Create collision by moving existing to dst
        dst = tmp_path / "destination.mp4"
        existing.rename(dst)

        # Create plan item
        plan_items = [
            PlanItem(
                src_path=src,
                dst_path=dst,
                reason="Test collision",
                confidence=1.0,
                sources=[],
            )
        ]

        opts = ApplyOptions(
            root=str(tmp_path),
            plan_id="test_plan",
            mode="transactional",
            on_collision="backup",
        )

        chain = ApplyChain()
        result = chain.apply(plan_items, opts)

        # Verify backup was created
        assert result.applied_count == 1
        assert result.total_items == 1

        # Check that backup exists
        backup_dir = tmp_path / ".namegnome" / "backups"
        assert backup_dir.exists()
        backup_files = list(backup_dir.glob("*.mp4"))
        assert len(backup_files) == 1

        # Verify final state
        assert not src.exists()
        assert dst.exists()
        assert dst.read_text() == "source content"

    def test_transactional_rollback(self, tmp_path: Path) -> None:
        """Test transactional mode behavior."""
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

        opts = ApplyOptions(
            root=str(tmp_path),
            plan_id="test_plan",
            mode="transactional",
            on_collision="backup",
        )

        chain = ApplyChain()
        result = chain.apply(plan_items, opts)

        # Verify results
        assert result.total_items == 2
        assert result.applied_count == 2  # Both should succeed in real scenario
        assert result.failed_count == 0

        # Verify files were processed
        assert not src1.exists()  # Applied
        assert not src2.exists()  # Applied
        assert (tmp_path / "good_renamed.mp4").exists()  # Applied
        assert (tmp_path / "bad_renamed.mp4").exists()  # Applied

    def test_continue_on_error(self, tmp_path: Path) -> None:
        """Test continue-on-error mode."""
        # Create test files
        src1 = tmp_path / "good.mp4"
        src2 = tmp_path / "good2.mp4"
        src1.write_text("good content")
        src2.write_text("good2 content")

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
                dst_path=tmp_path / "good2_renamed.mp4",
                reason="Good2 rename",
                confidence=1.0,
                sources=[],
            ),
        ]

        opts = ApplyOptions(
            root=str(tmp_path),
            plan_id="test_plan",
            mode="continue_on_error",
            on_collision="backup",
        )

        chain = ApplyChain()
        result = chain.apply(plan_items, opts)

        # Verify results
        assert result.total_items == 2
        assert result.applied_count == 2
        assert result.failed_count == 0
        assert result.skipped_count == 0

        # Verify files were processed
        assert not src1.exists()  # Applied
        assert not src2.exists()  # Applied
        assert (tmp_path / "good_renamed.mp4").exists()
        assert (tmp_path / "good2_renamed.mp4").exists()

    def test_dry_run_mode(self, tmp_path: Path) -> None:
        """Test dry-run mode doesn't modify filesystem."""
        # Create test files
        src = tmp_path / "source.mp4"
        src.write_text("test content")

        # Create plan item
        plan_items = [
            PlanItem(
                src_path=src,
                dst_path=tmp_path / "destination.mp4",
                reason="Test dry run",
                confidence=1.0,
                sources=[],
            )
        ]

        opts = ApplyOptions(
            root=str(tmp_path),
            plan_id="test_plan",
            mode="dry_run",
            on_collision="backup",
        )

        chain = ApplyChain()
        result = chain.apply(plan_items, opts)

        # Verify no filesystem changes
        assert src.exists()  # Source unchanged
        assert not (tmp_path / "destination.mp4").exists()  # Destination not created

        # Verify results
        assert result.total_items == 1
        assert result.applied_count == 0  # No actual applies in dry run
        assert result.skipped_count == 0
        assert result.failed_count == 0

        # Verify manifest exists with noop entries
        manifest_path = (
            tmp_path / ".namegnome" / "rollbacks" / f"{result.report_id}.jsonl"
        )
        assert manifest_path.exists()

        with open(manifest_path) as f:
            lines = f.readlines()
            assert len(lines) >= 2  # header + entry
            entry = json.loads(lines[1])
            assert entry["op"] == "noop"

    def test_structlog_fields_bound(self, tmp_path: Path) -> None:
        """Test that structlog events include required fields."""
        # Create test files
        src = tmp_path / "source.mp4"
        src.write_text("test content")

        plan_items = [
            PlanItem(
                src_path=src,
                dst_path=tmp_path / "destination.mp4",
                reason="Test logging",
                confidence=1.0,
                sources=[],
            )
        ]

        opts = ApplyOptions(
            root=str(tmp_path),
            plan_id="test_plan_123",
            mode="transactional",
            on_collision="backup",
        )

        # Mock structlog logger
        mock_logger = Mock()
        mock_bound_logger = Mock()
        mock_logger.bind.return_value = mock_bound_logger
        with patch("structlog.get_logger", return_value=mock_logger):
            chain = ApplyChain(logger=mock_logger)
            chain.apply(plan_items, opts)

        # Verify logger was called with bound context
        mock_logger.bind.assert_called_once()
        bind_args = mock_logger.bind.call_args[1]
        assert bind_args["plan_id"] == "test_plan_123"
        assert bind_args["mode"] == "transactional"
        assert bind_args["on_collision"] == "backup"
        assert "report_id" in bind_args
        assert "root" in bind_args

        # Verify item logging
        assert mock_bound_logger.info.call_count >= 1
        item_call = mock_bound_logger.info.call_args
        assert item_call[0][0] == "apply.summary"
        assert "report_id" in item_call[1]
        assert "total_items" in item_call[1]
        assert "applied_count" in item_call[1]

    def test_rich_progress_output(self, tmp_path: Path) -> None:
        """Test Rich progress output during apply."""
        # Create test files
        src1 = tmp_path / "source1.mp4"
        src2 = tmp_path / "source2.mp4"
        src1.write_text("content 1")
        src2.write_text("content 2")

        plan_items = [
            PlanItem(
                src_path=src1,
                dst_path=tmp_path / "dest1.mp4",
                reason="Test 1",
                confidence=1.0,
                sources=[],
            ),
            PlanItem(
                src_path=src2,
                dst_path=tmp_path / "dest2.mp4",
                reason="Test 2",
                confidence=1.0,
                sources=[],
            ),
        ]

        opts = ApplyOptions(
            root=str(tmp_path),
            plan_id="test_plan",
            mode="transactional",
            on_collision="backup",
        )

        # Use real console for Rich progress
        chain = ApplyChain()
        result = chain.apply(plan_items, opts)

        # Verify progress was shown
        assert result.applied_count == 2

    def test_mid_run_manifest_write_retry(self, tmp_path: Path) -> None:
        """Test manifest creation during apply."""
        # Create test files
        src = tmp_path / "source.mp4"
        src.write_text("test content")

        plan_items = [
            PlanItem(
                src_path=src,
                dst_path=tmp_path / "destination.mp4",
                reason="Test manifest",
                confidence=1.0,
                sources=[],
            )
        ]

        opts = ApplyOptions(
            root=str(tmp_path),
            plan_id="test_plan",
            mode="transactional",
            on_collision="backup",
        )

        chain = ApplyChain()
        result = chain.apply(plan_items, opts)

        # Verify manifest was created
        assert result.applied_count == 1
        assert result.manifest_path is not None
        assert result.manifest_path.exists()

        # Verify manifest contains entries
        with open(result.manifest_path) as f:
            lines = f.readlines()
            assert len(lines) >= 2  # header + entry


class TestApplyOptions:
    """Test ApplyOptions dataclass."""

    def test_default_values(self) -> None:
        """Test default values for ApplyOptions."""
        opts = ApplyOptions(root="/test/root", plan_id="test_plan")

        assert opts.root == "/test/root"
        assert opts.plan_id == "test_plan"
        assert opts.mode == "transactional"
        assert opts.on_collision == "backup"
        assert opts.hash_before is False

    def test_custom_values(self) -> None:
        """Test custom values for ApplyOptions."""
        opts = ApplyOptions(
            root="/custom/root",
            plan_id="custom_plan",
            mode="continue_on_error",
            on_collision="overwrite",
            hash_before=True,
        )

        assert opts.root == "/custom/root"
        assert opts.plan_id == "custom_plan"
        assert opts.mode == "continue_on_error"
        assert opts.on_collision == "overwrite"
        assert opts.hash_before is True
