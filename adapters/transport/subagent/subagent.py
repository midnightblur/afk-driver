"""Harness subagents: the harness spawns, messages and ends its own child, so no script can.

Every verb answers unsupported (exit 3) with the reason; a bad payload still answers exit 2 first. The agent
that starts such a child gets its report back as text and writes the report file itself.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import contract  # noqa: E402
from contract import Payload, unsupported  # noqa: E402

REASONS = {
    "agent-start": "the harness starts a subagent with its own subagent tool; start it there",
    "agent-send": "a subagent takes no message after its start; it returns its report as text",
    "agent-status": "the harness owns a subagent's lifecycle; its tool reports the state",
    "agent-read": "a subagent's output reaches only the agent that started it, as its returned text",
    "agent-stop": "the harness owns a subagent's lifecycle; it ends when its task returns",
    "agent-list": "a subagent has no pane id to list it by",
}


class Subagent:
    def __getattr__(self, name: str):
        verb = name.replace("_", "-")
        if verb not in REASONS:
            raise AttributeError(name)

        def answer(payload: Payload, deadline: contract.Deadline) -> dict:
            raise unsupported(REASONS[verb])
        return answer


if __name__ == "__main__":
    sys.exit(contract.run(Subagent(), sys.argv[1:]))
