#!/usr/bin/env python3
"""Verify that all required toolchain components are installed and configured.

This script checks Python, Poetry, Git versions and Poetry configuration.
Run this after setting up a new development environment.
"""

import subprocess
import sys
from typing import Tuple


def run_command(cmd: list[str]) -> Tuple[bool, str]:
    """Run a command and return success status and output."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )
        return True, result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        return False, str(e)


def check_python() -> bool:
    """Check Python version >= 3.12."""
    success, output = run_command([sys.executable, "--version"])
    if not success:
        print("❌ Python not found")
        return False

    version_str = output.split()[1]
    major, minor = map(int, version_str.split(".")[:2])

    if major >= 3 and minor >= 12:
        print(f"✅ Python {version_str} (>= 3.12 required)")
        return True
    else:
        print(f"❌ Python {version_str} (>= 3.12 required)")
        return False


def check_poetry() -> bool:
    """Check Poetry is installed."""
    success, output = run_command(["poetry", "--version"])
    if not success:
        print("❌ Poetry not found")
        print("   Install: curl -sSL https://install.python-poetry.org | python3 -")
        return False

    print(f"✅ {output}")
    return True


def check_git() -> bool:
    """Check Git is installed."""
    success, output = run_command(["git", "--version"])
    if not success:
        print("❌ Git not found")
        return False

    print(f"✅ {output}")
    return True


def check_poetry_config() -> bool:
    """Check Poetry virtualenvs.in-project setting."""
    success, output = run_command(["poetry", "config", "virtualenvs.in-project"])
    if not success:
        print("❌ Poetry config check failed")
        return False

    if output == "true":
        print("✅ Poetry configured for in-project .venv")
        return True
    else:
        print("❌ Poetry not configured for in-project .venv")
        print("   Run: poetry config virtualenvs.in-project true")
        return False


def main() -> int:
    """Run all toolchain checks."""
    print("🔧 NameGnome Serve Toolchain Verification\n")

    checks = [
        ("Python >= 3.12", check_python),
        ("Poetry", check_poetry),
        ("Git", check_git),
        ("Poetry Config", check_poetry_config),
    ]

    results = []
    for name, check_func in checks:
        results.append(check_func())
        print()

    if all(results):
        print("✅ All toolchain checks passed!")
        print("\nNext steps:")
        print("  1. poetry install")
        print("  2. poetry run pytest")
        return 0
    else:
        print("❌ Some toolchain checks failed. Please fix the issues above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

