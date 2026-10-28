"""Placement: catalog R on the worktree root and short names, and the worktree folder, on real git repositories."""
from __future__ import annotations

import builtins
import importlib.util
import io
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "placement.py"
IS_WINDOWS = os.name == "nt"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pl = load(SCRIPT, "afk_placement_under_test")
rl = pl.repo_list


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True,
                          text=True).stdout.strip()


def make_repo(parent: Path, name: str = "proj") -> Path:
    repo = parent / name
    repo.mkdir(parents=True)
    git(repo, "init", "-q", "-b", "dev")
    git(repo, "config", "user.name", "Test User")
    git(repo, "config", "user.email", "t@example.com")
    (repo / "sub").mkdir()
    (repo / "sub" / "README.md").write_text("seed\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "seed")
    return repo


def machine(home: Path, text: str) -> Path:
    file = home / ".afk" / "config.yaml"
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(text, encoding="utf-8")
    return file


def set_root(home: Path, root: Path | str, key: str = "worktreeRoot") -> None:
    machine(home, f"developer:\n  {key}: '{root}'\n")


def write_list(home: Path, rows: list[tuple[Path | str, str]]) -> None:
    file = home / ".afk" / "repositories.json"
    file.parent.mkdir(parents=True, exist_ok=True)
    data = {"schema": 1, "repositories": [{"path": str(path), "shortName": name} for path, name in rows]}
    file.write_text(json.dumps(data), encoding="utf-8")


def link(target: Path, at: Path) -> None:
    try:
        os.symlink(target, at, target_is_directory=True)
    except OSError:
        if not IS_WINDOWS:
            pytest.skip("this machine refuses to create a symbolic link")
        import _winapi
        _winapi.CreateJunction(str(target), str(at))


def same(a: str | Path, b: str | Path) -> bool:
    return os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))


@pytest.fixture
def home(tmp_path, monkeypatch):
    folder = tmp_path / "home"
    folder.mkdir()
    monkeypatch.setenv("HOME", str(folder))
    monkeypatch.setenv("USERPROFILE", str(folder))
    for name in ("GIT_DIR", "GIT_COMMON_DIR", "GIT_WORK_TREE"):
        monkeypatch.delenv(name, raising=False)
    return folder


@pytest.fixture
def root(tmp_path, home):
    folder = tmp_path / "wt-root"
    folder.mkdir()
    set_root(home, folder)
    return folder


@pytest.fixture
def listed(root, tmp_path):
    repo = make_repo(tmp_path / "src")
    rl.add_repository(repo, root)
    return repo


@pytest.fixture
def git_calls(monkeypatch):
    calls: list[list[str]] = []
    real = subprocess.run

    def run(args, *rest, **options):
        calls.append(list(args))
        return real(args, *rest, **options)

    monkeypatch.setattr(pl.subprocess, "run", run)
    return calls


# --- the root and its state -------------------------------------------------

def test_a_confirmed_root_comes_from_the_machine_file(root):
    state = pl.root_state()
    assert (state.state, state.source, state.rule) == (pl.CONFIRMED, "developer.worktreeRoot", None)
    assert same(state.path, root)


def test_the_old_base_value_is_the_root_while_none_is_confirmed(home, tmp_path):
    base = tmp_path / "old-base"
    base.mkdir()
    set_root(home, base, key="worktreeBasePath")
    state = pl.root_state()
    assert (state.state, state.source) == (pl.SUGGESTED, "developer.worktreeBasePath")
    assert same(state.path, base)


def test_a_confirmed_root_wins_over_the_old_base_value(home, tmp_path):
    new, old = tmp_path / "new", tmp_path / "old"
    new.mkdir()
    old.mkdir()
    machine(home, f"developer:\n  worktreeRoot: '{new}'\n  worktreeBasePath: '{old}'\n")
    assert same(pl.root_state().path, new)


def test_a_failing_old_base_value_is_refused_not_replaced_by_the_suggestion(home):
    (home / pl.SUGGESTION_NAME).mkdir()
    set_root(home, "relative/base", key="worktreeBasePath")
    state = pl.root_state()
    assert (state.state, state.source, state.rule) == (pl.REFUSED, "developer.worktreeBasePath", "R-01")


