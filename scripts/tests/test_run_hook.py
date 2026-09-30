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


def repository(tmp_path: Path, manifest: str, scripts: dict[str, str] | None = None) -> Path:
    root = tmp_path / "repo"
    (root / ".afk").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / ".afk" / "hooks.json").write_text(manifest, encoding="utf-8")
    for name, body in (scripts or {}).items():
        (root / ".afk" / name).write_text(body, encoding="utf-8")
    return root


def run(root: Path, event: str, envelope: dict, soft: bool = False):
    argv = [sys.executable, str(LAUNCHER)]
    if soft:
        argv.append("--soft")
    environ = dict(os.environ)
    environ["CLAUDE_PROJECT_DIR"] = str(root)
    return subprocess.run(
        [*argv, "repo-list", event],
        input=json.dumps(envelope), capture_output=True, text=True,
        cwd=str(root), env=environ, timeout=180,
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
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(root))
    monkeypatch.setattr(sys, "stdin", types.SimpleNamespace(
        buffer=io.BytesIO(json.dumps({"tool_name": "Bash"}).encode()), isatty=lambda: False))
    assert launcher.main(["repo-list", event]) == 0
    out = capsys.readouterr()
    assert "no POSIX shell to run .afk/g.sh" in out.out + out.err
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
