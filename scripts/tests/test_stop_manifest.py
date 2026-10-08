"""Stop runs only the repository's declared Stop handlers, and its stdout stays one JSON document."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = ROOT / "hooks" / "run-hook.py"
MOVED_GATES = ("stop-gates", "wiring", "skill-registry", "native-contract", "genericity", "behavior-registry")


def _launcher():
    spec = importlib.util.spec_from_file_location("afk_run_hook_for_stop", LAUNCHER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("manifest", ["hooks.json", "hooks.codex.json"])
def test_stop_runs_only_the_repository_list(manifest):
    groups = json.loads((ROOT / "hooks" / manifest).read_text(encoding="utf-8"))["hooks"]["Stop"]
    commands = [h["command"] for g in groups for h in g["hooks"]]
    assert len(commands) == 1 and commands[0].endswith("repo-list Stop"), commands
    assert not any(gate in commands[0] for gate in MOVED_GATES)


NOISY = "#!/bin/sh\necho 'noise on stdout'\necho 'finding' >&2\nexit {rc}\n"


@pytest.mark.skipif(_launcher().find_bash() is None, reason="no POSIX shell on this machine")
@pytest.mark.parametrize("provider", ["claude", "codex"])
@pytest.mark.parametrize("rc", [0, 2])
def test_a_noisy_stop_handler_leaves_one_document_or_none(tmp_path, provider, rc):
    root = tmp_path / "repo"
    (root / ".afk").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / ".afk" / "hooks.json").write_text(
        json.dumps([{"event": "Stop", "matcher": "*", "script": ".afk/s.sh"}]), encoding="utf-8")
    (root / ".afk" / "s.sh").write_text(NOISY.format(rc=rc), encoding="utf-8", newline="\n")
    env = {**os.environ, "AFK_PROVIDER": provider}
    for name in ("CLAUDE_PLUGIN_ROOT", "PLUGIN_ROOT", "CLAUDE_PROJECT_DIR", "PROJECT_DIR"):
        env.pop(name, None)
    done = subprocess.run([sys.executable, str(LAUNCHER), "repo-list", "Stop"], cwd=root, env=env,
                          input=json.dumps({"hook_event_name": "Stop"}), capture_output=True, text=True,
                          timeout=180)
    assert done.returncode == 0, done.stderr
    if rc == 0:
        assert done.stdout.strip() == "" and "noise on stdout" in done.stderr
        return
    document, end = json.JSONDecoder().raw_decode(done.stdout.strip())
    assert done.stdout.strip()[end:] == "" and document["decision"] == "block"
    assert "finding" in document["reason"] and "noise on stdout" not in done.stdout
