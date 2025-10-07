"""Plan chain helper for producing PlanReview payloads."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from namegnome_serve.core.plan_engine import PlanEngine
from namegnome_serve.core.plan_service import (
    plan_scan_result,
    plan_scan_result_json,
)
from namegnome_serve.routes.schemas import ScanResult


class PlanChain:
    """High-level orchestration entry point for planning."""

    def __init__(self, engine: PlanEngine) -> None:
        self._engine = engine

    async def plan(
        self,
        *,
        scan_result: ScanResult,
        candidate_map: dict[str, Sequence[dict[str, object]]] | None = None,
        plan_id: str | None = None,
        scan_id: str | None = None,
        source_fingerprint: str | None = None,
        generated_at: datetime | None = None,
        as_json: bool = False,
    ) -> dict[str, object] | str:
        """Produce a plan review dictionary or JSON payload."""

        if as_json:
            return await plan_scan_result_json(
                engine=self._engine,
                scan_result=scan_result,
                candidate_map=candidate_map,
                plan_id=plan_id,
                scan_id=scan_id,
                source_fingerprint=source_fingerprint,
                generated_at=generated_at,
            )

        return await plan_scan_result(
            engine=self._engine,
            scan_result=scan_result,
            candidate_map=candidate_map,
            plan_id=plan_id,
            scan_id=scan_id,
            source_fingerprint=source_fingerprint,
            generated_at=generated_at,
        )
