"""Integration tests for Ollama connectivity and model availability.

These tests verify that:
1. Ollama service is running and accessible
2. Required models are available
3. Models can respond to prompts
"""

import subprocess

import pytest


def check_ollama_running() -> bool:
    """Check if Ollama service is running."""
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def get_ollama_models() -> list[str]:
    """Get list of available Ollama models."""
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        # Parse output: skip header, extract model names
        lines = result.stdout.strip().split("\n")[1:]  # Skip header
        return [line.split()[0] for line in lines if line.strip()]
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, IndexError):
        return []


def test_ollama_service_running() -> None:
    """Test that Ollama service is accessible."""
    assert check_ollama_running(), (
        "Ollama service not running. Start it with: ollama serve (in separate terminal)"
    )


def test_llama3_model_available() -> None:
    """Test that llama3:8b model is available."""
    if not check_ollama_running():
        pytest.skip("Ollama service not running")

    models = get_ollama_models()
    llama3_available = any("llama3" in model for model in models)

    assert llama3_available, (
        f"llama3:8b model not found. Available models: {models}. "
        "Pull it with: ollama pull llama3:8b"
    )


def test_ollama_can_respond() -> None:
    """Test that Ollama can respond to a simple prompt."""
    if not check_ollama_running():
        pytest.skip("Ollama service not running")

    models = get_ollama_models()
    if not any("llama3" in model for model in models):
        pytest.skip("llama3 model not available")

    try:
        # Simple test prompt
        result = subprocess.run(
            ["ollama", "run", "llama3:8b", "Say 'OK' and nothing else"],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        output = result.stdout.strip().upper()

        # Model should respond with OK (may have extra formatting)
        assert "OK" in output, f"Expected 'OK' in response, got: {output}"

    except subprocess.TimeoutExpired:
        pytest.fail("Ollama response timed out after 30 seconds")
    except subprocess.CalledProcessError as e:
        pytest.fail(f"Ollama command failed: {e}")