def test_without_a_value_the_suggestion_in_the_home_folder_applies(home):
    (home / pl.SUGGESTION_NAME).mkdir()
    state = pl.root_state()
    assert (state.state, state.source) == (pl.SUGGESTED, "suggestion")
    assert same(state.path, home / "repo-worktrees")


@pytest.mark.parametrize("text", ["", "developer:\n", "developer:\n  worktreeRoot: ''\n",
                                  "developer:\n  worktreeRoot: ~\n"])
def test_an_empty_or_null_root_counts_as_unset(home, text):
    machine(home, text)
    (home / pl.SUGGESTION_NAME).mkdir()
    assert pl.root_state().source == "suggestion"


def test_a_root_in_a_repository_file_is_never_read_as_the_root(home, tmp_path, monkeypatch):
    repo = make_repo(tmp_path / "src")
    elsewhere = tmp_path / "repo-said"
    elsewhere.mkdir()
    (repo / ".afk").mkdir()
    (repo / ".afk" / "config.yaml").write_text(f"developer:\n  worktreeRoot: '{elsewhere}'\n", encoding="utf-8")
    (repo / ".git" / "afk").mkdir()
    (repo / ".git" / "afk" / "config.yaml").write_text(
        f"developer:\n  worktreeRoot: '{elsewhere}'\n", encoding="utf-8")
    monkeypatch.chdir(repo)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(repo))
    state = pl.root_state()
    assert state.source == "suggestion" and same(state.path, home / "repo-worktrees")


# --- catalog R, one test per row -------------------------------------------

@pytest.mark.parametrize("value", ["relative/root", "~/repo-worktrees", "./wt"]
                         + ([r"\no-drive\root"] if IS_WINDOWS else []))
def test_r01_a_root_that_is_not_absolute_is_refused(home, value):
    set_root(home, value)
    state = pl.root_state()
    assert (state.state, state.rule) == (pl.REFUSED, "R-01")
    assert state.reason == f"{value} is not an absolute path"


def test_r01_a_root_that_is_not_text_is_refused(home):
    machine(home, "developer:\n  worktreeRoot: 5\n")
    state = pl.root_state()
    assert (state.state, state.rule, state.reason) == (pl.REFUSED, "R-01", "5 is not a path")


def test_r02_a_root_inside_a_repository_is_refused_naming_it(home, tmp_path):
    repo = make_repo(tmp_path / "src")
    set_root(home, repo / "sub" / "wt")
    state = pl.root_state()
    assert state.rule == "R-02" and str(repo) in state.reason


def test_r02_a_root_that_is_a_repository_is_refused(home, tmp_path):
    repo = make_repo(tmp_path / "src")
    set_root(home, repo)
    assert pl.root_state().rule == "R-02"


def test_r02_a_root_inside_a_worktree_is_refused(home, tmp_path):
    repo = make_repo(tmp_path / "src")
    worktree = tmp_path / "beside"
    git(repo, "worktree", "add", "-q", "-b", "beside", str(worktree))
    set_root(home, worktree / "wt")
    assert pl.root_state().rule == "R-02"


def test_r02_a_link_into_a_repository_is_refused(home, tmp_path):
    repo = make_repo(tmp_path / "src")
    at = tmp_path / "looks-outside"
    link(repo / "sub", at)
    set_root(home, at)
    assert pl.root_state().rule == "R-02"


def test_r03_a_missing_root_is_reported_so_setup_creates_it(home, tmp_path):
    set_root(home, tmp_path / "not-yet")
    state = pl.root_state()
    assert (state.state, state.rule) == (pl.REFUSED, "R-03") and "/afk:setup" in state.reason


def test_r03_a_file_at_the_root_is_refused(home, tmp_path):
    (tmp_path / "a-file").write_text("x", encoding="utf-8")
    set_root(home, tmp_path / "a-file")
    assert pl.root_state().rule == "R-03"


def test_r04_a_space_warns_and_the_root_still_passes(home, tmp_path):
    spaced = tmp_path / "with space"
    spaced.mkdir()
    set_root(home, spaced)
    state = pl.root_state()
    assert state.state == pl.CONFIRMED and [w.rule for w in state.warnings] == ["R-04"]
    assert "Maven" in state.warnings[0].reason


