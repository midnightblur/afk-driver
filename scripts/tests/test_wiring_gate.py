"""wiring-gate.sh verdicts, run standalone against temp repositories only."""
import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BASH = _load("afk_run_hook_for_wiring", ROOT / "hooks" / "run-hook.py").find_bash()
SCAN = _load("afk_bounded_scan_for_wiring", ROOT / "hooks" / "lib" / "bounded_scan.py")
pytestmark = pytest.mark.skipif(BASH is None, reason="no POSIX shell on this machine")

TOKEN = "orphanthing"
ARTIFACT = f"lib/{TOKEN}.py"


def _git(cwd, *args):
    return subprocess.run(["git", "-c", "user.email=t@example.invalid", "-c", "user.name=t", *args],
                          cwd=cwd, check=True, capture_output=True, text=True).stdout


@pytest.fixture()
def repo(tmp_path):
    _git(tmp_path, "init", "-q")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "notes.md").write_text("nothing here\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "base")
    (tmp_path / "lib").mkdir()
    (tmp_path / ARTIFACT).write_text("x = 1\n", encoding="utf-8")
    return tmp_path


def _gate(cwd, env_extra=None, path=None):
    env = {**os.environ, "GATE_CACHE_DISABLE": "0", "GATE_METRICS_DISABLE": "0", **(env_extra or {})}
    env.pop("GATE_METRICS_FILE", None)
    if path is not None:
        env["PATH"] = path
    return subprocess.run([str(BASH), str(ROOT / "hooks" / "wiring-gate.sh")], cwd=cwd, env=env,
                          capture_output=True, encoding="utf-8", errors="replace", timeout=300)


def _ledger(repo, body):
    (repo / ".claude").mkdir(exist_ok=True)
    (repo / ".claude" / "wiring-ious.md").write_text(body, encoding="utf-8")


def _metrics(repo):
    path = repo / ".git" / "afk" / "metrics" / "gate-latency.jsonl"
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def test_orphan_blocks(repo):
    result = _gate(repo)
    assert result.returncode == 2, result.stderr
    assert ARTIFACT in result.stderr
    assert '"result":"blocked"' in _metrics(repo) and '"scan_ms"' in _metrics(repo)


def test_wired_passes_and_caches(repo):
    (repo / "docs" / "notes.md").write_text(f"see {TOKEN}\n", encoding="utf-8")
    result = _gate(repo)
    assert result.returncode == 0, result.stderr
    assert '"tokens_tree"' in _metrics(repo)
    assert (repo / ".git" / "afk" / "gate-cache" / "wiring").is_file()


def test_pending_iou_passes_but_blocks_in_final_mode(repo):
    _ledger(repo, f"- [ ] `{ARTIFACT}` -> anchor: plan step 3 will call it\n")
    assert _gate(repo).returncode == 0
    final = _gate(repo, {"WIRING_FINAL": "1"})
    assert final.returncode == 2 and "open IOUs" in final.stderr


def test_waive_silences(repo):
    _ledger(repo, f"waive: `{ARTIFACT}` — build junk\n")
    assert _gate(repo).returncode == 0


def test_iou_auto_closes_when_a_consumer_arrives(repo):
    _ledger(repo, f"- [ ] `{ARTIFACT}` -> anchor: plan step 3\n")
    (repo / "docs" / "notes.md").write_text(f"uses {TOKEN}\n", encoding="utf-8")
    assert _gate(repo).returncode == 0
    body = (repo / ".claude" / "wiring-ious.md").read_text(encoding="utf-8")
    assert f"- [x] `{ARTIFACT}`" in body


def test_unknown_scan_is_rc3_and_not_cached(repo):
    lock = repo / ".git" / "afk" / "locks" / "repository-scan.lock"
    holder = SCAN.LockFile(str(lock))
    assert holder.acquire()
    try:
        result = _gate(repo)
    finally:
        holder.release()
    assert result.returncode == 3, result.stderr
    assert "verdict unknown (lock_busy) — no orphan check this Stop." in result.stderr
    assert '"result":"unknown"' in _metrics(repo) and '"detail":"lock_busy"' in _metrics(repo)
    assert not (repo / ".git" / "afk" / "gate-cache" / "wiring").exists()
    assert "orphan" not in result.stderr.lower().replace("no orphan check", "")


def test_no_python_is_unknown(repo):
    bash_root = Path(BASH).resolve().parent.parent
    dirs = [d for d in (bash_root / "usr" / "bin", bash_root / "bin", bash_root / "mingw64" / "bin",
                        bash_root / "cmd") if d.is_dir()]
    path = os.pathsep.join(str(d) for d in dirs)
    if shutil.which("python", path=path) or shutil.which("python3", path=path):
        pytest.skip("the shell's own toolchain carries python")
    result = _gate(repo, path=path)
    assert result.returncode == 3, result.stderr
    assert "verdict unknown (no_python)" in result.stderr
