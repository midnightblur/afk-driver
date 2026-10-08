"""A hook that fails names itself: `[afk] <handler> (<event>) failed: <outcome>: <reason>`.

Each case runs a copy of the plugin's hooks with one handler swapped for a fixture, under
each provider declaration, and reads what the harness would get: the exit code, the stderr
line, and stdout. Contract: CAPABILITIES.md "Hook failures".
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = PLUGIN_ROOT / "hooks" / "run-hook.py"


def _launcher():
    spec = importlib.util.spec_from_file_location("afk_run_hook_failures", LAUNCHER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


launcher = _launcher()
BASH = launcher.find_bash()
pytestmark = pytest.mark.skipif(BASH is None, reason="no POSIX shell on this machine")


@pytest.fixture()
def plugin(tmp_path):
    root = tmp_path / "plugin"
    shutil.copytree(PLUGIN_ROOT / "hooks", root / "hooks", ignore=shutil.ignore_patterns("tests", "__pycache__"))
    return root


def handler(root: Path, name: str, body: str) -> None:
    (root / "hooks" / name).write_text("#!/usr/bin/env bash\n" + body, encoding="utf-8", newline="\n")


def environ(provider: str, **extra: str) -> dict:
    env = {k: v for k, v in os.environ.items()
           if k not in ("CLAUDE_PLUGIN_ROOT", "PLUGIN_ROOT", "CLAUDECODE", "PYTHONIOENCODING", "PYTHONUTF8")}
    env.update({"AFK_PROVIDER": provider, "AFK_PYTHON": sys.executable, **extra})
    return env


def launch(root: Path, *args: str, provider: str = "claude", event: str = "PreToolUse", cwd=None, **extra):
    envelope = json.dumps({"hook_event_name": event, "session_id": "s", "tool_name": "Bash",
                           "tool_input": {"command": "true"}, "cwd": str(cwd or root)})
    return subprocess.run([sys.executable, str(root / "hooks" / "run-hook.py"), *args], input=envelope.encode(),
                          capture_output=True, cwd=str(cwd or root), env=environ(provider, **extra), timeout=180)


def text(stream: bytes) -> str:
    return stream.decode("utf-8", "replace")


def one_document(stdout: bytes) -> dict:
    said = text(stdout).strip()
    document, end = json.JSONDecoder().raw_decode(said)
    assert said[end:].strip() == "", said
    return document


# ---- plugin handlers through the launcher (L1)

def test_a_failing_handler_names_itself_with_its_last_stderr_line(plugin):
    handler(plugin, "fail.sh", "echo 'first' >&2\necho 'the real cause' >&2\nexit 1\n")
    done = launch(plugin, "plugin", "fail.sh")
    assert done.returncode == 1
    assert text(done.stderr).splitlines() == [
        "first", "the real cause", "[afk] fail.sh (PreToolUse) failed: exit 1: the real cause"]
    assert done.stdout == b""


def test_a_silent_failure_still_names_its_handler(plugin):
    handler(plugin, "silent.sh", "cat >/dev/null\nexit 3\n")
    done = launch(plugin, "plugin", "silent.sh", event="Stop")
    assert done.returncode == 3
    assert text(done.stderr).strip() == "[afk] silent.sh (Stop) failed: exit 3: no message"


def test_a_timeout_names_itself_and_never_blocks(plugin):
    handler(plugin, "slow.sh", "echo 'still scanning' >&2\nsleep 30\n")
    done = launch(plugin, "--deadline", "2", "plugin", "slow.sh", event="Stop")
    assert done.returncode == 0
    assert ("[afk] slow.sh (Stop) failed: timed out after 2s, stopped, verdict unknown: still scanning"
            in text(done.stderr))
    assert done.stdout == b""


@pytest.mark.parametrize("event", ["PreToolUse", "Stop", "SessionStart", "PostToolUse"])
def test_success_adds_no_line_and_keeps_stdout(plugin, event):
    handler(plugin, "ok.sh", "printf '{\"k\": 1}\\n'\necho 'own message' >&2\nexit 0\n")
    done = launch(plugin, "plugin", "ok.sh", event=event)
    assert done.returncode == 0
    assert done.stdout == b'{"k": 1}\n'
    assert text(done.stderr).strip() == "own message"


DENY = {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                               "permissionDecisionReason": "no"}}
BLOCK = {"decision": "block", "reason": "no"}


@pytest.mark.parametrize("provider", ["claude", "codex"])
@pytest.mark.parametrize("event,document", [("PreToolUse", DENY), ("Stop", BLOCK)])
@pytest.mark.parametrize("code", [0, 1, 2])
def test_a_refusal_document_blocks_in_the_provider_form_whatever_the_exit_code(plugin, provider, event, document, code):
    handler(plugin, "deny.sh", f"printf '%s\\n' '{json.dumps(document)}'\nexit {code}\n")
    done = launch(plugin, "plugin", "deny.sh", provider=provider, event=event)
    assert done.returncode == 0  # both declarations: `stop_block_code` 0, PreToolUse denies at 0
    assert one_document(done.stdout) == document
    assert "failed" not in text(done.stderr)
    assert text(done.stderr).strip() == "no"  # an empty stderr gets the reason: one harness reads it at exit 2


@pytest.mark.parametrize("provider", ["claude", "codex"])
@pytest.mark.parametrize("event,field", [("PreToolUse", "permissionDecisionReason"), ("Stop", "reason")])
def test_exit_two_on_a_blocking_event_becomes_one_decision_document(plugin, provider, event, field):
    handler(plugin, "gate.sh", "echo 'two findings' >&2\nexit 2\n")
    done = launch(plugin, "plugin", "gate.sh", provider=provider, event=event)
    said = one_document(done.stdout)
    assert done.returncode == 0
    assert (said.get("hookSpecificOutput") or said)[field] == "two findings"
    assert text(done.stderr).strip() == "two findings"


@pytest.mark.parametrize("event", ["SessionStart", "PostToolUse"])
def test_exit_two_on_a_non_blocking_event_is_a_failure(plugin, event):
    handler(plugin, "two.sh", "echo 'not a gate' >&2\nexit 2\n")
    line = f"[afk] two.sh ({event}) failed: exit 2: not a gate"
    claude = launch(plugin, "plugin", "two.sh", provider="claude", event=event)
    assert claude.returncode == 2 and line in text(claude.stderr)
    codex = launch(plugin, "plugin", "two.sh", provider="codex", event=event)
    assert codex.returncode == 0 and one_document(codex.stdout) == {"systemMessage": line}


@pytest.mark.parametrize("provider,code", [("claude", 1), ("codex", 0)])
def test_a_deny_document_cut_off_mid_write_is_a_failure_not_a_verdict(plugin, provider, code):
    handler(plugin, "torn.sh", "printf '{\"hookSpecificOutput\": {\"permissionDecision\": \"de'\nexit 1\n")
    done = launch(plugin, "plugin", "torn.sh", provider=provider)
    assert done.returncode == code
    assert "[afk] torn.sh (PreToolUse) failed: exit 1: no message" in text(done.stderr)
    if provider == "codex":  # the harness gets one valid document, never the torn one
        assert one_document(done.stdout) == {"systemMessage": "[afk] torn.sh (PreToolUse) failed: exit 1: no message"}


def test_stdout_of_a_failing_handler_is_untouched_where_stderr_is_shown(plugin):
    handler(plugin, "fail.sh", "printf 'partial\\n'\nexit 1\n")
    done = launch(plugin, "plugin", "fail.sh", provider="claude")
    assert done.stdout == b"partial\n" and done.returncode == 1


def test_where_stderr_is_dropped_the_failure_is_one_system_message_at_exit_zero(plugin):
    handler(plugin, "fail.sh", "printf 'partial\\n'\necho 'the real cause' >&2\nexit 1\n")
    done = launch(plugin, "plugin", "fail.sh", provider="codex")
    line = "[afk] fail.sh (PreToolUse) failed: exit 1: the real cause"
    assert done.returncode == 0
    assert one_document(done.stdout) == {"systemMessage": line}
    assert line in text(done.stderr)


def test_soft_failures_are_named_on_stderr_and_exit_zero_with_untouched_stdout(plugin):
    handler(plugin, "fail.sh", "printf 'partial\\n'\nexit 1\n")
    for provider in ("claude", "codex"):
        done = launch(plugin, "--soft", "plugin", "fail.sh", provider=provider, event="SessionStart")
        assert done.returncode == 0 and done.stdout == b"partial\n"
        assert "[afk] fail.sh (SessionStart) failed: exit 1: no message" in text(done.stderr)


def test_a_caller_that_never_closes_stdin_does_not_hang_the_launcher(plugin, tmp_path):
    handler(plugin, "quiet.sh", "echo 'no envelope needed' >&2\nexit 1\n")
    with open(tmp_path / "out", "wb") as out, open(tmp_path / "err", "wb") as err:
        held = subprocess.Popen([sys.executable, str(plugin / "hooks" / "run-hook.py"), "plugin", "quiet.sh"],
                                stdin=subprocess.PIPE, stdout=out, stderr=err, cwd=str(plugin), env=environ("claude"))
        held.stdin.write(json.dumps({"hook_event_name": "SessionStart"}).encode())
        held.stdin.flush()  # and never closed: the launcher must not wait for EOF
        try:
            code = held.wait(timeout=60)
        except subprocess.TimeoutExpired:
            held.kill()
            pytest.fail("the launcher waited for an EOF the caller never sent")
        finally:
            held.stdin.close()
    assert code == 1
    said = (tmp_path / "err").read_text(encoding="utf-8")
    assert "[afk] quiet.sh (SessionStart) failed: exit 1: no envelope needed" in said


def test_a_handler_reads_the_envelope_it_was_sent(plugin):
    handler(plugin, "echo.sh", "cat\n")
    done = launch(plugin, "plugin", "echo.sh", event="PostToolUse")
    assert done.returncode == 0 and json.loads(done.stdout)["hook_event_name"] == "PostToolUse"


# ---- what the capture files must never break

def big_envelope(marker: str, size: int) -> bytes:
    return json.dumps({"hook_event_name": "PostToolUse", "marker": marker, "pad": "x" * size}).encode()


def test_an_eight_mebibyte_envelope_reaches_the_handler_whole(plugin, tmp_path):
    handler(plugin, "count.sh", "wc -c | tr -d ' '\n")
    sent = big_envelope("big", 8 * 1024 * 1024)
    done = subprocess.run([sys.executable, str(plugin / "hooks" / "run-hook.py"), "plugin", "count.sh"],
                          input=sent, capture_output=True, cwd=str(plugin), env=environ("claude"), timeout=180)
    assert done.returncode == 0 and int(done.stdout) == len(sent)
    root = repository(tmp_path, [{"event": "PostToolUse", "matcher": "*", "script": ".afk/count.sh"}],
                      {"count.sh": "wc -c | tr -d ' '\n"})
    done = subprocess.run([sys.executable, str(LAUNCHER), "repo-list", "PostToolUse"], input=sent,
                          capture_output=True, cwd=str(root), env=environ("claude"), timeout=180)
    assert done.returncode == 0 and int(done.stdout) == len(sent)


def captures(folder: Path) -> list[str]:
    return sorted(p.name for p in folder.iterdir())


def settle(folder: Path, seconds: float = 15.0) -> list[str]:
    stop = time.monotonic() + seconds
    while captures(folder) and time.monotonic() < stop:
        time.sleep(0.1)
    return captures(folder)


def test_capture_files_are_gone_after_a_run_and_after_a_kill(plugin, tmp_path):
    folder = tmp_path / "captures"
    folder.mkdir()
    temp = {"TMP": str(folder), "TEMP": str(folder), "TMPDIR": str(folder)}
    handler(plugin, "fail.sh", "echo 'x' >&2\nexit 1\n")
    done = launch(plugin, "plugin", "fail.sh", **temp)
    assert done.returncode == 1 and settle(folder) == []
    handler(plugin, "slow.sh", "sleep 60\n")
    held = subprocess.Popen([sys.executable, str(plugin / "hooks" / "run-hook.py"), "plugin", "slow.sh"],
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            cwd=str(plugin), env=environ("claude", **temp))
    stop = time.monotonic() + 60
    while len(captures(folder)) < 2 and time.monotonic() < stop and held.poll() is None:
        time.sleep(0.1)
    assert len(captures(folder)) >= 2, "the launcher never opened its capture files"
    held.kill()
    held.wait(timeout=30)
    assert settle(folder) == []


def test_a_background_child_holding_the_capture_files_does_not_hold_the_launcher(plugin):
    handler(plugin, "bg.sh", "( sleep 30; echo late ) &\necho done\n")
    started = time.monotonic()
    done = launch(plugin, "plugin", "bg.sh")
    assert time.monotonic() - started < 20
    assert done.returncode == 0 and b"done" in done.stdout and b"late" not in done.stdout


@pytest.mark.parametrize("provider", ["claude", "codex"])
def test_invalid_stderr_bytes_never_break_the_answer(plugin, provider):
    handler(plugin, "bytes.sh", "printf '\\377bad\\n' >&2\nexit 1\n")
    done = launch(plugin, "plugin", "bytes.sh", provider=provider)
    line = "[afk] bytes.sh (PreToolUse) failed: exit 1: �bad"
    assert b"\xffbad" in done.stderr  # the handler's own bytes pass through raw
    assert line in text(done.stderr)
    if provider == "codex":
        assert done.returncode == 0 and one_document(done.stdout) == {"systemMessage": line}
    else:
        assert done.returncode == 1


def test_parallel_launchers_never_share_a_capture(plugin):
    from concurrent.futures import ThreadPoolExecutor

    handler(plugin, "echo.sh", "cat\n")
    sent = [big_envelope(f"run-{n}", 512 * 1024 + n) for n in range(6)]

    def one(envelope: bytes) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(plugin / "hooks" / "run-hook.py"), "plugin", "echo.sh"],
                              input=envelope, capture_output=True, cwd=str(plugin), env=environ("claude"),
                              timeout=180)

    with ThreadPoolExecutor(max_workers=len(sent)) as pool:
        results = list(pool.map(one, sent))
    for envelope, done in zip(sent, results):
        assert done.returncode == 0 and done.stdout == envelope


# ---- the launcher's own faults (L3, L4)

def test_a_runtime_fault_names_the_handler_and_reaches_a_harness_that_drops_stderr(plugin):
    handler(plugin, "any.sh", "exit 0\n")
    for provider, code in (("claude", 1), ("codex", 0)):
        done = launch(plugin, "plugin", "any.sh", provider=provider, AFK_PYTHON="/nowhere/python")
        assert done.returncode == code
        assert "[afk] any.sh (PreToolUse) failed: exit 1: AFK_PYTHON names /nowhere/python" in text(done.stderr)
    assert "AFK_PYTHON names /nowhere/python" in one_document(done.stdout)["systemMessage"]


def test_an_exception_in_the_launcher_names_itself_and_soft_still_exits_zero(monkeypatch, capsys):
    def boom(*_args, **_kwargs):
        raise OSError("spawn refused")
    monkeypatch.setattr(launcher, "run_captured", boom)
    monkeypatch.setenv("AFK_PYTHON", sys.executable)
    monkeypatch.setenv("AFK_PROVIDER", "claude")
    monkeypatch.setattr(sys, "stdin", None)
    assert launcher.guarded_main(["plugin", "nested-steering.sh"]) in (0, 1)  # no-op or crash, never a traceback
    monkeypatch.setattr(launcher, "policy_noop", lambda _h: False)
    assert launcher.guarded_main(["plugin", "update-notice.sh"]) == 1
    assert "[afk] update-notice.sh (unknown event) failed: exit 1: OSError: spawn refused" in capsys.readouterr().err
    assert launcher.guarded_main(["--soft", "plugin", "update-notice.sh"]) == 0


# ---- repository handlers through repo-list (L2, L5, and the blocking path)

def repository(tmp_path: Path, entries: list[dict], scripts: dict[str, str]) -> Path:
    root = tmp_path / "repo"
    (root / ".afk").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / ".afk" / "hooks.json").write_text(json.dumps(entries), encoding="utf-8")
    for name, body in scripts.items():
        (root / ".afk" / name).write_text("#!/bin/sh\n" + body, encoding="utf-8", newline="\n")
    return root


def test_a_failing_post_tool_use_handler_names_itself(tmp_path):
    root = repository(tmp_path, [{"event": "PostToolUse", "matcher": "*", "script": ".afk/bad.sh"}],
                      {"bad.sh": "echo 'cannot write the counter' >&2\nexit 1\n"})
    done = launch(PLUGIN_ROOT, "repo-list", "PostToolUse", event="PostToolUse", cwd=root)
    assert done.returncode == 1
    assert ("[afk] .afk/bad.sh (PostToolUse) failed: exit 1: cannot write the counter"
            in text(done.stderr))


def test_where_stderr_is_dropped_the_failure_joins_the_other_handlers_document(tmp_path):
    context = json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": "ctx"}})
    root = repository(tmp_path, [{"event": "PostToolUse", "matcher": "*", "script": ".afk/ctx.sh"},
                                 {"event": "PostToolUse", "matcher": "*", "script": ".afk/bad.sh"}],
                      {"ctx.sh": f"printf '%s\\n' '{context}'\n", "bad.sh": "exit 1\n"})
    done = launch(PLUGIN_ROOT, "repo-list", "PostToolUse", provider="codex", event="PostToolUse", cwd=root)
    assert done.returncode == 0
    document = one_document(done.stdout)
    assert document["hookSpecificOutput"]["additionalContext"] == "ctx"
    assert document["systemMessage"] == "[afk] .afk/bad.sh (PostToolUse) failed: exit 1: no message"


def test_a_crashed_stop_gate_is_named_inside_the_one_block_document(tmp_path):
    root = repository(tmp_path, [{"event": "Stop", "matcher": "*", "script": ".afk/crash.sh"}],
                      {"crash.sh": "echo 'Python was not found' >&2\nexit 9\n"})
    done = launch(PLUGIN_ROOT, "repo-list", "Stop", provider="codex", event="Stop", cwd=root)
    document = one_document(done.stdout)
    assert document["decision"] == "block"
    assert "[afk] .afk/crash.sh (Stop) failed: exit 9: Python was not found" in document["reason"]


def test_a_deliberate_refusal_keeps_its_own_message(tmp_path):
    root = repository(tmp_path, [{"event": "Stop", "matcher": "*", "script": ".afk/gate.sh"}],
                      {"gate.sh": "echo 'two findings' >&2\nexit 2\n"})
    done = launch(PLUGIN_ROOT, "repo-list", "Stop", event="Stop", cwd=root)
    assert "failed" not in text(done.stdout) + text(done.stderr)
    assert "two findings" in text(done.stderr)


def test_a_non_object_envelope_is_not_a_launcher_crash(tmp_path):
    root = repository(tmp_path, [{"event": "PostToolUse", "matcher": "Bash", "script": ".afk/ok.sh"}],
                      {"ok.sh": "exit 0\n"})
    done = subprocess.run([sys.executable, str(LAUNCHER), "repo-list", "PostToolUse"], input=b"[1, 2]",
                          capture_output=True, cwd=str(root), env=environ("claude"), timeout=120)
    assert done.returncode == 0 and b"Traceback" not in done.stderr


# ---- direct Python entries (P1, P2)

def direct(root: Path, entry: str, provider: str, cwd: Path):
    envelope = json.dumps({"hook_event_name": "PostToolUse", "session_id": "s", "tool_name": "Bash",
                           "tool_input": {"command": "touch x"}, "cwd": str(cwd)})
    return subprocess.run([sys.executable, str(root / "hooks" / entry)], input=envelope.encode(),
                          capture_output=True, cwd=str(cwd), env=environ(provider), timeout=120)


@pytest.mark.parametrize("entry,lib,event", [
    ("protected-branch-meter.py", "change_meter.py", "PostToolUse"),
    ("protected-branch-occupancy.py", "occupancy.py", "SessionStart"),
])
def test_a_fail_open_entry_names_its_crash_and_still_exits_zero(plugin, tmp_path, entry, lib, event):
    (plugin / "hooks" / "lib" / lib).write_text("raise RuntimeError('broken install')\n", encoding="utf-8")
    line = f"[afk] {entry} ({event}) failed: uncaught exception: RuntimeError: broken install"
    for provider in ("claude", "codex"):
        done = direct(plugin, entry, provider, tmp_path)
        assert done.returncode == 0
        assert line in text(done.stderr)
    assert one_document(done.stdout) == {"systemMessage": line}


def test_the_guard_names_an_escaped_exception_and_still_refuses_inside_a_work_tree(plugin, tmp_path):
    (plugin / "hooks" / "lib" / "protected_branch_guard.py").write_text(
        "def main():\n    raise KeyboardInterrupt('stopped')\n", encoding="utf-8")
    inside = tmp_path / "work"
    subprocess.run(["git", "init", "-q", str(inside)], check=True)
    done = direct(plugin, "protected-branch-guard.py", "codex", inside)
    assert done.returncode == 0
    assert ("[afk] protected-branch-guard.py (PreToolUse) failed: uncaught exception: KeyboardInterrupt: stopped"
            in text(done.stderr))
    assert one_document(done.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_a_late_guard_crash_judges_the_envelope_cwd_not_the_process_directory(plugin, tmp_path):
    (plugin / "hooks" / "lib" / "protected_branch_guard.py").write_text(
        "import sys\n\ndef main():\n    sys.stdin.buffer.read()\n    raise KeyboardInterrupt('late')\n",
        encoding="utf-8")
    outside, inside = tmp_path / "outside", tmp_path / "work"
    outside.mkdir()
    subprocess.run(["git", "init", "-q", str(inside)], check=True)
    envelope = json.dumps({"hook_event_name": "PreToolUse", "session_id": "s", "tool_name": "Bash",
                           "tool_input": {"command": "touch x"}, "cwd": str(inside)})
    done = subprocess.run([sys.executable, str(plugin / "hooks" / "protected-branch-guard.py")],
                          input=envelope.encode(), capture_output=True, cwd=str(outside),
                          env=environ("claude"), timeout=120)
    assert done.returncode == 0
    assert one_document(done.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


# ---- bash handlers: regressions for each silent exit fixed at its source (S1, S2, S3)

def test_a_stop_gate_that_kills_the_shell_leaves_its_error_on_stderr(plugin, tmp_path):
    for name in ("wiring", "skill-registry", "native-contract", "genericity", "behavior-registry"):
        (plugin / "hooks" / f"{name}-gate.sh").write_text(
            f"set -u\ngate_{name.replace('-', '_')}() {{ return 0; }}\n", encoding="utf-8", newline="\n")
    (plugin / "hooks" / "wiring-gate.sh").write_text(
        "set -u\ngate_wiring() { echo \"$afk_fixture_unset_name\"; }\n", encoding="utf-8", newline="\n")
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / "new.md").write_text("x\n", encoding="utf-8")
    done = launch(plugin, "--deadline", "120", "plugin", "stop-gates.sh", event="Stop", cwd=repo,
                  GATE_CACHE_DISABLE="1", GATE_METRICS_DISABLE="1")
    err = text(done.stderr)
    assert "afk_fixture_unset_name: unbound variable" in err
    assert "[afk] stop-gates.sh (Stop) failed: exit 1: " in err and "unbound variable" in err.splitlines()[-1]
    assert done.stdout == b""


def test_a_signal_after_stderr_is_released_still_replays_the_findings(plugin, tmp_path):
    for name in ("skill-registry", "native-contract", "genericity", "behavior-registry"):
        (plugin / "hooks" / f"{name}-gate.sh").write_text(
            f"gate_{name.replace('-', '_')}() {{ return 0; }}\n", encoding="utf-8", newline="\n")
    # The gate refuses, and its emitter override lands a TERM between the release and the replay.
    (plugin / "hooks" / "wiring-gate.sh").write_text(
        "gate_wiring() { echo 'wiring finding' >&2; return 2; }\n"
        "afk_emit_stop_block() { kill -TERM $$; }\n", encoding="utf-8", newline="\n")
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / "new.md").write_text("x\n", encoding="utf-8")
    done = subprocess.run([str(BASH), str(plugin / "hooks" / "stop-gates.sh")], stdin=subprocess.DEVNULL,
                          capture_output=True, cwd=str(repo), timeout=180,
                          env=environ("claude", GATE_CACHE_DISABLE="1", GATE_METRICS_DISABLE="1"))
    assert done.returncode == 143
    assert "wiring finding" in text(done.stderr)


def test_worktree_create_says_why_when_create_worktree_prints_no_path(tmp_path):
    root = tmp_path / "plugin"
    (root / "scripts").mkdir(parents=True)
    (root / "scripts" / "create-worktree").write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8", newline="\n")
    done = subprocess.run([str(BASH), str(PLUGIN_ROOT / "hooks" / "worktree-create.sh")],
                          input=b'{"name": "n"}', capture_output=True, cwd=str(tmp_path),
                          env=environ("claude", AFK_PLUGIN_ROOT=str(root)), timeout=120)
    assert done.returncode == 1
    assert "printed no WORKTREE_PATH= line" in text(done.stderr)
