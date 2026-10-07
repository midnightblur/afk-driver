"""A declared repository hook that cannot run must not vanish quietly.

Every case here declares a handler in a throwaway repository, then breaks one
thing about it — the script, the matcher, the manifest, the time it takes — and
asks what the launcher answers. On Stop and PreToolUse the answer is the
decision object a failed gate emits; on the other events it is a line on
stderr and nothing else.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = PLUGIN_ROOT / "hooks" / "run-hook.py"


def _module():
    spec = importlib.util.spec_from_file_location("afk_run_hook", LAUNCHER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


launcher = _module()

pytestmark = pytest.mark.skipif(
    launcher.find_bash() is None,
    reason="no POSIX shell on this machine, so no handler can run at all",
)


def repository(
    tmp_path: Path, manifest: str, scripts: dict[str, str] | None = None, name: str = "repo"
) -> Path:
    root = tmp_path / name
    (root / ".afk").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / ".afk" / "hooks.json").write_text(manifest, encoding="utf-8")
    for name, body in (scripts or {}).items():
        (root / ".afk" / name).write_text(body, encoding="utf-8")
    return root


UNSET = object()


def run(root: Path, event: str, envelope: dict, soft: bool = False, *, project_dir=UNSET, cwd=None):
    argv = [sys.executable, str(LAUNCHER)]
    if soft:
        argv.append("--soft")
    environ = dict(os.environ)
    environ.pop("PROJECT_DIR", None)
    environ.pop("CLAUDE_PROJECT_DIR", None)
    named = root if project_dir is UNSET else project_dir
    if named is not None:
        environ["CLAUDE_PROJECT_DIR"] = str(named)
    return subprocess.run(
        [*argv, "repo-list", event],
        input=json.dumps(envelope), capture_output=True, text=True,
        cwd=str(cwd or root), env=environ, timeout=180,
    )


def decision(stdout: str) -> dict:
    return json.loads(stdout)


OK = "#!/bin/sh\nexit 0\n"


def test_missing_script_blocks_stop(tmp_path):
    root = repository(
        tmp_path, json.dumps([{"event": "Stop", "matcher": "*", "script": ".afk/gone.sh"}])
    )
    done = run(root, "Stop", {"hook_event_name": "Stop"})
    assert decision(done.stdout)["decision"] == "block"
    assert ".afk/gone.sh" in done.stderr


def test_invalid_matcher_denies_pretooluse(tmp_path):
    root = repository(
        tmp_path,
        json.dumps([{"event": "PreToolUse", "matcher": "Bash(", "script": ".afk/ok.sh"}]),
        {"ok.sh": OK},
    )
    done = run(root, "PreToolUse", {"hook_event_name": "PreToolUse", "tool_name": "Bash"})
    output = decision(done.stdout)["hookSpecificOutput"]
    assert output["permissionDecision"] == "deny"
    assert "regular expression" in output["permissionDecisionReason"]


def test_malformed_manifest_blocks_stop(tmp_path):
    root = repository(tmp_path, "[{bad")
    done = run(root, "Stop", {"hook_event_name": "Stop"})
    assert decision(done.stdout)["decision"] == "block"


def test_manifest_that_is_not_an_array_blocks_stop(tmp_path):
    root = repository(tmp_path, json.dumps({"event": "Stop"}))
    done = run(root, "Stop", {"hook_event_name": "Stop"})
    assert "JSON array" in decision(done.stdout)["reason"]


def test_timeout_blocks_stop(tmp_path):
    root = repository(
        tmp_path,
        json.dumps([{"event": "Stop", "matcher": "*", "timeout": 1, "script": ".afk/slow.sh"}]),
        {"slow.sh": "#!/bin/sh\nsleep 30\n"},
    )
    done = run(root, "Stop", {"hook_event_name": "Stop"})
    assert decision(done.stdout)["decision"] == "block"
    assert "no verdict" in done.stderr


def test_other_events_only_warn(tmp_path):
    root = repository(
        tmp_path, json.dumps([{"event": "SessionStart", "matcher": "*", "script": ".afk/gone.sh"}])
    )
    done = run(root, "SessionStart", {"hook_event_name": "SessionStart"})
    assert done.stdout == ""
    assert ".afk/gone.sh" in done.stderr
    assert done.returncode == 0


def test_soft_never_blocks(tmp_path):
    root = repository(
        tmp_path, json.dumps([{"event": "Stop", "matcher": "*", "script": ".afk/gone.sh"}])
    )
    done = run(root, "Stop", {"hook_event_name": "Stop"}, soft=True)
    assert done.stdout == ""
    assert done.returncode == 0


def test_healthy_handler_still_runs_silently(tmp_path):
    root = repository(
        tmp_path,
        json.dumps([{"event": "Stop", "matcher": "*", "script": ".afk/ok.sh"}]),
        {"ok.sh": OK},
    )
    done = run(root, "Stop", {"hook_event_name": "Stop"})
    assert done.stdout == ""
    assert done.stderr == ""
    assert done.returncode == 0


def _code_page_env() -> dict:
    """The environment a harness hands the launcher: no override of the console code page."""
    return {k: v for k, v in os.environ.items() if k not in ("PYTHONIOENCODING", "PYTHONUTF8")}


def test_handler_text_outside_the_code_page_reaches_the_harness_as_utf8(tmp_path):
    root = repository(
        tmp_path,
        json.dumps([{"event": "PreToolUse", "matcher": "*", "script": ".afk/say.sh"}]),
        {"say.sh": "#!/bin/sh\nprintf 'next \\342\\206\\222 step\\n' >&2\nexit 0\n"},
    )
    env = {**_code_page_env(), "CLAUDE_PROJECT_DIR": str(root)}
    done = subprocess.run([sys.executable, str(LAUNCHER), "repo-list", "PreToolUse"],
                          input=json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Bash"}).encode(),
                          capture_output=True, cwd=str(root), env=env, timeout=180)
    assert done.returncode == 0, done.stderr
    assert "next → step" in done.stderr.decode("utf-8")


def test_no_manifest_is_not_a_fault(tmp_path):
    root = tmp_path / "bare"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    done = run(root, "Stop", {"hook_event_name": "Stop"})
    assert done.stdout == ""
    assert done.returncode == 0


EXITS_2 = "#!/bin/sh\necho 'not allowed here' >&2\nexit 2\n"


def test_r7_1_a_pretooluse_script_that_exits_nonzero_becomes_the_deny_json_at_exit_zero(tmp_path):
    root = repository(
        tmp_path, json.dumps([{"event": "PreToolUse", "matcher": "*", "script": ".afk/no.sh"}]),
        {"no.sh": EXITS_2})
    done = run(root, "PreToolUse", {"hook_event_name": "PreToolUse", "tool_name": "Bash"})
    assert done.returncode == 0
    body = decision(done.stdout)["hookSpecificOutput"]
    assert body["permissionDecision"] == "deny" and "not allowed here" in body["permissionDecisionReason"]


def test_r7_1_a_stop_script_that_exits_nonzero_becomes_the_block_object(tmp_path):
    root = repository(
        tmp_path, json.dumps([{"event": "Stop", "matcher": "*", "script": ".afk/no.sh"}]), {"no.sh": EXITS_2})
    done = run(root, "Stop", {"hook_event_name": "Stop"})
    assert done.returncode == 0
    assert decision(done.stdout)["decision"] == "block" and "not allowed here" in done.stdout


def test_r8_2_a_script_that_printed_its_own_deny_leaves_one_verdict_at_exit_zero(tmp_path):
    own = ("#!/bin/sh\necho '{\"hookSpecificOutput\":{\"hookEventName\":\"PreToolUse\","
           "\"permissionDecision\":\"deny\",\"permissionDecisionReason\":\"mine\"}}'\nexit 0\n")
    root = repository(
        tmp_path, json.dumps([{"event": "PreToolUse", "matcher": "*", "script": ".afk/own.sh"}]), {"own.sh": own})
    done = run(root, "PreToolUse", {"hook_event_name": "PreToolUse", "tool_name": "Bash"})
    assert done.returncode == 0 and decision(done.stdout)["hookSpecificOutput"]["permissionDecisionReason"] is not None
    assert "mine" in done.stdout


def _denies(reason: str, code: int) -> str:
    deny = ('{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny",'
            f'"permissionDecisionReason":"{reason}"}}}}')
    return f"#!/bin/sh\necho '{deny}'\nexit {code}\n"


def test_r8_2_deny_json_with_exit_two_is_rewritten_to_exit_zero(tmp_path):
    root = repository(
        tmp_path, json.dumps([{"event": "PreToolUse", "matcher": "*", "script": ".afk/a.sh"}]),
        {"a.sh": _denies("belt", 2)})
    done = run(root, "PreToolUse", {"hook_event_name": "PreToolUse", "tool_name": "Bash"})
    assert done.returncode == 0
    assert decision(done.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny" and "belt" in done.stdout


def test_r8_2_two_refusing_handlers_leave_one_document(tmp_path):
    root = repository(
        tmp_path, json.dumps([{"event": "PreToolUse", "matcher": "*", "script": ".afk/a.sh"},
                              {"event": "PreToolUse", "matcher": "*", "script": ".afk/b.sh"}]),
        {"a.sh": _denies("first-no", 0), "b.sh": EXITS_2})
    done = run(root, "PreToolUse", {"hook_event_name": "PreToolUse", "tool_name": "Bash"})
    assert done.returncode == 0
    body = decision(done.stdout)["hookSpecificOutput"]
    assert done.stdout.count('"permissionDecision"') == 1
    assert "first-no" in body["permissionDecisionReason"] and "not allowed here" in body["permissionDecisionReason"]


def test_r8_2_a_stop_block_object_with_a_nonzero_exit_is_one_block_at_exit_zero(tmp_path):
    own = "#!/bin/sh\necho '{\"decision\":\"block\",\"reason\":\"mine\"}'\nexit 2\n"
    root = repository(
        tmp_path, json.dumps([{"event": "Stop", "matcher": "*", "script": ".afk/s.sh"},
                              {"event": "Stop", "matcher": "*", "script": ".afk/t.sh"}]),
        {"s.sh": own, "t.sh": own})
    done = run(root, "Stop", {"hook_event_name": "Stop"})
    assert done.returncode == 0 and done.stdout.count('"decision"') == 1 and "mine" in done.stdout


@pytest.mark.parametrize("event", ["PreToolUse", "Stop"])
def test_r7_2_with_no_shell_a_matching_blocking_entry_blocks(tmp_path, monkeypatch, capsys, event):
    import io
    import types
    root = repository(tmp_path, json.dumps([{"event": event, "matcher": "*", "script": ".afk/g.sh"}]),
                      {"g.sh": OK})
    monkeypatch.setattr(launcher, "find_bash", lambda: None)
    monkeypatch.chdir(root)
    monkeypatch.setattr(sys, "stdin", types.SimpleNamespace(
        buffer=io.BytesIO(json.dumps({"tool_name": "Bash"}).encode()), isatty=lambda: False))
    assert launcher.main(["repo-list", event]) == 0
    out = capsys.readouterr()
    assert "no POSIX shell found" in out.err and "cannot run .afk/g.sh" in out.out + out.err
    assert ("permissionDecision" if event == "PreToolUse" else '"decision"') in out.out


def test_r9_3_two_context_printing_handlers_leave_one_document(tmp_path):
    def printer(text: str) -> str:
        doc = json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": text}})
        return f"#!/bin/sh\necho '{doc}'\n"

    root = repository(
        tmp_path, json.dumps([{"event": "PreToolUse", "matcher": "*", "script": ".afk/a.sh"},
                              {"event": "PreToolUse", "matcher": "*", "script": ".afk/b.sh"}]),
        {"a.sh": printer("first note"), "b.sh": printer("second note")})
    done = run(root, "PreToolUse", {"hook_event_name": "PreToolUse", "tool_name": "Bash"})
    assert done.returncode == 0
    body = decision(done.stdout)["hookSpecificOutput"]
    assert body["additionalContext"] == "first note\nsecond note"


def test_r10_1_an_ask_is_never_turned_into_an_allow_by_another_handler():
    def doc(decision: str, reason: str, message: str) -> bytes:
        return json.dumps({"systemMessage": message, "hookSpecificOutput": {
            "hookEventName": "PreToolUse", "permissionDecision": decision,
            "permissionDecisionReason": reason}}).encode()

    for order in ((("ask", "gate A asks", "note A"), ("allow", "gate B ok", "note B")),
                  (("allow", "gate B ok", "note B"), ("ask", "gate A asks", "note A"))):
        merged = json.loads(launcher.merge_allowed([doc(*item) for item in order]))
        body = merged["hookSpecificOutput"]
        assert body["permissionDecision"] == "ask" and body["permissionDecisionReason"] == "gate A asks"
        assert sorted(merged["systemMessage"].split("\n")) == ["note A", "note B"]


BLOCK = OK.replace("exit 0", "echo gate-ran >&2\nexit 2")
STOP_GATE = json.dumps([{"event": "Stop", "matcher": "*", "script": ".afk/gate.sh"}])


@pytest.mark.parametrize(
    "case, project_dir, where, blocks",
    [
        ("A", "x", "y", False),
        ("B", "y", "x", True),
        ("C", "x", "xwt", False),
        ("D", None, "xwt", False),
        ("E", None, "x", True),
        ("F", "x/sub", "x/sub", True),
        ("G", None, "x/sub", True),
    ],
)
def test_repo_list_reads_the_working_tree_not_the_project_dir(
    tmp_path, case, project_dir, where, blocks
):
    x = repository(tmp_path, STOP_GATE, {"gate.sh": BLOCK}, name="x")
    y = repository(tmp_path, "[]", name="y")
    (x / "sub").mkdir()
    subprocess.run(["git", "-C", str(x), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(x), "-c", "user.name=t", "-c", "user.email=t@t", "commit",
         "-q", "-m", "init"], check=True)
    xwt = tmp_path / "xwt"
    subprocess.run(["git", "-C", str(x), "worktree", "add", "-q", "-b", "nogate", str(xwt)], check=True)
    (xwt / ".afk" / "hooks.json").write_text("[]", encoding="utf-8")
    dirs = {"x": x, "y": y, "xwt": xwt, "x/sub": x / "sub"}
    named = dirs[project_dir] if project_dir else None
    done = run(x, "Stop", {"hook_event_name": "Stop"}, project_dir=named, cwd=dirs[where])
    assert done.returncode == 0, case
    assert ('"decision"' in done.stdout and "gate-ran" in done.stdout) == blocks, case


# ---- process-tree ownership: a deadline or a killed launcher ends the whole tree --

import shutil
import time

CHILD = """\
import os, subprocess, sys, time
subprocess.Popen([sys.executable, "-c", "import os, time\\nopen(os.environ['MARK'] + '.grand', 'w').write(str(os.getpid()))\\ntime.sleep(120)"])
open(os.environ["MARK"] + ".child", "w").write(str(os.getpid()))
time.sleep(120)
"""

WAITER = """\
import importlib.util, os, sys
spec = importlib.util.spec_from_file_location("h2", os.environ["H2"])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.spawn([sys.executable, "-c", "import os, time\\nopen(os.environ['MARK'] + '.waiter', 'w').write(str(os.getpid()))\\ntime.sleep(60)"],
             env={"MARK": os.environ["MARK"]})
