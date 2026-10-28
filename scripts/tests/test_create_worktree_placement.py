"""`create-worktree` asks placement where a worktree goes, in every mode, before anything is made.

Real worktrees in temporary repositories under a temporary home; the plugin's own checkout
and the developer's `~/.afk` are never touched.
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
SCRIPT = PLUGIN_ROOT / "scripts" / "create-worktree"
SCRUB = ("AFK_", "CLAUDE", "CODEX", "PLUGIN_ROOT", "GIT_", "HERDR")


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


BASH = _load("afk_run_hook_for_placement_tests", PLUGIN_ROOT / "hooks" / "run-hook.py").find_bash()
rl = _load("afk_repo_list_for_creator_tests", PLUGIN_ROOT / "scripts" / "repo_list.py")
pytestmark = pytest.mark.skipif(BASH is None, reason="no POSIX shell on this machine")


def git(cwd: Path, *args: str, check: bool = True) -> str:
    return subprocess.run(["git", "-C", str(cwd), "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
                          check=check, capture_output=True, text=True).stdout.strip()


def make_repo(parent: Path, name: str = "proj") -> Path:
    repo = parent / name
    repo.mkdir(parents=True)
    git(repo, "init", "-q", "-b", "dev")
    git(repo, "commit", "-q", "--allow-empty", "-m", "seed")
    return repo


def same(a, b) -> bool:
    return os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))


@pytest.fixture
def home(tmp_path, monkeypatch):
    folder = tmp_path / "home"
    (folder / ".afk").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(folder))
    monkeypatch.setenv("USERPROFILE", str(folder))
    return folder


def set_root(home: Path, value, key: str = "worktreeRoot") -> None:
    text = value.as_posix() if isinstance(value, Path) else value
    (home / ".afk" / "config.yaml").write_text(f"developer:\n  {key}: '{text}'\n", encoding="utf-8")


@pytest.fixture
def root(tmp_path, home):
    folder = tmp_path / "root"
    folder.mkdir()
    set_root(home, folder)
    return folder


@pytest.fixture
def listed(tmp_path, root):
    repo = make_repo(tmp_path / "src")
    rl.add_repository(repo, root)
    return repo


def env_for(home: Path, agent: bool) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith(SCRUB)}
    env.update(HOME=str(home), USERPROFILE=str(home), AFK_PLUGIN_ROOT=str(PLUGIN_ROOT),
               AFK_PYTHON=sys.executable)
    if agent:
        env["AFK_PROVIDER"] = "claude"
    return env


def create(repo: Path, home: Path, *args: str, agent: bool = True, cwd: Path | None = None):
    return subprocess.run([str(BASH), str(SCRIPT), "--repo", repo.as_posix(), *args],
                          capture_output=True, text=True, cwd=cwd or repo, env=env_for(home, agent),
                          timeout=600)


def path_of(done) -> Path:
    lines = done.stdout.strip().splitlines()
    assert done.returncode == 0 and lines and lines[-1].startswith("WORKTREE_PATH="), done.stdout + done.stderr
    return Path(lines[-1].removeprefix("WORKTREE_PATH="))


def error_of(done, code: int) -> str:
    assert done.returncode == code, done.stdout + done.stderr
    assert "unexpected failure" not in done.stderr, done.stderr
    errors = [line for line in done.stderr.splitlines() if line.startswith("ERROR=")]
    assert len(errors) == 1 and done.stderr.rstrip().splitlines()[-1] == errors[0], done.stderr
    return errors[0].removeprefix("ERROR=")


def worktree_count(repo: Path) -> int:
    return git(repo, "worktree", "list", "--porcelain").count("worktree ")


def assert_nothing_made(repo: Path, branch: str, *folders: Path) -> None:
    assert worktree_count(repo) == 1
    assert git(repo, "branch", "--list", branch) == ""
    for folder in folders:
        assert not folder.exists(), folder
    owners = Path(git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir")) / "afk-worktrees"
    assert not owners.exists() or not any(owners.glob("*.json")), list(owners.iterdir())


# --- a listed repository lands under <root>/<short name> ------------------------------

def test_a_name_for_a_listed_repository_lands_under_the_root(listed, root, home):
    done = create(listed, home, "--name", "fix-login", "--session", "s1")
    path = path_of(done)
    assert same(path, root / "proj" / "fix-login")
    assert done.stdout.strip().splitlines()[-1] == f"WORKTREE_PATH={path.as_posix()}"
    assert same(git(path, "rev-parse", "--show-toplevel"), path)
    exclude = Path(git(listed, "rev-parse", "--path-format=absolute", "--git-common-dir")) / "info" / "exclude"
    assert "/.claude/worktrees/" not in (exclude.read_text(encoding="utf-8") if exclude.exists() else "")
    record = Path(git(listed, "rev-parse", "--path-format=absolute", "--git-common-dir")) / "afk-worktrees" / "fix-login.json"
    assert same(json.loads(record.read_text(encoding="utf-8"))["path"], path)


def test_a_branch_and_dir_for_a_listed_repository_lands_under_the_root(listed, root, home):
    path = path_of(create(listed, home, "--branch", "feat/a", "--dir", "a", "--base", "dev", "--no-open"))
    assert same(path, root / "proj" / "a")
    assert git(path, "rev-parse", "--abbrev-ref", "HEAD") == "feat/a"


def test_a_passing_old_base_value_is_the_root_while_none_is_confirmed(tmp_path, home):
    base = tmp_path / "old-base"
    base.mkdir()
    set_root(home, base, key="worktreeBasePath")
    repo = make_repo(tmp_path / "src")
    rl.add_repository(repo, base)
    assert same(path_of(create(repo, home, "--name", "n1")), base / "proj" / "n1")


def test_a_space_in_the_root_still_places_the_worktree(tmp_path, home):
    spaced = tmp_path / "my root"
    spaced.mkdir()
    set_root(home, spaced)
    repo = make_repo(tmp_path / "src dir")
    rl.add_repository(repo, spaced)
    path = path_of(create(repo, home, "--name", "spaced"))
    assert same(path, spaced / "proj" / "spaced") and (path / ".git").exists()


# --- an unlisted repository keeps today's folders ----------------------------------------

def test_a_name_for_an_unlisted_repository_lands_inside_the_main_checkout(tmp_path, root, home):
    repo = make_repo(tmp_path / "src")
    path = path_of(create(repo, home, "--name", "plain"))
    assert same(path, repo / ".claude" / "worktrees" / "plain")


def test_a_branch_for_an_unlisted_repository_lands_beside_the_main_checkout(tmp_path, root, home):
    repo = make_repo(tmp_path / "src")
    path = path_of(create(repo, home, "--branch", "feat/b", "--dir", "b", "--base", "dev", "--no-open"))
    assert same(path, tmp_path / "src" / "proj-worktrees" / "b")


def test_an_unlisted_repository_is_not_checked_against_a_broken_root(tmp_path, home):
    set_root(home, "relative/root")
    repo = make_repo(tmp_path / "src")
    assert same(path_of(create(repo, home, "--name", "free")), repo / ".claude" / "worktrees" / "free")


# --- a root or short name that fails a catalog R rule refuses with exit 3 -----------------

def _refusal_cases(tmp_path: Path, home: Path, repo: Path, root: Path):
    yield "R-01", lambda: set_root(home, "relative/root")
    yield "R-01", lambda: set_root(home, "~/trees")
    yield "R-02", lambda: set_root(home, repo / "inside")
    yield "R-03", lambda: set_root(home, tmp_path / "missing-root")


@pytest.mark.parametrize("case", range(4))
@pytest.mark.parametrize("mode", ["name", "branch"])
def test_a_root_that_fails_a_rule_refuses_with_exit_3_and_makes_nothing(tmp_path, listed, root, home, case, mode):
    rule, breaks = list(_refusal_cases(tmp_path, home, listed, root))[case]
    breaks()
    args = ("--name", "r1") if mode == "name" else ("--branch", "feat/r1", "--dir", "r1", "--base", "dev", "--no-open")
    reason = error_of(create(listed, home, *args), 3)
    assert reason.startswith(f"worktree root: {rule} ") and reason.endswith(" - run /afk:setup"), reason
    assert_nothing_made(listed, "worktree-r1" if mode == "name" else "feat/r1",
                        root / "proj" / "r1", listed / "inside", tmp_path / "missing-root")


def test_a_short_name_another_entry_holds_refuses_with_r05(tmp_path, root, home):
    first, second = make_repo(tmp_path / "a"), make_repo(tmp_path / "b")
    rl.add_repository(first, root)
    (home / ".afk" / "repositories.json").write_text(json.dumps({"schema": 1, "repositories": [
        {"path": rl.normalize(first), "shortName": "proj"},
        {"path": rl.normalize(second), "shortName": "proj"}]}), encoding="utf-8")
    reason = error_of(create(second, home, "--name", "clash"), 3)
    assert reason.startswith("worktree root: R-05 short name proj is also listed for "), reason
    assert_nothing_made(second, "worktree-clash", root / "proj" / "clash")


def test_a_short_name_folder_setup_did_not_make_refuses_with_r06(listed, root, home):
    (root / "proj" / rl.MARKER_NAME).unlink()
    (root / "proj" / "stranger.txt").write_text("x", encoding="utf-8")
    reason = error_of(create(listed, home, "--name", "foreign"), 3)
    assert reason.startswith("worktree root: R-06 ") and "was not made by setup" in reason, reason
    assert_nothing_made(listed, "worktree-foreign", root / "proj" / "foreign")


def test_an_existing_destination_exits_1_and_makes_nothing(listed, root, home):
    (root / "proj" / "taken").mkdir()
    reason = error_of(create(listed, home, "--name", "taken"), 1)
    assert "already exists" in reason
    assert_nothing_made(listed, "worktree-taken")


def test_a_missing_base_exits_1_before_the_parent_folder_is_made(tmp_path, home):
    repo = make_repo(tmp_path / "src")
    reason = error_of(create(repo, home, "--branch", "feat/nb", "--dir", "nb", "--base", "no-such", "--no-open"), 1)
    assert "base branch 'no-such' does not exist" in reason
    assert_nothing_made(repo, "feat/nb", tmp_path / "src" / "proj-worktrees")


def test_an_unreadable_machine_file_exits_1_for_a_listed_repository(listed, root, home):
    (home / ".afk" / "config.yaml").write_text("developer: text\n", encoding="utf-8")
    reason = error_of(create(listed, home, "--name", "broken"), 1)
    assert reason.startswith("placement: "), reason
    assert_nothing_made(listed, "worktree-broken", root / "proj" / "broken")


# --- --parent: an agent stays inside <root>/<short name>; a developer goes anywhere -------

def test_an_agent_parent_outside_the_folder_refuses_with_the_fixing_command(tmp_path, listed, root, home):
    outside = tmp_path / "elsewhere"
    reason = error_of(create(listed, home, "--branch", "feat/p", "--dir", "p", "--base", "dev",
                             "--parent", str(outside), "--no-open"), 3)
    folder = (root / "proj").as_posix()
    assert reason.startswith(f"parent {outside.as_posix()} is outside ")
    assert os.path.normcase(f"pass --parent {folder}") in os.path.normcase(reason), reason
    assert_nothing_made(listed, "feat/p", outside)


def test_an_agent_parent_inside_the_folder_is_used(listed, root, home):
    inner = root / "proj" / "group"
    path = path_of(create(listed, home, "--branch", "feat/q", "--dir", "q", "--base", "dev",
                          "--parent", str(inner), "--no-open"))
    assert same(path, inner / "q")


def test_an_agent_relative_parent_is_made_absolute_against_the_current_folder(tmp_path, listed, root, home):
    work = tmp_path / "cwd"
    work.mkdir()
    reason = error_of(create(listed, home, "--branch", "feat/rel", "--dir", "rel", "--base", "dev",
                             "--parent", "trees", "--no-open", cwd=work), 3)
    assert same(reason.split(" is outside ")[0].removeprefix("parent "), work / "trees"), reason
    assert_nothing_made(listed, "feat/rel", work / "trees", listed / "trees")


def test_an_agent_tilde_parent_is_made_absolute_first(listed, root, home):
    reason = error_of(create(listed, home, "--branch", "feat/t", "--dir", "t", "--base", "dev",
                             "--parent", "~/trees", "--no-open"), 3)
    assert same(reason.split(" is outside ")[0].removeprefix("parent "), home / "trees"), reason
    assert_nothing_made(listed, "feat/t", home / "trees", listed / "~")


def test_a_developer_parent_works_anywhere(tmp_path, listed, root, home):
    outside = tmp_path / "anywhere"
    path = path_of(create(listed, home, "--branch", "feat/d", "--dir", "d", "--base", "dev",
                          "--parent", str(outside), "--no-open", agent=False))
    assert same(path, outside / "d")


def test_a_developer_tilde_parent_lands_in_the_home_folder(listed, root, home):
    path = path_of(create(listed, home, "--branch", "feat/h", "--dir", "h", "--base", "dev",
                          "--parent", "~/trees", "--no-open", agent=False))
    assert same(path, home / "trees" / "h")


def test_a_developer_relative_parent_lands_beside_the_checkout_not_inside_it(tmp_path, listed, root, home):
    path = path_of(create(listed, home, "--branch", "feat/s", "--dir", "s", "--base", "dev",
                          "--parent", "../beside", "--no-open", agent=False))
    assert same(path, listed.parent / "beside" / "s")


@pytest.mark.parametrize("agent", [True, False])
def test_a_relative_parent_inside_the_main_checkout_refuses(tmp_path, home, agent):
    repo = make_repo(tmp_path / "src")
    reason = error_of(create(repo, home, "--branch", "feat/in", "--dir", "in", "--base", "dev",
                             "--parent", "wts", "--no-open", agent=agent), 3)
    assert reason.startswith(f"parent {(repo / 'wts').as_posix()} is inside the main checkout "), reason
    assert_nothing_made(repo, "feat/in", repo / "wts")


def test_an_absolute_parent_inside_another_repository_is_refused_before_creation(tmp_path, home):
    repo = make_repo(tmp_path / "src")
    foreign = make_repo(tmp_path / "foreign")
    parent = foreign / "not-created-yet" / "worktrees"
    reason = error_of(create(repo, home, "--branch", "feat/f", "--dir", "f", "--base", "dev",
                             "--parent", str(parent), "--no-open", agent=False), 1)
    assert "different Git repository" in reason
    assert_nothing_made(repo, "feat/f", parent)
