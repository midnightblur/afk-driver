"""dogfood.py start and status on the fake runner: the start flow, its refusals, the state file and the lookup."""

from __future__ import annotations

import hashlib
import json
import os
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


def test_a_failed_split_or_agent_start_writes_no_state_and_closes_the_pane_it_opened(world):
    runner = DogfoodFakeRunner(world["env"])
    runner.answer(("pane", "split"), herdr_error("pane_not_found"))
    code, answer, runner = run(world, ["start", "--ask-file", str(world["ask"])], runner)
    assert (code, answer["error"]["code"]) == (1, "herdr-failed") and not state_file(world).exists()
    assert not runner.calls_of("agent", "start") and not runner.calls_of("pane", "close")

    for herdr_code, expected in (("agent_not_ready", "agent-not-ready"), ("timeout", "herdr-failed")):
        runner = DogfoodFakeRunner(world["env"])
        runner.answer(("agent", "start"), herdr_error(herdr_code))
        code, answer, runner = run(world, ["start", "--ask-file", str(world["ask"])], runner)
        assert (code, answer["error"]["code"]) == (1, expected) and not state_file(world).exists()
        [split] = runner.calls_of("pane", "split")
        [close] = runner.calls_of("pane", "close")
        assert close[3] == runner.calls_of("agent", "start")[0][runner.calls_of("agent", "start")[0].index("--pane") + 1]
        assert set(runner.panes) == {MAIN} and not runner.prompts


def test_an_ask_of_0_or_more_than_8000_characters_or_not_utf8_is_unreadable(world):
    ask = world["ask"]
    for content in (b"", ("x" * 8001).encode("utf-8"), b"\xff\xfe bad"):
        ask.write_bytes(content)
        code, answer, runner = run(world, ["start", "--ask-file", str(ask)])
        assert (code, answer["error"]["code"]) == (2, "ask-unreadable") and not _herdr_calls(runner)
    code, answer, runner = run(world, ["start", "--ask-file", str(world["tmp"] / "absent.txt")])
    assert (code, answer["error"]["code"]) == (2, "ask-unreadable")
    for content in ("é", "é" * 8000):
        state_file(world).unlink(missing_ok=True)
        ask.write_text(content, encoding="utf-8")
        code, answer, runner = run(world, ["start", "--ask-file", str(ask)])
        assert (code, answer["status"]) == (0, "opened") and runner.prompts[0]["text"].endswith(content)


def test_a_managed_setting_that_bans_bypass_or_cannot_be_parsed_refuses_before_any_split(world):
    folder = Path(world["env"]["ProgramFiles"]) / "ClaudeCode"
    (folder / "managed-settings.d").mkdir(parents=True)
    banned = '{"permissions": {"disableBypassPermissionsMode": "disable"}}'
    for name, text in (("managed-settings.json", banned), ("managed-settings.json", "{not json"),
                       ("managed-settings.d/10-team.json", banned)):
        (folder / name).write_text(text, encoding="utf-8")
        code, answer, runner = run(world, ["start", "--ask-file", str(world["ask"])])
        assert (code, answer["error"]["code"]) == (1, "auto-approval-banned") and not runner.calls_of("pane", "split")
        (folder / name).unlink()
    runner = DogfoodFakeRunner(world["env"])
    runner.answer(("reg", "query"), (0, f"    Settings    REG_SZ    {banned}\n", ""))
    code, answer, runner = run(world, ["start", "--ask-file", str(world["ask"])], runner)
    assert (code, answer["error"]["code"]) == (1, "auto-approval-banned") and not runner.calls_of("pane", "split")
    (folder / "managed-settings.json").write_text('{"permissions": {"defaultMode": "plan"}}', encoding="utf-8")
    code, answer, runner = run(world, ["start", "--ask-file", str(world["ask"])])
    assert (code, answer["status"]) == (0, "opened")


def test_an_agent_name_that_clashes_takes_the_next_4_hex_digits_at_most_3_tries(world):
    for clashes in (1, 2):
        state_file(world).unlink(missing_ok=True)
        runner = DogfoodFakeRunner(world["env"])
        for n in range(clashes):
            runner.add_agent(name_of(MAIN, n))
        code, answer, runner = run(world, ["start", "--ask-file", str(world["ask"])], runner)
        assert (code, answer["agent"]) == (0, name_of(MAIN, clashes))
        assert runner.started[0]["name"] == name_of(MAIN, clashes)
    state_file(world).unlink()
    runner = DogfoodFakeRunner(world["env"])
    for n in range(3):
        runner.add_agent(name_of(MAIN, n))
    code, answer, runner = run(world, ["start", "--ask-file", str(world["ask"])], runner)
    assert (code, answer["error"]["code"]) == (1, "herdr-failed") and not runner.calls_of("pane", "split")
    assert all(name_of(MAIN, n) in answer["error"]["reason"] for n in range(3))


def _old_state(world, agent, pane):
    state = {"version": 1, "main_pane": MAIN, "agent": agent, "afkv2_pane": pane, "harness": "claude",
             "source": str(world["source"]), "base": "feat/afkv2",
             "worktrees": [{"path": str(world["tmp"] / "wt"), "branch": "feat/afkv2-df-20261126-0900", "lane": "small",
                            "created": "2026-11-26T09:00:00+00:00"}],
             "notes": [], "wrap_reported": False, "started": "2026-11-26T09:00:00+00:00"}
    state_file(world).write_text(json.dumps(state), encoding="utf-8")
    return state


