"""Apply chain for orchestrating filesystem operations with rollback.

This module provides the ApplyChain class that orchestrates the apply phase
of the scan→plan→apply pipeline, handling rollback manifests, structured logging,
and Rich console output.
"""

import json
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import structlog
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
)

from namegnome_serve.fs.fs_ops import (
    ApplyOutcome,
    ApplyReport,
    apply_plan_items,
    rename_with_rollback,
)
from namegnome_serve.fs.manifest import RollbackWriter
from namegnome_serve.routes.schemas import PlanItem

Mode = Literal["transactional", "continue_on_error", "dry_run"]
OnCollision = Literal["backup", "overwrite", "skip"]


@dataclass
class ApplyOptions:
    """Options for apply operations.

    Attributes:
        root: Root directory for the apply operation
        plan_id: Plan identifier
        mode: Apply mode (transactional, continue_on_error, dry_run)
        on_collision: Collision handling strategy (backup, overwrite, skip)
        hash_before: Whether to compute file hashes before operations
    """

    root: str
    plan_id: str
    mode: Mode = "transactional"
    on_collision: OnCollision = "backup"
    hash_before: bool = False


class ApplyChain:
    """Orchestrates apply operations with rollback manifests and structured logging.

    This chain handles the apply phase of the scan→plan→apply pipeline,
    providing atomic filesystem operations with rollback capability,
    structured logging, and Rich console output.
    """

    def __init__(self, logger: Any = None, ui: Console | None = None) -> None:
        """Initialize apply chain.

        Args:
            logger: Optional structlog logger instance
            ui: Optional Rich console for output
        """
        self._logger = logger or structlog.get_logger()
        self._ui = ui or Console()

    def apply(self, items: Sequence[PlanItem], opts: ApplyOptions) -> ApplyReport:
        """Apply a sequence of plan items with rollback manifest.

        Args:
            items: Sequence of plan items to apply
            opts: Apply options including mode and collision strategy

        Returns:
            ApplyReport with operation summary
        """
        # Use the existing apply_plan_items function from T4-01
        # This provides the core functionality we need
        return self._apply_with_logging(items, opts)

    def _apply_with_logging(
        self, items: Sequence[PlanItem], opts: ApplyOptions
    ) -> ApplyReport:
        """Apply items with enhanced logging and Rich output."""
        root_path = Path(opts.root)

        # Generate report ID
        import uuid

        report_id = str(uuid.uuid4())

        # Bind logger context with report_id
        bound_logger = self._logger.bind(
            plan_id=opts.plan_id,
            report_id=report_id,
            root=str(root_path),
            mode=opts.mode,
            on_collision=opts.on_collision,
        )

        # Show progress with Rich
        with self._create_progress() as progress:
            task = progress.add_task(
                f"Apply — {opts.mode}", total=len(items), start=False
            )

            # Use the existing apply_plan_items function
            result = apply_plan_items(
                list(items),
                root=root_path,
                plan_id=opts.plan_id,
                mode=opts.mode,
                on_collision=opts.on_collision,
            )

            # Update progress
            progress.update(
                task,
                completed=result.applied_count
                + result.skipped_count
                + result.failed_count,
            )

            # Log summary
            bound_logger.info(
                "apply.summary",
                report_id=result.report_id,
                total_items=result.total_items,
                applied_count=result.applied_count,
                skipped_count=result.skipped_count,
                failed_count=result.failed_count,
                manifest_path=str(result.manifest_path)
                if result.manifest_path
                else None,
            )

            return result

    def _create_progress(self) -> Progress:
        """Create Rich progress display."""
        return Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=self._ui,
            transient=False,
        )

    async def _apply_item_with_logging(
        self,
        item: PlanItem,
        manifest: RollbackWriter,
        opts: ApplyOptions,
        bound_logger: Any,
    ) -> ApplyOutcome:
        """Apply a single item with logging."""
        start_time = time.time()

        # Apply the item
        outcome = rename_with_rollback(
            src=item.src_path,
            dst=item.dst_path,
            manifest=manifest,
            on_collision=opts.on_collision,
            dry_run=(opts.mode == "dry_run"),
            hash_before=opts.hash_before,
        )

        elapsed_ms = int((time.time() - start_time) * 1000)

        # Log the item result
        bound_logger.info(
            "apply.item",
            src=str(item.src_path),
            dst=str(item.dst_path),
            status=outcome.status,
            reason=outcome.reason,
            backup_path=str(outcome.backup_path) if outcome.backup_path else None,
            elapsed_ms=elapsed_ms,
        )

        # Show Rich output
        self._show_item_result(outcome, item)

        return outcome

    def _show_item_result(self, outcome: ApplyOutcome, item: PlanItem) -> None:
        """Show Rich output for item result."""
        if outcome.status == "applied":
            self._ui.print(
                f"✅ [green]APPLIED[/green] {item.src_path.name} → {item.dst_path.name}"
            )
        elif outcome.status == "skipped_collision":
            self._ui.print(
                f"⚠️ [yellow]SKIPPED[/yellow] (collision) "
                f"{item.src_path.name} → {item.dst_path.name}"
            )
        elif outcome.status == "failed":
            self._ui.print(
                f"❌ [red]FAILED[/red] {item.src_path.name} → {item.dst_path.name} "
                f"({outcome.reason})"
            )
        elif outcome.status == "noop":
            self._ui.print(
                f"🔍 [blue]NOOP[/blue] {item.src_path.name} → {item.dst_path.name} "
                f"(dry run)"
            )

    async def _rollback_from_manifest(self, manifest_path: Path) -> None:
        """Rollback applied items using manifest."""
        self._ui.print("🔄 [yellow]Rolling back...[/yellow]")

        # Read manifest and rollback in reverse order
        if not manifest_path.exists():
            self._ui.print("❌ [red]No manifest found for rollback[/red]")
            return

        with open(manifest_path) as f:
            lines = f.readlines()

        # Skip header, process entries in reverse
        entries = [json.loads(line) for line in lines[1:] if line.strip()]

        for entry in reversed(entries):
            if entry.get("status") == "applied" and entry.get("op") == "rename":
                src = Path(entry["src_before"])
                dst = Path(entry["dst_after"])

                try:
                    # Restore original file
                    if dst.exists():
                        dst.rename(src)
                    self._ui.print(f"↩️ [blue]Restored[/blue] {src.name}")
                except OSError as e:
                    self._ui.print(f"❌ [red]Failed to restore[/red] {src.name}: {e}")

        self._ui.print("✅ [green]Rollback completed[/green]")
