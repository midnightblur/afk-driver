"""Integration tests for worktree_manager against real temp git repos."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from afk_driver.worktree_manager import (
    WorktreeError,
    WorktreeSpec,
    bootstrap_assets,
    commit_dirty_changes,
    ensure,
    find_worktree_for_branch,
    head_sha,
    publish_branch,
    push_branch,
    rebase_onto_target,
    reset_to_clean,
    validate_state,
)


def _run(cwd: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git {args} in {cwd} failed: {proc.stderr}")
    return proc.stdout


def _init_main_with_origin(tmp_path: Path, branch: str = "master") -> tuple[Path, Path]:
    origin = tmp_path / "origin.git"
    subprocess.run(
        ["git", "init", "--bare", "-q", "-b", branch, str(origin)], check=True
    )
    main = tmp_path / "main"
    main.mkdir()
    _run(main, "init", "-q", "-b", branch)
    _run(main, "config", "user.email", "afk@test")
    _run(main, "config", "user.name", "afk")
    _run(main, "remote", "add", "origin", str(origin))
    (main / "README.md").write_text("hello\n", encoding="utf-8")
    _run(main, "add", "README.md")
    _run(main, "commit", "-q", "-m", "init")
    _run(main, "push", "-q", "-u", "origin", branch)
    return main, origin


def _spec(main: Path, wt_root: Path, enh: str = "P2P-9999", base: str = "master") -> WorktreeSpec:
    return WorktreeSpec(repo_root=main, worktree_root=wt_root, parent_id=enh, base_branch=base)


def test_create_when_absent(tmp_path: Path):
    main, _ = _init_main_with_origin(tmp_path)
    spec = _spec(main, tmp_path / "wt")
    path = ensure(spec)
    assert path.exists()
    assert path == tmp_path / "wt" / "P2P-9999"
    branch = _run(path, "branch", "--show-current").strip()
    assert branch == "mvu/afk/p2p-9999"


def test_branch_lowercases_uppercase_parent_id():
    r"""GitLab branch-name pattern is ^[a-z0-9][a-z0-9\/\-\.]*$ — Jira keys are
    uppercase, so spec.branch must lowercase the parent_id segment."""
    import re
    spec = WorktreeSpec(
        repo_root=Path("."), worktree_root=Path("."), parent_id="P2P-1229", base_branch="master",
    )
    assert spec.branch == "mvu/afk/p2p-1229"
    assert re.match(r"^[a-z0-9][a-z0-9\/\-\.]*$", spec.branch)


def test_publish_branch_pushes_to_origin(tmp_path: Path):
    main, origin = _init_main_with_origin(tmp_path)
    spec = _spec(main, tmp_path / "wt")
    ensure(spec)
    publish_branch(spec)
    refs = subprocess.run(
        ["git", "ls-remote", "--heads", str(origin)],
        capture_output=True, text=True, check=True,
    ).stdout
    assert "refs/heads/mvu/afk/p2p-9999" in refs
    publish_branch(spec)  # idempotent


def test_idempotent_when_present(tmp_path: Path):
    main, _ = _init_main_with_origin(tmp_path)
    spec = _spec(main, tmp_path / "wt")
    p1 = ensure(spec)
    p2 = ensure(spec)
    assert p1 == p2


def test_refuse_on_dirty(tmp_path: Path):
    main, _ = _init_main_with_origin(tmp_path)
    spec = _spec(main, tmp_path / "wt")
    path = ensure(spec)
    (path / "scratch.txt").write_text("x", encoding="utf-8")
    with pytest.raises(WorktreeError, match="dirty"):
        validate_state(spec)


def test_refuse_on_wrong_branch(tmp_path: Path):
    main, _ = _init_main_with_origin(tmp_path)
    spec = _spec(main, tmp_path / "wt")
    path = ensure(spec)
    _run(path, "checkout", "-q", "-b", "other")
    with pytest.raises(WorktreeError, match="expected 'mvu/afk/p2p-9999'"):
        validate_state(spec)


def test_refuse_on_wrong_base(tmp_path: Path):
    main, _ = _init_main_with_origin(tmp_path)
    spec = _spec(main, tmp_path / "wt")
    ensure(spec)
    other_spec = _spec(main, tmp_path / "wt", enh="P2P-9999", base="orphan-branch")
    _run(main, "checkout", "-q", "--orphan", "orphan-branch")
    _run(main, "commit", "-q", "-m", "orphan")
    _run(main, "checkout", "-q", "master")
    with pytest.raises(WorktreeError, match="not based off 'orphan-branch'"):
        validate_state(other_spec)


def test_rebase_clean(tmp_path: Path):
    main, origin = _init_main_with_origin(tmp_path)
    spec = _spec(main, tmp_path / "wt")
    path = ensure(spec)
    (main / "another.md").write_text("a\n", encoding="utf-8")
    _run(main, "add", "another.md")
    _run(main, "commit", "-q", "-m", "advance master")
    _run(main, "push", "-q", "origin", "master")
    (path / "feature.txt").write_text("f\n", encoding="utf-8")
    _run(path, "add", "feature.txt")
    _run(path, "commit", "-q", "-m", "subtask work")
    assert rebase_onto_target(spec) == "clean"
    log = _run(path, "log", "--oneline").splitlines()
    assert any("advance master" in line for line in log)
    assert any("subtask work" in line for line in log)


def test_rebase_conflict_detected(tmp_path: Path):
    main, _ = _init_main_with_origin(tmp_path)
    spec = _spec(main, tmp_path / "wt")
    path = ensure(spec)
    (main / "README.md").write_text("origin-edit\n", encoding="utf-8")
    _run(main, "add", "README.md")
    _run(main, "commit", "-q", "-m", "origin edits readme")
    _run(main, "push", "-q", "origin", "master")
    (path / "README.md").write_text("worktree-edit\n", encoding="utf-8")
    _run(path, "add", "README.md")
    _run(path, "commit", "-q", "-m", "worktree edits readme")
    assert rebase_onto_target(spec) == "conflict"
    porcelain = _run(path, "status", "--porcelain").strip()
    assert porcelain == "", "rebase --abort should leave clean tree"


def test_multiple_target_branches(tmp_path: Path):
    main, _ = _init_main_with_origin(tmp_path)
    _run(main, "checkout", "-q", "-b", "fin-core/release")
    (main / "fc.md").write_text("fc\n", encoding="utf-8")
    _run(main, "add", "fc.md")
    _run(main, "commit", "-q", "-m", "fc init")
    _run(main, "push", "-q", "-u", "origin", "fin-core/release")
    _run(main, "checkout", "-q", "master")
    spec = _spec(main, tmp_path / "wt", enh="P2P-1234", base="fin-core/release")
    path = ensure(spec)
    branch = _run(path, "branch", "--show-current").strip()
    assert branch == "mvu/afk/p2p-1234"
    log = _run(path, "log", "--oneline").splitlines()
    assert any("fc init" in line for line in log)


# -- Post-claude safety net helpers ---------------------------------------

def test_commit_dirty_changes_commits_when_dirty(tmp_path: Path):
    """commit_dirty_changes is the runner's safety net for the
    P2P-1233/1234/1235 failure mode: spawned claude session edited files but
    exited without git commit, leaving the worktree dirty. The helper stages
    everything (including untracked files), commits with the given message,
    and returns True so the runner knows new work landed."""
    main, _ = _init_main_with_origin(tmp_path)
    spec = _spec(main, tmp_path / "wt")
    path = ensure(spec)
    pre_tip = head_sha(spec)

    (path / "edited.txt").write_text("claude wrote this\n", encoding="utf-8")
    (path / "README.md").write_text("hello modified\n", encoding="utf-8")

    committed = commit_dirty_changes(spec, "[P2P-9999] AFK auto-commit safety net")
    assert committed is True
    post_tip = head_sha(spec)
    assert post_tip != pre_tip, "tip must advance after commit_dirty_changes"
    log = _run(path, "log", "--oneline", "-1").strip()
    assert "AFK auto-commit safety net" in log
    porcelain = _run(path, "status", "--porcelain").strip()
    assert porcelain == "", "tree must be clean after commit_dirty_changes"


def test_commit_dirty_changes_returns_false_when_clean(tmp_path: Path):
    """If claude already committed (or did nothing at all), the runner's
    safety-net call must be a no-op and return False so the runner can
    distinguish 'work landed via claude itself' from 'no work happened'."""
    main, _ = _init_main_with_origin(tmp_path)
    spec = _spec(main, tmp_path / "wt")
    ensure(spec)
    pre_tip = head_sha(spec)
    committed = commit_dirty_changes(spec, "noop")
    assert committed is False
    assert head_sha(spec) == pre_tip


def test_commit_dirty_changes_refuses_wrong_branch(tmp_path: Path):
    """Defence-in-depth: commit_dirty_changes must verify branch identity
    before staging — the worktree path could have been hand-checked-out to
    another branch by the user."""
    main, _ = _init_main_with_origin(tmp_path)
    spec = _spec(main, tmp_path / "wt")
    path = ensure(spec)
    _run(path, "checkout", "-q", "-b", "stray-branch")
    (path / "x.txt").write_text("x\n", encoding="utf-8")
    with pytest.raises(WorktreeError, match="expected"):
        commit_dirty_changes(spec, "should not run")


def test_head_sha_returns_current_tip(tmp_path: Path):
    main, _ = _init_main_with_origin(tmp_path)
    spec = _spec(main, tmp_path / "wt")
    path = ensure(spec)
    expected = _run(path, "rev-parse", "HEAD").strip()
    assert head_sha(spec) == expected
    assert len(head_sha(spec)) == 40


def test_push_branch_pushes_freshly_committed_work(tmp_path: Path):
    """push_branch is the runner's post-auto-commit publisher. Unlike
    publish_branch, it tolerates a tree that was just made clean by
    commit_dirty_changes without re-running the full validate_state pre-flight
    (merge-base etc. are already verified earlier in the pass)."""
    main, origin = _init_main_with_origin(tmp_path)
    spec = _spec(main, tmp_path / "wt")
    path = ensure(spec)
    publish_branch(spec)  # initial publish

    (path / "work.txt").write_text("subtask work\n", encoding="utf-8")
    commit_dirty_changes(spec, "[P2P-9999] subtask work")
    push_branch(spec)

    bare_log = subprocess.run(
        ["git", "-C", str(origin), "log", "--oneline", "mvu/afk/p2p-9999"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    ).stdout
    assert "subtask work" in bare_log


def test_push_branch_refuses_wrong_branch(tmp_path: Path):
    main, _ = _init_main_with_origin(tmp_path)
    spec = _spec(main, tmp_path / "wt")
    path = ensure(spec)
    _run(path, "checkout", "-q", "-b", "stray-branch")
    with pytest.raises(WorktreeError, match="expected"):
        push_branch(spec)


# -- Asset bootstrap (mirrors ~/bin/new-task, minus npm + IntelliJ launch) ---

def _seed_intellij_assets(main: Path) -> None:
    """Create the same set of gitignored assets that new-task copies. The
    .gitignore must be committed first so the worktree inherits it and
    bootstrap-copied files don't show up as dirty under git status."""
    (main / ".gitignore").write_text(
        ".mcp.json\n.claude/\n.run/\n.idea/\n", encoding="utf-8",
    )
    _run(main, "add", ".gitignore")
    _run(main, "commit", "-q", "-m", "ignore intellij + claude assets")
    _run(main, "push", "-q", "origin", "HEAD")
    (main / ".mcp.json").write_text('{"mcpServers": {}}\n', encoding="utf-8")
    claude = main / ".claude"
    claude.mkdir()
    (claude / "settings.local.json").write_text('{"hooks": []}\n', encoding="utf-8")
    (claude / "hooks").mkdir()
    (claude / "hooks" / "pre-commit.sh").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    run_dir = main / ".run"
    run_dir.mkdir()
    (run_dir / "App.run.xml").write_text(
        f'<component><option value="{main}/build" /></component>\n', encoding="utf-8",
    )
    idea = main / ".idea"
    idea.mkdir()
    (idea / "workspace.xml").write_text(
        f'<terminal startingDirectory="{main}/foo" />\n', encoding="utf-8",
    )
    (idea / "modules.xml").write_text("<modules/>\n", encoding="utf-8")


