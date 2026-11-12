"""Drive 2 verification proposers, 1 Claude and 1 Codex, through herdr (SDD §8 row "proposer engine"; design ADR-0008).

The use-lavish proposer engine (`proposer_engine.py`) does the work; this file is its propose-verification adapter.
Verbs, run from the repository root; each answers one JSON object:
  plan     --doc D                        count 2 with both tools, or count 1 with the reason; starts nothing
  start    --doc D --brief F --base REF   per tool: a detached throwaway worktree, a pane, the tool, the brief
  wait     --doc D                        each proposer settles; after `critique` also the 4 file paths
  critique --doc D                        each proposer critiques the DRAFT.md of the other
  cleanup  --doc D                        closes each recorded pane and removes each recorded worktree

The refusal codes, the answers and the state file are in the docstring of the engine. The proposers may start at any
point of the session: `ready` refuses nothing. The state file is `<doc stem>.proposers.json` beside the page document.
Each worktree is `verifier-<doc stem>-<tool>`.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "use-lavish" / "scripts"))

import proposer_engine as engine  # noqa: E402
from grill_common import serve  # noqa: E402


def state_path(doc):
    """The proposers state file beside the page document."""
    return Path(doc).with_suffix(".proposers.json")


def _ready(doc, state):
    return None


# The command verbs, and the refusal codes that record a proposer failure; the skill guide names both.
VERBS, FAILURES = engine.VERBS, engine.FAILURES

ADAPTER = engine.SkillAdapter(state_path=state_path, ready=_ready, noun="verification", prefix="verifier")


def main(argv, runner=None):
    return engine.cli(ADAPTER, argv, runner)


if __name__ == "__main__":
    sys.exit(serve(main))