def test_the_first_failure_in_catalog_order_is_returned(home, tmp_path):
    repo = make_repo(tmp_path / "src")
    set_root(home, repo / "missing with space")
    state = pl.root_state()
    assert state.rule == "R-02" and state.warnings == ()


def test_r05_an_invalid_short_name_in_the_list_is_refused(root, home, tmp_path):
    repo = make_repo(tmp_path / "src")
    write_list(home, [(rl.normalize(repo), "..")])
    verdict = pl.target_for(repo, "wt1")
    assert (verdict.state, verdict.rule) == (pl.REFUSED, "R-05")


def test_r05_a_short_name_claimed_by_an_earlier_entry_is_refused_naming_it(root, home, tmp_path):
    first, second = make_repo(tmp_path / "a"), make_repo(tmp_path / "b")
    write_list(home, [(rl.normalize(first), "proj"), (rl.normalize(second), "proj")])
    verdict = pl.target_for(second, "wt1")
    assert verdict.rule == "R-05" and rl.normalize(first) in verdict.reason
    assert pl.target_for(first, "wt1").state == pl.INSIDE


def test_r06_a_short_name_folder_holding_other_content_is_refused(root, home, tmp_path):
    repo = make_repo(tmp_path / "src")
    write_list(home, [(rl.normalize(repo), "proj")])
    (root / "proj").mkdir()
    (root / "proj" / "stray.txt").write_text("x", encoding="utf-8")
    assert pl.target_for(repo, "wt1").rule == "R-06"


def test_r06_a_folder_reserved_for_another_repository_is_refused(listed, root, home, tmp_path):
    other = make_repo(tmp_path / "other-src")
    marker = root / "proj" / rl.MARKER_NAME
    marker.write_text(json.dumps({"path": rl.normalize(other)}), encoding="utf-8")
    verdict = pl.target_for(listed, "wt1")
    assert verdict.rule == "R-06" and "reserved" in verdict.reason


def test_r06_an_unreadable_marker_is_refused(listed, root):
    (root / "proj" / rl.MARKER_NAME).write_text("{", encoding="utf-8")
    verdict = pl.target_for(listed, "wt1")
    assert verdict.rule == "R-06" and "an unreadable marker" in verdict.reason


def test_r06_a_file_at_the_short_name_is_refused(root, home, tmp_path):
    repo = make_repo(tmp_path / "src")
    write_list(home, [(rl.normalize(repo), "proj")])
    (root / "proj").write_text("x", encoding="utf-8")
    verdict = pl.target_for(repo, "wt1")
    assert verdict.rule == "R-06" and "is not a folder" in verdict.reason


def test_r06_an_absent_folder_passes(root, home, tmp_path):
    repo = make_repo(tmp_path / "src")
    write_list(home, [(rl.normalize(repo), "proj")])
    assert pl.target_for(repo, "wt1").state == pl.INSIDE


def test_r06_an_empty_folder_passes(root, home, tmp_path):
    repo = make_repo(tmp_path / "src")
    write_list(home, [(rl.normalize(repo), "proj")])
    (root / "proj").mkdir()
    assert pl.target_for(repo, "wt1").state == pl.INSIDE


def test_r07_every_call_reads_the_root_again(listed, root, home, tmp_path):
    assert pl.target_for(listed, "wt1").state == pl.INSIDE
    set_root(home, "relative")
    verdict = pl.target_for(listed, "wt1")
    assert (verdict.state, verdict.rule) == (pl.REFUSED, "R-01")


# --- target for a new worktree ----------------------------------------------

def test_a_listed_repository_gets_root_short_name_worktree_name(listed, root):
    verdict = pl.target_for(listed, "wt1")
    assert verdict.state == pl.INSIDE and verdict.rule is None
    assert same(verdict.target, root / "proj" / "wt1") and same(verdict.folder, root / "proj")


