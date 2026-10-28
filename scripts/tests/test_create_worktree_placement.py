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


def create(repo: Path, home: Path, *args: str, agent: bool = True, cwd: Path | None = None, **extra: str):
    return subprocess.run([str(BASH), str(SCRIPT), "--repo", repo.as_posix(), *args],
                          capture_output=True, text=True, cwd=cwd or repo, env={**env_for(home, agent), **extra},
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


def test_an_agent_parent_under_a_broken_root_gives_one_clean_refusal_line(tmp_path, listed, root, home):
    set_root(home, "relative/root")
    reason = error_of(create(listed, home, "--branch", "feat/pr", "--dir", "pr", "--base", "dev",
                             "--parent", str(tmp_path / "anywhere"), "--no-open"), 3)
    assert reason.startswith("worktree root: R-01 ") and reason.endswith(" - run /afk:setup"), reason
    assert "\x1f" not in reason, reason
    assert_nothing_made(listed, "feat/pr", tmp_path / "anywhere")


def test_a_name_ignores_parent_and_lands_under_the_root(tmp_path, listed, root, home):
    outside = tmp_path / "elsewhere"
    path = path_of(create(listed, home, "--name", "np", "--parent", str(outside)))
    assert same(path, root / "proj" / "np")
    assert not outside.exists()


def test_an_agent_dir_that_climbs_out_of_the_folder_refuses_with_exit_3(listed, root, home):
    reason = error_of(create(listed, home, "--branch", "feat/up", "--dir", "../up", "--base", "dev", "--no-open",
                             agent=True), 3)
    assert reason.startswith("worktree folder: ") and " is outside " in reason, reason
    assert_nothing_made(listed, "feat/up", root / "up", root / "proj" / "up")


def test_a_file_at_the_destination_exits_1_and_makes_nothing(listed, root, home):
    (root / "proj" / "afile").write_text("x", encoding="utf-8")
    reason = error_of(create(listed, home, "--name", "afile"), 1)
    assert "already exists" in reason
    assert_nothing_made(listed, "worktree-afile")


def test_a_removed_short_name_folder_is_made_again_with_its_marker(listed, root, home):
    for item in (root / "proj").iterdir():
        item.unlink()
    (root / "proj").rmdir()
    first = path_of(create(listed, home, "--name", "again"))
    assert same(first, root / "proj" / "again")
    marker = json.loads((root / "proj" / rl.MARKER_NAME).read_text(encoding="utf-8"))
    assert same(marker["path"], listed)
    assert same(path_of(create(listed, home, "--name", "next")), root / "proj" / "next")


def test_a_developer_dir_that_climbs_out_of_the_folder_lands_where_it_points(listed, root, home):
    path = path_of(create(listed, home, "--branch", "feat/dv", "--dir", "../dv", "--base", "dev", "--no-open",
                          agent=False))
    assert same(path, root / "dv")


def test_an_agent_dir_whose_dots_stay_inside_the_folder_lands_there(listed, root, home):
    path = path_of(create(listed, home, "--branch", "feat/in", "--dir", "../proj/in", "--base", "dev", "--no-open"))
    assert same(path, root / "proj" / "in")


def test_an_empty_short_name_folder_with_no_marker_gets_its_marker(listed, root, home):
    (root / "proj" / rl.MARKER_NAME).unlink()
    assert same(path_of(create(listed, home, "--name", "first")), root / "proj" / "first")
    assert same(json.loads((root / "proj" / rl.MARKER_NAME).read_text(encoding="utf-8"))["path"], listed)
    assert same(path_of(create(listed, home, "--name", "second")), root / "proj" / "second")


def test_an_agent_parent_in_a_removed_short_name_folder_makes_it_with_its_marker(listed, root, home):
    (root / "proj" / rl.MARKER_NAME).unlink()
    (root / "proj").rmdir()
    path = path_of(create(listed, home, "--branch", "feat/pm", "--dir", "pm", "--base", "dev",
                          "--parent", str(root / "proj"), "--no-open"))
    assert same(path, root / "proj" / "pm")
    assert same(json.loads((root / "proj" / rl.MARKER_NAME).read_text(encoding="utf-8"))["path"], listed)
    assert same(path_of(create(listed, home, "--name", "after")), root / "proj" / "after")


def test_a_folder_claim_that_cannot_take_the_list_lock_exits_1_and_makes_nothing(listed, root, home):
    (root / "proj" / rl.MARKER_NAME).unlink()
    (root / "proj").rmdir()
    with rl.safe_write._file_lock(rl.list_file()):
        done = create(listed, home, "--name", "locked")
    reason = error_of(done, 1)
    assert reason.endswith("could not be made with its marker - run /afk:setup"), reason
    assert "Traceback" not in done.stderr, done.stderr
    assert_nothing_made(listed, "worktree-locked", root / "proj")


def test_a_developer_dir_that_climbs_out_prints_a_clean_path_and_makes_no_short_name_folder(listed, root, home):
    (root / "proj" / rl.MARKER_NAME).unlink()
    (root / "proj").rmdir()
    done = create(listed, home, "--branch", "feat/dc", "--dir", "../dc", "--base", "dev", "--no-open", agent=False)
    path = path_of(done)
    assert ".." not in path.as_posix() and same(path, root / "dc"), done.stdout
    assert not (root / "proj").exists()


def test_a_marked_short_name_folder_is_used_while_another_writer_holds_the_list_lock(listed, root, home):
    with rl.safe_write._file_lock(rl.list_file()):
        path = path_of(create(listed, home, "--name", "busy"))
    assert same(path, root / "proj" / "busy")


def test_an_agent_parent_through_a_linked_short_name_folder_keeps_its_marker(tmp_path, listed, root, home):
    real = tmp_path / "real-proj"
    (root / "proj").rename(real)
    try:
        os.symlink(real, root / "proj", target_is_directory=True)
    except OSError as error:
        pytest.skip(f"this machine cannot make a folder link: {error}")
    path = path_of(create(listed, home, "--branch", "feat/ln", "--dir", "ln", "--base", "dev",
                          "--parent", str(root / "proj"), "--no-open"))
    assert same(path, real / "ln")
    assert same(json.loads((real / rl.MARKER_NAME).read_text(encoding="utf-8"))["path"], listed)


def test_a_listed_name_ignores_a_harness_folder_that_leaves_the_repository(listed, root, home):
    path = path_of(create(listed, home, "--name", "hf", AFK_WORKTREE_FOLDER="../elsewhere"))
    assert same(path, root / "proj" / "hf")


def test_an_unlisted_name_with_a_harness_folder_that_leaves_the_repository_exits_1(tmp_path, home):
    loose = make_repo(tmp_path / "loose")
    reason = error_of(create(loose, home, "--name", "hf", AFK_WORKTREE_FOLDER="../elsewhere"), 1)
    assert reason == "the worktree folder '../elsewhere' must stay inside the repository", reason
    assert not (tmp_path / "elsewhere").exists()
