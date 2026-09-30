"""`create-worktree --name`: the one creation path an agent's move goes through.

Disposable repositories only; the plugin's own checkout is never touched.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = PLUGIN_ROOT / "scripts" / "create-worktree"


def _bash():
    spec = importlib.util.spec_from_file_location("afk_run_hook", PLUGIN_ROOT / "hooks" / "run-hook.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.find_bash()


BASH = _bash()
pytestmark = pytest.mark.skipif(BASH is None, reason="no POSIX shell on this machine")


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True,
                          text=True).stdout.strip()


def make_repo(tmp_path: Path, config: str = "", files: dict[str, str] | None = None) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "dev")
    git(repo, "config", "user.name", "Test User")
    git(repo, "config", "user.email", "t@example.com")
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    if config:
        (repo / ".afk").mkdir()
        (repo / ".afk" / "config.yaml").write_text("schema: 1\n" + config, encoding="utf-8")
    for name, body in (files or {}).items():
        target = repo / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "seed")
    return repo


def create(repo: Path, *args: str, session: str = "s1", cwd: Path | None = None):
    environ = dict(os.environ, AFK_PLUGIN_ROOT=str(PLUGIN_ROOT), AFK_PROVIDER="claude")
    environ.pop("CLAUDE_PROJECT_DIR", None)
    return subprocess.run(
        [str(BASH), str(SCRIPT), "--repo", repo.as_posix(), "--session", session, *args],
        capture_output=True, text=True, cwd=cwd or repo, env=environ, timeout=600)


def path_of(done) -> Path:
    line = done.stdout.strip().splitlines()[-1]
    assert line.startswith("WORKTREE_PATH="), done.stdout + done.stderr
    return Path(line.removeprefix("WORKTREE_PATH="))


def test_a_name_makes_a_worktree_inside_the_repository_on_its_own_branch(tmp_path):
    repo = make_repo(tmp_path)
    done = create(repo, "--name", "fix-login")
    assert done.returncode == 0, done.stderr
    assert len(done.stdout.strip().splitlines()) == 1     # A7: stdout is the contract line only
    wt = path_of(done)
    assert wt.samefile(repo / ".claude" / "worktrees" / "fix-login")
    assert git(wt, "rev-parse", "--abbrev-ref", "HEAD") == "worktree-fix-login"


def test_the_folder_stays_out_of_the_main_checkouts_status(tmp_path):
    repo = make_repo(tmp_path)
    (repo / ".claude").mkdir()
    (repo / ".claude" / "settings.local.json").write_text("{}", encoding="utf-8")
    create(repo, "--name", "one")
    create(repo, "--name", "two")
    status = git(repo, "status", "--porcelain")
    assert "worktrees" not in status
    exclude = (repo / ".git" / "info" / "exclude").read_text(encoding="utf-8")
    assert exclude.count("/.claude/worktrees/") == 1


def test_an_owner_record_names_harness_session_and_branch(tmp_path):
    repo = make_repo(tmp_path)
    create(repo, "--name", "rec", session="sess-9")
    record = json.loads((repo / ".git" / "afk-worktrees" / "rec.json").read_text(encoding="utf-8"))
    assert (record["harness"], record["session"], record["branch"]) == ("claude", "sess-9", "worktree-rec")
    assert set(record["owner"]) == {"pid", "ctime"}   # None when no harness ancestor is alive: kept, never pruned
    assert record["created"]


def test_a_taken_name_is_refused_and_nothing_else_changes(tmp_path):
    repo = make_repo(tmp_path)
    assert create(repo, "--name", "dup").returncode == 0
    again = create(repo, "--name", "dup")
    assert again.returncode != 0 and "already taken" in again.stderr
    assert len(git(repo, "worktree", "list").splitlines()) == 2


@pytest.mark.parametrize("bad", ["../x", "a b", ".hidden", "x.lock", "a..b", "-lead", "n" * 65, "end.", "/x", "/"])
def test_a_bad_name_is_rejected_before_any_filesystem_or_git_change(tmp_path, bad):
    repo = make_repo(tmp_path)
    done = create(repo, "--name", bad)
    assert done.returncode != 0 and "not allowed" in done.stderr
    assert "Example" in done.stderr
    assert not (repo / ".claude" / "worktrees").exists()
    assert not (repo / ".git" / "afk-worktrees").exists()
    assert len(git(repo, "worktree", "list").splitlines()) == 1


TEMPLATE = "git:\n  branch-pattern: '^team/[a-z0-9-]+/[a-z0-9-]+$'\n  branch-template: 'team/{user}/{name}'\n"


def test_the_branch_template_is_filled_with_name_and_user(tmp_path):
    repo = make_repo(tmp_path, TEMPLATE)
    wt = path_of(create(repo, "--name", "feat"))
    assert git(wt, "rev-parse", "--abbrev-ref", "HEAD") == "team/test-user/feat"


TICKET = ("git:\n  branch-pattern: '^team/[a-z0-9-]+/proj-[0-9]+$'\n"
          "  branch-template: 'team/{user}/{ticket_lower}'\n")


def test_r2_3_an_unresolvable_placeholder_is_filled_with_the_name(tmp_path):
    repo = make_repo(tmp_path, TICKET)
    wt = path_of(create(repo, "--name", "proj-123"))
    assert git(wt, "rev-parse", "--abbrev-ref", "HEAD") == "team/test-user/proj-123"


def test_r2_3_a_name_that_cannot_match_is_refused_with_pattern_template_and_the_rule(tmp_path):
    repo = make_repo(tmp_path, TICKET)
    done = create(repo, "--name", "feat")
    assert done.returncode != 0
    assert "^team/[a-z0-9-]+/proj-[0-9]+$" in done.stderr and "team/{user}/{ticket_lower}" in done.stderr
    assert "must make the expanded template match" in done.stderr
    assert not (repo / ".claude" / "worktrees" / "feat").exists()


def test_r2_5_a_slash_separated_name_becomes_one_folder_name(tmp_path):
    repo = make_repo(tmp_path)
    wt = path_of(create(repo, "--name", "fix/login"))
    assert wt.samefile(repo / ".claude" / "worktrees" / "fix-login")


def test_a_template_without_name_never_reuses_one_branch(tmp_path):
    fixed = "git:\n  branch-template: 'team/fixed'\n"
    repo = make_repo(tmp_path, fixed)
    assert git(path_of(create(repo, "--name", "a")), "rev-parse", "--abbrev-ref", "HEAD") == "worktree-a"


def test_simultaneous_starts_end_in_different_worktrees_on_different_branches(tmp_path):
    """AC-018."""
    repo = make_repo(tmp_path)
    with ThreadPoolExecutor(4) as pool:
        done = list(pool.map(lambda n: create(repo, "--name", f"p{n}", session=f"s{n}"), range(4)))
    assert [d.returncode for d in done] == [0, 0, 0, 0], [d.stderr for d in done]
    paths = {str(path_of(d)) for d in done}
    assert len(paths) == 4
    branches = git(repo, "branch", "--format=%(refname:short)").split()
    assert {f"worktree-p{n}" for n in range(4)} <= set(branches)
    exclude = (repo / ".git" / "info" / "exclude").read_text(encoding="utf-8")
    assert exclude.count("/.claude/worktrees/") == 1


def test_the_same_name_started_twice_at_once_makes_exactly_one(tmp_path):
    repo = make_repo(tmp_path)
    with ThreadPoolExecutor(2) as pool:
        done = list(pool.map(lambda n: create(repo, "--name", "same", session=f"s{n}"), range(2)))
    assert sorted(d.returncode == 0 for d in done) == [False, True]
    assert len(git(repo, "worktree", "list").splitlines()) == 2


def test_the_copy_walk_never_enters_sibling_worktrees(tmp_path):
    """A pre-existing sibling under a copied directory is not cloned into the next one."""
    repo = make_repo(tmp_path, files={".gitignore": ".claude/settings.local.json\n"})
    (repo / ".claude").mkdir(exist_ok=True)
    (repo / ".claude" / "settings.local.json").write_text("{}", encoding="utf-8")
    first = path_of(create(repo, "--name", "first"))
    (first / "big.marker").write_text("x" * 1000, encoding="utf-8")
    second = path_of(create(repo, "--name", "second"))
    assert (second / ".claude" / "settings.local.json").exists()
    assert not (second / ".claude" / "worktrees").exists()


def test_the_repository_copy_list_is_carried_over(tmp_path):
    """AC-016."""
    repo = make_repo(tmp_path, "worktree:\n  copy:\n    - notes.local\n",
                     files={".gitignore": "notes.local\n"})
    (repo / "notes.local").write_text("mine", encoding="utf-8")
    wt = path_of(create(repo, "--name", "cp"))
    assert (wt / "notes.local").read_text(encoding="utf-8") == "mine"


HOOKS = [
    {"event": "WorktreeCreated", "matcher": "*", "timeout": 30, "script": "setup/one.sh"},
    {"event": "WorktreeCreated", "matcher": "*", "timeout": 30, "script": "setup/fails.sh"},
    {"event": "WorktreeCreated", "matcher": "*", "timeout": 30, "script": "../outside.sh"},
    {"event": "WorktreeCreated", "matcher": "*", "timeout": 30, "script": "setup/two.sh"},
]
RECORD = 'printf "%s|%s|%s\\n" "$1" "$AFK_WORKTREE_BRANCH" "$(cat | tr -d "\\n " | head -c 200)" >> "$PWD/created.log"\n'


def hooked_repo(tmp_path: Path) -> Path:
    files = {
        ".afk/hooks.json": json.dumps(HOOKS),
        "setup/one.sh": "set -- one\n" + RECORD,
        "setup/two.sh": "set -- two\n" + RECORD,
        "setup/fails.sh": "echo boom >&2\nexit 3\n",
    }
    return make_repo(tmp_path, files=files)


def test_registered_scripts_run_in_order_and_receive_the_worktree_and_branch(tmp_path):
    """AC-020."""
    repo = hooked_repo(tmp_path)
    done = create(repo, "--name", "hooked")
    wt = path_of(done)
    lines = (wt / "created.log").read_text(encoding="utf-8").splitlines()
    assert [line.split("|")[0] for line in lines] == ["one", "two"]
    assert lines[0].split("|")[1] == "worktree-hooked"
    assert "hooked" in lines[0].split("|")[2]


def test_a_failing_script_warns_by_name_and_keeps_the_worktree(tmp_path):
    """AC-021."""
    repo = hooked_repo(tmp_path)
    done = create(repo, "--name", "warned")
    assert done.returncode == 0 and path_of(done).is_dir()
    assert "setup/fails.sh" in done.stderr


def test_a_script_outside_the_repository_is_not_run_and_is_named(tmp_path):
    """AC-022."""
    repo = hooked_repo(tmp_path)
    (tmp_path / "outside.sh").write_text('echo ran > "$PWD/outside.ran"\n', encoding="utf-8")
    done = create(repo, "--name", "guarded")
    assert "../outside.sh" in done.stderr
    assert not (path_of(done) / "outside.ran").exists()
    assert not (tmp_path / "outside.ran").exists()


def test_a_repository_without_a_manifest_runs_nothing_and_says_nothing(tmp_path):
    repo = make_repo(tmp_path)
    done = create(repo, "--name", "plain")
    assert done.returncode == 0 and "run-hook.py" not in done.stderr


HANDLER = PLUGIN_ROOT / "hooks" / "worktree-create.sh"


def handler(repo: Path, envelope: dict):
    environ = dict(os.environ, AFK_PLUGIN_ROOT=str(PLUGIN_ROOT), AFK_PROVIDER="claude")
    return subprocess.run([str(BASH), str(HANDLER)], input=json.dumps(envelope), text=True,
                          capture_output=True, cwd=repo, env=environ, timeout=600)


def test_the_creation_hook_prints_exactly_one_line_the_bare_path(tmp_path):
    repo = make_repo(tmp_path)
    done = handler(repo, {"session_id": "s7", "cwd": str(repo), "hook_event_name": "WorktreeCreate", "name": "h1"})
    assert done.returncode == 0, done.stderr
    lines = done.stdout.splitlines()
    assert len(lines) == 1 and not lines[0].startswith("WORKTREE_PATH=")
    assert Path(lines[0]).samefile(repo / ".claude" / "worktrees" / "h1")
    assert (repo / ".git" / "afk-worktrees" / "h1.json").is_file()


def test_the_creation_hook_fails_with_no_stdout_on_a_rejected_name(tmp_path):
    repo = make_repo(tmp_path)
    done = handler(repo, {"cwd": str(repo), "name": "../escape"})
    assert done.returncode != 0 and done.stdout.strip() == "" and "not allowed" in done.stderr


def add_linked(repo: Path, name: str, branch: str) -> Path:
    linked = repo.parent / name
    git(repo, "worktree", "add", "-q", "-b", branch, str(linked))
    (linked / "work.txt").write_text("parent work\n", encoding="utf-8")
    git(linked, "add", "-A")
    git(linked, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "parent-work")
    return linked


def test_r2_2_the_base_is_the_session_checkouts_head_not_the_main_checkouts(tmp_path):
    repo = make_repo(tmp_path)
    parent = add_linked(repo, "parent", "topic")
    wt = path_of(create(repo, "--name", "child", cwd=parent))
    assert git(wt, "rev-parse", "HEAD") == git(parent, "rev-parse", "HEAD")
    assert git(wt, "rev-parse", "HEAD") != git(repo, "rev-parse", "HEAD")
    assert (wt / "work.txt").is_file()


def test_r2_2_a_session_in_the_main_checkout_branches_from_its_head(tmp_path):
    repo = make_repo(tmp_path)
    wt = path_of(create(repo, "--name", "plain"))
    assert git(wt, "rev-parse", "HEAD") == git(repo, "rev-parse", "HEAD")


def test_r2_4_a_repository_with_no_commit_gets_an_orphan_worktree(tmp_path):
    repo = tmp_path / "fresh"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "dev")
    done = create(repo, "--name", "first")
    version = tuple(int(n) for n in git(repo, "--version").split()[-1].split(".")[:2] if n.isdigit())
    if version < (2, 42):
        assert done.returncode != 0 and "AFK_ALLOW_PROTECTED=1" in done.stderr
        return
    assert done.returncode == 0, done.stderr
    wt = path_of(done)
    assert git(wt, "symbolic-ref", "--short", "HEAD") == "worktree-first"
    git(wt, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "first commit")


def owner_module():
    spec = importlib.util.spec_from_file_location("owner_under_test", PLUGIN_ROOT / "scripts" / "worktree_owner.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_r2_6_a_lock_held_by_a_dead_process_is_broken(tmp_path):
    repo = make_repo(tmp_path)
    lock = repo / ".git" / "afk-worktrees" / ".lock"
    lock.mkdir(parents=True)
    (lock / "holder").write_text("2147483000:1", encoding="utf-8")
    done = create(repo, "--name", "after-crash")
    assert done.returncode == 0, done.stderr
    assert not lock.exists()


def test_r2_6_a_lock_held_by_a_live_process_is_kept_and_only_its_holder_releases_it(tmp_path):
    import time
    owner = owner_module()
    repo = make_repo(tmp_path)
    lock = repo / ".git" / "afk-worktrees" / ".lock"
    lock.mkdir(parents=True)
    (lock / "holder").write_text(f"{os.getpid()}:{owner.creation_time(os.getpid())}", encoding="utf-8")
    environ = dict(os.environ, AFK_PLUGIN_ROOT=str(PLUGIN_ROOT), AFK_PROVIDER="claude")
    waiting = subprocess.Popen([str(BASH), str(SCRIPT), "--repo", repo.as_posix(), "--name", "waits"],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=repo, env=environ)
    time.sleep(6)
    assert waiting.poll() is None, "a live holder's lock must not be broken"
    assert not (repo / ".claude" / "worktrees" / "waits").exists()
    (lock / "holder").unlink()
    lock.rmdir()
    out, err = waiting.communicate(timeout=300)
    assert waiting.returncode == 0, err
    assert not lock.exists()


def test_r2_1_the_registered_creation_hook_records_the_launching_process_as_owner(tmp_path):
    """The command a harness runs: the test's python process stands in for the harness."""
    import shlex
    repo = make_repo(tmp_path)
    manifest = json.loads((PLUGIN_ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    command = manifest["hooks"]["WorktreeCreate"][0]["hooks"][0]["command"]
    argv = shlex.split(command.replace("${CLAUDE_PLUGIN_ROOT}", str(PLUGIN_ROOT).replace("\\", "/")))
    argv[0] = __import__("sys").executable
    environ = dict(os.environ, AFK_PROVIDER="claude", AFK_OWNER_PROCESS="python,python3")
    environ.pop("AFK_WORKTREE_OWNER", None)
    done = subprocess.run(argv, input=json.dumps({"session_id": "s1", "cwd": str(repo), "name": "own"}),
                          text=True, capture_output=True, cwd=repo, env=environ, timeout=600)
    assert done.returncode == 0, done.stderr
    record = json.loads((repo / ".git" / "afk-worktrees" / "own.json").read_text(encoding="utf-8"))
    assert record["owner"]["pid"] == os.getpid() and record["owner"]["ctime"]


def test_r2_8_a_session_outside_any_repository_gets_a_move_that_can_work(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    done = handler(plain, {"cwd": str(plain), "name": "nowhere"})
    assert done.returncode != 0 and done.stdout.strip() == ""
    assert "inside the repository" in done.stderr and "path form" in done.stderr


def test_p1_a_claude_session_gets_the_claude_folder(tmp_path):
    repo = make_repo(tmp_path)
    environ = {k: v for k, v in os.environ.items() if not k.startswith(("AFK_", "CODEX", "PLUGIN_ROOT"))}
    environ.update(AFK_PLUGIN_ROOT=str(PLUGIN_ROOT), CLAUDECODE="1", CLAUDE_PLUGIN_ROOT=str(PLUGIN_ROOT))
    done = subprocess.run([str(BASH), str(SCRIPT), "--repo", repo.as_posix(), "--session", "p1", "--name", "p1x"],
                          capture_output=True, text=True, cwd=repo, env=environ, timeout=600)
    assert done.returncode == 0, done.stderr
    assert (repo / ".claude" / "worktrees" / "p1x").is_dir() and not (repo / ".codex").exists()


def test_q1_an_explicit_branch_refusal_names_the_template(tmp_path):
    repo = make_repo(tmp_path, "git:\n  branch-pattern: '^feat/[a-z0-9-]+$'\n  branch-template: 'feat/{name}'\n")
    done = create(repo, "--branch", "Bad_Name", "--dir", "bad")
    assert done.returncode != 0 and "^feat/[a-z0-9-]+$" in done.stderr and "feat/{name}" in done.stderr