def test_the_same_target_from_a_subfolder_and_from_a_worktree_under_the_root(listed, root, git_calls):
    worktree = root / "proj" / "wt0"
    git(listed, "worktree", "add", "-q", "-b", "wt0", str(worktree))
    git_calls.clear()
    for folder in (listed / "sub", worktree):
        assert same(pl.target_for(folder, "wt1").target, root / "proj" / "wt1")
    assert git_calls == []


def test_an_unlisted_repository_is_not_listed_and_not_checked(root, home, tmp_path):
    repo = make_repo(tmp_path / "src")
    set_root(home, "relative")
    assert pl.target_for(repo, "wt1") == pl.Verdict(pl.NOT_LISTED, None)


def test_an_unlisted_repository_is_not_listed_even_with_a_broken_machine_file(root, home, tmp_path):
    repo = make_repo(tmp_path / "src")
    machine(home, "developer: {worktreeRoot: /x}\n")
    assert pl.target_for(repo, "wt1") == pl.Verdict(pl.NOT_LISTED, None)
    assert pl.check_target(tmp_path / "away", repo).state == pl.NOT_LISTED


def test_a_listed_checkout_with_a_broken_machine_file_raises(listed, home):
    machine(home, "developer: {worktreeRoot: /x}\n")
    with pytest.raises(pl.PlacementError, match="flow syntax"):
        pl.target_for(listed, "wt1")


def test_a_worktree_under_the_root_with_a_broken_machine_file_raises(listed, root, home):
    worktree = root / "proj" / "wt0"
    git(listed, "worktree", "add", "-q", "-b", "wt0", str(worktree))
    machine(home, "developer: {worktreeRoot: /x}\n")
    with pytest.raises(pl.PlacementError, match="flow syntax"):
        pl.target_for(worktree, "wt1")


def test_a_name_that_climbs_out_of_the_folder_is_refused(listed, root):
    verdict = pl.target_for(listed, os.path.join("..", "escape"))
    assert (verdict.state, verdict.rule) == (pl.REFUSED, pl.OUTSIDE)
    assert str(verdict.folder) in verdict.reason


def test_a_failing_root_refuses_the_target_naming_the_rule_and_folder(listed, root, home, tmp_path):
    set_root(home, tmp_path / "gone")
    verdict = pl.target_for(listed, "wt1")
    assert (verdict.state, verdict.rule) == (pl.REFUSED, "R-03")
    assert same(verdict.folder, tmp_path / "gone" / "proj")


def test_a_root_warning_travels_with_the_target(home, tmp_path):
    spaced = tmp_path / "with space"
    spaced.mkdir()
    set_root(home, spaced)
    repo = make_repo(tmp_path / "src")
    rl.add_repository(repo, spaced)
    verdict = pl.target_for(repo, "wt1")
    assert verdict.state == pl.INSIDE and [w.rule for w in verdict.warnings] == ["R-04"]


# --- check a chosen target --------------------------------------------------

def test_a_target_inside_the_folder_passes(listed, root):
    verdict = pl.check_target(root / "proj" / "x", listed)
    assert verdict.state == pl.INSIDE and same(verdict.folder, root / "proj")


@pytest.mark.parametrize("where", ["beside the checkout", "inside the checkout", "another short name",
                                   "a short name sharing the prefix", "the folder itself"])
def test_a_target_outside_the_folder_is_refused_naming_it(listed, root, tmp_path, where):
    target = {"beside the checkout": tmp_path / "src" / "proj-wt",
              "inside the checkout": listed / ".claude" / "worktrees" / "x",
              "another short name": root / "other" / "x",
              "a short name sharing the prefix": root / "proj-extra" / "x",
              "the folder itself": root / "proj"}[where]
    verdict = pl.check_target(target, listed)
    assert (verdict.state, verdict.rule) == (pl.REFUSED, pl.OUTSIDE)
    assert verdict.reason == f"{verdict.target} is outside {verdict.folder}"


def test_a_relative_target_is_made_absolute_against_the_folder(listed, root):
    worktree = root / "proj" / "wt0"
    git(listed, "worktree", "add", "-q", "-b", "wt0", str(worktree))
    assert pl.check_target(os.path.join("..", "wt2"), worktree).state == pl.INSIDE
    outside = pl.check_target(os.path.join(".claude", "worktrees", "x"), listed)
    assert outside.rule == pl.OUTSIDE and same(outside.target, listed / ".claude" / "worktrees" / "x")


