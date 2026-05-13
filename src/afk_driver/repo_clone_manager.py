"""Idempotent ``gh repo clone`` wrapper.

Bottom-of-stack module per the SDD §8 onion DAG — no dependency on
``tracker_protocol`` / ``scm_protocol`` / ``runner``. Used by the multi-repo
queue discovery pre-flight (ADR-0003) to ensure each owner/repo pair
referenced in the queue is locally available before ``worktree_manager``
attempts to carve a per-Enhancement worktree inside it.

The ``GhRunner`` callable is injected so tests can stub the subprocess —
mirrors the ``GlabRunner`` pattern in ``gitlab_client``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Callable


# Generous per SDD §5 retry table — large repos on slow links may legitimately
# take a while; we accept the tail-latency cost on first encounter.
_CLONE_TIMEOUT_SECONDS = 120

# git fetch on an already-cloned repo is cheap; cap it tighter so a hung
# remote does not block the entire pre-flight pass.
_FETCH_TIMEOUT_SECONDS = 60


class RepoCloneError(RuntimeError):
    """Raised when ``gh repo clone`` or ``git fetch`` fails, times out, or the
    destination path exists but is not a git working tree.

    Per ADR-0003 the caller (multi-repo pre-flight) catches this, marks the
    repo failed, emits a digest entry, and continues with the next repo —
    isolation, not halt.
    """


GhRunner = Callable[[list[str]], subprocess.CompletedProcess]


def _default_runner(args: list[str]) -> subprocess.CompletedProcess:
    """Default runner — shells out to the host's ``gh`` / ``git`` CLI.

    ``args[0]`` is the executable name (``gh`` or ``git``); the remainder are
    its arguments. ``check`` is left False so the caller decides how to surface
    non-zero exits — keeps the error message in our domain vocabulary.
    """
    timeout = _CLONE_TIMEOUT_SECONDS if args and args[0] == "gh" else _FETCH_TIMEOUT_SECONDS
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def _is_git_repo(path: Path) -> bool:
    """A directory is a valid git working tree iff it contains a ``.git``
    entry (directory in normal clones; file in worktree-linked checkouts)."""
    return (path / ".git").exists()


def ensure_clone(
    owner: str,
    repo: str,
    root: Path,
    runner: GhRunner = _default_runner,
) -> Path:
    """Ensure ``{root}/github/{owner}/{repo}`` is a cloned working tree;
    return its absolute path.

    Behaviour per ADR-0003 + SDD §5 idempotency table:

    - Destination absent → ``gh repo clone {owner}/{repo} {dest}`` once.
    - Destination present and is a git repo → ``git fetch`` to refresh
      remote-tracking refs; no re-clone.
    - Destination present but NOT a git repo → ``RepoCloneError``. Refuse to
      operate on foreign directories — the user may have a manually-managed
      checkout there and silently re-cloning would clobber it.

    Subprocess failures (non-zero exit, timeout) are wrapped as
    ``RepoCloneError`` so the caller can isolate per-repo without catching
    raw subprocess types.
    """
    dest = (root / "github" / owner / repo).resolve()

    if dest.exists():
        if not _is_git_repo(dest):
            raise RepoCloneError(
                f"{dest} exists but is not a git repository — refusing to clone over it"
            )
        try:
            proc = runner(["git", "-C", str(dest), "fetch", "--all", "--prune"])
        except subprocess.TimeoutExpired as e:
            raise RepoCloneError(
                f"git fetch in {dest} timed out after {_FETCH_TIMEOUT_SECONDS}s"
            ) from e
        if proc.returncode != 0:
            raise RepoCloneError(
                f"git fetch in {dest} failed: {proc.stderr.strip()}"
            )
        return dest

    # First encounter — clone via gh so auth + protocol selection follow the
    # user's existing gh configuration (ADR-0003 alternative B).
    dest.parent.mkdir(parents=True, exist_ok=True)
    slug = f"{owner}/{repo}"
    try:
        proc = runner(["gh", "repo", "clone", slug, str(dest)])
    except subprocess.TimeoutExpired as e:
        raise RepoCloneError(
            f"gh repo clone {slug} timed out after {_CLONE_TIMEOUT_SECONDS}s"
        ) from e
    if proc.returncode != 0:
        raise RepoCloneError(
            f"gh repo clone {slug} failed: {proc.stderr.strip()}"
        )
    return dest