"""


def _alive(pid: int) -> bool:
    if os.name == "nt":
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True).stdout
        return str(pid) in out
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _pids(mark: Path, kinds: tuple[str, ...], wait: float = 20.0) -> list[int]:
    end = time.monotonic() + wait
    while time.monotonic() < end:
        files = [Path(f"{mark}.{k}") for k in kinds]
        if all(f.is_file() and f.read_text().strip() for f in files):
            return [int(f.read_text()) for f in files]
        time.sleep(0.1)
    raise AssertionError(f"handler never recorded {kinds}")


def _gone(pids: list[int], within: float = 10.0) -> bool:
    end = time.monotonic() + within
    while time.monotonic() < end:
        if not any(_alive(p) for p in pids):
            return True
        time.sleep(0.2)
    return False


@pytest.fixture()
def plugin_copy(tmp_path):
    root = tmp_path / "plugin"
    (root / "hooks").mkdir(parents=True)
    shutil.copy(LAUNCHER, root / "hooks" / "run-hook.py")
    (tmp_path / "child.py").write_text(CHILD, encoding="utf-8")
    (tmp_path / "waiter.py").write_text(WAITER, encoding="utf-8")
    for name, script in (("slow.sh", "child.py"), ("worktree-remove.sh", "waiter.py")):
        (root / "hooks" / name).write_text(
            f'#!/bin/sh\n"$PY" "{(tmp_path / script).as_posix()}"\n',
            encoding="utf-8", newline="\n")
    mark = tmp_path / "mark"
    env = {**os.environ, "PY": sys.executable, "MARK": str(mark),
           "H2": str(PLUGIN_ROOT / "hooks" / "lib" / "h2_move.py")}
    return root, mark, env


def _launch(root: Path, env, *args: str):
    env = {k: v for k, v in env.items() if k not in ("PYTHONIOENCODING", "PYTHONUTF8")}
    return subprocess.Popen([sys.executable, str(root / "hooks" / "run-hook.py"), *args],
                            env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf-8",
                            errors="replace")


def test_deadline_kills_the_handler_tree(plugin_copy):
    root, mark, env = plugin_copy
    start = time.monotonic()
    proc = _launch(root, env, "--deadline", "2", "plugin", "slow.sh")
    out, err = proc.communicate(timeout=60)
    assert time.monotonic() - start < 10
    assert proc.returncode == 0
    assert "slow.sh exceeded its 2s budget — stopped, verdict unknown." in err
    assert _gone(_pids(mark, ("child", "grand")))


def test_terminating_the_launcher_kills_the_tree(plugin_copy):
    root, mark, env = plugin_copy
    proc = _launch(root, env, "plugin", "slow.sh")
    pids = _pids(mark, ("child", "grand"))
    proc.terminate()
    proc.communicate(timeout=30)
    assert _gone(pids)


def test_a_detached_waiter_survives_a_normal_launcher_exit(plugin_copy):
    root, mark, env = plugin_copy
    proc = _launch(root, env, "plugin", "worktree-remove.sh")
    proc.communicate(timeout=60)
    (waiter,) = _pids(mark, ("waiter",))
    try:
        time.sleep(1.0)
        assert _alive(waiter)
    finally:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/PID", str(waiter)], capture_output=True)
        else:
            os.kill(waiter, 9)


def test_repo_list_timeout_returns_promptly_and_still_blocks(tmp_path, plugin_copy):
    _root, mark, env = plugin_copy
    repo_root_ = repository(
        tmp_path,
        json.dumps([{"event": "Stop", "matcher": "*", "timeout": 1, "script": ".afk/slow.sh"}]),
        {"slow.sh": f'#!/bin/sh\n"$PY" "{(tmp_path / "child.py").as_posix()}"\n'},
    )
    start = time.monotonic()
    done = subprocess.run([sys.executable, str(LAUNCHER), "repo-list", "Stop"], input=json.dumps({}),
                          capture_output=True, text=True, cwd=str(repo_root_), env=env, timeout=120)
    assert time.monotonic() - start < 10
    assert decision(done.stdout)["decision"] == "block" and "no verdict" in done.stderr
    assert _gone(_pids(mark, ("child", "grand")))


BACKGROUNDER = """\
import os, subprocess, sys
child = subprocess.Popen([sys.executable, "-c", "import os, time\\nopen(os.environ['MARK'] + '.bg', 'w').write(str(os.getpid()))\\ntime.sleep(120)"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
import time
for _ in range(100):
    if os.path.isfile(os.environ["MARK"] + ".bg") and os.path.getsize(os.environ["MARK"] + ".bg"):
        break
    time.sleep(0.1)
"""


def test_a_background_child_ends_when_its_handler_exits(plugin_copy, tmp_path):
    root, mark, env = plugin_copy
    (tmp_path / "bg.py").write_text(BACKGROUNDER, encoding="utf-8")
    (root / "hooks" / "leaver.sh").write_text(
        f'#!/bin/sh\n"$PY" "{(tmp_path / "bg.py").as_posix()}"\nexit 0\n', encoding="utf-8", newline="\n")
    proc = _launch(root, env, "plugin", "leaver.sh")
    proc.communicate(timeout=60)
    assert proc.returncode == 0
    assert _gone(_pids(mark, ("bg",)))


def test_a_plugin_handler_learns_the_wall_clock_deadline(plugin_copy):
    root, _, env = plugin_copy
    (root / "hooks" / "budget.sh").write_text('#!/bin/sh\nprintf "%s" "${AFK_HOOK_DEADLINE:-}"\n',
                                              encoding="utf-8", newline="\n")
    start = time.time()
    proc = _launch(root, env, "--deadline", "30", "plugin", "budget.sh")
    out, err = proc.communicate(timeout=60)
    assert proc.returncode == 0, err
    assert start + 25 < float(out) <= time.time() + 30
    proc = _launch(root, {k: v for k, v in env.items() if k != "AFK_HOOK_DEADLINE"}, "plugin", "budget.sh")
    out, _ = proc.communicate(timeout=60)
    assert out == ""


# ---- bails before any shell, and the AFK_PYTHON check before any handler

class ShellLookups:
    """Stands in for find_bash and counts the calls: a bail never looks for a shell."""

    def __init__(self):
        self.calls = 0

    def __call__(self):
        self.calls += 1
        return None


def _main_in(root: Path, monkeypatch, argv: list[str], envelope: dict | None = None) -> tuple[int, ShellLookups]:
    import io
    import types
    lookups = ShellLookups()
    monkeypatch.setattr(launcher, "find_bash", lookups)
    monkeypatch.setenv("AFK_PYTHON", sys.executable)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.delenv("PROJECT_DIR", raising=False)
    monkeypatch.chdir(root)
    monkeypatch.setattr(sys, "stdin", types.SimpleNamespace(
        buffer=io.BytesIO(json.dumps(envelope or {}).encode()), isatty=lambda: False))
    return launcher.main(argv), lookups


@pytest.mark.parametrize("declared", [None, "[]", json.dumps([{"event": "Stop", "matcher": "*", "script": "g.sh"}])])
def test_repo_list_with_nothing_declared_for_the_event_exits_before_any_shell_lookup(tmp_path, monkeypatch, declared):
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    if declared is not None:
        (root / ".afk").mkdir()
        (root / ".afk" / "hooks.json").write_text(declared, encoding="utf-8")
    code, lookups = _main_in(root, monkeypatch, ["repo-list", "PreToolUse"], {"tool_name": "Read"})
    assert code == 0 and lookups.calls == 0


def test_repo_list_outside_any_repository_exits_before_any_shell_lookup(tmp_path, monkeypatch):
    plain = tmp_path / "plain"
    plain.mkdir()
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    code, lookups = _main_in(plain, monkeypatch, ["repo-list", "Stop"])
    assert code == 0 and lookups.calls == 0


@pytest.mark.parametrize("answer", [OSError("git: cannot execute"), (1, "", "wrapper: broken"),
                                    (128, "", "fatal: not a git repository (or any of the parent directories)")])
def test_only_gits_own_answer_counts_as_no_repository(monkeypatch, answer):
    def git(*args, **kwargs):
        if isinstance(answer, Exception):
            raise answer
        return subprocess.CompletedProcess(args, answer[0], answer[1], answer[2])

    monkeypatch.setattr(launcher.subprocess, "run", git)
    root, answered = launcher.git_toplevel(dict(os.environ))
    assert root is None and answered == (not isinstance(answer, Exception) and answer[0] == 128)


def test_a_failed_repository_lookup_still_looks_for_a_shell(tmp_path, monkeypatch):
    root = repository(tmp_path, json.dumps([{"event": "Stop", "matcher": "*", "script": ".afk/g.sh"}]), {"g.sh": OK})
    monkeypatch.setattr(launcher, "git_toplevel", lambda env: (None, False))
    _code, lookups = _main_in(root, monkeypatch, ["repo-list", "Stop"])
    assert lookups.calls == 1


@pytest.mark.parametrize("manifest", [
    json.dumps([{"event": "PreToolUse", "matcher": "*", "script": ".afk/g.sh"}]),
    "{not json",
])
def test_repo_list_with_a_declared_entry_or_a_fault_still_looks_for_a_shell(tmp_path, monkeypatch, manifest):
    root = repository(tmp_path, manifest, {"g.sh": OK})
    _code, lookups = _main_in(root, monkeypatch, ["repo-list", "PreToolUse"], {"tool_name": "Read"})
    assert lookups.calls == 1


@pytest.mark.parametrize("handler, provider, bails", [
    ("nested-steering.sh", "claude", True),
    ("nested-steering.sh", "codex", False),
    ("agents-md-config-check.sh", "codex", True),
    ("agents-md-config-check.sh", "claude", False),
    ("nested-steering.sh", "nonesuch", True),
    ("update-notice.sh", "claude", False),
])
def test_a_handler_its_provider_declares_a_no_op_exits_before_any_shell_lookup(
        tmp_path, monkeypatch, handler, provider, bails):
    monkeypatch.setenv("AFK_PROVIDER", provider)
    code, lookups = _main_in(tmp_path, monkeypatch, ["--soft", "plugin", handler], {"hook_event_name": "PostToolUse"})
    assert code == 0 and lookups.calls == (0 if bails else 1)


@pytest.mark.parametrize("provider", ["claude", "codex"])
def test_the_launcher_and_the_shell_read_one_policy_declaration(provider):
    lib = (PLUGIN_ROOT / "hooks" / "lib" / "provider.sh").as_posix()
    done = subprocess.run(
        [str(launcher.find_bash()), "-c", f'. "{lib}"; afk_nested_inject_mode; afk_provider_fact instruction_files_setting'],
        env={**os.environ, "AFK_PROVIDER": provider}, capture_output=True, text=True, timeout=60)
    mode, setting = done.stdout.split()
    facts = launcher.load_lib("facts", PLUGIN_ROOT / "hooks" / "lib" / "provider_facts.py").facts({"AFK_PROVIDER": provider})
    assert launcher.POLICY_NOOP["nested-steering.sh"](facts) == (mode == "never")
    assert launcher.POLICY_NOOP["agents-md-config-check.sh"](facts) == (setting != "true")


def _without_afk_python(**extra: str) -> dict:
    env = {k: v for k, v in os.environ.items() if k not in ("AFK_PYTHON", "CLAUDE_PROJECT_DIR", "PROJECT_DIR")}
    return {**env, **extra}


def _bare(env: dict, cwd: Path, *args: str) -> subprocess.CompletedProcess:
    # -S skips site, so the entry's .pth cannot fill AFK_PYTHON in: the launcher sees `env` as given.
    return subprocess.run([sys.executable, "-S", str(LAUNCHER), *args], input="{}", capture_output=True,
                          text=True, env=env, timeout=120, cwd=str(cwd))


@pytest.mark.parametrize("named", [None, "elsewhere"])
def test_a_handler_never_starts_unless_afk_python_names_this_interpreter(tmp_path, named):
    env = _without_afk_python(**({"AFK_PYTHON": str(tmp_path / "afk-python")} if named else {}))
    done = _bare(env, PLUGIN_ROOT, "plugin", "update-notice.sh")
    assert done.returncode == 1 and "run /afk:setup" in done.stderr
    assert ("AFK_PYTHON is not set" if named is None else "not this interpreter") in done.stderr
    assert _bare(env, PLUGIN_ROOT, "--soft", "plugin", "update-notice.sh").returncode == 0


@pytest.mark.parametrize("event", ["PreToolUse", "Stop"])
def test_a_blocking_repository_gate_blocks_when_afk_python_is_missing(tmp_path, event):
    root = repository(tmp_path, json.dumps([{"event": event, "matcher": "*", "script": ".afk/g.sh"}]), {"g.sh": OK})
    done = _bare(_without_afk_python(), root, "repo-list", event)
    assert done.returncode == 0 and "AFK_PYTHON" in done.stdout
    assert ("permissionDecision" if event == "PreToolUse" else '"decision"') in done.stdout


def test_the_afk_python_check_passes_this_interpreter_and_a_handler_sees_it(plugin_copy):
    root, _, env = plugin_copy
    (root / "hooks" / "who.sh").write_text('#!/bin/sh\nprintf "%s" "$AFK_PYTHON"\n', encoding="utf-8", newline="\n")
    proc = _launch(root, {**env, "AFK_PYTHON": sys.executable}, "plugin", "who.sh")
    out, err = proc.communicate(timeout=60)
    assert proc.returncode == 0, err
    assert os.path.normcase(out) == os.path.normcase(sys.executable)
