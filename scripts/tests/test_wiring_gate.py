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
    _git(tmp_path, "add", ARTIFACT)
    return tmp_path


def _gate(cwd, env_extra=None, path=None):
    env = {**os.environ, "GATE_CACHE_DISABLE": "0", "GATE_METRICS_DISABLE": "0", **(env_extra or {})}
    env.pop("GATE_METRICS_FILE", None)
    if path is not None:
        env["PATH"] = path
        env.pop("AFK_PYTHON", None)
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


def test_an_untracked_file_is_never_a_candidate_but_a_committed_add_is(repo):
    _git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    _git(repo, "commit", "-qm", "add the artifact")
    (repo / "lib" / "leftoverscratch.py").write_text("y = 2\n", encoding="utf-8")
    result = _gate(repo)
    assert result.returncode == 2, result.stderr
    assert ARTIFACT in result.stderr and "leftoverscratch" not in result.stderr


def test_a_checkout_with_only_untracked_files_passes(repo):
    _git(repo, "rm", "-q", "--cached", ARTIFACT)
    result = _gate(repo)
    assert result.returncode == 0, result.stderr
    assert ARTIFACT not in result.stderr


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
    assert "verdict unknown (lock_busy) — no orphan check this run." in result.stderr
    assert '"result":"unknown"' in _metrics(repo) and '"detail":"lock_busy"' in _metrics(repo)
    assert not (repo / ".git" / "afk" / "gate-cache" / "wiring").exists()
    assert "orphan" not in result.stderr.lower().replace("no orphan check", "")


def test_no_python_is_unknown(repo):
    bash_root = Path(BASH).resolve().parent.parent
    dirs = [d for d in (bash_root / "usr" / "bin", bash_root / "bin", bash_root / "mingw64" / "bin",
                        bash_root / "cmd") if d.is_dir()]
    path = os.pathsep.join(str(d) for d in dirs)
    if shutil.which("afk-python", path=path):
        pytest.skip("the shell's own toolchain carries afk-python")
    result = _gate(repo, path=path)
    assert result.returncode == 3, result.stderr
    assert "verdict unknown (no_python)" in result.stderr


def test_metrics_report_counts_unknown_apart_from_red(tmp_path):
    log = tmp_path / "m.jsonl"
    log.write_text('{"gate":"wiring","result":"pass","duration_ms":10}\n'
                   '{"gate":"wiring","result":"unknown","duration_ms":20}\n'
                   '{"gate":"wiring","result":"blocked","duration_ms":30}\n', encoding="utf-8")
    done = subprocess.run([str(BASH), str(ROOT / "hooks" / "gate-metrics-report.sh"), str(log)],
                          capture_output=True, encoding="utf-8", errors="replace", timeout=60)
    assert "runs=3" in done.stdout and "red=1" in done.stdout and "unknown=1" in done.stdout


def _list(repo, mode):
    done = subprocess.run([str(BASH), str(ROOT / "hooks" / "wiring-gate.sh"), mode], cwd=repo,
                          capture_output=True, encoding="utf-8", timeout=120)
    assert done.returncode == 0, done.stderr
    return done.stdout.split()


@pytest.mark.parametrize("committed", [False, True], ids=["staged", "committed"])
def test_the_changed_list_names_deletions_and_both_names_of_a_rename(repo, committed):
    (repo / "docs" / "old.md").write_text("a provider the loader resolves\n", encoding="utf-8")
    _git(repo, "add", "docs/old.md")
    _git(repo, "commit", "-qm", "provider", "--", "docs/old.md")
    _git(repo, "remote", "add", "origin", repo.as_posix())
    _git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    _git(repo, "rm", "-q", "docs/notes.md")
    _git(repo, "mv", "docs/old.md", "docs/new.md")
    if committed:
        _git(repo, "commit", "-qm", "delete and rename")
    assert sorted(_list(repo, "--list-changed")) == ["docs/new.md", "docs/notes.md", "docs/old.md", ARTIFACT]
    assert sorted(_list(repo, "--list-candidates")) == ["docs/new.md", ARTIFACT]


def test_the_lists_use_the_integration_base_even_when_the_upstream_is_head(repo):
    _git(repo, "remote", "add", "origin", repo.as_posix())
    _git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    (repo / "docs" / "notes.md").write_text("changed\n", encoding="utf-8")
    _git(repo, "commit", "-qam", "add the artifact")
    _git(repo, "update-ref", "refs/remotes/origin/feature", "HEAD")
    _git(repo, "branch", "-q", "--set-upstream-to=origin/feature")
    assert _git(repo, "rev-parse", "@{u}").strip() == _git(repo, "rev-parse", "HEAD").strip()
    (repo / "lib" / "leftoverscratch.py").write_text("y = 2\n", encoding="utf-8")
    assert _list(repo, "--list-candidates") == [ARTIFACT]
    assert _list(repo, "--list-changed") == ["docs/notes.md", ARTIFACT]
    result = _gate(repo)
    assert result.returncode == 2 and ARTIFACT in result.stderr, result.stderr
