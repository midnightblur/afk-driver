"""GitLabWorld — in-memory state for ``glab`` MR operations.

Models the subset of ``glab mr {view,list,create,update}`` that
``afk_driver.gitlab_client.GitLabClient`` actually invokes. ``FakeGlabRunner``
parses the argv list the client passes and returns a
``subprocess.CompletedProcess`` with the JSON shape that real ``glab`` emits.

Not a glab simulator — a regression simulator. Adds rules only when a real
``glab`` shape has previously broken the driver.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class _MR:
    iid: int
    web_url: str
    state: str
    title: str
    description: str
    source_branch: str
    target_branch: str

    def to_json(self) -> dict:
        return {
            "iid": self.iid,
            "web_url": self.web_url,
            "state": self.state,
            "title": self.title,
            "description": self.description,
            "source_branch": self.source_branch,
            "target_branch": self.target_branch,
        }


@dataclass
class GitLabWorld:
    mrs: list[_MR] = field(default_factory=list)
    _next_iid: int = 100
    _base_url: str = "https://gitlab.example.com/group/project/-/merge_requests"

    def seed_existing_mr(
        self,
        *,
        source_branch: str,
        target_branch: str,
        title: str,
        description: str = "",
        state: str = "opened",
    ) -> _MR:
        mr = _MR(
            iid=self._next_iid,
            web_url=f"{self._base_url}/{self._next_iid}",
            state=state,
            title=title,
            description=description,
            source_branch=source_branch,
            target_branch=target_branch,
        )
        self._next_iid += 1
        self.mrs.append(mr)
        return mr

    def find_by_branch(self, branch: str) -> Optional[_MR]:
        for mr in self.mrs:
            if mr.source_branch == branch and mr.state == "opened":
                return mr
        return None

    def __call__(self, args: list[str]) -> subprocess.CompletedProcess:
        return _dispatch(self, list(args))


# Backwards-compat alias used in tests for clarity.
FakeGlabRunner = GitLabWorld


def _ok(stdout: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")


def _err(stderr: str, returncode: int = 1) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout="", stderr=stderr)


def _dispatch(world: GitLabWorld, args: list[str]) -> subprocess.CompletedProcess:
    if len(args) < 2 or args[0] != "mr":
        return _err(f"fake-glab: unsupported args {args!r}")
    sub = args[1]
    rest = args[2:]
    if sub == "view":
        return _handle_view(world, rest)
    if sub == "list":
        return _handle_list(world, rest)
    if sub == "create":
        return _handle_create(world, rest)
    if sub == "update":
        return _handle_update(world, rest)
    return _err(f"fake-glab: unsupported subcommand {sub!r}")


def _handle_view(world: GitLabWorld, rest: list[str]) -> subprocess.CompletedProcess:
    if not rest:
        return _err("fake-glab mr view: missing branch")
    branch = rest[0]
    mr = world.find_by_branch(branch)
    if mr is None:
        return _err(f"glab error: 404 not found for {branch}", returncode=1)
    return _ok(json.dumps(mr.to_json()))


def _handle_list(world: GitLabWorld, rest: list[str]) -> subprocess.CompletedProcess:
    search_token: Optional[str] = None
    i = 0
    while i < len(rest):
        if rest[i] == "--search" and i + 1 < len(rest):
            search_token = rest[i + 1]
            i += 2
            continue
        i += 1
    items = [
        mr.to_json()
        for mr in world.mrs
        if search_token is None or search_token in mr.title or search_token in mr.description
    ]
    return _ok(json.dumps(items))


def _handle_create(world: GitLabWorld, rest: list[str]) -> subprocess.CompletedProcess:
    flags = _flags(rest)
    required = ("--source-branch", "--target-branch", "--title", "--description")
    missing = [f for f in required if f not in flags]
    if missing:
        return _err(f"fake-glab mr create: missing flags {missing}")
    if "--draft" not in rest:
        return _err("fake-glab mr create: AFK driver must always pass --draft")
    if "--yes" not in rest:
        return _err("fake-glab mr create: missing --yes (would prompt)")
    source = flags["--source-branch"]
    if world.find_by_branch(source) is not None:
        return _err(f"fake-glab mr create: MR already open for {source}")
    mr = _MR(
        iid=world._next_iid,
        web_url=f"{world._base_url}/{world._next_iid}",
        state="opened",
        title=flags["--title"],
        description=flags["--description"],
        source_branch=source,
        target_branch=flags["--target-branch"],
    )
    world._next_iid += 1
    world.mrs.append(mr)
    return _ok(json.dumps(mr.to_json()))


def _handle_update(world: GitLabWorld, rest: list[str]) -> subprocess.CompletedProcess:
    if not rest:
        return _err("fake-glab mr update: missing branch")
    branch = rest[0]
    flags = _flags(rest[1:])
    mr = world.find_by_branch(branch)
    if mr is None:
        return _err(f"fake-glab mr update: no MR for {branch}")
    if "--description" in flags:
        mr.description = flags["--description"]
    return _ok(json.dumps(mr.to_json()))


def _flags(args: list[str]) -> dict[str, str]:
    """Pair --flag value tokens into a dict. Bare flags map to empty string."""
    out: dict[str, str] = {}
    i = 0
    while i < len(args):
        tok = args[i]
        if tok.startswith("--"):
            if i + 1 < len(args) and not args[i + 1].startswith("--"):
                out[tok] = args[i + 1]
                i += 2
                continue
            out[tok] = ""
        i += 1
    return out
