import importlib.util
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
pytestmark = pytest.mark.skipif(BASH is None, reason="no POSIX shell on this machine")


def _env():
    env = {**os.environ, "GATE_CACHE_DISABLE": "0", "GATE_METRICS_DISABLE": "0"}
    env.pop("GATE_METRICS_FILE", None)
    return env


def _stop(cwd):
    return subprocess.run([str(BASH), str(ROOT / "hooks" / "stop-gates.sh")], cwd=cwd, env=_env(),
                          input="{}", capture_output=True, text=True, timeout=300)


def _git(cwd, *args):
    return subprocess.run(["git", "-c", "user.email=t@example.invalid", "-c", "user.name=t", *args],
                          cwd=cwd, check=True, capture_output=True, text=True).stdout


def test_stop_stamp_is_written_in_a_repository_without_a_cache_directory(tmp_path):
    _git(tmp_path, "init", "-q")
    result = _stop(tmp_path)
    assert "No such file or directory" not in result.stderr
    stamp = tmp_path / ".git" / "afk" / "gate-cache" / ".last-stop"
    assert stamp.read_text(encoding="utf-8").startswith("pass:")


def test_stop_leaves_the_working_tree_clean_and_short_circuits_an_unchanged_tree(tmp_path):
    _git(tmp_path, "init", "-q")
    (tmp_path / "README.md").write_text("x\n", encoding="utf-8")
    _git(tmp_path, "add", "README.md")
    _git(tmp_path, "commit", "-qm", "first")

    assert _stop(tmp_path).returncode == 0
    assert _git(tmp_path, "status", "--porcelain", "-uall") == ""
    assert not (tmp_path / ".claude").exists()
    assert (tmp_path / ".git" / "afk" / "metrics" / "gate-latency.jsonl").is_file()

    stamp = tmp_path / ".git" / "afk" / "gate-cache" / ".last-stop"
    assert stamp.read_text(encoding="utf-8").startswith("pass:")
    os.utime(stamp, ns=(1_000_000_000, 1_000_000_000))
    assert _stop(tmp_path).returncode == 0
    assert stamp.stat().st_mtime_ns == 1_000_000_000, "an unchanged all-green tree re-ran the gates"
    assert _git(tmp_path, "status", "--porcelain", "-uall") == ""


def test_linked_worktree_keeps_its_own_cache_and_shares_the_metrics_file(tmp_path):
    main = tmp_path / "main"
    main.mkdir()
    _git(main, "init", "-q")
    _git(main, "commit", "-q", "--allow-empty", "-m", "first")
    _git(main, "worktree", "add", "-q", "-b", "side", str(tmp_path / "side"))

    assert _stop(tmp_path / "side").returncode == 0
    assert _git(tmp_path / "side", "status", "--porcelain", "-uall") == ""
    assert (main / ".git" / "worktrees" / "side" / "afk" / "gate-cache" / ".last-stop").is_file()
    assert not (main / ".git" / "afk" / "gate-cache").exists()
    assert (main / ".git" / "afk" / "metrics" / "gate-latency.jsonl").is_file()


def test_stop_outside_a_repository_writes_nothing(tmp_path):
    env = {**_env(), "GIT_CEILING_DIRECTORIES": str(tmp_path.parent)}
    result = subprocess.run([str(BASH), str(ROOT / "hooks" / "stop-gates.sh")], cwd=tmp_path, env=env,
                            input="{}", capture_output=True, text=True, timeout=300)
    assert result.returncode == 0
    assert list(tmp_path.iterdir()) == []
