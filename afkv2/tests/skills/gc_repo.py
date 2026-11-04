"""The scratch repository the gc tests share: a bare remote, a main checkout, a feature worktree, and an orphan run branch in its run worktree."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

MAIN = "main"
FEATURE = "feat/gc"
RUN = FEATURE + "-run"


def git(cwd, *args):
    done = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                          stdin=subprocess.DEVNULL, timeout=60)
    assert done.returncode == 0, f"git {args}: {done.stderr}"
    return done.stdout.strip()


@dataclass
class GcRepo:
    remote: Path
    main: Path
    feature: Path
    run: Path
    feature_branch: str = FEATURE
    run_branch: str = RUN

    def commit(self, worktree, name, text, message):
        """Commit one file in a worktree; answer the new commit id."""
        path = Path(worktree) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        git(worktree, "add", name)
        git(worktree, "commit", "-qm", message)
        return git(worktree, "rev-parse", "HEAD")


def build_gc_repo(root):
    """Under `root`: `remote.git`, `main` on `main`, `feature` on `feat/gc`, `feature-run` on the orphan `feat/gc-run`. Every branch is pushed."""
    root = Path(root)
    remote, main, feature = root / "remote.git", root / "main", root / "feature"
    run = Path(str(feature) + "-run")
    main.mkdir(parents=True)
    git(root, "init", "-q", "--bare", "-b", MAIN, str(remote))
    git(main, "init", "-q", "-b", MAIN)
    for key, value in (("user.name", "t"), ("user.email", "t@t.test"), ("commit.gpgsign", "false")):
        git(main, "config", key, value)
    git(main, "remote", "add", "origin", str(remote))
    repo = GcRepo(remote, main, feature, run)
    repo.commit(main, "README.md", "a repository\n", "start")
    git(main, "push", "-qu", "origin", MAIN)
    git(main, "worktree", "add", "-q", "-b", FEATURE, str(feature))
    repo.commit(feature, "feature.txt", "the feature\n", "the feature")
    git(feature, "push", "-qu", "origin", FEATURE)
    git(main, "worktree", "add", "-q", "--detach", str(run))
    git(run, "checkout", "-q", "--orphan", RUN)
    git(run, "rm", "-rfq", ".")
    repo.commit(run, "plan/PLAN.md", "# plan\n", "plan")
    git(run, "push", "-qu", "origin", RUN)
    return repo
