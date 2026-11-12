"""Drive 2 solution proposers, 1 Claude and 1 Codex, through herdr (SDD §3 rows S-6 to S-8; design ADR-0003).

The use-lavish proposer engine (`proposer_engine.py`) does the work; this file is its propose-solution adapter.
Verbs, run from the repository root; each answers one JSON object:
  plan     --doc D                        count 2 with both tools, or count 1 with the reason; starts nothing
  start    --doc D --brief F --base REF   per tool: a detached throwaway worktree, a pane, the tool, the brief
  wait     --doc D                        each proposer settles; after `critique` also the 4 file paths
  critique --doc D                        each proposer critiques the DRAFT.md of the other
  cleanup  --doc D                        closes each recorded pane and removes each recorded worktree

The refusal codes, the answers and the state file are in the docstring of the engine. This adapter adds:
plan and start refuse `aspects-open` until every critical aspect settles. `plan` answers exactly the `proposers`
input of the design build: {count, tools, reason}; reason `proposer-failed` after a failure means the agent in charge
drafts alone (SDD §6, §7; decision D-10). The state file is `<doc stem>.proposers.json` beside the page document;
`cleanup` keeps it with `cleaned` true (decision D-7). Each worktree is `proposer-<doc stem>-<tool>`.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "use-lavish" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import design_round as dr  # noqa: E402
import proposer_engine as engine  # noqa: E402
from grill_common import Refusal, serve  # noqa: E402


def _ready(doc, state):
    if dr.next_step(dr._view(doc), state)["phase"] == "aspects":
        raise Refusal("aspects-open", "the solution proposers start after every critical aspect settles")


ADAPTER = engine.SkillAdapter(state_path=dr.proposers_state_path, ready=_ready, noun="solution", prefix="proposer")


def main(argv, runner=None):
    return engine.cli(ADAPTER, argv, runner)


if __name__ == "__main__":
    sys.exit(serve(main))
