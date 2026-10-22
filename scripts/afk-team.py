#!/usr/bin/env afk-python
"""The team entry script: the one command agents call to start, message and stop each other.

    afk-python "${AFK_PLUGIN_ROOT}/scripts/afk-team.py" <command> '<one JSON object>'

Commands: agent-start, agent-send, agent-status, agent-read, agent-stop, agent-list, run-open, wait. It prints one
JSON object and exits 0 done, 2 bad payload or refused check, 3 unsupported, 4 unavailable, 5 an agent started
but its manifest write failed and it was stopped. The logic and each command's fields: scripts/team/entry.py.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from team import entry  # noqa: E402


def dispatch_verb(verb: str, text: str, host: entry.Host | None = None) -> tuple[int, dict]:
    """Run one command on its JSON object text: (exit code, answer object)."""
    try:
        data = json.loads(text)
    except ValueError as problem:
        return 2, {"error": True, "operation": verb, "reason": f"the payload is not JSON: {problem}"}
    if not isinstance(data, dict):
        return 2, {"error": True, "operation": verb, "reason": "the payload is not one JSON object"}
    return entry.run_command(verb, data, host)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        code, body = 2, {"error": True, "operation": argv[0] if argv else "",
                         "reason": "the input is a command, then one JSON object as the next argument"}
    else:
        code, body = dispatch_verb(argv[0], argv[1])
    sys.stdout.write(json.dumps(body, sort_keys=True) + "\n")
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
