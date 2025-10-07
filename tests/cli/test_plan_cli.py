"""CLI tests for plan review command."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from namegnome_serve.routes.schemas import MediaFile, ScanResult

runner = CliRunner()


@pytest.fixture()
def stub_scan(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_scan(paths: list[Path], media_type: str) -> ScanResult:
        return ScanResult(
            root_path=paths[0],
            media_type=media_type,
            files=[
                MediaFile(
                    path=paths[0] / "file.mkv",
                    size=1,
                    mtime=0,
                    parsed_title="Demo",
                )
            ],
            total_size=1,
            file_count=1,
        )

    monkeypatch.setattr("namegnome_serve.cli.plan.scan", fake_scan)


class StubChain:
    def __init__(self, _engine: object) -> None:
        self.calls: list[tuple[str | None, bool]] = []

    async def plan(
        self, *, plan_id: str | None, as_json: bool, **_: object
    ) -> dict[str, object] | str:
        self.calls.append((plan_id, as_json))
        payload = {"plan_id": plan_id or "generated", "summary": {"total_items": 1}}
        if as_json:
            return json.dumps(payload, sort_keys=True)
        return payload


@pytest.fixture()
def stub_chain(monkeypatch: pytest.MonkeyPatch) -> StubChain:
    chain = StubChain(object())
    monkeypatch.setattr("namegnome_serve.cli.plan.PlanChain", lambda engine: chain)
    return chain


@pytest.fixture()
def stub_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("namegnome_serve.cli.plan.create_plan_engine", lambda: object())


def test_cli_generate_plan_json(
    tmp_path: Path, stub_scan: None, stub_chain: StubChain, stub_engine: None
) -> None:
    from namegnome_serve.cli.plan import app

    result = runner.invoke(
        app,
        [
            "--media-type",
            "tv",
            "--root",
            str(tmp_path),
            "--json",
            "--plan-id",
            "pln_cli",
        ],
    )

    assert result.exit_code == 0
    assert '"plan_id":"pln_cli"' in result.output.replace(" ", "")
    assert stub_chain.calls == [("pln_cli", True)]


def test_cli_reports_engine_errors(
    tmp_path: Path, stub_scan: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from namegnome_serve.cli.plan import app

    monkeypatch.setattr(
        "namegnome_serve.cli.plan.create_plan_engine",
        lambda: (_ for _ in ()).throw(ValueError("API key missing")),
    )

    result = runner.invoke(
        app,
        ["--media-type", "tv", "--root", str(tmp_path)],
    )

    assert result.exit_code == 1
    assert "API key missing" in result.output
