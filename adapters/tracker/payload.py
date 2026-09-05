"""The one reading of a command-line payload every tracker kind shares.

A tracker command surface takes its argument as one JSON object on the command
line. Text that is not JSON, or JSON that is not an object, is a caller fault,
and a caller can only route on an answer it can read: this returns the family's
normalized error object so the surface can print it and exit 2, instead of
letting a decoder raise and print a Python traceback.
"""
from __future__ import annotations

import json

# The exit code a tracker surface returns when the payload could not be read.
# It is the family's "could not resolve what this verb needed", not a verdict
# from the tracker.
EXIT_UNREADABLE_PAYLOAD = 2


def parse(text: str | None, operation: str = "") -> tuple[dict | None, dict | None]:
    """Read one payload. Returns (payload, None), or (None, error object)."""
    if text is None:
        return {}, None
    try:
        value = json.loads(text)
    except ValueError as problem:
        return None, {
            "error": True, "operation": operation,
            "reason": f"the payload is not JSON: {problem}",
        }
    if value is None:
        return {}, None
    if not isinstance(value, dict):
        return None, {
            "error": True, "operation": operation,
            "reason": (
                f"the payload is a JSON {type(value).__name__}, "
                "and every operation takes one JSON object"
            ),
        }
    return value, None
