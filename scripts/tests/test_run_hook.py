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
