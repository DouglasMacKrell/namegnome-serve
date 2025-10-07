"""CLI entry point for generating PlanReview payloads."""

from __future__ import annotations

import asyncio
import importlib
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any

if TYPE_CHECKING:  # pragma: no cover - typing only
    import typer
    from typer import Typer as TyperType
else:  # pragma: no cover - runtime fallback for typing
    typer = importlib.import_module("typer")
    TyperType = Any

from namegnome_serve.chains.plan_chain import PlanChain
from namegnome_serve.core.plan_service import create_plan_engine
from namegnome_serve.core.scanner import scan

app: TyperType = typer.Typer(help="Generate planning previews with PlanReview output.")


RootOption = Annotated[
    Path,
    typer.Option("--root", help="Root directory to plan."),
]
MediaTypeOption = Annotated[
    str,
    typer.Option("--media-type", help="Media type to plan (tv, movie, music)."),
]
PlanIdOption = Annotated[
    str | None,
    typer.Option("--plan-id", help="Optional plan identifier."),
]
ScanIdOption = Annotated[
    str | None,
    typer.Option("--scan-id", help="Optional scan identifier."),
]
JsonFlag = Annotated[
    bool,
    typer.Option("--json", help="Emit JSON instead of pretty-printed dict."),
]
VerboseFlag = Annotated[
    bool,
    typer.Option("--verbose", help="Print summary counts."),
]


def generate_plan(  # noqa: D401
    root: RootOption,
    media_type: MediaTypeOption,
    plan_id: PlanIdOption = None,
    scan_id: ScanIdOption = None,
    json_output: JsonFlag = False,
    verbose: VerboseFlag = False,
) -> None:
    """Run planning for a directory and print the PlanReview payload."""

    try:
        engine = create_plan_engine()
    except ValueError as exc:  # Missing API keys, etc.
        typer.secho(
            f"Failed to create plan engine: {exc}", err=True, fg=typer.colors.RED
        )
        raise typer.Exit(code=1) from exc

    chain = PlanChain(engine)

    scan_result = scan(paths=[root], media_type=media_type)  # type: ignore[arg-type]
    generated_at = datetime.now(UTC)

    result = asyncio.run(
        chain.plan(
            scan_result=scan_result,
            plan_id=plan_id,
            scan_id=scan_id,
            generated_at=generated_at,
            as_json=json_output,
        )
    )

    if json_output:
        typer.echo(result)
        return

    if not isinstance(result, dict):
        typer.secho("Unexpected planner payload.", err=True, fg=typer.colors.RED)
        raise typer.Exit(code=1)

    result_dict: dict[str, object] = result
    typer.echo(json.dumps(result_dict, indent=2, sort_keys=True))

    if verbose:
        summary = result_dict.get("summary", {})
        if isinstance(summary, dict):
            value = summary.get("total_items", 0)
            try:
                total_items = int(value)
            except (TypeError, ValueError):
                total_items = 0
        else:
            total_items = 0
        typer.secho(f"total_items: {total_items}", fg=typer.colors.GREEN)


def run_cli(args: Sequence[str] | None = None) -> None:
    app(args=args)


app.command("generate")(generate_plan)
