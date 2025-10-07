#!/usr/bin/env python3
"""Timing diagnostics for NameGnome Serve development.

This script provides comprehensive timing analysis for:
- Test execution times
- Provider API response times
- Retry/backoff timing
- Performance bottlenecks
"""

import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table

console = Console()


class TimingDiagnostics:
    """Comprehensive timing analysis for development workflow."""

    def __init__(self):
        self.start_time = time.time()
        self.checkpoints: list[dict[str, Any]] = []
        self.provider_times: dict[str, list[float]] = {}

    def checkpoint(self, name: str, details: str = ""):
        """Record a timing checkpoint."""
        elapsed = time.time() - self.start_time
        self.checkpoints.append(
            {
                "name": name,
                "elapsed": elapsed,
                "timestamp": datetime.now(UTC),
                "details": details,
            }
        )
        console.print(f"⏱️  [{elapsed:.2f}s] {name}: {details}")

    def record_provider_time(self, provider: str, duration: float):
        """Record provider API response time."""
        if provider not in self.provider_times:
            self.provider_times[provider] = []
        self.provider_times[provider].append(duration)

    def analyze_test_timing(self, test_results_file: str = "test_results.log"):
        """Analyze pytest timing from log file."""
        if not Path(test_results_file).exists():
            console.print(f"❌ Test results file not found: {test_results_file}")
            return

        console.print("\n🔍 [bold]Test Timing Analysis[/bold]")

        # Parse pytest durations from log
        slow_tests = []
        with open(test_results_file) as f:
            for line in f:
                if "call     " in line and "s call" in line:
                    # Extract test name and duration
                    parts = line.strip().split()
                    if len(parts) >= 3:
                        duration = float(parts[0].replace("s", ""))
                        test_name = parts[2]
                        if duration > 1.0:  # Tests taking > 1 second
                            slow_tests.append((duration, test_name))

        if slow_tests:
            table = Table(title="🐌 Slow Tests (>1s)")
            table.add_column("Duration", style="red")
            table.add_column("Test", style="yellow")

            for duration, test_name in sorted(slow_tests, reverse=True)[:10]:
                table.add_row(f"{duration:.2f}s", test_name)

            console.print(table)
        else:
            console.print("✅ No slow tests detected!")

    def analyze_provider_performance(self):
        """Analyze provider API performance."""
        if not self.provider_times:
            console.print("📊 No provider timing data recorded")
            return

        console.print("\n📊 [bold]Provider Performance Analysis[/bold]")

        table = Table(title="Provider Response Times")
        table.add_column("Provider", style="cyan")
        table.add_column("Calls", style="green")
        table.add_column("Avg (ms)", style="yellow")
        table.add_column("Min (ms)", style="blue")
        table.add_column("Max (ms)", style="red")

        for provider, times in self.provider_times.items():
            avg_ms = sum(times) / len(times) * 1000
            min_ms = min(times) * 1000
            max_ms = max(times) * 1000

            table.add_row(
                provider,
                str(len(times)),
                f"{avg_ms:.1f}",
                f"{min_ms:.1f}",
                f"{max_ms:.1f}",
            )

        console.print(table)

    def generate_timing_report(self):
        """Generate comprehensive timing report."""
        total_time = time.time() - self.start_time

        console.print("\n📈 [bold]Timing Report[/bold]")
        console.print(f"Total elapsed: {total_time:.2f}s")

        if self.checkpoints:
            console.print("\n⏰ [bold]Checkpoint Timeline[/bold]")
            for i, cp in enumerate(self.checkpoints):
                prev_time = self.checkpoints[i - 1]["elapsed"] if i > 0 else 0
                delta = cp["elapsed"] - prev_time
                console.print(f"  {cp['name']}: +{delta:.2f}s ({cp['details']})")

    async def monitor_async_operation(self, name: str, coro):
        """Monitor an async operation with timing."""
        start = time.time()
        try:
            result = await coro
            duration = time.time() - start
            console.print(f"✅ {name}: {duration:.2f}s")
            return result
        except Exception as e:
            duration = time.time() - start
            console.print(f"❌ {name}: {duration:.2f}s - {e}")
            raise

    def detect_bottlenecks(self):
        """Detect potential performance bottlenecks."""
        console.print("\n🔍 [bold]Bottleneck Detection[/bold]")

        # Check for long gaps between checkpoints
        if len(self.checkpoints) > 1:
            gaps = []
            for i in range(1, len(self.checkpoints)):
                gap = (
                    self.checkpoints[i]["elapsed"] - self.checkpoints[i - 1]["elapsed"]
                )
                if gap > 5.0:  # Gaps > 5 seconds
                    gaps.append(
                        (
                            gap,
                            self.checkpoints[i - 1]["name"],
                            self.checkpoints[i]["name"],
                        )
                    )

            if gaps:
                console.print("⚠️  [yellow]Potential bottlenecks detected:[/yellow]")
                for gap, from_name, to_name in gaps:
                    console.print(f"  {from_name} → {to_name}: {gap:.1f}s gap")
            else:
                console.print("✅ No significant bottlenecks detected")

    def suggest_optimizations(self):
        """Suggest performance optimizations based on timing data."""
        console.print("\n💡 [bold]Optimization Suggestions[/bold]")

        suggestions = []

        # Check provider times
        for provider, times in self.provider_times.items():
            avg_time = sum(times) / len(times)
            if avg_time > 2.0:  # Average > 2 seconds
                suggestions.append(
                    f"Consider caching for {provider} (avg: {avg_time:.1f}s)"
                )

        # Check for many slow tests
        if len(self.provider_times) > 0:
            total_calls = sum(len(times) for times in self.provider_times.values())
            if total_calls > 50:
                suggestions.append("Consider parallel API calls for better performance")

        if suggestions:
            for suggestion in suggestions:
                console.print(f"  • {suggestion}")
        else:
            console.print("  • Performance looks good!")


# Global timing instance
timing = TimingDiagnostics()


def checkpoint(name: str, details: str = ""):
    """Convenience function for timing checkpoints."""
    timing.checkpoint(name, details)


def record_provider_time(provider: str, duration: float):
    """Convenience function for provider timing."""
    timing.record_provider_time(provider, duration)


async def monitor_async(name: str, coro):
    """Convenience function for async monitoring."""
    return await timing.monitor_async_operation(name, coro)


def generate_report():
    """Generate timing report."""
    timing.analyze_test_timing()
    timing.analyze_provider_performance()
    timing.detect_bottlenecks()
    timing.suggest_optimizations()
    timing.generate_timing_report()


if __name__ == "__main__":
    generate_report()
