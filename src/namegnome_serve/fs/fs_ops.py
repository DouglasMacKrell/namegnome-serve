"""Atomic filesystem operations with rollback capability.

This module provides safe rename/move operations with collision handling,
rollback manifest generation, and cross-platform compatibility.
"""

import json
import os
import shutil
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from namegnome_serve.fs.manifest import RollbackWriter
from namegnome_serve.fs.paths import (
    ensure_parent_dir,
    get_backup_path,
    get_file_stats,
    get_temp_path_for_case_change,
    is_case_insensitive_fs,
    normalize_path,
)
from namegnome_serve.routes.schemas import PlanItem
from namegnome_serve.utils.debug import debug


@dataclass
class ApplyOutcome:
    """Result of a filesystem operation."""

    src: Path
    dst: Path
    status: Literal["applied", "skipped_collision", "failed", "noop"]
    op: Literal["rename", "noop"] = "rename"
    reason: str | None = None
    backup_path: Path | None = None
    pre: dict[str, Any] | None = None
    post: dict[str, Any] | None = None


@dataclass
class ApplyReport:
    """Summary report of plan application."""

    total_items: int
    applied_count: int
    skipped_count: int
    failed_count: int
    report_id: str
    manifest_path: Path | None = None
    errors: list[str] | None = None


def rename_with_rollback(
    src: Path,
    dst: Path,
    manifest: RollbackWriter,
    *,
    on_collision: Literal["backup", "overwrite", "skip"] = "backup",
    dry_run: bool = False,
    hash_before: bool = False,
) -> ApplyOutcome:
    """Perform atomic rename with rollback manifest recording.

    Args:
        src: Source file path
        dst: Destination file path
        manifest: Rollback manifest writer
        on_collision: Strategy for handling destination collisions
        dry_run: If True, simulate operation without filesystem changes
        hash_before: If True, compute hash before operation

    Returns:
        ApplyOutcome with operation result
    """
    # Normalize paths
    src = normalize_path(src)
    dst = normalize_path(dst)

    # Get pre-operation stats
    pre_stats = get_file_stats(src) if src.exists() else {}

    # Handle dry run
    if dry_run:
        entry = {
            "ts": datetime.now(UTC).isoformat(),
            "op": "noop",
            "src_before": str(src),
            "dst_after": str(dst),
            "status": "noop",
            "collision_strategy": on_collision,
            "reason": "dry_run_mode",
        }
        manifest.append(entry)
        return ApplyOutcome(
            src=src,
            dst=dst,
            status="noop",
            op="noop",
            reason="dry_run_mode",
            pre=pre_stats,
        )

    # Check for source existence
    if not src.exists():
        entry = {
            "ts": datetime.now(UTC).isoformat(),
            "op": "rename",
            "src_before": str(src),
            "dst_after": str(dst),
            "status": "failed",
            "collision_strategy": on_collision,
            "reason": "source file does not exist",
        }
        manifest.append(entry)
        return ApplyOutcome(
            src=src,
            dst=dst,
            status="failed",
            reason="source file does not exist",
            pre=pre_stats,
        )

    # Handle destination collision
    backup_path: Path | None = None
    if dst.exists():
        if on_collision == "skip":
            entry = {
                "ts": datetime.now(UTC).isoformat(),
                "op": "rename",
                "src_before": str(src),
                "dst_after": str(dst),
                "status": "skipped_collision",
                "collision_strategy": on_collision,
                "reason": "destination exists",
            }
            manifest.append(entry)
            return ApplyOutcome(
                src=src,
                dst=dst,
                status="skipped_collision",
                reason="destination exists",
                pre=pre_stats,
            )
        elif on_collision == "backup":
            backup_path = get_backup_path(dst)
            try:
                shutil.move(str(dst), str(backup_path))
                debug(f"Backed up existing file to: {backup_path}")
            except OSError as e:
                entry = {
                    "ts": datetime.now(UTC).isoformat(),
                    "op": "rename",
                    "src_before": str(src),
                    "dst_after": str(dst),
                    "status": "failed",
                    "collision_strategy": on_collision,
                    "reason": f"failed to backup existing file: {e}",
                }
                manifest.append(entry)
                return ApplyOutcome(
                    src=src,
                    dst=dst,
                    status="failed",
                    reason=f"failed to backup existing file: {e}",
                    pre=pre_stats,
                )
        elif on_collision == "overwrite":
            try:
                dst.unlink()
                debug(f"Removed existing file: {dst}")
            except OSError as e:
                entry = {
                    "ts": datetime.now(UTC).isoformat(),
                    "op": "rename",
                    "src_before": str(src),
                    "dst_after": str(dst),
                    "status": "failed",
                    "collision_strategy": on_collision,
                    "reason": f"failed to remove existing file: {e}",
                }
                manifest.append(entry)
                return ApplyOutcome(
                    src=src,
                    dst=dst,
                    status="failed",
                    reason=f"failed to remove existing file: {e}",
                    pre=pre_stats,
                )

    # Ensure destination parent directory exists
    try:
        ensure_parent_dir(dst)
    except OSError as e:
        entry = {
            "ts": datetime.now(UTC).isoformat(),
            "op": "rename",
            "src_before": str(src),
            "dst_after": str(dst),
            "status": "failed",
            "collision_strategy": on_collision,
            "reason": f"failed to create destination directory: {e}",
        }
        manifest.append(entry)
        return ApplyOutcome(
            src=src,
            dst=dst,
            status="failed",
            reason=f"failed to create destination directory: {e}",
            pre=pre_stats,
        )

    # Handle case-insensitive filesystem case changes
    if (
        is_case_insensitive_fs(src)
        and str(src).lower() == str(dst).lower()
        and src != dst
    ):
        temp_path = get_temp_path_for_case_change(dst)
        try:
            # Two-step rename for case changes
            src.rename(temp_path)
            temp_path.rename(dst)
            debug(f"Case change rename: {src} -> {temp_path} -> {dst}")
        except OSError as e:
            # Try to restore from temp if it exists
            if temp_path.exists():
                try:
                    temp_path.rename(src)
                except OSError:
                    pass
            entry = {
                "ts": datetime.now(UTC).isoformat(),
                "op": "rename",
                "src_before": str(src),
                "dst_after": str(dst),
                "status": "failed",
                "collision_strategy": on_collision,
                "reason": f"failed case change rename: {e}",
            }
            manifest.append(entry)
            return ApplyOutcome(
                src=src,
                dst=dst,
                status="failed",
                reason=f"failed case change rename: {e}",
                pre=pre_stats,
            )
    else:
        # Standard rename operation
        try:
            # Try direct rename first
            src.rename(dst)
            debug(f"Direct rename: {src} -> {dst}")
        except OSError as e:
            if e.errno == 18:  # EXDEV - Invalid cross-device link
                # Cross-device move: copy + fsync + remove
                try:
                    shutil.copy2(str(src), str(dst))
                    os.fsync(dst.open("rb").fileno())
                    src.unlink()
                    debug(f"Cross-device move: {src} -> {dst}")
                except OSError as copy_e:
                    # Clean up partial copy
                    if dst.exists():
                        try:
                            dst.unlink()
                        except OSError:
                            pass
                    entry = {
                        "ts": datetime.now(UTC).isoformat(),
                        "op": "rename",
                        "src_before": str(src),
                        "dst_after": str(dst),
                        "status": "failed",
                        "collision_strategy": on_collision,
                        "reason": f"failed cross-device move: {copy_e}",
                    }
                    manifest.append(entry)
                    return ApplyOutcome(
                        src=src,
                        dst=dst,
                        status="failed",
                        reason=f"failed cross-device move: {copy_e}",
                        pre=pre_stats,
                    )
            else:
                entry = {
                    "ts": datetime.now(UTC).isoformat(),
                    "op": "rename",
                    "src_before": str(src),
                    "dst_after": str(dst),
                    "status": "failed",
                    "collision_strategy": on_collision,
                    "reason": f"rename failed: {e}",
                }
                manifest.append(entry)
                return ApplyOutcome(
                    src=src,
                    dst=dst,
                    status="failed",
                    reason=f"rename failed: {e}",
                    pre=pre_stats,
                )

    # Get post-operation stats
    post_stats = get_file_stats(dst) if dst.exists() else {}

    # Record successful operation
    entry = {
        "ts": datetime.now(UTC).isoformat(),
        "op": "rename",
        "src_before": str(src),
        "dst_after": str(dst),
        "status": "applied",
        "collision_strategy": on_collision,
        "pre": json.dumps(pre_stats) if pre_stats else "{}",
        "post": json.dumps(post_stats) if post_stats else "{}",
    }

    # Add backup path if we backed up an existing file
    if backup_path is not None:
        entry["backup_path"] = str(backup_path)

    manifest.append(entry)

    return ApplyOutcome(
        src=src,
        dst=dst,
        status="applied",
        backup_path=backup_path,
        pre=pre_stats,
        post=post_stats,
    )