def test_ensure_copies_intellij_and_claude_assets_on_fresh_creation(tmp_path: Path):
    """Fresh worktree creation must mirror new-task: copy .mcp.json, .claude/,
    .run/, .idea/ — with repo-root paths in .run + workspace.xml rewritten to
    the worktree path. No npm install, no IntelliJ launch — those are the AFK
    deviations from new-task."""
    main, _ = _init_main_with_origin(tmp_path)
    _seed_intellij_assets(main)
    spec = _spec(main, tmp_path / "wt")

    path = ensure(spec)

    assert (path / ".mcp.json").read_text(encoding="utf-8") == '{"mcpServers": {}}\n'
    assert (path / ".claude" / "settings.local.json").is_file()
    assert (path / ".claude" / "hooks" / "pre-commit.sh").is_file()
    run_xml = (path / ".run" / "App.run.xml").read_text(encoding="utf-8")
    assert str(main) not in run_xml and str(main).replace("\\", "/") not in run_xml
    assert str(path) in run_xml or str(path).replace("\\", "/") in run_xml
    ws = (path / ".idea" / "workspace.xml").read_text(encoding="utf-8")
    assert str(main) not in ws and str(main).replace("\\", "/") not in ws
    assert str(path) in ws or str(path).replace("\\", "/") in ws
    assert (path / ".idea" / "modules.xml").read_text(encoding="utf-8") == "<modules/>\n"
    assert (path / ".idea" / ".name").read_text(encoding="utf-8") == path.name


