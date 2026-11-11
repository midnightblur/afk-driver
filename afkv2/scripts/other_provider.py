"""The other-provider adapter: 1 headless, read-only call of the other provider's CLI.

Command: `other_provider.py which|judge|attack --session claude|codex [--input DIR] [--log PATH]`.
Answers one JSON object. Exit 0 ok, 1 refused, 2 unreadable input.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from afkv2_config import Refusal, data_folder  # noqa: E402

PROVIDERS = ("claude", "codex")
EFFORT = "medium"
CLI_DEFAULT = "cli-default"
JUDGE_KEY = "judge_{provider}"
STATUS_SECONDS = 30
STATUS_COMMAND = {"claude": ["auth", "status"], "codex": ["login", "status"]}


@dataclass
class Ran:
    exit: int | None
    stdout: str
    timed_out: bool


def run_cli(argv, *, stdin, cwd, timeout) -> Ran:
    try:
        done = subprocess.run(argv, input=(stdin or "").encode("utf-8"), cwd=cwd, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return Ran(None, "", True)
    except OSError as error:
        return Ran(None, str(error), False)
    return Ran(done.returncode, done.stdout.decode("utf-8", "replace"), False)


def which(session_provider, *, lookup=shutil.which, runner=run_cli) -> dict:
    """The judge: the other provider if its CLI is on the path and signed in, else the own provider at the
    judge model the install record names. Raises `Refusal` `no-provider` when neither can run."""
    if session_provider not in PROVIDERS:
        raise Refusal("bad-input", f"the session provider must be one of {', '.join(PROVIDERS)}, not {session_provider!r}")
    other = next(name for name in PROVIDERS if name != session_provider)
    models = _judge_models()
    cli = lookup(other)
    if cli and _signed_in(other, cli, runner):
        return {"provider": other, "model": models.get(other) or CLI_DEFAULT, "effort": EFFORT, "cli": cli}
    own = lookup(session_provider)
    if own and models.get(session_provider):
        return {"provider": session_provider, "model": models[session_provider], "effort": EFFORT, "cli": own}
    raise Refusal("no-provider", f"{other} is not on the path or not signed in, and the install record names no "
                  f"`{JUDGE_KEY.format(provider=session_provider)}` model: run the judge step of /afkv2:setup")


def _signed_in(provider, cli, runner) -> bool:
    return runner([cli, *STATUS_COMMAND[provider]], stdin="", cwd=None, timeout=STATUS_SECONDS).exit == 0


def _judge_models() -> dict:
    try:
        path = data_folder() / "install.txt"
        lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    except (Refusal, OSError):
        lines = []
    record = dict(line.partition(" ")[::2] for line in lines)
    return {name: record[JUDGE_KEY.format(provider=name)].strip() for name in PROVIDERS
            if record.get(JUDGE_KEY.format(provider=name), "").strip()}
