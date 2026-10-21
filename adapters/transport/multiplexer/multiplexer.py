"""Multiplexer panes: each agent runs in a pane of a terminal multiplexer this session runs inside.

The six verbs are the same for every tool; the first tool usable in this session answers them, by its own
recipe file in this folder (one per tool). No usable tool answers unavailable, naming each tool's state;
agent-stop then still kills the tree by its process id and answers the pane not closed.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
import contract  # noqa: E402
import herdr  # noqa: E402
import process  # noqa: E402
from contract import Answer, Deadline, Payload, unavailable  # noqa: E402

TOOLS = {"herdr": (herdr.detect, herdr.Herdr)}
DETECT_SHARE = 6                          # each of detection's two calls waits at most a sixth of the budget


class Multiplexer:
    def __init__(self, env=None):
        self.env = dict(os.environ if env is None else env)
        self._tool = None

    def tool(self, deadline: Deadline):
        if self._tool is None:
            states = []
            for name, (detect, make) in TOOLS.items():
                found = detect(self.env, (), timeout=max(1.0, deadline.left() / DETECT_SHARE))
                if found.status == "usable":
                    self._tool = make(self.env)
                    break
                states.append(f"{name}: {found.reason}")
            else:
                raise unavailable("no multiplexer tool is usable in this session (" + "; ".join(states) + ")")
        return self._tool

    def agent_stop(self, p: Payload, deadline: Deadline) -> dict:
        try:
            tool = self.tool(deadline)
        except Answer as answer:
            return _stop_without_tool(p, deadline, answer.body["reason"])
        return tool.agent_stop(p, deadline)

    def __getattr__(self, name: str):
        if name.replace("_", "-") not in contract.VERBS:
            raise AttributeError(name)
        return lambda p, deadline: getattr(self.tool(deadline), name)(p, deadline)


def _stop_without_tool(p: Payload, deadline: Deadline, why: str) -> dict:
    """With no usable tool the pane cannot close, but the process tree still dies by its id."""
    pid, handle, force = p.integer("pid", False), p.text("handle", False), p.boolean("force")
    answer = process.stop(pid, force=force, wait_s=min(20.0, deadline.left()))
    if pid is None and handle:
        answer = {"stopped": False, "reason": f"no process id was given and no tool can close pane {handle}",
                  "survivors": []}
    if handle:
        answer.update({"pane_closed": False, "pane_id": handle,
                       "pane_reason": f"pane {handle} was not closed: {why}"})
    return answer


if __name__ == "__main__":
    sys.exit(contract.run(Multiplexer(), sys.argv[1:]))