def test_a_tilde_target_is_expanded_before_the_check(home, tmp_path):
    root = home / pl.SUGGESTION_NAME
    root.mkdir()
    repo = make_repo(tmp_path / "src")
    rl.add_repository(repo, root)
    assert pl.check_target("~/repo-worktrees/proj/x", repo).state == pl.INSIDE
    assert pl.check_target("~/elsewhere/x", repo).rule == pl.OUTSIDE


def test_a_target_with_a_space_is_checked_as_written(listed, root):
    assert pl.check_target(root / "proj" / "with space", listed).state == pl.INSIDE


def test_links_are_resolved_on_both_sides(listed, root, tmp_path):
    into = tmp_path / "into-folder"
    link(root / "proj", into)
    assert pl.check_target(into / "x", listed).state == pl.INSIDE
    away = tmp_path / "away"
    away.mkdir()
    link(away, root / "proj" / "door")
    assert pl.check_target(root / "proj" / "door" / "x", listed).rule == pl.OUTSIDE


def test_a_link_then_dotdot_is_judged_where_the_folder_lands(listed, root, tmp_path):
    (tmp_path / "away" / "inner").mkdir(parents=True)
    link(tmp_path / "away" / "inner", root / "proj" / "door")
    target = os.path.join(str(root / "proj" / "door"), "..", "x")
    verdict = pl.check_target(target, listed)
    os.makedirs(target)
    landed = next(p for p in (root / "proj" / "x", tmp_path / "away" / "x") if p.is_dir())
    assert same(verdict.target, landed)
    assert (verdict.state == pl.INSIDE) == same(landed.parent, root / "proj")


def test_a_target_under_a_linked_root_is_shown_with_its_folder_in_one_spelling(home, tmp_path):
    real = tmp_path / "real-root"
    real.mkdir()
    link(real, tmp_path / "root-link")
    set_root(home, tmp_path / "root-link")
    repo = make_repo(tmp_path / "src")
    rl.add_repository(repo, tmp_path / "root-link")
    verdict = pl.check_target(tmp_path / "away" / "x", repo)
    assert verdict.rule == pl.OUTSIDE
    assert os.path.dirname(verdict.folder) == os.path.realpath(real)
    assert verdict.target == os.path.realpath(tmp_path / "away" / "x")


@pytest.mark.skipif(not IS_WINDOWS, reason="drive letters exist only on Windows")
def test_drive_letter_case_is_resolved_on_both_sides(listed, root):
    text = str(root / "proj" / "x")
    flipped = (text[0].lower() if text[0].isupper() else text[0].upper()) + text[1:]
    assert pl.check_target(flipped, listed).state == pl.INSIDE
    assert pl.check_target(text.upper(), str(listed).lower()).state == pl.INSIDE


def test_an_unlisted_repository_target_is_not_checked(root, tmp_path):
    repo = make_repo(tmp_path / "src")
    verdict = pl.check_target(tmp_path / "anywhere", repo)
    assert verdict.state == pl.NOT_LISTED and same(verdict.target, tmp_path / "anywhere")


def test_a_folder_in_no_repository_is_not_listed(root, tmp_path, git_calls):
    plain = tmp_path / "plain"
    plain.mkdir()
    assert pl.check_target(root / "proj" / "x", plain).state == pl.NOT_LISTED
    assert git_calls == []


# --- unusual layouts start git ----------------------------------------------

def test_the_usual_layouts_start_no_git(listed, root, git_calls):
    worktree = root / "proj" / "wt0"
    git(listed, "worktree", "add", "-q", "-b", "wt0", str(worktree))
    git_calls.clear()
    pl.check_target(root / "proj" / "x", listed)
    pl.check_target(root / "proj" / "x", worktree / "sub")
    pl.root_state()
    assert git_calls == []


