"""The other-provider adapter, with an in-process fake CLI: no real provider runs here."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import other_provider as op  # noqa: E402

CHECKS = ["VC-2", "VC-4", "VC-6", "VC-7", "level", "flaky"]


class FakeCli:
    """Answers each call from a queue and records argv, stdin and cwd. A queued item is
    (exit, stdout) or "timeout"."""

    def __init__(self, *answers, signed_in=("claude", "codex"), on_path=("claude", "codex")):
        self.answers = list(answers)
        self.calls = []
        self.signed_in = set(signed_in)
        self.on_path = set(on_path)

    def lookup(self, name):
        return f"/bin/{name}" if name in self.on_path else None

    def run(self, argv, *, stdin, cwd, timeout):
        name = Path(argv[0]).name
        if argv[1:] in (["auth", "status"], ["login", "status"]):
            return op.Ran(0 if name in self.signed_in else 1, "", False)
        self.calls.append({"argv": argv, "stdin": stdin, "cwd": cwd, "timeout": timeout})
        answer = self.answers.pop(0)
        if answer == "timeout":
            return op.Ran(None, "", True)
        return op.Ran(answer[0], answer[1], False)


def record(lines):
    folder = Path(os.environ["LOCALAPPDATA"]) / "afkv2"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "install.txt").write_text("".join(f"{k} {v}\n" for k, v in lines.items()), encoding="utf-8")


# ---------------------------------------------------------------- which


def test_which_picks_the_other_provider_when_its_cli_is_on_the_path_and_signed_in():
    fake = FakeCli()
    assert op.which("claude", lookup=fake.lookup, runner=fake.run) == {
        "provider": "codex", "model": "cli-default", "effort": "medium", "cli": "/bin/codex"}
    assert op.which("codex", lookup=fake.lookup, runner=fake.run)["provider"] == "claude"


def test_which_gives_the_other_provider_the_judge_model_the_install_record_names():
    record({"judge_codex": "gpt-9"})
    fake = FakeCli()
    assert op.which("claude", lookup=fake.lookup, runner=fake.run)["model"] == "gpt-9"


def test_which_falls_back_to_the_own_provider_at_the_recorded_judge_model_when_the_other_is_signed_out():
    record({"judge_claude": "opus-x"})
    fake = FakeCli(signed_in=("claude",))
    assert op.which("claude", lookup=fake.lookup, runner=fake.run) == {
        "provider": "claude", "model": "opus-x", "effort": "medium", "cli": "/bin/claude"}


def test_which_falls_back_when_the_other_cli_is_not_on_the_path():
    record({"judge_codex": "gpt-9"})
    fake = FakeCli(on_path=("codex",))
    assert op.which("codex", lookup=fake.lookup, runner=fake.run)["provider"] == "codex"


def test_which_refuses_no_provider_when_the_record_names_no_own_judge_model():
    fake = FakeCli(on_path=("claude",))
    with pytest.raises(op.Refusal) as refused:
        op.which("claude", lookup=fake.lookup, runner=fake.run)
    assert refused.value.code == "no-provider"


def test_which_refuses_an_unknown_session_provider():
    fake = FakeCli()
    with pytest.raises(op.Refusal) as refused:
        op.which("gemini", lookup=fake.lookup, runner=fake.run)
    assert refused.value.code == "bad-input"
