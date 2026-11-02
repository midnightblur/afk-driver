"""The repository config, read through the one config reader command."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

READER = Path(__file__).resolve().parents[2] / "scripts" / "afkv2_config.py"


def read_config():
    """The reader's answer, or {} when the reader is absent or answers no config."""
    if not Path(READER).is_file():
        return {}
    try:
        done = subprocess.run([sys.executable, str(READER), "read"], capture_output=True,
                              stdin=subprocess.DEVNULL, timeout=60)
        answer = json.loads(done.stdout.decode("utf-8", "replace"))
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return {}
    return answer if isinstance(answer, dict) and answer.get("ok") else {}