def test_an_unlisted_submodule_inside_a_listed_checkout_is_not_listed(root, tmp_path, git_calls):
    library = make_repo(tmp_path / "src", "lib")
    outer = make_repo(tmp_path / "src", "outer")
    git(outer, "-c", "protocol.file.allow=always", "submodule", "add", "-q", str(library), "lib")
    rl.add_repository(outer, root)
    git_calls.clear()
    assert pl.check_target(tmp_path / "anywhere", outer / "lib").state == pl.NOT_LISTED
    assert git_calls, "a submodule is an unusual layout: placement asks git"
    assert pl.check_target(tmp_path / "anywhere", outer).rule == pl.OUTSIDE


def test_a_listed_submodules_worktree_elsewhere_is_found_through_git(root, tmp_path, git_calls):
    library = make_repo(tmp_path / "src", "lib")
    outer = make_repo(tmp_path / "src", "outer")
    git(outer, "-c", "protocol.file.allow=always", "submodule", "add", "-q", str(library), "lib")
    rl.add_repository(outer / "lib", root, short_name="lib")
    worktree = tmp_path / "lib-wt"
    git(outer / "lib", "worktree", "add", "-q", "-b", "wt", str(worktree))
    git_calls.clear()
    verdict = pl.check_target(tmp_path / "beside", worktree)
    assert verdict.rule == pl.OUTSIDE and same(verdict.folder, root / "lib")
    assert git_calls


@pytest.mark.parametrize("where", ["beside the checkout", "inside the checkout"])
def test_a_worktree_elsewhere_of_a_listed_repository_is_found_through_git(listed, root, tmp_path, git_calls,
                                                                          where):
    worktree = {"beside the checkout": tmp_path / "beside",
                "inside the checkout": listed / ".claude" / "worktrees" / "inner"}[where]
    git(listed, "worktree", "add", "-q", "-b", worktree.name, str(worktree))
    git_calls.clear()
    assert pl.check_target(tmp_path / "away", worktree).rule == pl.OUTSIDE
    assert pl.target_for(worktree, "wt1").state == pl.INSIDE
    assert git_calls


def test_a_worktree_two_levels_under_the_short_name_is_found_by_text(listed, root, git_calls):
    worktree = root / "proj" / "team" / "wt0"
    git(listed, "worktree", "add", "-q", "-b", "wt0", str(worktree))
    git_calls.clear()
    assert pl.target_for(worktree, "wt1").state == pl.INSIDE
    assert git_calls == []


def test_a_clone_inside_a_worktree_under_the_root_is_not_listed(listed, root, tmp_path):
    worktree = root / "proj" / "wt0"
    git(listed, "worktree", "add", "-q", "-b", "wt0", str(worktree))
    make_repo(worktree / "vendor", "lib")
    assert pl.check_target(tmp_path / "away", worktree / "vendor" / "lib").state == pl.NOT_LISTED


def test_a_submodule_inside_a_worktree_under_the_root_is_not_listed(listed, root, tmp_path):
    worktree = root / "proj" / "wt0"
    git(listed, "worktree", "add", "-q", "-b", "wt0", str(worktree))
    library = make_repo(tmp_path / "lib-src", "lib")
    git(worktree, "-c", "protocol.file.allow=always", "submodule", "add", "-q", str(library), "lib")
    assert pl.check_target(tmp_path / "away", worktree / "lib").state == pl.NOT_LISTED


def test_a_clone_directly_under_the_short_name_is_not_listed(listed, root, tmp_path):
    make_repo(root / "proj", "lib")
    assert pl.check_target(tmp_path / "away", root / "proj" / "lib").state == pl.NOT_LISTED


def test_a_worktree_of_a_separate_git_folder_without_core_worktree_is_not_listed(root, tmp_path, git_calls):
    repo = tmp_path / "src" / "proj"
    repo.mkdir(parents=True)
    git(repo, "init", "-q", "-b", "dev", f"--separate-git-dir={tmp_path / 'store.git'}")
    git(repo, "-c", "user.name=T", "-c", "user.email=t@example.com", "commit", "-q", "--allow-empty", "-m", "seed")
    rl.add_repository(repo, root)
    worktree = tmp_path / "elsewhere"
    git(repo, "worktree", "add", "-q", "-b", "wt", str(worktree))
    git_calls.clear()
    assert pl.check_target(tmp_path / "away", worktree).state == pl.NOT_LISTED
    assert git_calls, "D-35: git names no main checkout, so the answer is not listed"


