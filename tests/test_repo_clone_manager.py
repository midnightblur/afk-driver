"""Unit tests for repo_clone_manager.

``gh`` and ``git`` subprocesses are faked through the injected ``GhRunner``;
no network, no real cloning. Coverage per ST03 spec:

- clone-when-absent → invokes ``gh repo clone`` once
- no-op when already cloned → invokes ``git fetch`` instead of re-cloning
- refuse-when-destination-is-not-git → typed error, no subprocess call
- clone-failure-surfaces-as-typed-error → non-zero exit and timeout both wrap
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Callable

import pytest

from afk_driver.repo_clone_manager import (
    GhRunner,
    RepoCloneError,
    ensure_clone,
)


def _proc(returncode: int, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=["gh"], returncode=returncode, stdout=stdout, stderr=stderr
    )


class FakeRunner:
    """Pattern mirrors ``tests/test_gitlab_client.FakeRunner`` — predicate
    list keyed by argv shape, with call recording for assertions."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self._responses: list[
            tuple[Callable[[list[str]], bool], subprocess.CompletedProcess]
        ] = []
        self._raise: dict[int, BaseException] = {}

    def add(
        self,
        predicate: Callable[[list[str]], bool],
        response: subprocess.CompletedProcess,
    ) -> None:
        self._responses.append((predicate, response))

    def raise_on_call(self, call_index: int, exc: BaseException) -> None:
        """Make the Nth call (0-indexed) raise instead of returning."""
        self._raise[call_index] = exc

    def __call__(self, args: list[str]) -> subprocess.CompletedProcess:
        idx = len(self.calls)
        self.calls.append(args)
        if idx in self._raise:
            raise self._raise[idx]
        for pred, resp in self._responses:
            if pred(args):
                return resp
        raise AssertionError(f"FakeRunner: no handler for {args}")


# ---------------------------------------------------------------------------
# clone-when-absent
# ---------------------------------------------------------------------------


def test_ensure_clone_runs_gh_repo_clone_when_destination_absent(tmp_path: Path):
    r = FakeRunner()
    r.add(lambda a: a[:3] == ["gh", "repo", "clone"], _proc(0))

    result = ensure_clone("octo", "widget", tmp_path, runner=r)

    expected = (tmp_path / "github" / "octo" / "widget").resolve()
    assert result == expected
    assert len(r.calls) == 1
    assert r.calls[0][:4] == ["gh", "repo", "clone", "octo/widget"]
    assert r.calls[0][4] == str(expected)


def test_ensure_clone_creates_parent_directory(tmp_path: Path):
    r = FakeRunner()
    r.add(lambda a: a[:3] == ["gh", "repo", "clone"], _proc(0))

    ensure_clone("acme", "thing", tmp_path, runner=r)

    # ``gh repo clone`` itself creates the leaf in the real world; we only
    # need to verify the parent exists so the subprocess does not fail with
    # "no such directory".
    assert (tmp_path / "github" / "acme").is_dir()


# ---------------------------------------------------------------------------
# idempotent rerun
# ---------------------------------------------------------------------------


def test_ensure_clone_runs_git_fetch_when_destination_already_cloned(tmp_path: Path):
    dest = tmp_path / "github" / "octo" / "widget"
    (dest / ".git").mkdir(parents=True)

    r = FakeRunner()
    r.add(lambda a: a[0] == "git" and "fetch" in a, _proc(0))

    result = ensure_clone("octo", "widget", tmp_path, runner=r)

    assert result == dest.resolve()
    assert len(r.calls) == 1
    assert r.calls[0][0] == "git"
    assert "fetch" in r.calls[0]
    # Critically: no ``gh repo clone`` invocation.
    assert not any(call[:3] == ["gh", "repo", "clone"] for call in r.calls)


def test_ensure_clone_treats_git_file_as_valid_repo(tmp_path: Path):
    """``.git`` can be a file in linked worktrees — still a valid repo."""
    dest = tmp_path / "github" / "octo" / "linked"
    dest.mkdir(parents=True)
    (dest / ".git").write_text("gitdir: ../../real/.git\n")

    r = FakeRunner()
    r.add(lambda a: a[0] == "git", _proc(0))

    ensure_clone("octo", "linked", tmp_path, runner=r)
    assert r.calls[0][0] == "git"


# ---------------------------------------------------------------------------
# refuse-when-destination-is-not-git
# ---------------------------------------------------------------------------


def test_ensure_clone_refuses_when_destination_exists_but_is_not_git(tmp_path: Path):
    dest = tmp_path / "github" / "octo" / "stray"
    dest.mkdir(parents=True)
    (dest / "README.md").write_text("not a git repo")

    r = FakeRunner()
    # No predicates added — any subprocess call would fail the test.

    with pytest.raises(RepoCloneError, match="not a git repository"):
        ensure_clone("octo", "stray", tmp_path, runner=r)

    # Defence-in-depth: refusal must happen before any subprocess call.
    assert r.calls == []


# ---------------------------------------------------------------------------
# clone-failure-surfaces-as-typed-error
# ---------------------------------------------------------------------------


def test_ensure_clone_wraps_non_zero_exit_as_repo_clone_error(tmp_path: Path):
    r = FakeRunner()
    r.add(
        lambda a: a[:3] == ["gh", "repo", "clone"],
        _proc(1, stderr="GraphQL: Could not resolve to a Repository"),
    )

    with pytest.raises(RepoCloneError, match="gh repo clone octo/missing failed"):
        ensure_clone("octo", "missing", tmp_path, runner=r)


def test_ensure_clone_wraps_timeout_as_repo_clone_error(tmp_path: Path):
    r = FakeRunner()
    r.raise_on_call(0, subprocess.TimeoutExpired(cmd=["gh"], timeout=120))

    with pytest.raises(RepoCloneError, match="timed out"):
        ensure_clone("octo", "huge", tmp_path, runner=r)


def test_ensure_clone_wraps_fetch_failure_on_idempotent_rerun(tmp_path: Path):
    dest = tmp_path / "github" / "octo" / "widget"
    (dest / ".git").mkdir(parents=True)

    r = FakeRunner()
    r.add(
        lambda a: a[0] == "git",
        _proc(1, stderr="fatal: unable to access remote"),
    )

    with pytest.raises(RepoCloneError, match="git fetch"):
        ensure_clone("octo", "widget", tmp_path, runner=r)


def test_ensure_clone_wraps_fetch_timeout_on_idempotent_rerun(tmp_path: Path):
    dest = tmp_path / "github" / "octo" / "widget"
    (dest / ".git").mkdir(parents=True)

    r = FakeRunner()
    r.raise_on_call(0, subprocess.TimeoutExpired(cmd=["git"], timeout=60))

    with pytest.raises(RepoCloneError, match="timed out"):
        ensure_clone("octo", "widget", tmp_path, runner=r)


# ---------------------------------------------------------------------------
# typing surface
# ---------------------------------------------------------------------------


def test_gh_runner_type_is_exported():
    """ST03 ``Produces`` declares ``GhRunner`` as a public symbol."""
    # Trivial smoke — ensures the alias resolves and is callable-typed.
    assert GhRunner is not None
    runner: GhRunner = lambda args: _proc(0)  # noqa: E731
    assert runner(["gh"]).returncode == 0
