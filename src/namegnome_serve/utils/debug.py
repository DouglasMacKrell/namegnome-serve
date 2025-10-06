"""Debug utility for NameGnome Serve.

Provides a single debug() function that can be toggled via the
NAMEGNOME_DEBUG environment variable. This replaces ad-hoc print()
statements throughout the codebase.

Usage:
    from namegnome_serve.utils.debug import debug

    debug("Starting scan operation")
    debug(f"Found {count} files")

Environment:
    NAMEGNOME_DEBUG: Set to '1', 'true', 'yes' (case-insensitive) to enable
                     debug output. Any other value or unset disables it.

Example:
    $ NAMEGNOME_DEBUG=1 python script.py    # Debug enabled
    $ NAMEGNOME_DEBUG=0 python script.py    # Debug disabled
    $ python script.py                      # Debug disabled (default)
"""

import os
import sys
from typing import Any

# Determine if debug mode is enabled at module import time
_DEBUG_ENABLED = os.environ.get("NAMEGNOME_DEBUG", "").lower() in (
    "1",
    "true",
    "yes",
)


def debug(msg: Any) -> None:
    """Print debug message if NAMEGNOME_DEBUG is enabled.

    Args:
        msg: Message to print. Will be converted to string.

    Note:
        This function checks the NAMEGNOME_DEBUG environment variable
        at module import time. Changing the env var after import will
        not affect behavior unless the module is reloaded.

    Examples:
        >>> debug("Starting operation")  # Only prints if DEBUG enabled
        >>> debug(f"Processing {count} items")
    """
    if _DEBUG_ENABLED:
        print(f"[DEBUG] {msg}", file=sys.stdout)
