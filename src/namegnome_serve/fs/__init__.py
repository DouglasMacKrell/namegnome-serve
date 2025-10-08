"""Filesystem operations for atomic rename and rollback functionality.

This module provides safe filesystem operations with rollback capability,
including atomic rename operations, collision handling, and manifest generation.
"""

from namegnome_serve.fs.fs_ops import (
    ApplyOutcome,
    apply_plan_items,
    rename_with_rollback,
)
from namegnome_serve.fs.manifest import RollbackWriter
from namegnome_serve.fs.paths import normalize_path

__all__ = [
    "ApplyOutcome",
    "RollbackWriter",
    "apply_plan_items",
    "normalize_path",
    "rename_with_rollback",
]
