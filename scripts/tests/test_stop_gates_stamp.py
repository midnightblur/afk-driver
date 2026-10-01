import importlib.util
import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _bash():
    spec = importlib.util.spec_from_file_location("afk_run_hook_for_stop", ROOT / "hooks" / "run-hook.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.find_bash()


BASH = _bash()


@pytest.mark.skipif(BASH is None, reason="no POSIX shell on this machine")
def test_stop_stamp_is_written_in_a_repository_without_a_cache_directory(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    env = {**os.environ, "GATE_CACHE_DISABLE": "0"}
    result = subprocess.run([str(BASH), str(ROOT / "hooks" / "stop-gates.sh")], cwd=tmp_path, env=env,
                            input="{}", capture_output=True, text=True, timeout=300)
    assert "No such file or directory" not in result.stderr
    stamp = tmp_path / ".claude" / "hooks" / ".gate-cache" / ".last-stop"
    assert stamp.read_text(encoding="utf-8").startswith("pass:")


def _stop(repo, provider):
    env = {**os.environ, "GATE_CACHE_DISABLE": "0", "AFK_PROVIDER": provider}
    result = subprocess.run([str(BASH), str(ROOT / "hooks" / "stop-gates.sh")], cwd=repo, env=env,
                            input="{}", capture_output=True, text=True, timeout=300)
    said = json.loads(result.stdout) if result.stdout.strip() else {}
    return result, said


@pytest.mark.skipif(BASH is None, reason="no POSIX shell on this machine")
@pytest.mark.parametrize("provider", ["claude", "codex"])
def test_an_unchanged_blocked_tree_is_released_after_three_blocks(tmp_path, provider):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    # The runtime paths a provisioned worktree excludes; inside the change set they alter the tree key.
    exclude = tmp_path / ".git" / "info" / "exclude"
    exclude.write_text("/.claude/hooks/.gate-cache/\n/.claude/metrics/\n", encoding="utf-8")
    orphan = tmp_path / "unreferenced-artifact.txt"
    orphan.write_text("first\n", encoding="utf-8")
    stamp = tmp_path / ".claude" / "hooks" / ".gate-cache" / ".last-stop"

    for count in (1, 2, 3):
        result, said = _stop(tmp_path, provider)
        assert said.get("decision") == "block", (count, result.stdout, result.stderr)
        assert stamp.read_text(encoding="utf-8").startswith(f"blocked:{count}:")

    for _ in range(2):
        result, said = _stop(tmp_path, provider)
        assert result.returncode == 0
        assert "decision" not in said
        assert "findings still stand: wiring" in said["systemMessage"]
        assert "findings still stand: wiring" in result.stderr
        assert not stamp.read_text(encoding="utf-8").startswith("pass:")

    orphan.write_text("second\n", encoding="utf-8")
    result, said = _stop(tmp_path, provider)
    assert said.get("decision") == "block", (result.stdout, result.stderr)
    assert stamp.read_text(encoding="utf-8").startswith("blocked:1:")
