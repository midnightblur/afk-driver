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


def create(repo: Path, *args: str, session: str = "s1"):
    environ = dict(os.environ, AFK_PLUGIN_ROOT=str(PLUGIN_ROOT), AFK_PROVIDER="claude")
    environ.pop("CLAUDE_PROJECT_DIR", None)
    return subprocess.run(
        [str(BASH), str(SCRIPT), "--repo", repo.as_posix(), "--session", session, *args],
        capture_output=True, text=True, cwd=repo, env=environ, timeout=600)


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


@pytest.mark.parametrize("bad", ["../x", "a b", ".hidden", "x.lock", "a..b", "-lead", "n" * 65, "x/y", "end."])
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


def test_a_template_with_other_placeholders_falls_back_and_a_pattern_miss_is_rejected(tmp_path):
    other = "git:\n  branch-pattern: '^team/'\n  branch-template: 'team/{ticket}/{name}'\n"
    repo = make_repo(tmp_path, other)
    done = create(repo, "--name", "feat")
    assert done.returncode != 0
    assert "^team/" in done.stderr and "worktree-<name>" in done.stderr
    assert not (repo / ".claude" / "worktrees" / "feat").exists()


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
