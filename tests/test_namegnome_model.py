"""Tests for the custom namegnome Ollama model."""

import subprocess

import pytest


def check_model_exists(model_name: str) -> bool:
    """Check if a specific Ollama model exists."""
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        return model_name in result.stdout
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


def test_namegnome_model_exists() -> None:
    """Test that custom namegnome model was created."""
    assert check_model_exists("namegnome"), (
        "namegnome model not found. "
        "Create it with: ollama create namegnome -f models/namegnome/Modelfile"
    )


def test_namegnome_model_responds() -> None:
    """Test that namegnome model can respond to prompts."""
    if not check_model_exists("namegnome"):
        pytest.skip("namegnome model not available")

    try:
        result = subprocess.run(
            ["ollama", "run", "namegnome", "You are NameGnome's assistant. Reply 'OK'"],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        output = result.stdout.strip()

        # Model should respond (exact content may vary due to system prompt)
        assert len(output) > 0, "Model produced no output"
        assert "OK" in output.upper(), f"Expected 'OK' in response, got: {output}"

    except subprocess.TimeoutExpired:
        pytest.fail("namegnome model response timed out")
    except subprocess.CalledProcessError as e:
        pytest.fail(f"namegnome model command failed: {e}")