def apply_plan_items(
    items: list[PlanItem],
    *,
    root: Path,
    plan_id: str,
    mode: Literal["transactional", "continue_on_error", "dry_run"] = "transactional",
    on_collision: Literal["backup", "overwrite", "skip"] = "backup",
) -> ApplyReport:
    """Apply a list of plan items with rollback manifest.

    Args:
        items: List of plan items to apply
        root: Root directory for the apply operation
        plan_id: Plan identifier
        mode: Apply mode (transactional, continue_on_error, dry_run)
        on_collision: Collision handling strategy

    Returns:
        ApplyReport with operation summary
    """
    report_id = str(uuid.uuid4())
    applied_count = 0
    skipped_count = 0
    failed_count = 0
    errors: list[str] = []

    with RollbackWriter(
        report_id=report_id,
        root=root,
        mode=mode,
        collision_strategy=on_collision,
        plan_id=plan_id,
    ) as manifest:
        for item in items:
            try:
                outcome = rename_with_rollback(
                    src=item.src_path,
                    dst=item.dst_path,
                    manifest=manifest,
                    on_collision=on_collision,
                    dry_run=(mode == "dry_run"),
                )

                if outcome.status == "applied":
                    applied_count += 1
                elif outcome.status == "skipped_collision":
                    skipped_count += 1
                elif outcome.status == "failed":
                    failed_count += 1
                    if outcome.reason:
                        errors.append(f"{item.src_path}: {outcome.reason}")

                    # Stop on first failure in transactional mode
                    if mode == "transactional":
                        break

            except Exception as e:
                failed_count += 1
                error_msg = f"{item.src_path}: unexpected error: {e}"
                errors.append(error_msg)
                debug(f"Unexpected error in apply_plan_items: {e}")

                # Stop on first failure in transactional mode
                if mode == "transactional":
                    break

    return ApplyReport(
        total_items=len(items),
        applied_count=applied_count,
        skipped_count=skipped_count,
        failed_count=failed_count,
        report_id=report_id,
        manifest_path=root / ".namegnome" / "rollbacks" / f"{report_id}.jsonl",
        errors=errors if errors else None,
    )