def test_ensure_silently_skips_missing_assets(tmp_path: Path):
    """Bootstrap is best-effort — if the main checkout has no .mcp.json /
    .claude / .run / .idea, the worktree just doesn't get them. No errors."""
    main, _ = _init_main_with_origin(tmp_path)
    spec = _spec(main, tmp_path / "wt")
    path = ensure(spec)
    assert not (path / ".mcp.json").exists()
    assert not (path / ".claude").exists()
    assert not (path / ".run").exists()
    assert not (path / ".idea").exists()


def test_bootstrap_assets_handles_backslash_path_form(tmp_path: Path):
    """IntelliJ XML on Windows may store paths in backslash form. Substitution
    must handle both slash directions so the rewrite catches every occurrence."""
    main = tmp_path / "main"
    main.mkdir()
    wt = tmp_path / "wt" / "P2P-1"
    wt.mkdir(parents=True)
    (main / ".run").mkdir()
    back = str(main).replace("/", "\\")
    fwd = str(main).replace("\\", "/")
    (main / ".run" / "App.run.xml").write_text(
        f"<a fwd='{fwd}/build'/><b back='{back}\\build'/>\n", encoding="utf-8",
    )
    bootstrap_assets(main, wt)
    out = (wt / ".run" / "App.run.xml").read_text(encoding="utf-8")
    assert fwd not in out
    assert back not in out


