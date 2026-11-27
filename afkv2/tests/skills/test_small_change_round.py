"""Acceptance: a reader of step 4 of /afkv2:small-change acts on its text alone and reaches the go of step 5.

The dry run takes each command from the fenced `sh step=...` blocks of SKILL.md and fills it only with the answer
of `start` (step 1) and the reader's own round input: a page command that step 4 does not state, or a placeholder
that those values cannot fill, fails the test. It runs the real small-lane and round scripts in a temporary git
repository, with the recorded fake page engine (fakes/fake_engine.py) as the page host. The developer's round send
is the fake's raw grammar, `<card id>: sign`. With AFKV2_EVIDENCE set, each command, its answer and the page
session go to that folder.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

AFKV2 = Path(__file__).resolve().parents[2]
SKILL_MD = AFKV2 / "skills" / "small-change" / "SKILL.md"
FAKE_ENGINE = Path(__file__).resolve().parent / "fakes" / "fake_engine.py"
STEP = re.compile(r"^ *```sh step=([\w-]+)\n *(.*?)\n *```", re.S | re.M)
STEP_4 = re.compile(r"^4\. \*\*.*?(?=^5\. \*\*)", re.S | re.M)
PAGE_COMMANDS = ("build", "present", "wait", "ingest")
TICKET = "PROJ-1"
GO_CARD = "i-go"
ROUND_INPUT = {"short_title": "A small fix", "banner": {"settled": [], "unlocks": ["The go"], "parked": []},
               "items": [{"id": GO_CARD, "kind": "signoff", "title": "Your go",
                          "body": {"type": "text", "props": {"text": "Sign to give the go."}}}]}


def fences(text):
    return dict(STEP.findall(text))


def git(cwd, *args):
    done = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", timeout=60,
                          stdin=subprocess.DEVNULL)
    assert done.returncode == 0, f"git {args}: {done.stderr}"


def evidence(name, entry):
    folder = os.environ.get("AFKV2_EVIDENCE")
    if folder:
        with open(Path(folder) / name, "a", encoding="utf-8") as out:
            out.write(json.dumps(entry, ensure_ascii=False) + "\n")


@pytest.fixture(scope="module")
def plugin(tmp_path_factory):
    """The plugin tree, with the recorded fake page engine as its engine."""
    root = tmp_path_factory.mktemp("plugin")
    for part in ("skills", "ports", "scripts"):
        shutil.copytree(AFKV2 / part, root / part, ignore=shutil.ignore_patterns("__pycache__"))
    (root / "engine").mkdir()
    shutil.copy(FAKE_ENGINE, root / "engine" / "engine.py")
    return root


class Lane:
    """A repository with a spec folder, where the reader runs the commands that SKILL.md states."""

    def __init__(self, root, plugin, name):
        self.plugin, self.repo, self.name = plugin, root / "repo", name
        self.repo.mkdir()
        for args in (("init", "-q"), ("config", "user.name", "Test"), ("config", "user.email", "test@example.test"),
                     ("config", "core.autocrlf", "false")):
            git(self.repo, *args)
        (self.repo / ".afkv2").mkdir()
        (self.repo / ".afkv2" / "config.json").write_text(
            json.dumps({"spec_folder": "specs", "tracker": {"kind": "jira"}}), "utf-8")
        (self.repo / "README.md").write_text("A repository.\n", "utf-8")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "seed")
        self.round_send = root / "round-send.txt"
        self.round_input = root / "round-input.json"
        self.round_input.write_text(json.dumps(ROUND_INPUT), "utf-8")
        self.env = {**os.environ, "FAKE_CALL_LOG": str(root / "engine-calls.log"),
                    "FAKE_POLL_RAW": str(self.round_send), "LOCALAPPDATA": str(root / "data")}
        self.steps = fences(SKILL_MD.read_text("utf-8"))

    def run(self, step, payload=None, extra=(), expect=0, **values):
        """The 1 JSON answer of the command of fence `step`, its placeholders filled with `values`."""
        assert step in self.steps, f"SKILL.md states no fence step={step}; it states {sorted(self.steps)}"
        command = self.steps[step]
        filled = {"python": Path(sys.executable), "this skill's folder": self.plugin / "skills" / "small-change",
                  **{key.replace("_", " "): value for key, value in values.items()}}
        for name, value in filled.items():
            command = command.replace(f"<{name}>", Path(value).as_posix() if isinstance(value, Path) else str(value))
        left = re.findall(r"<[^<>]+>", command)
        assert not left, f"step={step}: the values {sorted(values)} leave {left} unfilled in: {command}"
        args = [*shlex.split(command), *extra]
        done = subprocess.run(args, cwd=self.repo, capture_output=True, text=True, encoding="utf-8", timeout=120,
                              env=self.env, input=json.dumps(payload) if payload is not None else "")
        answer = json.loads(done.stdout) if done.stdout.strip().startswith("{") else None
        evidence(f"{self.name}.jsonl", {"step": step, "command": args, "stdin": payload, "exit": done.returncode,
                                        "answer": answer})
        assert done.returncode == expect and answer is not None, (
            f"step={step}: expected exit {expect}, got {done.returncode}\ncommand: {args}\nstdout: {done.stdout}\n"
            f"stderr: {done.stderr}")
        return answer

    def page_round(self, started, round_send):
        """Step 4 as SKILL.md states it: build, present, wait for the round send, ingest."""
        built = self.run("build", extra=("--ticket", TICKET), doc=started["doc"], session=started["session"],
                         round_input=self.round_input)
        self.run("present", doc=started["doc"])
        self.round_send.write_text(round_send, "utf-8")
        self.run("wait", doc=started["doc"], raw_file=started["raw_file"])
        self.run("ingest", doc=started["doc"], raw_file=started["raw_file"])
        session = json.loads(Path(started["doc"]).read_text("utf-8"))["session"]
        evidence(f"{self.name}.jsonl", {"page": started["doc"], "session": session})
        return built, session


def started_lane(tmp_path, plugin, name):
    lane = Lane(tmp_path, plugin, name)
    started = lane.run("lane", verb="start", payload={"kind": "enhancement", "why": "1 skill file", "ticket": TICKET})
    return lane, started


def test_step_4_states_each_page_command_inside_step_4():
    step_4 = STEP_4.search(SKILL_MD.read_text("utf-8"))
    assert step_4, f"{SKILL_MD} holds no step 4 before a step 5"
    stated = sorted(fences(step_4.group(0)))
    missing = [command for command in PAGE_COMMANDS if command not in stated]
    assert not missing, f"step 4 states the fences {stated}; it lacks {missing} of {list(PAGE_COMMANDS)}"


def test_a_reader_of_step_4_gets_the_go_on_the_page_of_start(tmp_path, plugin):
    lane, started = started_lane(tmp_path, plugin, "signed")
    built, session = lane.page_round(started, f"{GO_CARD}: sign\n")
    assert Path(built["doc"]) == Path(started["doc"]), f"build wrote {built['doc']}, not the page of start {started['doc']}"
    assert session["skill"] == "small-change", f"the page writer is {session['skill']!r}, expected 'small-change'"
    go = lane.run("lane", verb="go", payload={"doc": started["doc"], "card": GO_CARD, "test_plan": "acceptance: 1 test"})
    assert go["go"]["card"] == GO_CARD, f"go recorded {go['go']}, expected the card {GO_CARD!r}"


def test_a_round_send_with_no_sign_on_the_go_card_gets_no_go(tmp_path, plugin):
    lane, started = started_lane(tmp_path, plugin, "unsigned")
    lane.page_round(started, f"{GO_CARD}: note: not yet\n")
    refused = lane.run("lane", verb="go", expect=1,
                       payload={"doc": started["doc"], "card": GO_CARD, "test_plan": "acceptance: 1 test"})
    assert refused["error"]["code"] == "no-go-mark", f"go answered {refused}, expected the refusal 'no-go-mark'"
