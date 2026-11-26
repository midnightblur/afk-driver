"""dogfood.py start and status on the fake runner: the start flow, its refusals, the state file and the lookup."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

AFKV2 = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(AFKV2 / "skills" / "dogfood" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "fakes"))

import dogfood  # noqa: E402
from dogfood_runner import DogfoodFakeRunner, herdr_error  # noqa: E402

MAIN = "w1:p1"
ASK = "Add a link to the rep"  # 21 characters


@pytest.fixture
def world(tmp_path):
    """A herdr main pane, a plugin source with its install record line, and an ask file."""
    source = tmp_path / "plugin source"
    (source / "afkv2" / ".claude-plugin").mkdir(parents=True)
    (source / "afkv2" / ".claude-plugin" / "plugin.json").write_text('{"name": "afkv2"}', encoding="utf-8")
    env = {"HERDR_ENV": "1", "HERDR_PANE_ID": MAIN, "LOCALAPPDATA": str(tmp_path / "local"),
           "ProgramFiles": str(tmp_path / "program files")}
    data = tmp_path / "local" / "afkv2"
    data.mkdir(parents=True)
    (data / "install.txt").write_text(f"installed 2026-11-26T00:00:00+00:00\nsource {source}\n", encoding="utf-8")
    ask = tmp_path / "ask.txt"
    ask.write_text(ASK, encoding="utf-8")
    return {"env": env, "source": source, "data": data, "ask": ask, "tmp": tmp_path}


def run(world, argv, runner=None, env=None):
    """Run main as the command line does: 1 JSON object on stdout, and the exit code."""
    env = env if env is not None else world["env"]
    runner = runner if runner is not None else DogfoodFakeRunner(env)
    out = []
    code = dogfood.main(argv, env, runner, out=out.append)
    assert len(out) == 1
    return code, json.loads(out[0]), runner


def state_file(world, pane=MAIN):
    return world["data"] / f"dogfood-{pane.replace(':', '_')}.json"


def name_of(pane, n=0):
    return f"dogfood-{hashlib.sha256(pane.encode('utf-8')).hexdigest()[4 * n:4 * n + 4]}"


def test_start_opens_a_pane_starts_the_agent_then_writes_the_state_and_sends_the_ask(world):
    runner = DogfoodFakeRunner(world["env"])
    seen = {}
    runner.on(("agent", "start"), lambda argv: seen.setdefault("at_start", state_file(world).exists()))
    runner.on(("agent", "prompt"), lambda argv: seen.setdefault("at_prompt", state_file(world).exists()))

    code, answer, runner = run(world, ["start", "--ask-file", str(world["ask"])], runner)

    assert code == 0 and answer["ok"] and answer["status"] == "opened"
    order = [argv[1:3] for argv in runner.calls if argv[0] == runner.herdr and argv[1:3] in
             (["pane", "split"], ["agent", "start"], ["agent", "prompt"])]
    assert order == [["pane", "split"], ["agent", "start"], ["agent", "prompt"]]
    split = runner.calls_of("pane", "split")[0]
    assert split[split.index("--pane") + 1] == MAIN and split[split.index("--cwd") + 1] == str(world["source"])
    started = runner.started[0]
    assert started["name"] == name_of(MAIN) == answer["agent"] and started["kind"] == "claude"
    assert started["args"] == ["--model", "opus", "--effort", "max", "--dangerously-skip-permissions"]
    assert seen == {"at_start": False, "at_prompt": True}
    [prompt] = runner.prompts
    assert prompt["target"] == name_of(MAIN) and ASK in prompt["text"] and "AGENT.md" in prompt["text"]
    state = json.loads(state_file(world).read_text(encoding="utf-8"))
    assert state == answer["state"]
    assert {key: state[key] for key in state if key != "started"} == {
        "version": 1, "main_pane": MAIN, "agent": name_of(MAIN), "afkv2_pane": answer["pane"], "harness": "claude",
        "source": str(world["source"]), "base": None, "worktrees": [], "notes": [], "wrap_reported": False}
    assert state["started"].endswith("+00:00")


def _herdr_calls(runner):
    return [argv for argv in runner.calls if argv[0] == runner.herdr]


def test_start_refuses_outside_herdr_and_without_a_working_source_line(world):
    for change in ({"HERDR_ENV": "0"}, {"HERDR_PANE_ID": ""}):
        env = {**world["env"], **change}
        code, answer, runner = run(world, ["start", "--ask-file", str(world["ask"])], env=env)
        assert (code, answer["error"]["code"]) == (1, "outside-herdr") and not runner.calls
        assert "start herdr" in answer["error"]["reason"] and "again" in answer["error"]["reason"]
    runner = DogfoodFakeRunner(world["env"], herdr=None)
    code, answer, runner = run(world, ["start", "--ask-file", str(world["ask"])], runner)
    assert (code, answer["error"]["code"]) == (1, "outside-herdr") and not runner.calls

    record = world["data"] / "install.txt"
    record.write_text("installed 2026-11-26T00:00:00+00:00\n", encoding="utf-8")
    code, answer, runner = run(world, ["start", "--ask-file", str(world["ask"])])
    assert (code, answer["error"]["code"]) == (1, "no-source") and "/afkv2:setup" in answer["error"]["reason"]
    assert not _herdr_calls(runner)

    def broken(source):
        record.write_text(f"source {source}\n", encoding="utf-8")
        code, answer, runner = run(world, ["start", "--ask-file", str(world["ask"])])
        assert (code, answer["error"]["code"]) == (1, "source-broken") and "/afkv2:setup" in answer["error"]["reason"]
        assert not _herdr_calls(runner) and not state_file(world).exists()

    broken(world["tmp"] / "gone")
    other = world["tmp"] / "other"
    (other / "afkv2" / ".claude-plugin").mkdir(parents=True)
    (other / "afkv2" / ".claude-plugin" / "plugin.json").write_text('{"name": "other"}', encoding="utf-8")
    broken(other)
    record.write_text(f"source {world['source']}\n", encoding="utf-8")
    runner = DogfoodFakeRunner(world["env"])
    runner.linked.add(str(world["source"]))
    code, answer, runner = run(world, ["start", "--ask-file", str(world["ask"])], runner)
    assert (code, answer["error"]["code"]) == (1, "source-broken") and not _herdr_calls(runner)
