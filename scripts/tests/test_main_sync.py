"""Main checkout sync (PRD D5/A4): `git pull --ff-only` on a clean base branch, nothing else.

The guard writes a one-shot authorization at PreToolUse; the reference-transaction backstop
consumes it for the one branch update that matches. Disposable repositories only.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import time
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
GUARD = PLUGIN_ROOT / "hooks" / "protected-branch-guard.py"
BACKSTOP = PLUGIN_ROOT / "hooks" / "git-backstop.py"
INSTALLER = PLUGIN_ROOT / "hooks" / "install-git-hooks.sh"
IDENTITY = ("-c", "user.name=t", "-c", "user.email=t@example.com")
AGENT_VARS = ("AFK_PROVIDER", "PLUGIN_ROOT", "CLAUDE_PLUGIN_ROOT", "CLAUDECODE", "AFK_ALLOW_PROTECTED",
              "AFK_WORKTREE_OP", "GH_TOKEN", "GITHUB_TOKEN", "GITLAB_TOKEN", "AFK_GITHUB_API_URL", "AFK_GITLAB_API_URL")


def _bash():
    spec = importlib.util.spec_from_file_location("afk_run_hook", PLUGIN_ROOT / "hooks" / "run-hook.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.find_bash()


BASH = _bash()
pytestmark = pytest.mark.skipif(BASH is None, reason="no POSIX shell on this machine")


def human() -> dict:
    return {k: v for k, v in os.environ.items() if k not in AGENT_VARS}


def agent(**extra: str) -> dict:
    return dict(human(), CLAUDECODE="1", CLAUDE_PLUGIN_ROOT=str(PLUGIN_ROOT), AFK_PLUGIN_ROOT=str(PLUGIN_ROOT),
                AFK_PROVIDER="claude", AFK_MOVE_SPAWN="0", **extra)


def git(cwd: Path, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(cwd), *IDENTITY, *args], capture_output=True, text=True,
                          env=env or human(), timeout=120)


def ok(done: subprocess.CompletedProcess) -> str:
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


def advance(path: Path, name: str = "n") -> str:
    ok(git(path, "commit", "-q", "--allow-empty", "-m", name))
    return ok(git(path, "rev-parse", "HEAD"))


@pytest.fixture
def sync(tmp_path: Path) -> dict:
    """`main`: a clone on `main` tracking origin/main, hooks installed; `up`: the origin, one commit ahead."""
    up = tmp_path / "up"
    up.mkdir()
    ok(git(up, "init", "-q", "-b", "main"))
    advance(up, "a")
    ok(subprocess.run(["git", "clone", "-q", str(up), str(tmp_path / "main")], capture_output=True, text=True,
                      env=human()))
    main = tmp_path / "main"
    done = subprocess.run([str(BASH), INSTALLER.as_posix()], capture_output=True, text=True, cwd=main,
                          env=agent(), timeout=120)
    assert done.returncode == 0, done.stderr
    advance(up, "b")
    return {"up": up, "main": main, "tmp": tmp_path}


def verdict(cwd: Path, command: str, session: str = "s1", **env) -> subprocess.CompletedProcess:
    call = {"session_id": session, "cwd": str(cwd), "hook_event_name": "PreToolUse", "tool_name": "Bash",
            "tool_input": {"command": command}}
    return subprocess.run([os.sys.executable, str(GUARD)], input=json.dumps(call), text=True, capture_output=True,
                          cwd=cwd, env=agent(**env), timeout=120)


def denied(done: subprocess.CompletedProcess) -> bool:
    return done.returncode == 0 and '"permissionDecision": "deny"' in done.stdout


def record_dir(main: Path) -> Path:
    return main / ".git" / "afk-session"


def records(main: Path) -> list[Path]:
    return sorted(record_dir(main).glob("sync-*.json"))


def test_a_clean_base_branch_pull_is_authorized_and_the_real_pull_moves_the_branch(sync):
    main = sync["main"]
    wanted = ok(git(sync["up"], "rev-parse", "HEAD"))
    done = verdict(main, "git pull --ff-only")
    assert not denied(done), done.stderr
    [path] = records(main)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["branch"] == "main" and data["upstream_ref"] == "refs/remotes/origin/main"
    assert data["old"] == ok(git(main, "rev-parse", "HEAD")) and data["expires"] > time.time()
    pulled = git(main, "pull", "--ff-only", "-q", env=agent())
    assert pulled.returncode == 0, pulled.stderr
    assert ok(git(main, "rev-parse", "HEAD")) == wanted
    assert records(main) == [], "the one-shot record is deleted at committed"


def test_without_an_authorization_the_backstop_still_refuses_a_pull(sync):
    done = git(sync["main"], "pull", "--ff-only", "-q", env=agent())
    assert done.returncode != 0 and "main checkout" in done.stderr


def test_composition_and_a_named_upstream_are_accepted(sync):
    main = sync["main"]
    assert not denied(verdict(main, "git status && git pull --ff-only origin main && git log -1"))
    assert not denied(verdict(sync["tmp"], f"cd {main} && git pull --ff-only", session="s2"))
    assert not denied(verdict(sync["tmp"], f"git -C {main} pull --ff-only", session="s3"))


@pytest.mark.parametrize("command", [
    "git pull", "git pull --rebase", "git pull --ff-only origin other", "git pull --ff-only upstream main",
    "git pull --ff-only --rebase", "git pull --ff-only origin", "git pull --ff-only -s ours",
])
def test_only_the_exact_ff_forms_pass(sync, command):
    done = verdict(sync["main"], command)
    assert denied(done) and records(sync["main"]) == []


def test_a_refused_line_writes_no_authorization(sync):
    done = verdict(sync["main"], "git pull --ff-only && touch changed")
    assert denied(done) and records(sync["main"]) == []


def test_a_dirty_tracked_file_refuses_and_names_the_condition(sync):
    main = sync["main"]
    (main / "f.txt").write_text("x\n", encoding="utf-8")
    ok(git(main, "add", "f.txt"))
    ok(git(main, "commit", "-q", "-m", "f", env=human()))
    ok(git(sync["up"], "reset", "-q", "--hard", "HEAD"))
    (main / "f.txt").write_text("changed\n", encoding="utf-8")
    done = verdict(main, "git pull --ff-only")
    assert denied(done) and "uncommitted" in done.stderr and records(main) == []


def test_untracked_files_do_not_block_the_sync(sync):
    (sync["main"] / "scratch.txt").write_text("x\n", encoding="utf-8")
    assert not denied(verdict(sync["main"], "git pull --ff-only"))


def test_a_branch_that_is_not_the_base_refuses(sync):
    main = sync["main"]
    ok(git(main, "switch", "-q", "-c", "topic"))
    ok(git(main, "branch", "-q", "--set-upstream-to=origin/main", "topic"))
    done = verdict(main, "git pull --ff-only")
    assert denied(done) and "base branch" in done.stderr


def test_a_branch_without_an_upstream_refuses(sync):
    main = sync["main"]
    ok(git(main, "branch", "-q", "--unset-upstream"))
    done = verdict(main, "git pull --ff-only")
    assert denied(done) and "upstream" in done.stderr


def test_a_detached_head_refuses(sync):
    ok(git(sync["main"], "switch", "-q", "--detach"))
    done = verdict(sync["main"], "git pull --ff-only")
    assert denied(done) and "detached" in done.stderr


def test_a_half_done_operation_refuses(sync):
    main = sync["main"]
    (main / ".git" / "MERGE_HEAD").write_text(ok(git(main, "rev-parse", "HEAD")) + "\n", encoding="utf-8")
    done = verdict(main, "git pull --ff-only")
    assert denied(done) and "in progress" in done.stderr


def test_a_linked_worktree_pull_is_judged_as_a_plain_mutation(sync):
    main = sync["main"]
    topic = sync["tmp"] / "topic"
    ok(git(main, "worktree", "add", "-q", "-b", "topic", str(topic)))
    assert not denied(verdict(topic, "git pull --ff-only"))
    prot = sync["tmp"] / "prot"
    ok(git(main, "worktree", "add", "-q", "-b", "keep", str(prot), "main"))
    ok(git(main, "branch", "-q", "-m", "keep", "master"))
    assert denied(verdict(prot, "git pull --ff-only"))
    assert records(main) == []


def test_an_expired_record_refuses_and_is_deleted(sync):
    main = sync["main"]
    assert not denied(verdict(main, "git pull --ff-only"))
    [path] = records(main)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["expires"] = time.time() - 1
    path.write_text(json.dumps(data), encoding="utf-8")
    done = git(main, "pull", "--ff-only", "-q", env=agent())
    assert done.returncode != 0 and not path.exists()


def test_a_record_for_another_old_commit_does_not_authorize(sync):
    main = sync["main"]
    assert not denied(verdict(main, "git pull --ff-only"))
    [path] = records(main)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["old"] = "1" * 40
    path.write_text(json.dumps(data), encoding="utf-8")
    assert git(main, "pull", "--ff-only", "-q", env=agent()).returncode != 0


def test_a_record_does_not_authorize_a_move_to_anything_but_the_upstream_commit(sync):
    main = sync["main"]
    advance(sync["up"], "c")
    ok(git(main, "fetch", "-q", "origin"))
    assert not denied(verdict(main, "git pull --ff-only"))
    old = ok(git(main, "rev-parse", "HEAD"))
    between = ok(git(main, "rev-parse", "origin/main~1"))
    done = git(main, "merge", "--ff-only", "-q", between, env=agent())
    assert done.returncode != 0 and ok(git(main, "rev-parse", "HEAD")) == old


def test_a_force_moved_upstream_is_not_a_descendant_and_is_refused(sync):
    main = sync["main"]
    assert not denied(verdict(main, "git pull --ff-only"))
    assert git(main, "pull", "--ff-only", "-q", env=agent()).returncode == 0
    assert not denied(verdict(main, "git pull --ff-only"))
    old = ok(git(main, "rev-parse", "HEAD"))
    ok(git(sync["up"], "reset", "-q", "--hard", "HEAD~1"))
    ok(git(sync["up"], "commit", "-q", "--allow-empty", "-m", "diverged"))
    ok(git(main, "fetch", "-q", "origin"))
    done = git(main, "reset", "-q", "--hard", "origin/main", env=agent())
    assert done.returncode != 0 and ok(git(main, "rev-parse", "HEAD")) == old


def test_the_ref_hook_deletes_the_record_when_the_transaction_aborts(sync):
    main = sync["main"]
    assert not denied(verdict(main, "git pull --ff-only"))
    old = ok(git(main, "rev-parse", "HEAD"))
    line = f"{old} {'2' * 40} refs/heads/main\n"
    done = subprocess.run([os.sys.executable, str(BACKSTOP), "reference-transaction", "aborted"], input=line,
                          text=True, capture_output=True, cwd=main, env=agent(), timeout=60)
    assert done.returncode == 0 and records(main) == []


def test_a_foreign_branch_line_does_not_delete_the_record(sync):
    main = sync["main"]
    assert not denied(verdict(main, "git pull --ff-only"))
    line = f"{'1' * 40} {'2' * 40} refs/heads/other\n"
    subprocess.run([os.sys.executable, str(BACKSTOP), "reference-transaction", "committed"], input=line, text=True,
                   capture_output=True, cwd=sync["main"], env=agent(), timeout=60)
    assert len(records(main)) == 1


def test_a_human_pull_is_never_gated(sync):
    assert git(sync["main"], "pull", "--ff-only", "-q", env=human()).returncode == 0


def test_a_sync_is_not_metered(sync):
    """The pull legitimately changes tracked files, so no pre-snapshot is taken for it."""
    assert not denied(verdict(sync["main"], "git pull --ff-only"))
    assert list(record_dir(sync["main"]).glob("*.pre")) == []


@pytest.mark.parametrize("linked", [False, True])
def test_the_committed_hook_finds_the_sync_folder_from_git_dir_without_a_subprocess(tmp_path, linked):
    """O2-2: `$GIT_DIR` (or its `commondir`) names the record folder; no `git rev-parse` runs."""
    common = tmp_path / "common"
    (common / "afk-session").mkdir(parents=True)
    (common / "afk-session" / "sync-s1.json").write_text("{}", encoding="utf-8")
    gitdir = common / "worktrees" / "w" if linked else common
    gitdir.mkdir(parents=True, exist_ok=True)
    if linked:
        (gitdir / "commondir").write_text("../..\n", encoding="utf-8")
    shim = tmp_path / "bin"
    shim.mkdir()
    marker = tmp_path / "ran"
    (shim / "python").write_text(f'#!/bin/sh\necho ran > "{marker.as_posix()}"\ncat >/dev/null\n', encoding="utf-8")
    (shim / "git").write_text('#!/bin/sh\nexit 9\n', encoding="utf-8")
    for name in ("python", "git"):
        os.chmod(shim / name, 0o755)
    env = {**human(), "AFK_PROVIDER": "claude", "GIT_DIR": gitdir.as_posix(),
           "PATH": f"{shim.as_posix()}{os.pathsep}{os.environ['PATH']}"}
    done = subprocess.run([BASH, str(PLUGIN_ROOT / "hooks" / "branch-name-gate.sh"), "committed"], input="x\n",
                          text=True, capture_output=True, cwd=tmp_path, env=env, timeout=60)
    assert done.returncode == 0 and marker.exists(), done.stderr