def test_bootstrap_fills_in_gitignored_claude_md_at_any_depth(tmp_path: Path):
    """Gitignored CLAUDE.md at root + nested paths in the main checkout —
    which ``git worktree add`` would never bring across — must land in the
    worktree at the same relative path. Heavy/irrelevant dirs (node_modules,
    target, .git, .claude, etc.) are not traversed."""
    main, _ = _init_main_with_origin(tmp_path)
    (main / ".gitignore").write_text("CLAUDE.md\n", encoding="utf-8")
    _run(main, "add", ".gitignore")
    _run(main, "commit", "-q", "-m", "ignore CLAUDE.md")
    _run(main, "push", "-q", "origin", "HEAD")
    (main / "CLAUDE.md").write_text("root local\n", encoding="utf-8")
    (main / "src" / "afk_driver").mkdir(parents=True)
    (main / "src" / "afk_driver" / "CLAUDE.md").write_text("nested local\n", encoding="utf-8")
    (main / "tests").mkdir()
    (main / "tests" / "CLAUDE.md").write_text("tests local\n", encoding="utf-8")
    # noise that must not be traversed:
    (main / "node_modules" / "evil").mkdir(parents=True)
    (main / "node_modules" / "evil" / "CLAUDE.md").write_text("DO NOT COPY\n", encoding="utf-8")
    (main / "target" / "classes").mkdir(parents=True)
    (main / "target" / "classes" / "CLAUDE.md").write_text("DO NOT COPY\n", encoding="utf-8")

    spec = _spec(main, tmp_path / "wt")
    path = ensure(spec)

    assert (path / "CLAUDE.md").read_text(encoding="utf-8") == "root local\n"
    assert (path / "src" / "afk_driver" / "CLAUDE.md").read_text(encoding="utf-8") == "nested local\n"
    assert (path / "tests" / "CLAUDE.md").read_text(encoding="utf-8") == "tests local\n"
    assert not (path / "node_modules").exists()
    assert not (path / "target" / "classes" / "CLAUDE.md").exists()
    # Worktree must still be clean — bootstrap must not introduce dirty state.
    porcelain = _run(path, "status", "--porcelain").strip()
    assert porcelain == ""


