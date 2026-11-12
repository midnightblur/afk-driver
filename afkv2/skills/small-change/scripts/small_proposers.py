"""Drive 2 fix proposers, 1 Claude and 1 Codex, through herdr (SDD §8 row "small lane"; design ADR-0008).

The use-lavish proposer engine (`proposer_engine.py`) does the work; this file is its small-change adapter. Verbs,
run from the repository root: `plan`, `start`, `wait`, `critique`, `cleanup`, each with `--doc D`; `start` also takes
`--brief F --base REF`. The refusal codes, the answers and the state file are in the docstring of the engine. The
state file is `<doc stem>.proposers.json` beside the page document; each worktree is `small-<doc stem>-<tool>`.
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


VERBS, FAILURES = engine.VERBS, engine.FAILURES

ADAPTER = engine.SkillAdapter(state_path=state_path, ready=_ready, noun="fix", prefix="small")


def main(argv, runner=None):
    return engine.cli(ADAPTER, argv, runner)


if __name__ == "__main__":
    sys.exit(serve(main))
