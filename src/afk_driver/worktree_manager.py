"""Per-Enhancement git worktree lifecycle.

Wraps ``git worktree add``, status checks, and the post-last-SubTask rebase
against the parent Enhancement's resolved Target Branch. Pure subprocess; no
Jira / GitLab calls live here.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional


class WorktreeError(RuntimeError):
    """Raised when the worktree state is unsafe to operate on."""


@dataclass(frozen=True)
class WorktreeSpec:
    """Per-Enhancement git worktree descriptor.

    ``branch_override`` and ``path_override`` exist so the runner can point
    the driver at a branch/worktree the user created by hand (Nakisa
    convention: ``kapteyn/development/mvu/{slug}``) instead of always
    minting a fresh ``mvu/afk/{parent_id}`` branch under the managed
    worktree root. When unset, the template branch + managed path apply.
    """
    repo_root: Path
    worktree_root: Path
    parent_id: str
    base_branch: str
    branch_template: str = "mvu/afk/{parent_id}"
    branch_override: Optional[str] = None
    path_override: Optional[Path] = None

    @property
    def branch(self) -> str:
        if self.branch_override:
            return self.branch_override
        # GitLab branch-name pattern is ^[a-z0-9][a-z0-9\/\-\.]*$ — Jira keys
        # like "P2P-1229" are uppercase, so lowercase the parent_id segment.
        return self.branch_template.format(parent_id=self.parent_id.lower())

    @property
    def path(self) -> Path:
        if self.path_override is not None:
            return self.path_override
        return self.worktree_root / self.parent_id


RebaseOutcome = Literal["clean", "conflict"]


def ensure(spec: WorktreeSpec) -> Path:
    """Create the worktree when absent; validate when present. Returns the path.

    Three creation paths, in order of precedence:

    1. ``spec.path`` already exists — treat as a returning worktree: discard
       any uncommitted leftover (``reset_to_clean``), validate, return. The
       reset is safe because completed SubTasks always commit before the
       runner moves on (auto-commit safety net in
       ``runner._process_subtask``), so dirt at this point is by definition
       not part of a completed SubTask. Without it, a crash that left the
       tree dirty (claude server died, process killed) would block every
       subsequent pass until manual intervention.

    2. The branch (``spec.branch``) already exists locally or on
       ``origin`` — check it out into a fresh worktree at ``spec.path``.
       This is the "user prepped a feature branch by hand" path; the AFK
       driver must continue work on that branch instead of minting a new
       ``mvu/afk/{parent_id}`` one.

    3. Branch is brand-new — ``git worktree add -b BRANCH PATH BASE`` as
       before.

    Asset bootstrap (``bootstrap_assets``) runs only when this call actually
    creates the worktree directory; reusing an existing path leaves the
    user's tooling config intact.
    """
    if spec.path.exists():
        reset_to_clean(spec)
        validate_state(spec)
        return spec.path
    spec.worktree_root.mkdir(parents=True, exist_ok=True)
    if _branch_exists_local(spec.repo_root, spec.branch):
        _git_check(
            spec.repo_root,
            ["worktree", "add", str(spec.path), spec.branch],
        )
    elif _branch_exists_remote(spec.repo_root, spec.branch):
        # Pull the ref into the local repo so worktree add can resolve it.
        _git_check(spec.repo_root, ["fetch", "origin", spec.branch])
        _git_check(
            spec.repo_root,
            [
                "worktree", "add", "--track",
                "-b", spec.branch, str(spec.path), f"origin/{spec.branch}",
            ],
        )
    else:
        _git_check(
            spec.repo_root,
            ["worktree", "add", "-b", spec.branch, str(spec.path), spec.base_branch],
        )
    bootstrap_assets(spec.repo_root, spec.path)
    return spec.path


def find_worktree_for_branch(repo_root: Path, branch: str) -> Optional[Path]:
    """Return the path of the existing worktree checked out on ``branch``,
    or ``None`` if no worktree currently has that branch.

    Used by the runner to detect a user-created worktree that lives outside
    the managed ``~/.afk-driver/worktrees/{ID}/`` root, so the driver can
    reuse it in place rather than refusing or duplicating.

    Parses ``git worktree list --porcelain``: each record is a sequence of
    ``key value\\n`` lines (``worktree``, ``HEAD``, ``branch``, etc.)
    terminated by a blank line. The ``branch`` line for a checked-out
    worktree is ``branch refs/heads/NAME``; detached worktrees have no
    ``branch`` line at all (skipped).
    """
    if not repo_root.is_dir():
        return None
    proc = _git_run(repo_root, ["worktree", "list", "--porcelain"])
    if proc.returncode != 0:
        return None
    target_ref = f"refs/heads/{branch}"
    current_path: Optional[str] = None
    for line in proc.stdout.splitlines():
        if line.startswith("worktree "):
            current_path = line[len("worktree "):].strip()
        elif line.startswith("branch "):
            ref = line[len("branch "):].strip()
            if ref == target_ref and current_path:
                return Path(current_path)
        elif not line.strip():
            current_path = None
    return None


def _branch_exists_local(repo_root: Path, branch: str) -> bool:
    proc = _git_run(
        repo_root, ["rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"]
    )
    return proc.returncode == 0


def _branch_exists_remote(repo_root: Path, branch: str) -> bool:
    """Check ``origin`` for ``branch`` without mutating local state.

    ``ls-remote`` queries the remote directly — no fetch, no local ref
    update — so we can answer "does origin have this branch?" cheaply
    before committing to a fetch + worktree add.
    """
    proc = _git_run(
        repo_root, ["ls-remote", "--exit-code", "--heads", "origin", branch]
    )
    return proc.returncode == 0


def bootstrap_assets(repo_root: Path, worktree_path: Path) -> None:
    """Copy IntelliJ + Claude Code config assets from main checkout to a fresh worktree.

    Mirrors the asset-copy steps in ``~/bin/new-task`` so AFK-managed worktrees
    pick up the same hooks, MCP servers, run-configs, and IntelliJ project files
    as a manually-bootstrapped worktree. We do NOT run npm install and we do NOT
    launch IntelliJ — the AFK runner spawns a headless ``claude`` subprocess and
    must not pop a UI.

    Assets, all gitignored in the main repo:
      - ``.mcp.json`` — Claude Code project-scoped MCP servers
      - ``.claude/`` — hooks, settings, skills, rules
      - ``.run/`` — IntelliJ run configurations (path-substituted)
      - ``.idea/`` — IntelliJ project (workspace.xml path-substituted; ``.name``
        marks it as a portable project so IntelliJ doesn't reuse the main
        checkout's project identity)

    Plus every ``CLAUDE.md`` at any depth (root + nested) is copied from the
    main checkout into the worktree at the same relative path *if missing*
    in the worktree. Committed CLAUDE.md files arrive via ``git worktree
    add`` and are left untouched (overwriting would dirty the worktree and
    break ``validate_state``); the fill-in only matters for gitignored or
    untracked CLAUDE.md (e.g. ``CLAUDE.local.md`` conventions, scratch
    instructions) so Claude in the worktree gets the same instruction set
    as the main checkout.

    Silently skips any asset that doesn't exist in ``repo_root``. Path
    substitution covers both forward-slash and backslash forms of the repo path
    so XML files written on Windows or *nix both get rewritten correctly.
    """
    _copy_file_if_exists(repo_root / ".mcp.json", worktree_path / ".mcp.json")
    _copy_dir_if_exists(repo_root / ".claude", worktree_path / ".claude")
    _copy_with_path_substitution(
        repo_root / ".run", worktree_path / ".run", repo_root, worktree_path,
        substitute_filenames=None,
    )
    _copy_with_path_substitution(
        repo_root / ".idea", worktree_path / ".idea", repo_root, worktree_path,
        substitute_filenames={"workspace.xml"},
    )
    idea_dir = worktree_path / ".idea"
    if idea_dir.is_dir():
        (idea_dir / ".name").write_text(worktree_path.name, encoding="utf-8")
    _copy_claude_md_recursive(repo_root, worktree_path)


# Dirs we never recurse into when scanning for CLAUDE.md — both for speed and
# to avoid double-copying paths already handled by the asset bootstrap above
# (.claude/ gets dir-copied wholesale; .git holds the worktree's git plumbing,
# never source instructions; the rest are common build/cache dirs that should
# never own a CLAUDE.md and would dominate walk time on large repos).
_CLAUDE_MD_SKIP_DIRS = frozenset({
    ".git", ".claude", ".idea", ".run",
    "node_modules", "target", "dist", "build", "out",
    "__pycache__", ".venv", "venv", ".tox", ".mypy_cache", ".pytest_cache",
})


def _copy_claude_md_recursive(repo_root: Path, worktree_path: Path) -> None:
    """Fill in any ``CLAUDE.md`` at any depth that exists in the main
    checkout but not in the worktree. Skips heavy / irrelevant dirs (see
    ``_CLAUDE_MD_SKIP_DIRS``) and never recurses into the worktree itself
    if it happens to live under the repo root.

    Skip-if-present is deliberate: a committed CLAUDE.md is already on disk
    in the worktree (placed by ``git worktree add``) and overwriting it
    with the main checkout's working-tree copy would mark the worktree
    dirty, breaking ``validate_state`` on the next pass. The realistic
    win here is gitignored / untracked CLAUDE.md files (e.g. local
    instructions) that ``git worktree add`` would never bring across.
    """
    if not repo_root.is_dir():
        return
    repo_root_resolved = repo_root.resolve()
    worktree_resolved = worktree_path.resolve()
    for dirpath, dirnames, filenames in os.walk(repo_root_resolved):
        dirnames[:] = [
            d for d in dirnames
            if d not in _CLAUDE_MD_SKIP_DIRS
            and (Path(dirpath) / d).resolve() != worktree_resolved
        ]
        if "CLAUDE.md" not in filenames:
            continue
        src = Path(dirpath) / "CLAUDE.md"
        rel = src.relative_to(repo_root_resolved)
        dst = worktree_resolved / rel
        if dst.exists():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def _copy_file_if_exists(src: Path, dst: Path) -> None:
    if src.is_file():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def _copy_dir_if_exists(src: Path, dst: Path) -> None:
    if src.is_dir():
        shutil.copytree(src, dst, dirs_exist_ok=True)


def _copy_with_path_substitution(
    src_dir: Path,
    dst_dir: Path,
    repo_root: Path,
    worktree_path: Path,
    substitute_filenames: set[str] | None,
) -> None:
    """Copy ``src_dir`` -> ``dst_dir``. Files in ``substitute_filenames`` (or
    all files when None) get repo_root path occurrences rewritten to
    worktree_path. Both forward-slash and backslash forms are rewritten."""
    if not src_dir.is_dir():
        return
    dst_dir.mkdir(parents=True, exist_ok=True)
    repo_fwd = str(repo_root).replace("\\", "/")
    repo_back = str(repo_root).replace("/", "\\")
    wt_fwd = str(worktree_path).replace("\\", "/")
    wt_back = str(worktree_path).replace("/", "\\")
    for entry in src_dir.iterdir():
        target = dst_dir / entry.name
        if entry.is_dir():
            shutil.copytree(entry, target, dirs_exist_ok=True)
            continue
        if substitute_filenames is None or entry.name in substitute_filenames:
            text = entry.read_text(encoding="utf-8", errors="replace")
            text = text.replace(repo_fwd, wt_fwd).replace(repo_back, wt_back)
            target.write_text(text, encoding="utf-8")
        else:
            shutil.copy2(entry, target)


def validate_state(spec: WorktreeSpec) -> None:
    """Refuse on: not a worktree, wrong branch, dirty tree, branch not rooted in base."""
    if not spec.path.exists():
        raise WorktreeError(f"{spec.path} does not exist")
    if not (spec.path / ".git").exists():
        raise WorktreeError(f"{spec.path} is not a git working tree")
    current = _git_check(spec.path, ["branch", "--show-current"]).strip()
    if current != spec.branch:
        raise WorktreeError(
            f"worktree {spec.path} on branch {current!r}, expected {spec.branch!r}"
        )
    porcelain = _git_check(spec.path, ["status", "--porcelain"]).strip()
    if porcelain:
        raise WorktreeError(f"worktree {spec.path} is dirty:\n{porcelain}")
    proc = _git_run(spec.path, ["merge-base", spec.branch, spec.base_branch])
    if proc.returncode != 0 or not proc.stdout.strip():
        raise WorktreeError(
            f"worktree branch {spec.branch!r} is not based off {spec.base_branch!r}"
        )


def publish_branch(spec: WorktreeSpec) -> None:
    """Push the worktree's branch to origin with upstream tracking.

    Idempotent: safe to call when the remote already has the branch (no-op
    fast-forward). Required before ``glab mr create`` — GitLab rejects MRs
    whose ``source_branch`` only exists locally.
    """
    validate_state(spec)
    _git_check(spec.path, ["push", "--set-upstream", "origin", spec.branch])


def commit_dirty_changes(spec: WorktreeSpec, message: str) -> bool:
    """Stage all tracked + untracked files in the worktree and commit them.

    Tolerates a dirty tree (that's the point — used as a safety net after a
    spawned ``claude /afk-go`` session edits files but exits without
    committing). Returns True if a commit was created, False if there was
    nothing to commit. Branch identity is still checked so the runner can't
    accidentally commit into the wrong worktree.
    """
    if not spec.path.exists():
        raise WorktreeError(f"{spec.path} does not exist")
    current = _git_check(spec.path, ["branch", "--show-current"]).strip()
    if current != spec.branch:
        raise WorktreeError(
            f"worktree {spec.path} on branch {current!r}, expected {spec.branch!r}"
        )
    porcelain = _git_check(spec.path, ["status", "--porcelain"]).strip()
    if not porcelain:
        return False
    _git_check(spec.path, ["add", "-A"])
    _git_check(spec.path, ["commit", "-m", message])
    return True


def head_sha(spec: WorktreeSpec) -> str:
    """Return the current HEAD commit SHA for the worktree's branch."""
    if not spec.path.exists():
        raise WorktreeError(f"{spec.path} does not exist")
    return _git_check(spec.path, ["rev-parse", "HEAD"]).strip()


def reset_to_clean(spec: WorktreeSpec) -> bool:
    """Discard any uncommitted state in the worktree; return True if it had any.

    Hard-resets the index + working tree to ``HEAD`` and removes untracked
    files / dirs (``git reset --hard HEAD`` + ``git clean -fd``). HEAD itself
    is unchanged — only uncommitted work goes away. Used as a recovery hook
    when a prior pass left the worktree dirty (claude server died, OS killed
    the process, machine rebooted mid-session): the contract is "completed
    SubTasks must be committed before the next starts", so a dirty tree at
    SubTask boundary means the prior SubTask did NOT complete cleanly and
    its leftovers are noise — claude has no way to safely resume partial
    edits, so the deterministic recovery is to start from HEAD.

    Branch identity is verified first so the runner cannot accidentally nuke
    work on a wrong branch the user manually checked out into the worktree
    path.
    """
    if not spec.path.exists():
        raise WorktreeError(f"{spec.path} does not exist")
    current = _git_check(spec.path, ["branch", "--show-current"]).strip()
    if current != spec.branch:
        raise WorktreeError(
            f"worktree {spec.path} on branch {current!r}, expected {spec.branch!r}"
        )
    porcelain = _git_check(spec.path, ["status", "--porcelain"]).strip()
    if not porcelain:
        return False
    _git_check(spec.path, ["reset", "--hard", "HEAD"])
    _git_check(spec.path, ["clean", "-fd"])
    return True


def push_branch(spec: WorktreeSpec) -> None:
    """Push the worktree's branch to origin without re-validating tree state.

    Lighter-weight than ``publish_branch`` — used after
    ``commit_dirty_changes`` when we know a fresh commit just landed and the
    tree is clean again, but don't need the full pre-flight from
    ``validate_state`` (merge-base etc. already verified once per pass).
    """
    current = _git_check(spec.path, ["branch", "--show-current"]).strip()
    if current != spec.branch:
        raise WorktreeError(
            f"worktree {spec.path} on branch {current!r}, expected {spec.branch!r}"
        )
    _git_check(spec.path, ["push", "--set-upstream", "origin", spec.branch])


def rebase_onto_target(spec: WorktreeSpec) -> RebaseOutcome:
    """Fetch ``base_branch`` from origin and rebase onto it. Aborts on conflict."""
    validate_state(spec)
    _git_check(spec.path, ["fetch", "origin", spec.base_branch])
    proc = _git_run(spec.path, ["rebase", f"origin/{spec.base_branch}"])
    if proc.returncode == 0:
        return "clean"
    _git_run(spec.path, ["rebase", "--abort"])
    return "conflict"


def _git_check(cwd: Path, args: list[str]) -> str:
    proc = _git_run(cwd, args)
    if proc.returncode != 0:
        raise WorktreeError(
            f"git {' '.join(args)} failed in {cwd}: {proc.stderr.strip()}"
        )
    return proc.stdout


def _git_run(cwd: Path, args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
