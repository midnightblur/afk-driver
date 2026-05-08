"""MonorepoBuilder + MonorepoFixture — per-test git scaffold for scenarios.

Builds a real bare remote + working clone with the requested files committed
on master and pushed. The scenario harness uses this so the real
``worktree_manager`` operates against deterministic git state.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MonorepoFixture:
    repo_root: Path
    bare_remote: Path
    initial_head: str
    master_branch: str = "master"


class MonorepoBuilder:
    def __init__(self, master_branch: str = "master") -> None:
        self._files: dict[str, str] = {
            "README.md": "afk fixture\n",
        }
        self._master = master_branch

    def with_file(self, relative_path: str, content: str) -> "MonorepoBuilder":
        self._files[relative_path] = content
        return self

    def build(self, tmp_path: Path) -> MonorepoFixture:
        origin = tmp_path / "origin.git"
        repo = tmp_path / "repo"
        repo.mkdir(parents=True)
        _run(tmp_path, "git", "init", "--bare", "-q", "-b", self._master, str(origin))
        _run(repo, "git", "init", "-q", "-b", self._master)
        _run(repo, "git", "config", "user.email", "afk@test")
        _run(repo, "git", "config", "user.name", "afk")
        _run(repo, "git", "remote", "add", "origin", str(origin))
        for rel, content in self._files.items():
            target = repo / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        _run(repo, "git", "add", "-A")
        _run(repo, "git", "commit", "-q", "-m", "init")
        head = _run(repo, "git", "rev-parse", "HEAD").strip()
        _run(repo, "git", "push", "-q", "-u", "origin", self._master)
        return MonorepoFixture(
            repo_root=repo,
            bare_remote=origin,
            initial_head=head,
            master_branch=self._master,
        )


def _run(cwd: Path, *args: str) -> str:
    proc = subprocess.run(
        list(args),
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"command {args!r} in {cwd} failed: {proc.stderr.strip()}"
        )
    return proc.stdout
