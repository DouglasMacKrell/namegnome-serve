"""Tests for the debug utility module.

The debug utility provides a single entrypoint for debug logging that can be
toggled via the NAMEGNOME_DEBUG environment variable.
"""

import os
from io import StringIO
from unittest.mock import patch


def test_debug_import() -> None:
    """Test that debug utility can be imported."""
    from namegnome_serve.utils.debug import debug

    assert callable(debug)


def test_debug_disabled_by_default() -> None:
    """Test that debug output is disabled when NAMEGNOME_DEBUG is not set."""
    # Ensure env var is not set
    os.environ.pop("NAMEGNOME_DEBUG", None)

    # Reimport to reset state
    import importlib

    from namegnome_serve.utils import debug as debug_module

    importlib.reload(debug_module)
    from namegnome_serve.utils.debug import debug

    # Capture stdout
    with patch("sys.stdout", new=StringIO()) as fake_stdout:
        debug("This should not print")
        output = fake_stdout.getvalue()

    assert output == "", f"Expected no output, got: {output}"


def test_debug_enabled_when_env_var_set() -> None:
    """Test that debug output is enabled when NAMEGNOME_DEBUG=1."""
    # Set env var
    os.environ["NAMEGNOME_DEBUG"] = "1"

    # Reimport to pick up env var
    import importlib

    from namegnome_serve.utils import debug as debug_module

    importlib.reload(debug_module)
    from namegnome_serve.utils.debug import debug

    # Capture stdout
    with patch("sys.stdout", new=StringIO()) as fake_stdout:
        debug("Test message")
        output = fake_stdout.getvalue()

    # Clean up
    os.environ.pop("NAMEGNOME_DEBUG", None)

    assert "Test message" in output, f"Expected 'Test message' in output, got: {output}"
    assert "[DEBUG]" in output, f"Expected '[DEBUG]' prefix in output, got: {output}"


def test_debug_with_various_truthy_values() -> None:
    """Test that debug works with various truthy env var values."""
    truthy_values = ["1", "true", "True", "TRUE", "yes", "Yes", "YES"]

    for value in truthy_values:
        os.environ["NAMEGNOME_DEBUG"] = value

        # Reimport to pick up env var
        import importlib

        from namegnome_serve.utils import debug as debug_module

        importlib.reload(debug_module)
        from namegnome_serve.utils.debug import debug

        with patch("sys.stdout", new=StringIO()) as fake_stdout:
            debug(f"Testing {value}")
            output = fake_stdout.getvalue()

        os.environ.pop("NAMEGNOME_DEBUG", None)

        assert f"Testing {value}" in output, (
            f"Failed for NAMEGNOME_DEBUG={value}, output: {output}"
        )


def test_debug_disabled_for_falsy_values() -> None:
    """Test that debug is disabled for falsy env var values."""
    falsy_values = ["0", "false", "False", "FALSE", "no", "No", "NO", ""]

    for value in falsy_values:
        os.environ["NAMEGNOME_DEBUG"] = value

        # Reimport to pick up env var
        import importlib

        from namegnome_serve.utils import debug as debug_module

        importlib.reload(debug_module)
        from namegnome_serve.utils.debug import debug

        with patch("sys.stdout", new=StringIO()) as fake_stdout:
            debug(f"Testing {value}")
            output = fake_stdout.getvalue()

        os.environ.pop("NAMEGNOME_DEBUG", None)

        assert output == "", (
            f"Expected no output for NAMEGNOME_DEBUG={value}, got: {output}"
        )


def test_debug_multiple_messages() -> None:
    """Test that multiple debug calls work correctly."""
    os.environ["NAMEGNOME_DEBUG"] = "1"

    import importlib

    from namegnome_serve.utils import debug as debug_module

    importlib.reload(debug_module)
    from namegnome_serve.utils.debug import debug

    with patch("sys.stdout", new=StringIO()) as fake_stdout:
        debug("First message")
        debug("Second message")
        debug("Third message")
        output = fake_stdout.getvalue()

    os.environ.pop("NAMEGNOME_DEBUG", None)

    assert "First message" in output
    assert "Second message" in output
    assert "Third message" in output
    assert output.count("[DEBUG]") == 3


def test_debug_with_empty_message() -> None:
    """Test that debug handles empty messages gracefully."""
    os.environ["NAMEGNOME_DEBUG"] = "1"

    import importlib

    from namegnome_serve.utils import debug as debug_module

    importlib.reload(debug_module)
    from namegnome_serve.utils.debug import debug

    with patch("sys.stdout", new=StringIO()) as fake_stdout:
        debug("")
        output = fake_stdout.getvalue()

    os.environ.pop("NAMEGNOME_DEBUG", None)

    # Should still print the prefix even if message is empty
    assert "[DEBUG]" in output