def test_bootstrap_does_not_overwrite_committed_claude_md(tmp_path: Path):
    """Committed CLAUDE.md arrives in the worktree via ``git worktree add``.
    Bootstrap must NOT overwrite it with the main checkout's working-tree
    copy — that would mark the worktree dirty and break validate_state."""
    main, _ = _init_main_with_origin(tmp_path)
    (main / "CLAUDE.md").write_text("committed text\n", encoding="utf-8")
    _run(main, "add", "CLAUDE.md")
    _run(main, "commit", "-q", "-m", "add CLAUDE.md")
    _run(main, "push", "-q", "origin", "HEAD")
    # uncommitted edit in the main checkout — must NOT propagate:
    (main / "CLAUDE.md").write_text("WIP edit\n", encoding="utf-8")

    spec = _spec(main, tmp_path / "wt")
    path = ensure(spec)

    assert (path / "CLAUDE.md").read_text(encoding="utf-8") == "committed text\n"
    porcelain = _run(path, "status", "--porcelain").strip()
    assert porcelain == ""
    validate_state(spec)  # must not raise


# -- Crash-recovery: reset_to_clean + ensure() auto-recover -----------------

def test_reset_to_clean_wipes_uncommitted_state(tmp_path: Path):
    """Models the recovery hook for "claude server died mid-session, leaving
    edits uncommitted in the worktree". reset_to_clean must hard-reset the
    index, throw away modifications to tracked files, AND remove untracked
    files / dirs. HEAD is unchanged — only the dirt goes."""
    main, _ = _init_main_with_origin(tmp_path)
    spec = _spec(main, tmp_path / "wt")
    path = ensure(spec)
    pre_tip = head_sha(spec)

    (path / "README.md").write_text("modified\n", encoding="utf-8")  # tracked-edit
    (path / "scratch.txt").write_text("untracked\n", encoding="utf-8")  # untracked-file
    (path / "scratch_dir").mkdir()
    (path / "scratch_dir" / "more.txt").write_text("nested\n", encoding="utf-8")

    cleaned = reset_to_clean(spec)
    assert cleaned is True
    assert (path / "README.md").read_text(encoding="utf-8") == "hello\n"
    assert not (path / "scratch.txt").exists()
    assert not (path / "scratch_dir").exists()
    assert head_sha(spec) == pre_tip
    porcelain = _run(path, "status", "--porcelain").strip()
    assert porcelain == ""


def test_reset_to_clean_returns_false_when_already_clean(tmp_path: Path):
    """No-op when the tree is already clean — the runner uses the bool to
    decide whether to log a "wiped leftovers" message."""
    main, _ = _init_main_with_origin(tmp_path)
    spec = _spec(main, tmp_path / "wt")
    ensure(spec)
    pre_tip = head_sha(spec)
    assert reset_to_clean(spec) is False
    assert head_sha(spec) == pre_tip


def test_reset_to_clean_refuses_wrong_branch(tmp_path: Path):
    """Defence-in-depth: the worktree path could have been hand-checked-out
    to another branch by the user. reset_to_clean must not nuke work on a
    branch it doesn't own."""
    main, _ = _init_main_with_origin(tmp_path)
    spec = _spec(main, tmp_path / "wt")
    path = ensure(spec)
    _run(path, "checkout", "-q", "-b", "stray-branch")
    (path / "x.txt").write_text("x\n", encoding="utf-8")
    with pytest.raises(WorktreeError, match="expected"):
        reset_to_clean(spec)


# -- Reuse of pre-existing branches / worktrees -----------------------------