def test_a_live_state_gets_the_ask_and_a_stale_state_is_replaced_by_a_new_pane(world):
    old = _old_state(world, name_of(MAIN), "w1:p7")
    runner = DogfoodFakeRunner(world["env"])
    runner.add_agent(name_of(MAIN), "w1:p7")
    code, answer, runner = run(world, ["start", "--ask-file", str(world["ask"])], runner)
    assert (code, answer["status"], answer["agent"], answer["pane"]) == (0, "existing", name_of(MAIN), "w1:p7")
    assert answer["state"] == old == json.loads(state_file(world).read_text(encoding="utf-8"))
    assert not runner.calls_of("pane", "split") and not runner.started
    [prompt] = runner.prompts
    assert prompt["target"] == name_of(MAIN) and prompt["text"].endswith(ASK)

    for live_elsewhere in (False, True):
        _old_state(world, name_of(MAIN), "w1:p7")
        runner = DogfoodFakeRunner(world["env"])
        if live_elsewhere:
            runner.add_agent(name_of(MAIN), "w1:p8")
        code, answer, runner = run(world, ["start", "--ask-file", str(world["ask"])], runner)
        assert (code, answer["status"]) == (0, "opened") and len(runner.calls_of("pane", "split")) == 1
        state = json.loads(state_file(world).read_text(encoding="utf-8"))
        assert state == answer["state"] and state["afkv2_pane"] == answer["pane"] != "w1:p7"
        assert (state["base"], state["worktrees"]) == (None, [])


def _snapshot(folder):
    return {path: path.stat().st_mtime_ns for path in folder.rglob("*")}


def test_status_reads_the_state_from_either_pane_and_refuses_an_unknown_version(world):
    old = _old_state(world, name_of(MAIN), "w1:p7")
    before = _snapshot(world["tmp"])
    for pane, expected in ((MAIN, old), ("w1:p7", old), ("w1:p9", None)):
        code, answer, runner = run(world, ["status"], env={**world["env"], "HERDR_PANE_ID": pane})
        assert (code, answer) == (0, {"ok": True, "state": expected}) and not runner.calls
    code, answer, runner = run(world, ["status"], env={key: value for key, value in world["env"].items()
                                                        if not key.startswith("HERDR")})
    assert (code, answer) == (0, {"ok": True, "state": None})
    assert _snapshot(world["tmp"]) == before

    code, answer, runner = run(world, ["start", "--ask-file", str(world["ask"])],
                               env={**world["env"], "HERDR_PANE_ID": "w1:p7"})
    assert (code, answer["error"]["code"]) == (1, "in-afkv2-pane") and not _herdr_calls(runner)

    for text in (json.dumps({**old, "version": 2}), "{broken"):
        state_file(world).write_text(text, encoding="utf-8")
        for argv in (["status"], ["start", "--ask-file", str(world["ask"])]):
            code, answer, runner = run(world, argv)
            assert (code, answer["error"]["code"]) == (2, "state-unreadable") and not _herdr_calls(runner)
            assert str(state_file(world)) in answer["error"]["reason"]


def test_the_state_file_name_is_sanitised_and_the_lookup_reads_at_most_10_files(world):
    pane = "w1:p 2/é"
    code, answer, runner = run(world, ["start", "--ask-file", str(world["ask"])],
                               env={**world["env"], "HERDR_PANE_ID": pane})
    assert code == 0 and (world["data"] / "dogfood-w1_p_2__.json").is_file()
    assert answer["state"]["main_pane"] == pane

    for n in range(12):
        path = world["data"] / f"dogfood-w5_p{n}.json"
        text = "{broken" if n < 2 else json.dumps({**answer["state"], "main_pane": f"w5:p{n}",
                                                   "afkv2_pane": f"w6:p{n}"})
        path.write_text(text, encoding="utf-8")
        os.utime(path, (1_700_000_000 + n, 1_700_000_000 + n))
    code, answer, runner = run(world, ["status"], env={**world["env"], "HERDR_PANE_ID": "w7:p1"})
    assert (code, answer) == (0, {"ok": True, "state": None})
    code, answer, runner = run(world, ["status"], env={**world["env"], "HERDR_PANE_ID": "w6:p11"})
    assert code == 0 and answer["state"]["main_pane"] == "w5:p11"


def test_a_stalled_first_prompt_gets_1_enter_and_a_refused_one_leaves_the_session_open(world):
    runner = DogfoodFakeRunner(world["env"])
    runner.answer(("agent", "prompt"), herdr_error("agent_prompt_stalled"), times=1)
    runner.on(("pane", "read"), lambda argv: runner.screens.update({argv[3]: "> You are the afkv2 agent of a dogfood session. Read"}))
    code, answer, runner = run(world, ["start", "--ask-file", str(world["ask"])], runner)
    assert (code, answer["status"], answer["submitted"]) == (0, "opened", True)
    assert runner.keys == [(answer["pane"], ["enter"])] and len(runner.calls_of("agent", "wait")) == 1

    state_file(world).unlink()
    runner = DogfoodFakeRunner(world["env"])
    runner.answer(("agent", "prompt"), herdr_error("agent_prompt_stalled"), times=1)
    code, answer, runner = run(world, ["start", "--ask-file", str(world["ask"])], runner)
    assert (code, answer["submitted"], runner.keys) == (0, True, [])

    state_file(world).unlink()
    runner = DogfoodFakeRunner(world["env"])
    runner.answer(("agent", "prompt"), herdr_error("agent_blocked"))
    code, answer, runner = run(world, ["start", "--ask-file", str(world["ask"])], runner)
    assert (code, answer["status"], answer["submitted"]) == (0, "opened", False)
    assert "agent_blocked" in answer["prompt_error"] and state_file(world).is_file()
    assert answer["pane"] in runner.panes
