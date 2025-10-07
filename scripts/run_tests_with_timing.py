#!/usr/bin/env python3
"""Run tests with comprehensive timing diagnostics."""

import subprocess
import sys
import time
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from timing_diagnostics import generate_report, timing

console = Console()


def run_tests_with_timing():
    """Run pytest with comprehensive timing analysis."""

    console.print(
        Panel.fit(
            "🧪 [bold blue]NameGnome Serve Test Runner with Timing[/bold blue]",
            border_style="blue",
        )
    )

    # Start timing
    timing.checkpoint("Test runner started", "Initializing timing diagnostics")

    # Check if we're in the right directory
    if not Path("pyproject.toml").exists():
        console.print("❌ [red]Not in project root directory[/red]")
        sys.exit(1)

    timing.checkpoint("Project validation", "Found pyproject.toml")

    # Run pytest with timing
    cmd = [
        "poetry",
        "run",
        "pytest",
        "--no-cov",
        "--durations=20",
        "--timeout=30",
        "-v",
    ]

    console.print(f"🚀 [green]Running: {' '.join(cmd)}[/green]")
    timing.checkpoint("Pytest command", f"Executing: {' '.join(cmd)}")

    start_time = time.time()

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Running tests...", total=None)

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )

            progress.update(task, description="Tests completed!")

    except subprocess.TimeoutExpired:
        timing.checkpoint("Test timeout", "Tests exceeded 5 minute limit")
        console.print("⏰ [yellow]Tests timed out after 5 minutes[/yellow]")
        return False

    except KeyboardInterrupt:
        timing.checkpoint("Test interrupted", "User cancelled tests")
        console.print("🛑 [yellow]Tests interrupted by user[/yellow]")
        return False

    duration = time.time() - start_time
    timing.checkpoint("Test execution", f"Completed in {duration:.2f}s")

    # Analyze results
    if result.returncode == 0:
        console.print("✅ [green]All tests passed![/green]")
        timing.checkpoint("Test success", "All tests passed")
    else:
        console.print("❌ [red]Some tests failed[/red]")
        timing.checkpoint("Test failure", f"Exit code: {result.returncode}")

    # Save output for analysis
    with open("test_results.log", "w") as f:
        f.write(result.stdout)
        if result.stderr:
            f.write("\n--- STDERR ---\n")
            f.write(result.stderr)

    timing.checkpoint("Results saved", "Written to test_results.log")

    # Generate comprehensive report
    console.print("\n" + "=" * 60)
    generate_report()

    return result.returncode == 0


if __name__ == "__main__":
    success = run_tests_with_timing()
    sys.exit(0 if success else 1)