def test_ensure_reuses_existing_local_branch_via_branch_override(tmp_path: Path):
    """Nakisa convention: a developer prepares the parent's branch by hand
    (``kapteyn/development/mvu/{slug}``). The runner sets
    spec.branch_override to that branch name; ``ensure()`` must check it
    out into a fresh worktree at spec.path WITHOUT trying to ``-b`` it
    (that fails: branch already exists)."""
    main, _ = _init_main_with_origin(tmp_path)
    # User pre-creates a branch off master in the main checkout — no
    # worktree yet, just a local branch ref.
    _run(main, "branch", "kapteyn/development/mvu/payable-fixes")
    spec = WorktreeSpec(
        repo_root=main,
        worktree_root=tmp_path / "wt",
        parent_id="P2P-9999",
        base_branch="master",
        branch_override="kapteyn/development/mvu/payable-fixes",
    )
    path = ensure(spec)
    assert path == tmp_path / "wt" / "P2P-9999"
    branch = _run(path, "branch", "--show-current").strip()
    assert branch == "kapteyn/development/mvu/payable-fixes"


def test_ensure_reuses_remote_only_branch_by_fetching_first(tmp_path: Path):
    """Branch exists on origin but no local ref yet (e.g. user pushed it
    from another machine). ``ensure()`` must fetch then check it out into
    the worktree, tracking origin/BRANCH."""
    main, origin = _init_main_with_origin(tmp_path)
    # Build the branch in a SEPARATE clone, push to origin, then drop the
    # local ref from main so the situation is "remote-only from main's POV".
    other = tmp_path / "other"
    subprocess.run(["git", "clone", "-q", str(origin), str(other)], check=True)
    _run(other, "config", "user.email", "afk@test")
    _run(other, "config", "user.name", "afk")
    _run(other, "checkout", "-q", "-b", "kapteyn/development/mvu/from-elsewhere")
    (other / "feature.txt").write_text("from-other\n", encoding="utf-8")
    _run(other, "add", "feature.txt")
    _run(other, "commit", "-q", "-m", "elsewhere commit")
    _run(other, "push", "-q", "-u", "origin", "kapteyn/development/mvu/from-elsewhere")

    spec = WorktreeSpec(
        repo_root=main,
        worktree_root=tmp_path / "wt",
        parent_id="P2P-8888",
        base_branch="master",
        branch_override="kapteyn/development/mvu/from-elsewhere",
    )
    path = ensure(spec)
    assert (path / "feature.txt").read_text(encoding="utf-8") == "from-other\n"
    branch = _run(path, "branch", "--show-current").strip()
    assert branch == "kapteyn/development/mvu/from-elsewhere"
    # Tracking is set up so later push_branch is a fast-forward, not a
    # rejected "no upstream" push.
    upstream = _run(path, "rev-parse", "--abbrev-ref", "@{upstream}").strip()
    assert upstream == "origin/kapteyn/development/mvu/from-elsewhere"


def test_ensure_uses_path_override_for_foreign_worktree_reuse(tmp_path: Path):
    """If the user already has a worktree open at a non-managed path (e.g.
    IntelliJ via ``new-task``), the runner sets spec.path_override and
    ``ensure()`` validates THAT path rather than creating a new one. No
    bootstrap_assets in this case — the user's existing tooling stands."""
    main, _ = _init_main_with_origin(tmp_path)
    # Simulate the user's foreign worktree by creating it via git directly.
    foreign = tmp_path / "user" / "feature-X"
    _run(main, "worktree", "add", "-b", "kapteyn/development/mvu/feature-x", str(foreign), "master")

    spec = WorktreeSpec(
        repo_root=main,
        worktree_root=tmp_path / "wt",
        parent_id="P2P-7777",
        base_branch="master",
        branch_override="kapteyn/development/mvu/feature-x",
        path_override=foreign,
    )
    path = ensure(spec)
    assert path == foreign
    branch = _run(path, "branch", "--show-current").strip()
    assert branch == "kapteyn/development/mvu/feature-x"
    # validate_state passed (merge-base check vs master holds) — no error.
    validate_state(spec)


def test_find_worktree_for_branch_returns_path_when_checked_out(tmp_path: Path):
    """Discovery helper used by the runner before calling ``ensure``: given
    the discovered branch name, return the path of any existing worktree
    on it so the runner can pin spec.path_override there."""
    main, _ = _init_main_with_origin(tmp_path)
    foreign = tmp_path / "manual" / "wt"
    _run(main, "worktree", "add", "-b", "kapteyn/development/mvu/foo", str(foreign), "master")
    found = find_worktree_for_branch(main, "kapteyn/development/mvu/foo")
    assert found is not None
    assert found.resolve() == foreign.resolve()