def test_a_git_dir_variable_points_placement_at_its_repository(listed, root, tmp_path, git_calls):
    plain = tmp_path / "plain"
    plain.mkdir()
    environ = {**os.environ, "GIT_DIR": str(listed / ".git")}
    verdict = pl.check_target(tmp_path / "away", plain, environ=environ)
    assert verdict.rule == pl.OUTSIDE and same(verdict.folder, root / "proj")
    assert git_calls


def test_a_nested_clone_inside_a_listed_checkout_is_not_listed(listed, root, tmp_path):
    make_repo(listed / "vendor", "nested")
    assert pl.check_target(tmp_path / "away", listed / "vendor" / "nested").state == pl.NOT_LISTED


# --- what placement reads ---------------------------------------------------

def test_a_listed_check_reads_only_the_machine_file_the_list_and_the_marker(listed, root, home, monkeypatch):
    opened: list[str] = []
    real = builtins.open

    def spy(file, *args, **kwargs):
        opened.append(os.path.normcase(os.path.realpath(os.fspath(file))))
        return real(file, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", spy)
    monkeypatch.setattr(io, "open", spy)
    verdict = pl.check_target(root / "proj" / "x", listed)
    assert verdict.state == pl.INSIDE
    allowed = {os.path.normcase(os.path.realpath(path)) for path in (
        home / ".afk" / "config.yaml", home / ".afk" / "repositories.json", root / "proj" / rl.MARKER_NAME)}
    assert set(opened) == allowed
    assert len(opened) <= 4, opened


def test_import_and_machine_file_parse_time_is_reported(home, root, capsys):
    probe = (
        "import time, importlib.util, sys; start = time.perf_counter(); "
        f"spec = importlib.util.spec_from_file_location('p', {str(SCRIPT)!r}); "
        "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); m.root_state(); "
        "print(round((time.perf_counter() - start) * 1000, 1))"
    )
    done = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, env=dict(os.environ))
    assert done.returncode == 0, done.stderr
    with capsys.disabled():
        print(f"\n[informational] placement import plus machine-file parse: {done.stdout.strip()} ms (budget 20)")


# --- failures ---------------------------------------------------------------

def test_a_module_loaded_from_another_file_under_the_same_name_is_not_reused(monkeypatch):
    import types
    monkeypatch.setitem(sys.modules, "afk_config", types.ModuleType("afk_config"))
    private = "_afk_placement_afk_config"
    try:
        fresh = load(SCRIPT, "afk_placement_fresh")
        assert hasattr(fresh.afk_config, "parse_single_file")
        assert same(fresh.afk_config.__file__, ROOT / "scripts" / "afk-config.py")
    finally:
        sys.modules.pop(private, None)


def test_a_machine_file_outside_the_subset_raises(home):
    machine(home, "developer: {worktreeRoot: /x}\n")
    with pytest.raises(pl.PlacementError, match="flow syntax"):
        pl.root_state()


def test_a_developer_value_that_is_not_a_mapping_raises(home):
    machine(home, "developer: someone\n")
    with pytest.raises(pl.PlacementError, match="not a mapping"):
        pl.root_state()


def test_a_broken_list_raises(listed, home):
    (home / ".afk" / "repositories.json").write_text("{", encoding="utf-8")
    with pytest.raises(pl.PlacementError, match="not valid JSON"):
        pl.check_target("/x", listed)


@pytest.mark.parametrize("call", [lambda: pl.check_target("", "."), lambda: pl.check_target("/x", " "),
                                  lambda: pl.target_for(".", "")])
def test_a_blank_path_or_name_raises(home, call):
    with pytest.raises(pl.PlacementError, match="empty"):
        call()


def test_a_missing_git_raises(listed, root, monkeypatch):
    def gone(*args, **kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr(pl.subprocess, "run", gone)
    with pytest.raises(pl.PlacementError, match="git is not on PATH"):
        pl.check_target("/x", listed, environ={**os.environ, "GIT_DIR": str(listed / ".git")})
