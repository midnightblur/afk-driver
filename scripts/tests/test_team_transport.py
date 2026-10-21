"""The transport adapter family: the verb set, the answer shapes, the launch switches and the three kinds."""
from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
FAMILY = REPO / "adapters" / "transport"
sys.path.insert(0, str(FAMILY))
sys.path.insert(0, str(FAMILY / "multiplexer"))

import contract  # noqa: E402
import herdr  # noqa: E402
import launch  # noqa: E402
import process  # noqa: E402
from contract import Answer, Deadline, Payload  # noqa: E402

KINDS = ("subagent", "headless", "multiplexer")
VERBS = ("agent-start", "agent-send", "agent-status", "agent-read", "agent-stop", "agent-list")


def _bash():
    spec = importlib.util.spec_from_file_location("afk_run_hook_for_transport", REPO / "hooks" / "run-hook.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.find_bash()


BASH = _bash()
needs_bash = pytest.mark.skipif(BASH is None, reason="no POSIX shell on this machine")


def kind_call(kind: str, *args: str, env: dict | None = None) -> tuple[int, str, str]:
    entry = FAMILY / kind / "transport.sh"
    full = {**(os.environ if env is None else env), "AFK_PYTHON": sys.executable}
    done = subprocess.run([BASH, str(entry), *args], capture_output=True, text=True, env=full, timeout=120)
    return done.returncode, done.stdout, done.stderr


def answer(stdout: str) -> dict:
    return json.loads(stdout.strip().splitlines()[-1])


# ---- the family contract -------------------------------------------------------------------------------

@pytest.mark.parametrize("kind", KINDS)
def test_every_kind_registers_the_six_verbs_with_a_cli_runner(kind):
    manifest = json.loads((FAMILY / kind / "adapter.json").read_text(encoding="utf-8"))
    assert manifest["family"] == "transport" and manifest["kind"] == kind
    assert tuple(manifest["operations"]) == VERBS == contract.VERBS
    assert manifest["runner"] == {"type": "cli", "entry": "transport.sh"}
    text = (FAMILY / kind / "CONTRACT.md").read_text(encoding="utf-8")
    assert all(f"`{verb}`" in text for verb in VERBS)


def test_each_verb_keeps_its_time_budget():
    assert contract.BUDGET_MS == {"agent-start": 120000, "agent-send": 30000, "agent-status": 10000,
                                  "agent-read": 30000, "agent-stop": 60000, "agent-list": 10000}


@pytest.mark.parametrize("verb", VERBS)
@needs_bash
def test_the_subagent_kind_answers_every_verb_unsupported(verb):
    code, out, _ = kind_call("subagent", verb, "{}")
    body = answer(out)
    assert code == 3 and body["unsupported"] is True and body["reason"]


@pytest.mark.parametrize("args, code, field", [
    (("agent-start", "[1, 2]"), 2, "error"),
    (("agent-start", "not json"), 2, "error"),
    (("agent-start",), 2, "error"),
    (("agent-start", "{}", "{}"), 2, "error"),
    ((), 2, "error"),
    (("agent-close", "{}"), 3, "unsupported"),
])
@needs_bash
def test_bad_input_answers_in_the_house_shapes(args, code, field):
    got, out, _ = kind_call("subagent", *args)
    body = answer(out)
    assert got == code and body[field] is True and body["reason"]
    if field == "error":
        assert "operation" in body


@needs_bash
def test_a_payload_never_comes_from_standard_input():
    entry = FAMILY / "subagent" / "transport.sh"
    done = subprocess.run([BASH, str(entry), "agent-start"], input="{}", capture_output=True, text=True,
                          env={**os.environ, "AFK_PYTHON": sys.executable}, timeout=60)
    assert done.returncode == 2 and answer(done.stdout)["error"] is True


class Crashing:
    def agent_status(self, payload, deadline):
        raise OSError("the disk went away")


def test_a_verb_that_crashes_answers_unavailable_not_a_traceback():
    import io
    out = io.StringIO()
    code = contract.run(Crashing(), ["agent-status", "{}"], out=out)
    body = json.loads(out.getvalue())
    assert code == 4 and body["unavailable"] is True and body["operation"] == "agent-status"
    assert "OSError: the disk went away" in body["reason"]


class Clock:
    """A monotonic clock that moves `step` seconds on every read."""

    def __init__(self, step: float):
        self.now, self.step = 0.0, step

    def __call__(self) -> float:
        self.now += self.step
        return self.now


def test_a_herdr_call_with_no_budget_left_refuses_without_running_herdr(monkeypatch):
    monkeypatch.setattr(herdr.subprocess, "run", lambda *a, **k: pytest.fail("herdr ran"))
    with pytest.raises(Answer) as caught:
        herdr.Herdr({}).agent_status(Payload("agent-status", {"handle": "w1:p2"}),
                                     Deadline("agent-status", clock=Clock(20.0)))
    assert caught.value.code == 4 and "no time left in the agent-status budget" in caught.value.body["reason"]


def test_detection_waits_inside_the_verbs_budget(monkeypatch):
    import multiplexer
    waits = []

    def detect(env, harnesses, timeout):
        waits.append(timeout)
        return herdr.Detection("herdr", "outside", "not in a pane")

    monkeypatch.setitem(multiplexer.TOOLS, "herdr", (detect, herdr.Herdr))
    with pytest.raises(Answer):
        multiplexer.Multiplexer({}).agent_status(Payload("agent-status", {"handle": "w1:p2"}),
                                                 Deadline("agent-status"))
    assert waits and 2 * waits[0] <= contract.BUDGET_MS["agent-status"] / 1000 / 2


def test_a_bad_field_names_the_field():
    with pytest.raises(Answer) as caught:
        Payload("agent-stop", {"pid": "12"}).integer("pid")
    assert caught.value.code == 2 and "`pid`" in caught.value.body["reason"]
    assert caught.value.body["operation"] == "agent-stop"


# ---- the launch switches: seam-test for "Harness update check at an agent's start" ----------------------

@pytest.mark.parametrize("build", [
    lambda h: launch.interactive(h, "go", model="m", effort="high"),
    lambda h: launch.interactive(h, "go", resume="sess-1"),
    lambda h: launch.headless(h, "go", model="m"),
])
def test_each_start_command_carries_its_harness_update_switch_on_its_own_launch(build):
    before = dict(os.environ)
    claude, codex = build("claude"), build("codex")
    assert claude.env == {"DISABLE_AUTOUPDATER": "1"}
    assert "check_for_update_on_startup=false" not in claude.args
    assert codex.env == {}
    pair = [codex.args[i:i + 2] for i in range(len(codex.args) - 1)]
    assert ["-c", "check_for_update_on_startup=false"] in pair
    assert dict(os.environ) == before


def test_launch_refuses_an_unknown_harness():
    with pytest.raises(ValueError):
        launch.interactive("other", "go")


# ---- the headless kind, against a stub harness ---------------------------------------------------

STUB = r'''
import os, subprocess, sys, time
open(sys.argv[1], "w").write(str(subprocess.Popen([sys.executable, "-c", "import time; time.sleep(300)"]).pid))
print("STUB-START", os.environ.get("DISABLE_AUTOUPDATER", "-"), *sys.argv[2:], flush=True)
print("STUB-STDIN", repr(sys.stdin.buffer.read().decode("utf-8")), flush=True)
time.sleep(300)
'''


@pytest.fixture
def stub_harness(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    script = tmp_path / "stub.py"
    script.write_text(STUB, encoding="utf-8")
    grand = tmp_path / "grandchild.pid"
    if sys.platform == "win32":
        (bin_dir / "claude.cmd").write_text(f'@"{sys.executable}" "{script}" "{grand}" %*\r\n', encoding="utf-8")
    else:
        stub = bin_dir / "claude"
        stub.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "{grand}" "$@"\n', encoding="utf-8")
        stub.chmod(0o755)
    return bin_dir, grand


def headless(*args: str, path: str) -> tuple[int, dict]:
    done = subprocess.run([sys.executable, str(FAMILY / "headless" / "headless.py"), *args], capture_output=True,
                          text=True, env={**os.environ, "PATH": path}, timeout=120)
    return done.returncode, answer(done.stdout)


def wait_for(check, seconds: float = 20.0) -> bool:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if check():
            return True
        time.sleep(0.2)
    return check()


def test_headless_starts_reads_and_stops_a_run_and_its_whole_tree(tmp_path, stub_harness):
    bin_dir, grand = stub_harness
    path = str(bin_dir) + os.pathsep + os.environ["PATH"]
    log = str(tmp_path / "run" / "agent.log")
    code, body = headless("agent-start", json.dumps({"harness": "claude", "prompt": "do it", "cwd": str(tmp_path),
                                                     "log": log, "model": "m1"}), path=path)
    assert code == 0, body
    pid = body["pid"]
    assert body["kind"] == "headless" and body["handle"] == str(pid)
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", body["started_at"])
    assert wait_for(lambda: grand.exists() and grand.read_text().strip())
    assert wait_for(lambda: "STUB-STDIN" in Path(log).read_text(encoding="utf-8", errors="replace"))
    code, status = headless("agent-status", json.dumps({"pid": pid, "log": log}), path=path)
    assert code == 0 and status["alive"] is True and status["state"] == "running"
    code, read = headless("agent-read", json.dumps({"log": log}), path=path)
    assert code == 0 and "STUB-START 1 -p --model m1" in read["text"] and read["complete"] is True
    code, again = headless("agent-read", json.dumps({"log": log, "since_marker": read["marker"]}), path=path)
    assert code == 0 and again["text"] == ""
    code, stop = headless("agent-stop", json.dumps({"pid": pid}), path=path)
    assert code == 0 and stop == {"stopped": True, "method": "killed the process tree"}
    grandchild = int(grand.read_text().strip())
    assert wait_for(lambda: not process.alive(grandchild)) and not process.alive(pid)
    code, status = headless("agent-status", json.dumps({"pid": pid, "log": log}), path=path)
    assert code == 0 and status["alive"] is False and status["state"] == "exited"
    code, stop = headless("agent-stop", json.dumps({"pid": pid}), path=path)
    assert code == 0 and stop["stopped"] is True


def test_the_headless_run_sits_under_its_owners_job(tmp_path, stub_harness):
    bin_dir, grand = stub_harness
    path = str(bin_dir) + os.pathsep + os.environ["PATH"]
    log = str(tmp_path / "agent.log")
    code, body = headless("agent-start", json.dumps({"harness": "claude", "prompt": "go", "cwd": str(tmp_path),
                                                     "log": log}), path=path)
    assert code == 0, body
    pid = body["pid"]
    assert wait_for(lambda: grand.exists() and grand.read_text().strip())
    grandchild = int(grand.read_text().strip())
    try:
        owner = process._parents()[pid]
        if sys.platform == "win32":     # the kill-on-close job ends every member with its owner
            subprocess.run(["taskkill", "/F", "/PID", str(owner)], capture_output=True, check=False)
            assert wait_for(lambda: not process.alive(pid) and not process.alive(grandchild))
        else:
            assert os.getsid(pid) == owner == os.getsid(grandchild)
    finally:
        process.kill_tree(pid, force=True, wait_s=5)
        process.kill_tree(grandchild, force=True, wait_s=5)


def test_the_prompt_reaches_the_harness_whole_on_standard_input(tmp_path, stub_harness):
    bin_dir, grand = stub_harness           # on Windows the stub is a batch file, which cmd.exe runs
    prompt = 'line one\nline "two" & 50% | <x> ^ !y'
    log = tmp_path / "a.log"
    code, body = headless("agent-start", json.dumps({"harness": "claude", "prompt": prompt, "cwd": str(tmp_path),
                                                     "log": str(log)}),
                          path=str(bin_dir) + os.pathsep + os.environ["PATH"])
    assert code == 0, body
    try:
        assert wait_for(lambda: "STUB-STDIN" in log.read_text(encoding="utf-8", errors="replace"))
        text = log.read_text(encoding="utf-8", errors="replace")
        assert f"STUB-STDIN {prompt!r}" in text and "line one" not in text.split("STUB-STDIN")[0]
    finally:
        process.kill_tree(body["pid"], force=True, wait_s=5)
        if grand.exists() and grand.read_text().strip():
            process.kill_tree(int(grand.read_text()), force=True, wait_s=5)


def test_a_codex_headless_run_reads_its_instructions_from_standard_input():
    run = launch.headless("codex", "do it")
    assert run.args[-1] == "-" and "do it" not in run.args and run.stdin == "do it"
    run = launch.headless("claude", "do it")
    assert "do it" not in run.args and run.stdin == "do it"


def test_a_start_whose_owner_never_reports_ends_the_owner(tmp_path, monkeypatch, stub_harness):
    sys.path.insert(0, str(FAMILY / "headless"))
    import headless as kind
    owners = []

    def silent(argv, env):
        owners.append(subprocess.Popen([sys.executable, "-c", "import time; time.sleep(300)"]))
        return owners[-1]

    monkeypatch.setattr(kind, "_spawn_owner", silent)
    monkeypatch.setenv("PATH", str(stub_harness[0]) + os.pathsep + os.environ["PATH"])
    log = tmp_path / "a.log"
    with pytest.raises(Answer) as caught:
        kind.Headless().agent_start(Payload("agent-start", {"harness": "claude", "prompt": "go",
                                                            "cwd": str(tmp_path), "log": str(log)}),
                                    Deadline("agent-start", clock=Clock(119.0)))
    assert caught.value.code == 4 and "reported no process in time" in caught.value.body["reason"]
    assert wait_for(lambda: owners[0].poll() is not None)
    assert not Path(str(log) + ".status.json").exists()


ORPHAN = r'''
import subprocess, sys, time
middle = subprocess.Popen([sys.executable, "-c",
    "import subprocess,sys; p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(300)']);"
    "open(sys.argv[1],'w').write(str(p.pid))", sys.argv[1]])
middle.wait()
print("ORPHAN-READY", flush=True)
time.sleep(300)
'''


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX: a descendant whose parent ended moves to init")
def test_a_posix_stop_reaches_a_descendant_that_moved_to_init(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    script, grand = tmp_path / "orphan.py", tmp_path / "orphan.pid"
    script.write_text(ORPHAN, encoding="utf-8")
    stub = bin_dir / "claude"
    stub.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "{grand}"\n', encoding="utf-8")
    stub.chmod(0o755)
    path = str(bin_dir) + os.pathsep + os.environ["PATH"]
    log = str(tmp_path / "a.log")
    code, body = headless("agent-start", json.dumps({"harness": "claude", "prompt": "go", "cwd": str(tmp_path),
                                                     "log": log}), path=path)
    assert code == 0, body
    assert wait_for(lambda: grand.exists() and grand.read_text().strip())
    orphan = int(grand.read_text().strip())
    assert orphan not in process.tree(body["pid"])
    code, stop = headless("agent-stop", json.dumps({"pid": body["pid"]}), path=path)
    assert code == 0 and stop["stopped"] is True
    assert wait_for(lambda: not process.alive(orphan))


def test_headless_answers_unavailable_when_the_harness_is_absent(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    code, body = headless("agent-start", json.dumps({"harness": "codex", "prompt": "p", "cwd": str(tmp_path),
                                                     "log": str(tmp_path / "x.log")}), path=str(empty))
    assert code == 4 and body["unavailable"] is True and "codex" in body["reason"]


def test_headless_refuses_a_marker_it_never_gave(tmp_path):
    log = tmp_path / "a.log"
    log.write_text("abc", encoding="utf-8")
    code, body = headless("agent-read", json.dumps({"log": str(log), "since_marker": "x9"}), path=os.environ["PATH"])
    assert code == 2 and "since_marker" in body["reason"]
    code, body = headless("agent-read", json.dumps({"log": str(log), "since_marker": "99"}), path=os.environ["PATH"])
    assert code == 2


@pytest.mark.parametrize("status, text, complete", [
    ({"exit_code": 0}, "ab\ufffd", True),
    (None, "ab", False),
])
def test_a_cut_last_character_is_kept_only_once_the_run_has_finished(tmp_path, status, text, complete):
    log = tmp_path / "a.log"
    log.write_bytes(b"ab" + "\u00e9".encode("utf-8")[:1])
    if status is not None:
        (tmp_path / "a.log.status.json").write_text(json.dumps(status), encoding="utf-8")
    code, body = headless("agent-read", json.dumps({"log": str(log)}), path=os.environ["PATH"])
    assert code == 0 and body["text"] == text and body["complete"] is complete


def test_a_run_that_ends_between_the_status_read_and_the_log_read_keeps_its_cut_character(tmp_path,
                                                                                          monkeypatch):
    spec = importlib.util.spec_from_file_location("headless_kind", FAMILY / "headless" / "headless.py")
    kind = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(kind)
    log = tmp_path / "a.log"
    log.write_bytes(b"ab" + "\u00e9".encode("utf-8")[:1])
    real = kind.os.path.getsize

    def finish_then_size(path):
        (tmp_path / "a.log.status.json").write_text(json.dumps({"exit_code": 0}), encoding="utf-8")
        return real(path)

    monkeypatch.setattr(kind.os.path, "getsize", finish_then_size)
    body = kind.Headless().agent_read(Payload("agent-read", {"log": str(log)}), Deadline("agent-read"))
    assert body["text"] == "ab" and body["marker"] == "2" and body["complete"] is False


@pytest.mark.parametrize("verb", ["agent-send", "agent-list"])
def test_headless_has_no_message_and_no_list(verb):
    code, body = headless(verb, "{}", path=os.environ["PATH"])
    assert code == 3 and body["unsupported"] is True


# ---- the multiplexer kind's herdr mapping, against a recorded herdr ------------------------------

class FakeHerdr:
    """herdr's JSON answers over an in-memory session; `fail` maps a command to an error code."""

    def __init__(self):
        self.tabs = {"w1:t1": {"label": "contact", "panes": ["w1:p1"]}}
        self.panes = {"w1:p1": {"tab": "w1:t1", "label": "contact", "agent": "claude", "name": None, "pid": None}}
        self.calls: list[list[str]] = []
        self.fail: dict[str, str] = {}
        self.pids: list[int] = []
        self.alive_at_close: list[bool] = []
        self.screen = "line 1\nline 2\nline 3\n"
        self.status = "idle"
        self.start_timeout = False
        self._n = 1

    def _new_pane(self, tab: str) -> str:
        self._n += 1
        pane = f"w1:p{self._n}"
        pid = self.pids.pop(0) if self.pids else None
        self.panes[pane] = {"tab": tab, "label": "", "agent": None, "name": None, "pid": pid}
        self.tabs[tab]["panes"].append(pane)
        return pane

    def handle(self, args: list[str]) -> dict:
        self.calls.append(list(args))
        key = " ".join(args[:2])
        if key in self.fail:
            raise herdr.HerdrError(self.fail[key], "refused by the fake")
        if key == "tab list":
            return {"tabs": [{"tab_id": t, "label": v["label"], "pane_count": len(v["panes"])}
                             for t, v in self.tabs.items()]}
        if key == "tab create":
            tab = f"w1:t{len(self.tabs) + 1}"
            self.tabs[tab] = {"label": args[args.index("--label") + 1], "panes": []}
            pane = self._new_pane(tab)
            return {"tab": {"tab_id": tab}, "root_pane": {"pane_id": pane}}
        if key == "pane list":
            return {"panes": [{"pane_id": p, "tab_id": v["tab"]} for p, v in self.panes.items()]}
        if key == "pane split":
            return {"pane": {"pane_id": self._new_pane(self.panes[args[2]]["tab"])}}
        pane = args[2] if len(args) > 2 else ""
        if key in ("pane get", "pane rename", "pane close", "pane run", "pane read", "agent start") \
                and key != "agent start" and pane not in self.panes:
            raise herdr.HerdrError("pane_not_found", pane)
        if key == "pane rename":
            self.panes[pane]["label"] = args[3]
            return {}
        if key == "agent start":
            target = args[args.index("--pane") + 1]
            self.panes[target].update(agent=args[args.index("--kind") + 1], name=args[2])
            if self.start_timeout:
                raise herdr.HerdrError("timeout", "timed out waiting for agent startup")
            return {}
        if key == "pane run":
            self.panes[pane]["agent"] = "codex"
            return {}
        if key == "agent rename":
            self.panes[pane]["name"] = args[3]
            return {}
        if key == "pane process-info":
            target = args[args.index("--pane") + 1]
            pid = self.panes[target]["pid"]
            return {"process_info": {"foreground_processes": [{"pid": pid, "name": "claude"}] if pid else [],
                                     "shell_pid": None}}
        if key == "agent get":
            if pane not in self.panes or not self.panes[pane]["agent"]:
                raise herdr.HerdrError("agent_not_found", pane)
            return {"agent": {"agent": self.panes[pane]["agent"], "agent_status": self.status,
                              "agent_session": {"value": "sess-9"}}}
        if key == "agent prompt":
            if pane not in self.panes:
                raise herdr.HerdrError("agent_not_found", pane)
            return {}
        if key == "pane get":
            return {"pane": {"pane_id": pane, "tab_id": self.panes[pane]["tab"]}}
        if key == "pane close":
            pid = self.panes[pane]["pid"]
            self.alive_at_close.append(bool(pid) and process.alive(pid))
            tab = self.panes.pop(pane)["tab"]
            self.tabs[tab]["panes"].remove(pane)
            return {}
        if key == "tab get":
            if args[2] not in self.tabs:
                raise herdr.HerdrError("tab_not_found", args[2])
            return {"tab": {"pane_count": len(self.tabs[args[2]]["panes"])}}
        if key == "tab close":
            self.tabs.pop(args[2])
            return {}
        if key == "pane read":
            return {"text": self.screen}
        if key == "agent list":
            return {"agents": [{"name": v["name"], "pane_id": p} for p, v in self.panes.items() if v["name"]]}
        raise AssertionError(f"unexpected herdr call {args}")


SESSION = {"HERDR_ENV": "1", "HERDR_PANE_ID": "w1:p1", "HERDR_TAB_ID": "w1:t1", "HERDR_WORKSPACE_ID": "w1"}


@pytest.fixture
def fake(monkeypatch):
    session = FakeHerdr()
    def call(self, args, deadline, cap=30.0):
        if deadline.left() <= 0:
            raise herdr.HerdrError("timeout", f"no time left in the {deadline.verb} budget")
        return session.handle(args)

    monkeypatch.setattr(herdr.Herdr, "call", call)
    return session


def mux(verb: str, data: dict) -> dict:
    tool = herdr.Herdr({**os.environ, **SESSION})
    return getattr(tool, verb.replace("-", "_"))(Payload(verb, data), Deadline(verb))


def start(name: str, harness: str = "claude", tab: str = "goal step", **extra) -> dict:
    return mux("agent-start", {"harness": harness, "name": name, "label": f"{name} label", "cwd": str(REPO),
                               "tab": tab, "prompt": "brief", **extra})


def calls(fake: FakeHerdr, key: str) -> list[list[str]]:
    return [c for c in fake.calls if " ".join(c[:2]) == key]


def test_a_start_opens_a_pane_in_a_new_tab_never_the_contact_tab(fake):
    body = start("a1")
    assert body["kind"] == "multiplexer" and body["tool"] == "herdr" and body["handle"] == "w1:p2"
    assert body["pane_label"] == "a1 label" and body["agent_name"] == "a1" and body["session_id"] == "sess-9"
    assert fake.panes["w1:p2"]["tab"] != "w1:t1" and fake.tabs["w1:t2"]["label"] == "goal step"
    created = calls(fake, "tab create")[0]
    assert "DISABLE_AUTOUPDATER=1" in created and created[created.index("DISABLE_AUTOUPDATER=1") - 1] == "--env"
    assert calls(fake, "pane rename")[0][2:] == ["w1:p2", "a1 label"]
    begun = calls(fake, "agent start")[0]
    assert begun[2] == "a1" and begun[begun.index("--kind") + 1] == "claude"


def test_one_step_fills_a_tab_as_a_2_by_2_grid_then_opens_the_next(fake):
    for n in range(5):
        start(f"a{n}")
    splits = [(c[2], c[c.index("--direction") + 1]) for c in calls(fake, "pane split")]
    assert splits == [("w1:p2", "right"), ("w1:p2", "down"), ("w1:p3", "down")]
    assert len(fake.tabs["w1:t2"]["panes"]) == 4 and fake.tabs["w1:t3"]["label"] == "goal step 2"
    assert fake.tabs["w1:t1"]["panes"] == ["w1:p1"]


def test_another_step_gets_its_own_tab(fake):
    start("a1", tab="goal build")
    start("a2", tab="goal verify")
    assert sorted(t["label"] for t in fake.tabs.values()) == ["contact", "goal build", "goal verify"]


def test_a_tab_that_cannot_be_made_refuses_the_start_naming_the_tab(fake):
    fake.fail["tab create"] = "error"
    with pytest.raises(Answer) as caught:
        start("a1")
    assert caught.value.code == 4 and caught.value.body["tab"] == "goal step"
    assert "goal step" in caught.value.body["reason"]
    assert not calls(fake, "pane split") and fake.tabs["w1:t1"]["panes"] == ["w1:p1"]


def test_a_codex_start_carries_the_update_switch_after_the_separator(fake):
    start("c1", harness="codex", model="m2", effort="high")
    begun = calls(fake, "agent start")[0]
    native = begun[begun.index("--") + 1:]
    assert native[:2] == ["-c", "check_for_update_on_startup=false"]
    assert "DISABLE_AUTOUPDATER=1" not in calls(fake, "tab create")[0]


def test_a_codex_resume_types_the_command_with_pane_run(fake):
    body = start("c1", harness="codex", resume="sess-7")
    assert not calls(fake, "agent start")
    line = calls(fake, "pane run")[0][3]
    assert "resume" in line and "sess-7" in line and "check_for_update_on_startup=false" in line
    assert calls(fake, "agent rename")[0][2:] == [body["handle"], "c1"]


def test_a_start_a_dialog_blocks_is_stopped_and_answers_unavailable(fake):
    fake.fail["agent start"] = "agent_not_ready"
    with pytest.raises(Answer) as caught:
        start("a1")
    assert caught.value.code == 4 and caught.value.body["dialog"] is True
    assert calls(fake, "pane close") and "w1:t2" not in fake.tabs
    assert "line 1 / line 2 / line 3" in caught.value.body["reason"]


def test_a_start_whose_first_turn_outlasts_herdrs_wait_counts_as_started(fake):
    fake.start_timeout, fake.status = True, "working"
    body = start("a1")
    assert body["handle"] == "w1:p2" and not calls(fake, "pane close")


def test_a_start_that_times_out_with_no_agent_is_refused_and_closed(fake):
    fake.fail["agent start"] = "timeout"
    with pytest.raises(Answer) as caught:
        start("a1")
    assert caught.value.code == 4 and calls(fake, "pane close") and "w1:t2" not in fake.tabs


def test_a_start_that_times_out_at_a_dialog_answers_dialog(fake):
    fake.start_timeout, fake.status = True, "blocked"
    with pytest.raises(Answer) as caught:
        start("a1")
    assert caught.value.code == 4 and caught.value.body["dialog"] is True and calls(fake, "pane close")


def test_a_message_goes_into_the_receivers_pane_by_agent_prompt(fake):
    pane = start("a1")["handle"]
    body = mux("agent-send", {"handle": pane, "text": "<envelope id=m1>"})
    assert body["delivered"] is True and body["way"] == "agent-prompt"
    assert calls(fake, "agent prompt")[0][2:] == [pane, "<envelope id=m1>"]
    with pytest.raises(Answer) as caught:
        mux("agent-send", {"handle": "w1:p99", "text": "x"})
    assert caught.value.code == 4 and caught.value.body["receiver_gone"] is True


def child_tree(tmp_path: Path) -> tuple[subprocess.Popen, Path]:
    grand = tmp_path / "g.pid"
    code = ("import subprocess,sys,time;"
            "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(300)']);"
            f"open(r'{grand}','w').write(str(p.pid)); time.sleep(300)")
    child = subprocess.Popen([sys.executable, "-c", code])
    assert wait_for(lambda: grand.exists() and grand.read_text().strip())
    return child, grand


def test_a_stop_kills_the_whole_tree_before_it_closes_the_pane_and_the_empty_tab(fake, tmp_path):
    child, grand = child_tree(tmp_path)
    fake.pids.append(child.pid)
    pane = start("a1")["handle"]
    body = mux("agent-stop", {"pid": child.pid, "handle": pane})
    assert body == {"stopped": True, "method": "killed the process tree", "pane_closed": True, "pane_id": pane}
    assert fake.alive_at_close == [False]
    assert wait_for(lambda: not process.alive(int(grand.read_text())))
    assert "w1:t2" not in fake.tabs and "w1:t1" in fake.tabs
    again = mux("agent-stop", {"pid": child.pid, "handle": pane})
    assert again["stopped"] is True and again["pane_closed"] is True


@pytest.mark.skipif(sys.platform != "win32" or BASH is None,
                    reason="an MSYS child's Windows parent is gone only under Git for Windows")
def test_a_tree_kill_reaches_an_msys_child_whose_windows_parent_is_gone():
    shell = subprocess.Popen([BASH, "-c", "sleep 300; true"])
    try:
        assert wait_for(lambda: len(process.tree(shell.pid)) >= 3)
        members = process.tree(shell.pid)
        assert process.kill_tree(shell.pid, force=True, wait_s=5) == []
        assert not [m for m in members if process.alive(m)]
    finally:
        for member in process.tree(shell.pid):
            process.kill_tree(member, force=True, wait_s=1)


def test_a_tree_skips_a_process_older_than_the_one_holding_its_parents_id(monkeypatch):
    monkeypatch.setattr(process, "_parents", lambda: {100: 1, 200: 100, 300: 100, 400: 200})
    monkeypatch.setattr(process, "_msys_children", lambda: {})
    born = {100: 50, 200: 60, 300: 10, 400: 70}
    monkeypatch.setattr(process, "_created", born.get)
    assert process.tree(100) == [100, 200, 400]


def test_a_tree_keeps_an_msys_child_newer_windows_parent_did_not_create(monkeypatch):
    monkeypatch.setattr(process, "_parents", lambda: {100: 1, 200: 100, 300: 5})
    monkeypatch.setattr(process, "_msys_children", lambda: {100: [300]})
    born = {100: 50, 200: 60, 300: 10}
    monkeypatch.setattr(process, "_created", born.get)
    assert sorted(process.tree(100)) == [100, 200, 300]


def test_a_failed_pane_close_answers_pane_closed_false_naming_the_pane(fake):
    pane = start("a1")["handle"]
    fake.fail["pane close"] = "error"
    body = mux("agent-stop", {"handle": pane})
    assert body["stopped"] is False and body["pane_closed"] is False and body["pane_id"] == pane
    assert pane in body["reason"] and body["survivors"] == [] and "method" not in body


def test_agent_list_returns_every_match_of_the_prefix(fake):
    start("goal-a")
    start("goal-b")
    start("other-c", tab="x")
    body = mux("agent-list", {"prefix": "goal-"})
    assert sorted(a["agent_name"] for a in body["agents"]) == ["goal-a", "goal-b"]
    assert all(a["pane_id"] for a in body["agents"])


def test_agent_read_returns_the_text_after_its_marker(fake):
    pane = start("a1")["handle"]
    first = mux("agent-read", {"handle": pane})
    assert first["text"].startswith("line 1") and first["complete"] is True
    fake.screen += "line 4\n"
    second = mux("agent-read", {"handle": pane, "since_marker": first["marker"]})
    assert second["text"] == "line 4" and second["complete"] is True
    fake.screen = "new\n"
    third = mux("agent-read", {"handle": pane, "since_marker": first["marker"]})
    assert third["complete"] is False and third["text"] == "new"
    with pytest.raises(Answer) as caught:
        mux("agent-read", {"handle": pane, "since_marker": "nope"})
    assert caught.value.code == 2


def test_a_failed_send_makes_one_attempt(fake):
    pane = start("a1")["handle"]
    fake.fail["agent prompt"] = "error"
    with pytest.raises(Answer) as caught:
        mux("agent-send", {"handle": pane, "text": "x"})
    assert caught.value.code == 4 and len(calls(fake, "agent prompt")) == 1


def test_a_stop_with_no_usable_tool_still_kills_the_tree_and_names_the_pane(monkeypatch, tmp_path):
    import multiplexer
    monkeypatch.setitem(multiplexer.TOOLS, "herdr",
                        (lambda env, harnesses, timeout: herdr.Detection("herdr", "broken", "no server"),
                         herdr.Herdr))
    child, grand = child_tree(tmp_path)
    body = multiplexer.Multiplexer({}).agent_stop(Payload("agent-stop", {"pid": child.pid, "handle": "w1:p2"}),
                                                  Deadline("agent-stop"))
    assert body["stopped"] is True and body["pane_closed"] is False and body["pane_id"] == "w1:p2"
    assert "no server" in body["pane_reason"]
    assert wait_for(lambda: not process.alive(int(grand.read_text()))) and not process.alive(child.pid)


def test_a_stop_with_no_tool_and_no_process_id_answers_not_stopped(monkeypatch):
    import multiplexer
    monkeypatch.setitem(multiplexer.TOOLS, "herdr",
                        (lambda env, harnesses, timeout: herdr.Detection("herdr", "broken", "no server"),
                         herdr.Herdr))
    body = multiplexer.Multiplexer({}).agent_stop(Payload("agent-stop", {"handle": "w1:p2"}),
                                                  Deadline("agent-stop"))
    assert body["stopped"] is False and "no process id" in body["reason"] and body["survivors"] == []
    assert body["pane_closed"] is False and body["pane_id"] == "w1:p2"


@pytest.mark.parametrize("stdout, stderr, code, want", [
    ('{"id":"1","result":{"type":"pane_info","pane":{"pane_id":"w1:p2","tab_id":"w1:t2"}}}', "", 0,
     {"type": "pane_info", "pane": {"pane_id": "w1:p2", "tab_id": "w1:t2"}}),
    ("line 1\nline 2\n", "", 0, {"text": "line 1\nline 2\n"}),
    ("", '{"id":"1","error":{"code":"pane_not_found","message":"pane w1:p9 not found"}}', 1, "pane_not_found"),
    ("", "server not running", 1, "error"),
])
def test_one_herdr_call_reads_herdrs_answer_shapes(monkeypatch, stdout, stderr, code, want):
    monkeypatch.setattr(herdr.subprocess, "run",
                        lambda argv, **kw: subprocess.CompletedProcess(argv, code, stdout, stderr))
    tool = herdr.Herdr({})
    if isinstance(want, dict):
        assert tool.call(["pane", "get", "w1:p2"], Deadline("agent-status")) == want
    else:
        with pytest.raises(herdr.HerdrError) as caught:
            tool.call(["pane", "get", "w1:p9"], Deadline("agent-status"))
        assert caught.value.code == want


def test_a_codex_resume_that_never_settles_leaves_time_to_close_its_pane(fake, monkeypatch):
    monkeypatch.setattr(herdr.time, "sleep", lambda s: None)
    fake.status = "working"
    tool = herdr.Herdr({**os.environ, **SESSION})
    payload = Payload("agent-start", {"harness": "codex", "name": "c1", "label": "c1 label", "cwd": str(REPO),
                                      "tab": "goal step", "resume": "sess-7"})
    with pytest.raises(Answer) as caught:
        tool.agent_start(payload, Deadline("agent-start", clock=Clock(5.0)))
    assert caught.value.code == 4 and "sess-7" in caught.value.body["reason"]
    assert calls(fake, "pane close") and "w1:t2" not in fake.tabs


def test_a_read_whose_marked_body_scrolled_away_is_not_complete(fake):
    pane = start("a1")["handle"]
    footer = "\n+------+\n| >    |\n+------+\n  ? for shortcuts\n"
    fake.screen = "line 1\nline 2" + footer
    first = mux("agent-read", {"handle": pane})
    fake.screen = "other x\nother y" + footer
    second = mux("agent-read", {"handle": pane, "since_marker": first["marker"]})
    assert second["complete"] is False and second["text"].startswith("other x\nother y")


def test_agent_read_finds_new_output_above_a_footer_that_never_changes(fake):
    pane = start("a1")["handle"]
    footer = "\n+------+\n| >    |\n+------+\n  ? for shortcuts\n"
    fake.screen = "line 1\nline 2" + footer
    first = mux("agent-read", {"handle": pane})
    fake.screen = "line 1\nline 2\nline 3\nline 4" + footer
    second = mux("agent-read", {"handle": pane, "since_marker": first["marker"]})
    assert second["complete"] is True and second["text"].startswith("line 3\nline 4")
    again = mux("agent-read", {"handle": pane, "since_marker": second["marker"]})
    assert again["text"].strip() == ""


def test_a_successor_tab_takes_the_next_number_in_use(fake):
    fake.tabs["w1:t9"] = {"label": "goal step 2", "panes": ["x1", "x2", "x3", "x4"]}
    start("a1")
    assert sorted(t["label"] for t in fake.tabs.values()) == ["contact", "goal step 2", "goal step 3"]


def test_a_tab_name_that_ends_in_a_number_keeps_its_own_tab(fake):
    start("a1", tab="goal step 2")
    start("a2", tab="goal step 2")
    assert [t["label"] for t in fake.tabs.values()].count("goal step 2") == 1


def test_agent_status_tells_a_live_agent_from_a_gone_pane(fake):
    pane = start("a1")["handle"]
    assert mux("agent-status", {"handle": pane})["alive"] is True
    assert mux("agent-status", {"handle": "w1:p99"}) == {"alive": False, "state": "gone", "since": None}


@needs_bash
def test_the_multiplexer_kind_is_unavailable_outside_a_herdr_pane():
    env = {k: v for k, v in os.environ.items() if not k.startswith("HERDR_")}
    code, out, _ = kind_call("multiplexer", "agent-status", '{"handle": "w1:p1"}', env=env)
    body = answer(out)
    assert code == 4 and body["unavailable"] is True and "herdr" in body["reason"]


# ---- the setup register row C15 ------------------------------------------------------------------------

MANIFEST = REPO / "skills" / "afk" / "setup" / "MANIFEST.md"


def c15() -> str:
    text = MANIFEST.read_text(encoding="utf-8")
    return text[text.index("### C15 · herdr"):text.index("### C16 ·")]


def test_c15_is_edited_in_place_names_no_harness_and_keeps_its_no_skill_line():
    text = MANIFEST.read_text(encoding="utf-8")
    assert text.count("### C15 ·") == 1 and "herdr" in c15()
    assert not re.search(r"\b(?:Claude Code|Codex|claude|codex)\b", c15())
    assert "No skill invokes it" in c15() and "adapters/transport/multiplexer/" in c15()


def test_c15_skips_with_no_human_reprobes_and_prints_a_removal_line():
    row = " ".join(c15().split())
    assert "With no human present, skip this row" in row and "`skipped (user choice)`" in row
    assert "is not fixed" in row and "print the removal line" in row
    assert r'`Remove-Item -Recurse -Force "$env:USERPROFILE\.herdr"`' in row
    assert '`rm -f "$(command -v herdr)"`' in row
    assert "teardown" not in row


@needs_bash
def test_an_installer_that_stops_part_way_leaves_the_row_not_fixed(tmp_path):
    probe = re.search(r"- \*\*Probe:\*\* `([^`]+)`", c15()).group(1)
    stub = tmp_path / "bin"
    stub.mkdir()
    # the part-way installer leaves a binary cut off mid-download; the complete one leaves a working one
    (stub / "partial.sh").write_text('mkdir -p "$1/.herdr/packages/standalone/releases"\n'
                                     "printf '#!/bin/sh\\nexit 1\\n' > \"$1/.herdr/herdr\"\n"
                                     'chmod +x "$1/.herdr/herdr"\nexit 1\n', encoding="utf-8")
    (stub / "complete.sh").write_text('mkdir -p "$1/.herdr"\n'
                                      "printf '#!/bin/sh\\necho herdr 0.9.1\\n' > \"$1/.herdr/herdr\"\n"
                                      'chmod +x "$1/.herdr/herdr"\n', encoding="utf-8")
    codes = {}
    for installer, expect in (("partial.sh", 1), ("complete.sh", 0)):
        home = tmp_path / installer
        installed = subprocess.run([BASH, str(stub / installer), str(home)], capture_output=True, text=True)
        assert installed.returncode == expect and (home / ".herdr" / "herdr").is_file()
        codes[installer] = subprocess.run([BASH, "-c", probe], capture_output=True, text=True, timeout=30,
                                          env={"PATH": f"{home / '.herdr'}{os.pathsep}{stub}",
                                               "HOME": str(home)}).returncode
    assert codes == {"partial.sh": 1, "complete.sh": 0}
    step5 = (REPO / "skills" / "afk" / "setup" / "SKILL.md").read_text(encoding="utf-8")
    assert "A fix not flipping its probe to exit 0\n   is not fixed" in step5
