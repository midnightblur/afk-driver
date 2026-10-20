"""Multiplexer panes: each agent runs in a pane of a terminal multiplexer this session runs inside.

The six verbs are the same for every tool; the first tool usable in this session answers them, by its own
recipe file in this folder (one per tool). No usable tool answers unavailable, naming each tool's state.
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
from contract import unavailable  # noqa: E402

TOOLS = {"herdr": (herdr.detect, herdr.Herdr)}


class Multiplexer:
    def __init__(self, env=None):
        self.env = dict(os.environ if env is None else env)
        self._tool = None

    def tool(self):
        if self._tool is None:
            states = []
            for name, (detect, make) in TOOLS.items():
                found = detect(self.env, ())
                if found.status == "usable":
                    self._tool = make(self.env)
                    break
                states.append(f"{name}: {found.reason}")
            else:
                raise unavailable("no multiplexer tool is usable in this session (" + "; ".join(states) + ")")
        return self._tool

    def __getattr__(self, name: str):
        if name.replace("_", "-") not in contract.VERBS:
            raise AttributeError(name)
        return getattr(self.tool(), name)


if __name__ == "__main__":
    sys.exit(contract.run(Multiplexer(), sys.argv[1:]))
