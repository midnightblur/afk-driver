#!/usr/bin/env afk-python
"""Start a harness inside a linked worktree.

    afk-launch.py <harness> [harness args...]

From the main checkout, or from a worktree on a protected branch, this cuts a new
worktree for the session (from the folder it was started in) and runs the harness
there. From an unprotected linked worktree, or outside a repository, it runs the
harness where it is: no worktree is made. The harness's exit code is returned. A worktree
this command cut is removed when the harness exits, unless it holds work worth keeping
(`scripts/remove-worktree.py`); this process owns it, so a crashed launcher is pruned later.
"""
from __future__ import annotations

import importlib.util
import os
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLUGIN_ROOT = HERE.parent
sys.path.insert(0, str(PLUGIN_ROOT / "hooks" / "lib"))
import protected_branch_guard as guard  # noqa: E402


def needs_worktree(where: Path) -> bool:
    place = guard.placement(where)
    return place is not None and guard.Judge("").verdict(place) is not None


def own_process() -> str:
    """`<pid>:<creation time>` of this launcher, the owner its worktree is recorded under."""
    spec = importlib.util.spec_from_file_location("afk_worktree_owner", HERE / "worktree_owner.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    ctime = module.creation_time(os.getpid())
    return f"{os.getpid()}:{ctime}" if ctime else ""


def cut(where: Path, provider: str) -> Path:
    spec = importlib.util.spec_from_file_location("afk_run_hook", PLUGIN_ROOT / "hooks" / "run-hook.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    shell = module.find_bash() or shutil.which("bash")
    if shell is None:
        raise RuntimeError("no POSIX shell to run create-worktree")
    env = dict(os.environ, AFK_PLUGIN_ROOT=str(PLUGIN_ROOT))
    own = own_process()
    if own:
        env["AFK_WORKTREE_OWNER"] = own
    if (guard.PROVIDERS / f"{provider}.json").is_file():
        env["AFK_PROVIDER"] = provider
    done = subprocess.run([str(shell), (HERE / "create-worktree").as_posix(), "--name",
                           f"session-{uuid.uuid4().hex[:8]}"], capture_output=True, encoding="utf-8", errors="replace", cwd=where, env=env,
                          timeout=900)
    found = re.findall(r"^WORKTREE_PATH=(.+)$", done.stdout, re.M)
    if done.returncode != 0 or not found:
        raise RuntimeError(done.stderr.strip() or "create-worktree made no worktree")
    return Path(found[-1].strip())


def main(argv: list[str]) -> int:
    if not argv:
        sys.stderr.write(__doc__ or "")
        return 2
    where = Path.cwd()
    made = None
    provider = re.sub(r"\.(exe|cmd|bat)$", "", Path(argv[0]).name.lower())
    try:
        if needs_worktree(where):
            where = made = cut(where, provider)
            sys.stderr.write(f"afk: starting {argv[0]} in the new worktree {where}\n")
    except Exception as problem:
        sys.stderr.write(f"afk: no worktree was made ({problem}); not starting {argv[0]} in a guarded place.\n")
        return 1
    exe = shutil.which(argv[0])
    if exe is None:
        sys.stderr.write(f"afk: {argv[0]} is not on PATH.\n")
        return 127
    try:
        return subprocess.run([exe, *argv[1:]], cwd=where).returncode
    finally:
        if made is not None:
            own = own_process()  # this launcher is the owner, so removal does not count it as another session
            subprocess.run([sys.executable, str(HERE / "remove-worktree.py"), "--path", str(made)],
                           cwd=made.parent, check=False,
                           env=dict(os.environ, **({"AFK_WORKTREE_OWNER": own} if own else {})))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