def test_find_worktree_for_branch_returns_none_when_branch_not_checked_out(tmp_path: Path):
    """When the branch exists locally but no worktree currently has it
    checked out, the helper returns None so the runner falls through to
    creating a fresh worktree at spec.path."""
    main, _ = _init_main_with_origin(tmp_path)
    _run(main, "branch", "kapteyn/development/mvu/unchecked")
    assert find_worktree_for_branch(main, "kapteyn/development/mvu/unchecked") is None
    # Also: completely unknown branch.
    assert find_worktree_for_branch(main, "does/not/exist") is None


def test_ensure_re_bootstraps_managed_worktree_on_re_entry(tmp_path: Path):
    """Stale-worktree heal: a managed worktree created before bootstrap_assets
    shipped (or by an older install that has since been replaced) is missing
    .mcp.json / .claude/. Pass 2 calls ensure(spec) and the assets self-heal.
    Without this, claude sessions in old worktrees silently miss MCP servers,
    skills, and settings until manual intervention."""
    main, _ = _init_main_with_origin(tmp_path)
    _seed_intellij_assets(main)
    spec = _spec(main, tmp_path / "wt")
    path = ensure(spec)

    # Simulate a worktree from before bootstrap shipped: nuke the assets.
    (path / ".mcp.json").unlink()
    shutil.rmtree(path / ".claude")
    shutil.rmtree(path / ".run")
    shutil.rmtree(path / ".idea")

    again = ensure(spec)
    assert again == path
    assert (path / ".mcp.json").read_text(encoding="utf-8") == '{"mcpServers": {}}\n'
    assert (path / ".claude" / "settings.local.json").is_file()
    assert (path / ".claude" / "hooks" / "pre-commit.sh").is_file()
    assert (path / ".run" / "App.run.xml").is_file()
    assert (path / ".idea" / "workspace.xml").is_file()
    porcelain = _run(path, "status", "--porcelain").strip()
    assert porcelain == "", "re-bootstrap must keep tree clean (assets are gitignored)"


def test_ensure_does_not_rebootstrap_path_override_worktree(tmp_path: Path):
    """Foreign path_override worktrees belong to the user (IntelliJ via
    new-task etc.). Re-bootstrap would clobber any .mcp.json / .claude
    the user has tuned for their own session — keep hands off."""
    main, _ = _init_main_with_origin(tmp_path)
    _seed_intellij_assets(main)  # main HAS assets that would otherwise be copied
    foreign = tmp_path / "user" / "feature-Y"
    _run(main, "worktree", "add", "-b", "kapteyn/development/mvu/feature-y", str(foreign), "master")
    # User-tuned .mcp.json in the foreign worktree we must preserve verbatim:
    (foreign / ".mcp.json").write_text('{"mcpServers": {"USER_OWNED": {}}}\n', encoding="utf-8")

    spec = WorktreeSpec(
        repo_root=main,
        worktree_root=tmp_path / "wt",
        parent_id="P2P-6666",
        base_branch="master",
        branch_override="kapteyn/development/mvu/feature-y",
        path_override=foreign,
    )
    ensure(spec)

    assert (foreign / ".mcp.json").read_text(encoding="utf-8") == '{"mcpServers": {"USER_OWNED": {}}}\n'
    # And bootstrap-only assets that main has but foreign didn't never appear:
    assert not (foreign / ".claude").exists()


def test_ensure_auto_recovers_from_dirty_worktree_on_re_entry(tmp_path: Path):
    """Cross-pass crash recovery: pass 1 left the worktree dirty (claude died,
    process killed, etc.). Pass 2 calls ensure(spec) on the same parent and
    must NOT throw — it auto-cleans the dirt and continues. Without this, the
    dirty state would block every subsequent run until manual intervention."""
    main, _ = _init_main_with_origin(tmp_path)
    spec = _spec(main, tmp_path / "wt")
    path = ensure(spec)
    pre_tip = head_sha(spec)

    # Simulate a crashed prior pass
    (path / "half_done.py").write_text("def broken(:\n", encoding="utf-8")
    (path / "README.md").write_text("dirty\n", encoding="utf-8")

    # Re-enter: must not raise, must clean
    again = ensure(spec)
    assert again == path
    assert head_sha(spec) == pre_tip
    assert (path / "README.md").read_text(encoding="utf-8") == "hello\n"
    assert not (path / "half_done.py").exists()
