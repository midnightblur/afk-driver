"""`remove-worktree.py`, the removal and prune handlers, and their registration.

Disposable repositories only. A worktree counts as plugin-made when it has an owner record.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = PLUGIN_ROOT / "scripts" / "remove-worktree.py"
IDENTITY = ("-c", "user.name=t", "-c", "user.email=t@example.com")


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BASH = _load("afk_run_hook", PLUGIN_ROOT / "hooks" / "run-hook.py").find_bash()
OWNER = _load("afk_owner", PLUGIN_ROOT / "scripts" / "worktree_owner.py")


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(cwd), *IDENTITY, *args], check=True, capture_output=True,
                          text=True).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    path = tmp_path / "repo"
    path.mkdir()
    git(path, "init", "-q", "-b", "dev")
    git(path, "commit", "-q", "--allow-empty", "-m", "seed")
    return path


def made(repo: Path, name: str, owner: dict | None = None, record: bool = True) -> Path:
    """A linked worktree on branch `worktree-<name>` with an owner record."""
    path = repo / ".claude" / "worktrees" / name
    git(repo, "worktree", "add", "-q", "-b", f"worktree-{name}", str(path))
    if record:
        folder = repo / ".git" / "afk-worktrees"
        folder.mkdir(exist_ok=True)
        (folder / f"{name}.json").write_text(json.dumps({
            "name": name, "path": path.as_posix(), "branch": f"worktree-{name}", "harness": "claude",
            "owner": owner or {"pid": None, "ctime": None}}), encoding="utf-8")
    return path


def run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, cwd=cwd,
                          timeout=120)


def branches(repo: Path) -> list[str]:
    return git(repo, "branch", "--format=%(refname:short)").split()


def test_a_clean_plugin_worktree_is_removed_with_its_branch(repo):
    path = made(repo, "clean")
    done = run("--path", str(path))
    assert done.returncode == 0, done.stderr
    assert not path.exists() and "worktree-clean" not in branches(repo)
    assert not (repo / ".git" / "afk-worktrees" / "clean.json").exists()


def test_uncommitted_work_keeps_the_worktree_and_prints_resume_and_remove(repo):
    path = made(repo, "dirty")
    (path / "w.txt").write_text("x", encoding="utf-8")
    done = run("--path", str(path))
    assert path.is_dir() and "worktree-dirty" in branches(repo)
    assert "resume: cd" in done.stderr and "--force" in done.stderr and path.as_posix() in done.stderr


def test_an_unpushed_commit_keeps_the_worktree_and_its_branch(repo):
    path = made(repo, "ahead")
    git(path, "commit", "-q", "--allow-empty", "-m", "own work")
    done = run("--path", str(path))
    assert path.is_dir() and "worktree-ahead" in branches(repo) and "exist nowhere else" in done.stderr


def test_a_commit_that_another_branch_holds_is_not_unpushed(repo):
    path = made(repo, "shared")
    git(path, "commit", "-q", "--allow-empty", "-m", "kept elsewhere")
    git(repo, "branch", "elsewhere", "worktree-shared")
    run("--path", str(path))
    assert not path.exists() and "elsewhere" in branches(repo)
    assert git(repo, "log", "-1", "--format=%s", "elsewhere") == "kept elsewhere"


def test_a_worktree_with_no_record_is_never_touched(repo):
    path = made(repo, "foreign", record=False)
    run("--path", str(path))
    assert path.is_dir()


def test_force_removes_a_kept_worktree(repo):
    path = made(repo, "forced")
    (path / "w.txt").write_text("x", encoding="utf-8")
    run("--path", str(path), "--force")
    assert not path.exists()


def test_prune_removes_only_a_clean_worktree_whose_owner_is_dead(repo):
    dead = {"pid": 2147483000, "ctime": "1"}
    gone = made(repo, "gone", dead)
    busy = made(repo, "busy", dead)
    (busy / "w.txt").write_text("x", encoding="utf-8")
    live = made(repo, "live", {"pid": os.getpid(), "ctime": OWNER.creation_time(os.getpid())})
    unknown = made(repo, "unknown")
    lost = made(repo, "lost", dead)
    import shutil
    shutil.rmtree(lost)
    done = run("--prune", cwd=repo)
    assert done.returncode == 0, done.stderr
    assert not gone.exists()
    assert busy.is_dir() and live.is_dir() and unknown.is_dir()
    assert not (repo / ".git" / "afk-worktrees" / "lost.json").exists()


def test_the_removal_handler_takes_worktree_path_or_cwd(repo):
    if BASH is None:
        pytest.skip("no POSIX shell")
    handler = PLUGIN_ROOT / "hooks" / "worktree-remove.sh"
    by_path = made(repo, "by-path")
    by_cwd = made(repo, "by-cwd")
    for key, target in (("worktree_path", by_path), ("cwd", by_cwd)):
        done = subprocess.run([str(BASH), handler.as_posix()], input=json.dumps({key: str(target)}),
                              capture_output=True, text=True, timeout=120,
                              env=dict(os.environ, AFK_PLUGIN_ROOT=str(PLUGIN_ROOT)))
        assert done.returncode == 0 and not target.exists(), done.stderr


@pytest.mark.parametrize("manifest,var,event", [("hooks.json", "CLAUDE_PLUGIN_ROOT", "WorktreeRemove"),
                                                ("hooks.json", "CLAUDE_PLUGIN_ROOT", "SessionEnd"),
                                                ("hooks.codex.json", "PLUGIN_ROOT", "SessionEnd")])
def test_the_manifests_register_the_removal_and_the_prune(manifest, var, event):
    document = json.loads((PLUGIN_ROOT / "hooks" / manifest).read_text(encoding="utf-8"))["hooks"]
    commands = [h["command"] for g in document[event] for h in g["hooks"]]
    assert any("worktree-remove.sh" in c and var in c for c in commands)
    start = [h["command"] for g in document["SessionStart"] for h in g["hooks"]]
    assert any("worktree-prune.sh" in c for c in start)


def run_env(*args: str, cwd: Path | None = None, **env: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, cwd=cwd,
                          env=dict(os.environ, **env), timeout=120)


def test_r5_4_a_prune_run_from_inside_a_worktree_keeps_it_and_adopts_it(repo):
    path = made(repo, "resumed", owner={"pid": 999999, "ctime": "1"})
    me = f"{os.getpid()}:{OWNER.creation_time(os.getpid())}"
    done = run_env("--prune", cwd=path, AFK_WORKTREE_OWNER=me)
    assert done.returncode == 0 and path.is_dir() and "worktree-resumed" in branches(repo), done.stderr
    record = json.loads((repo / ".git" / "afk-worktrees" / "resumed.json").read_text(encoding="utf-8"))
    assert record["owner"]["pid"] == os.getpid()
    other = made(repo, "gone", owner={"pid": 999999, "ctime": "1"})
    run_env("--prune", cwd=path, AFK_WORKTREE_OWNER=me)
    assert not other.exists() and path.is_dir()


def test_r5_5_only_the_recorded_branch_is_deleted(repo):
    path = made(repo, "moved")
    git(repo, "branch", "human-feature")
    git(path, "switch", "-q", "human-feature")
    run("--path", str(path))
    assert not path.exists()
    assert "human-feature" in branches(repo) and "worktree-moved" not in branches(repo)


@pytest.mark.parametrize("flags", [(), ("--force",)])
def test_r5_5_a_recorded_branch_with_commits_of_its_own_survives(repo, flags):
    path = made(repo, "mine")
    git(path, "commit", "-q", "--allow-empty", "-m", "own work")
    git(repo, "branch", "safe", "worktree-mine")
    git(path, "switch", "-q", "--detach", "dev")
    git(repo, "branch", "-f", "safe", "dev")
    run("--path", str(path), *flags)
    assert "worktree-mine" in branches(repo)


def test_r5_9_a_removed_worktree_forgets_its_pane_marker(repo):
    path = made(repo, "paned")
    session = repo / ".git" / "afk-session"
    session.mkdir()
    marker = session / "w_p1.move"
    marker.write_text(json.dumps({"path": path.as_posix()}), encoding="utf-8")
    old = marker.stat().st_mtime - 3600
    os.utime(marker, (old, old))
    run("--path", str(path))
    assert not path.exists() and not marker.exists()


def test_r5_11_a_pending_move_target_is_not_removed_at_session_end(repo):
    path = made(repo, "target")
    session = repo / ".git" / "afk-session"
    session.mkdir()
    marker = session / "w_p2.move"
    marker.write_text(json.dumps({"path": path.as_posix()}), encoding="utf-8")
    run("--path", str(path))
    assert path.is_dir()
    old = marker.stat().st_mtime - 3600
    os.utime(marker, (old, old))
    run("--path", str(path))
    assert not path.exists()


def test_r5_12_a_kept_worktree_is_shown_once_in_the_next_session_context(repo):
    path = made(repo, "unseen")
    (path / "w.txt").write_text("x", encoding="utf-8")
    run("--path", str(path))
    first = run("--report-kept", cwd=repo)
    context = json.loads(first.stdout)["hookSpecificOutput"]
    assert context["hookEventName"] == "SessionStart"
    assert path.as_posix() in context["additionalContext"] and "uncommitted" in context["additionalContext"]
    assert run("--report-kept", cwd=repo).stdout.strip() == ""
    run("--path", str(path))  # kept again: not reported a second time
    assert run("--report-kept", cwd=repo).stdout.strip() == ""


def test_r5_12_the_prune_handler_prints_the_report_on_stdout(repo):
    path = made(repo, "handler")
    (path / "w.txt").write_text("x", encoding="utf-8")
    run("--path", str(path))
    env = dict(os.environ, AFK_PLUGIN_ROOT=str(PLUGIN_ROOT))
    done = subprocess.run([str(BASH), (PLUGIN_ROOT / "hooks" / "worktree-prune.sh").as_posix()], cwd=repo,
                          capture_output=True, text=True, env=env, timeout=120)
    assert json.loads(done.stdout)["hookSpecificOutput"]["hookEventName"] == "SessionStart", done.stderr


def test_r5_10_the_owner_walk_stops_at_a_parent_created_after_its_child(monkeypatch):
    table = {os.getpid(): (100, "python.exe"), 100: (0, "codex.exe")}
    born = {os.getpid(): "50", 100: "10"}
    monkeypatch.setattr(OWNER, "snapshot", lambda: table)
    monkeypatch.setattr(OWNER, "creation_time", lambda pid: born.get(pid))
    monkeypatch.delenv("AFK_OWNER_PROCESS", raising=False)
    assert OWNER.find_owner()["pid"] == 100
    born[100] = "90"
    assert OWNER.find_owner() is None


def test_r8_1_a_removal_run_from_inside_the_folder_leaves_it_for_the_next_prune(repo):
    path = made(repo, "held", {"pid": 2147483000, "ctime": "1"})
    done = run_env("--path", str(path), cwd=path, AFK_WORKTREE_OWNER=f"{os.getpid()}:{OWNER.creation_time(os.getpid())}")
    assert done.returncode == 0 and path.is_dir(), done.stderr
    assert "later session start" in done.stderr
    assert (repo / ".git" / "afk-worktrees" / "held.json").exists() and "worktree-held" in branches(repo)
    run("--prune", cwd=repo)
    assert not path.exists() and "worktree-held" not in branches(repo)


def test_r8_1_a_child_holding_the_folder_does_not_strand_a_leftover(repo):
    path = made(repo, "child", {"pid": 2147483000, "ctime": "1"})
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], cwd=path)
    try:
        run("--path", str(path))
    finally:
        child.kill()
        child.wait()
    run("--prune", cwd=repo)
    assert not path.exists() and "worktree-child" not in branches(repo)
    assert not (repo / ".git" / "afk-worktrees" / "child.json").exists()


def test_r8_1_an_empty_folder_git_no_longer_lists_is_cleared_with_its_record_and_branch(repo):
    path = made(repo, "ghost", {"pid": 2147483000, "ctime": "1"})
    git(repo, "worktree", "remove", "--force", str(path))
    path.mkdir(parents=True)
    done = run("--prune", cwd=repo)
    assert done.returncode == 0, done.stderr
    assert not path.exists() and "worktree-ghost" not in branches(repo)
    assert not (repo / ".git" / "afk-worktrees" / "ghost.json").exists()


def test_r8_1_a_folder_that_is_not_its_own_worktree_is_kept_not_judged_by_the_main_checkout(repo):
    path = made(repo, "plain", {"pid": 2147483000, "ctime": "1"})
    git(repo, "worktree", "remove", "--force", str(path))
    path.mkdir(parents=True)
    (path / "mine.txt").write_text("x", encoding="utf-8")
    run("--prune", cwd=repo)
    assert (path / "mine.txt").exists()
    assert "uncommitted" not in (repo / ".git" / "afk-session" / "kept.json").read_text() \
        if (repo / ".git" / "afk-session" / "kept.json").exists() else True


def _runtime_files(path: Path) -> None:
    for rel in (".claude/hooks/.gate-cache/stop", ".claude/metrics/gate-latency.jsonl"):
        (path / rel).parent.mkdir(parents=True, exist_ok=True)
        (path / rel).write_text("x", encoding="utf-8")


def test_p4_a_worktree_holding_only_the_plugins_runtime_files_is_removed(repo):
    path = made(repo, "runtime")
    _runtime_files(path)
    run("--path", str(path))
    assert not path.exists()


def test_p4_any_other_untracked_file_still_keeps_the_worktree(repo):
    path = made(repo, "mixed")
    _runtime_files(path)
    (path / ".claude" / "metrics" / "notes.md").write_text("mine", encoding="utf-8")
    (path / "extra.txt").write_text("mine", encoding="utf-8")
    done = run("--path", str(path))
    assert path.is_dir() and "uncommitted" in done.stderr


def test_p4_a_tracked_change_under_a_runtime_path_keeps_the_worktree(repo):
    path = made(repo, "tracked")
    target = path / ".claude" / "metrics" / "kept.txt"
    target.parent.mkdir(parents=True)
    target.write_text("x", encoding="utf-8")
    git(path, "add", "-f", ".claude/metrics/kept.txt")
    run("--path", str(path))
    assert path.is_dir()


def test_r9_4_a_forced_removal_from_inside_the_folder_says_to_run_it_from_outside(repo):
    path = made(repo, "forcein")
    (path / "w.txt").write_text("x", encoding="utf-8")
    done = run("--path", str(path), "--force", cwd=path)
    assert done.returncode != 0 and path.is_dir()
    assert "from outside the worktree" in done.stderr and "--force" in done.stderr
    assert "later session start" not in done.stderr
    assert run("--path", str(path), "--force", cwd=repo).returncode == 0 and not path.exists()


def harness() -> tuple[subprocess.Popen, str]:
    """A stand-in for the harness process a session-end waiter follows."""
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(600)"])
    return child, f"{child.pid}:{OWNER.creation_time(child.pid)}"


def spec_of(owner: str) -> dict:
    pid, _, ctime = owner.partition(":")
    return {"pid": int(pid), "ctime": ctime}


def until(check, seconds: float = 60) -> bool:
    end = time.time() + seconds
    while time.time() < end:
        if check():
            return True
        time.sleep(0.25)
    return check()


def test_p6_a_session_ending_inside_its_worktree_removes_it_once_the_harness_exits(repo):
    child, owner = harness()
    path = made(repo, "waited", owner=spec_of(owner))
    try:
        done = run_env("--path", str(path), cwd=path, AFK_WORKTREE_OWNER=owner, AFK_WAIT_POLL="0.2")
        assert done.returncode == 0 and "when the session exits" in done.stderr, done.stderr
        time.sleep(2)
        assert path.is_dir(), "the waiter must wait for the harness"
    finally:
        child.kill()
        child.wait()
    assert until(lambda: not path.exists() and "worktree-waited" not in branches(repo)),         "the waiter removes the worktree and its branch after the harness exits"


def test_p6_the_waiter_keeps_a_dirty_worktree_and_records_it(repo):
    child, owner = harness()
    path = made(repo, "waited-dirty", owner=spec_of(owner))
    (path / "w.txt").write_text("x", encoding="utf-8")
    try:
        run_env("--path", str(path), cwd=path, AFK_WORKTREE_OWNER=owner, AFK_WAIT_POLL="0.2")
    finally:
        child.kill()
        child.wait()
    kept = repo / ".git" / "afk-session" / "kept.json"
    assert until(lambda: kept.exists()), "a kept worktree is recorded for the next session start"
    assert path.is_dir() and "worktree-waited-dirty" in branches(repo)


def test_p6_a_session_end_without_an_owner_record_removes_nothing(repo):
    path = made(repo, "unowned", record=False)
    child, owner = harness()
    try:
        done = run_env("--path", str(path), cwd=path, AFK_WORKTREE_OWNER=owner, AFK_WAIT_POLL="0.2")
    finally:
        child.kill()
        child.wait()
    time.sleep(2)
    assert done.returncode == 0 and path.is_dir() and "worktree-unowned" in branches(repo)
    assert not list((repo / ".git").glob("afk-worktrees/*.wait"))


def waiter(path: Path, owner: str, **env: str) -> subprocess.CompletedProcess:
    """Run the waiter in the foreground against an owner that has already died."""
    return run_env("--after-exit", owner, "--path", str(path), cwd=path.parents[2], **env)


def dead_harness() -> str:
    child, owner = harness()
    child.kill()
    child.wait()
    return owner


def test_r11_1_a_worktree_another_live_session_shares_is_kept(repo):
    gone = dead_harness()
    child, alive = harness()
    try:
        path = made(repo, "shared")
        record = repo / ".git" / "afk-worktrees" / "shared.json"
        body = json.loads(record.read_text(encoding="utf-8"))
        body["owners"] = [spec_of(gone), spec_of(alive)]
        record.write_text(json.dumps(body), encoding="utf-8")
        waiter(path, gone)
        assert path.is_dir() and "worktree-shared" in branches(repo)
    finally:
        child.kill()
        child.wait()


def test_r11_1_adopt_appends_an_owner_and_keeps_the_earlier_ones(repo):
    first = dead_harness()
    path = made(repo, "joined", owner=spec_of(first))
    me = f"{os.getpid()}:{OWNER.creation_time(os.getpid())}"
    run_env("--prune", cwd=path, AFK_WORKTREE_OWNER=me)
    body = json.loads((repo / ".git" / "afk-worktrees" / "joined.json").read_text(encoding="utf-8"))
    assert [item["pid"] for item in OWNER.owners_of(body)] == [spec_of(first)["pid"], os.getpid()]


def test_r11_1_a_record_in_the_old_single_owner_shape_reads_as_one_owner():
    assert OWNER.owners_of({"owner": {"pid": 7, "ctime": "1"}}) == [{"pid": 7, "ctime": "1"}]
    assert OWNER.owners_of({}) == [] and not OWNER.all_dead({})


def load_remove():
    return _load("afk_remove", SCRIPT)


def test_r11_2_an_unknown_owner_state_keeps_the_worktree(repo, monkeypatch):
    gone = dead_harness()
    path = made(repo, "unsure", owner=spec_of(gone))
    module = load_remove()
    real = module.owner_module()
    stub = type("Stub", (), {"state": staticmethod(lambda pid, ctime: "unknown"),
                             "all_dead": staticmethod(lambda record: False), "owners_of": real.owners_of})
    monkeypatch.setattr(module, "owner_module", lambda: stub)
    monkeypatch.chdir(repo)
    module.after_exit(gone, path)
    assert path.is_dir() and "worktree-unsure" in branches(repo)


def test_r11_2_reaching_the_cap_keeps_the_worktree(repo, monkeypatch):
    child, alive = harness()
    try:
        path = made(repo, "capped", owner=spec_of(alive))
        module = load_remove()
        monkeypatch.setattr(module, "WAIT_CAP", 0)
        monkeypatch.chdir(repo)
        module.after_exit(alive, path)
        assert path.is_dir() and "worktree-capped" in branches(repo)
    finally:
        child.kill()
        child.wait()
