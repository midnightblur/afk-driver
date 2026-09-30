"""The protected-branch guard's verdict per placement, per harness envelope.

Each case builds a throwaway repository: a main checkout, plus linked worktrees
nested under it the way a harness nests its own. No remote is set, so the
forge lookup takes the fallback (`main`, `master`, the remote default branch)
and nothing here reaches a network; one case stubs `gh` for a forge answer.
"""
from __future__ import annotations

import importlib.util
import json
import os
import stat
import subprocess
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
GUARD = PLUGIN_ROOT / "hooks" / "protected-branch-guard.sh"


def _bash():
    spec = importlib.util.spec_from_file_location(
        "afk_run_hook", PLUGIN_ROOT / "hooks" / "run-hook.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.find_bash()


BASH = _bash()
pytestmark = pytest.mark.skipif(BASH is None, reason="no POSIX shell on this machine")

PATCH = "*** Begin Patch\n*** Update File: {path}\n@@\n-a\n+b\n*** End Patch\n"


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(cwd), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


def make_repo(root: Path, branch: str) -> Path:
    main = root / "repo"
    main.mkdir()
    git(main, "init", "-q", "-b", branch)
    git(main, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q",
        "--allow-empty", "-m", "seed")
    return main


def add_worktree(main: Path, name: str, branch: str) -> Path:
    linked = main / ".claude" / "worktrees" / name
    git(main, "worktree", "add", "-q", "-b", branch, str(linked))
    return linked


@pytest.fixture
def repo(tmp_path: Path):
    """Main checkout on `dev`; linked worktrees on `main` (protected) and `topic`."""
    main = make_repo(tmp_path, "dev")
    return {"main": main, "protected": add_worktree(main, "prot", "main"),
            "topic": add_worktree(main, "topic", "topic"), "tmp": tmp_path}


def run(harness: str, cwd: Path, tool: str, tool_input: dict, envelope_extra=None, **env):
    envelope = {"session_id": "s1", "cwd": str(cwd), "hook_event_name": "PreToolUse",
                "tool_name": tool, "tool_input": tool_input, **(envelope_extra or {})}
    environ = {k: v for k, v in os.environ.items()
               if k not in ("AFK_ALLOW_PROTECTED", "CLAUDECODE", "CLAUDE_PLUGIN_ROOT", "PLUGIN_ROOT")}
    environ.update({"AFK_PROVIDER": harness, "AFK_PLUGIN_ROOT": str(PLUGIN_ROOT), **env})
    return subprocess.run([str(BASH), str(GUARD)], input=json.dumps(envelope), text=True,
                          capture_output=True, cwd=cwd, env=environ, timeout=120)


# One (harness, edit call, shell call) per envelope shape.
SHAPES = {
    "claude": (lambda p: ("Edit", {"file_path": str(p / "a.txt")}),
               lambda: ("Bash", {"command": "ls"})),
    "codex": (lambda p: ("apply_patch", {"command": PATCH.format(path=p / "a.txt")}),
              lambda: ("Bash", {"command": "ls"})),
}


@pytest.mark.parametrize("harness", SHAPES)
class TestCatalogP:
    def test_p1_main_checkout_on_protected_branch_refused(self, harness, tmp_path):
        main = make_repo(tmp_path, "main")
        edit, shell = SHAPES[harness]
        assert run(harness, main, *edit(main)).returncode == 2
        assert run(harness, main, *shell()).returncode == 2

    def test_p2_main_checkout_on_any_branch_refused(self, harness, repo):
        edit, shell = SHAPES[harness]
        assert run(harness, repo["main"], *edit(repo["main"])).returncode == 2
        assert run(harness, repo["main"], *shell()).returncode == 2

    def test_p3_linked_worktree_on_protected_branch_refused(self, harness, repo):
        edit, shell = SHAPES[harness]
        p = repo["protected"]
        assert run(harness, p, *edit(p)).returncode == 2
        assert run(harness, p, *shell()).returncode == 2

    def test_p4_linked_worktree_on_unprotected_branch_allowed(self, harness, repo):
        edit, shell = SHAPES[harness]
        t = repo["topic"]
        assert run(harness, t, *edit(t)).returncode == 0
        assert run(harness, t, *shell()).returncode == 0

    def test_p5_outside_git_allowed(self, harness, tmp_path):
        outside = tmp_path / "plain"
        outside.mkdir()
        edit, shell = SHAPES[harness]
        assert run(harness, outside, *edit(outside)).returncode == 0
        assert run(harness, outside, *shell()).returncode == 0

    def test_p6_override_allows_every_placement(self, harness, repo):
        edit, shell = SHAPES[harness]
        for place in (repo["main"], repo["protected"]):
            assert run(harness, place, *edit(place), AFK_ALLOW_PROTECTED="1").returncode == 0
            assert run(harness, place, *shell(), AFK_ALLOW_PROTECTED="1").returncode == 0
        # the same checkout, same time, without it: still refused
        assert run(harness, repo["main"], *shell()).returncode == 2

    def test_detached_head_is_not_protected(self, harness, repo):
        git(repo["topic"], "checkout", "-q", "--detach")
        assert run(harness, repo["topic"], *SHAPES[harness][1]()).returncode == 0

    def test_unborn_branch_is_not_protected(self, harness, repo):
        git(repo["topic"], "checkout", "-q", "--orphan", "fresh")
        assert run(harness, repo["topic"], *SHAPES[harness][1]()).returncode == 0


def test_edit_target_in_main_checkout_refused_from_a_worktree_session(repo):
    """AC-002: the session sits in a P-4 worktree, the file lies in the main checkout."""
    done = run("claude", repo["topic"], "Edit", {"file_path": str(repo["main"] / "a.txt")})
    assert done.returncode == 2
    assert "main checkout" in done.stderr


def test_edit_target_in_protected_worktree_refused_from_a_worktree_session(repo):
    done = run("claude", repo["topic"], "Write", {"file_path": str(repo["protected"] / "n" / "b.md")})
    assert done.returncode == 2


def test_relative_target_resolves_against_the_session_folder(repo):
    assert run("claude", repo["topic"], "Edit", {"file_path": "a.txt"}).returncode == 0


def test_edit_outside_the_repository_from_a_worktree_passes(repo):
    outside = repo["tmp"] / "elsewhere" / "note.md"
    assert run("claude", repo["topic"], "Write", {"file_path": str(outside)}).returncode == 0


def test_patch_with_a_target_in_the_main_checkout_is_refused(repo):
    """AC-005: same patch is fine when every target lies in the worktree."""
    bad = PATCH.format(path=repo["main"] / "a.txt")
    good = PATCH.format(path=repo["topic"] / "a.txt")
    assert run("codex", repo["topic"], "apply_patch", {"command": bad}).returncode == 2
    assert run("codex", repo["topic"], "apply_patch", {"command": good}).returncode == 0
    moved = "*** Begin Patch\n*** Update File: a.txt\n*** Move to: %s\n*** End Patch\n" % (repo["main"] / "b.txt")
    assert run("codex", repo["topic"], "apply_patch", {"command": moved}).returncode == 2


def test_refusal_names_cause_and_move_per_harness_class(repo):
    claude = run("claude", repo["main"], "Bash", {"command": "ls"})
    assert "main checkout" in claude.stderr and "EnterWorktree" in claude.stderr
    codex = run("codex", repo["protected"], "Bash", {"command": "ls"})
    assert "`main` is protected" in codex.stderr and "/cd" in codex.stderr
    decision = json.loads(claude.stdout)["hookSpecificOutput"]
    assert decision["permissionDecision"] == "deny"
    assert "main checkout" in decision["permissionDecisionReason"]


@pytest.mark.parametrize("tool", ["Read", "Grep", "Glob", "EnterWorktree", "WebFetch", "Agent",
                                  "AskUserQuestion", "ToolSearch", "Skill"])
def test_read_and_worktree_tools_are_allowed_in_the_main_checkout(repo, tool):
    """AC-004 (A-3, A-4)."""
    assert run("claude", repo["main"], tool, {"file_path": "x"}).returncode == 0


def test_mcp_tools_pass_unless_the_name_carries_a_mutating_verb(repo):
    assert run("claude", repo["main"], "mcp__docs__search", {}).returncode == 0
    assert run("claude", repo["main"], "mcp__docs__update_page", {}).returncode == 2


def test_an_unknown_builtin_is_refused_in_the_main_checkout(repo):
    assert run("claude", repo["main"], "SomeNewTool", {}).returncode == 2
    assert run("claude", repo["topic"], "SomeNewTool", {}).returncode == 0


def test_allowed_tools_make_no_git_call(repo, tmp_path):
    """The classification comes before any subprocess: a git that fails must not matter."""
    binaries = tmp_path / "nogit"
    binaries.mkdir()
    fake = binaries / "git"
    fake.write_text("#!/bin/sh\nexit 99\n", encoding="utf-8")
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    path = str(binaries) + os.pathsep + os.environ["PATH"]
    assert run("claude", repo["main"], "Read", {}, PATH=path).returncode == 0


NO_GIT = """
import subprocess, sys
real = subprocess.run
def run(cmd, *a, **k):
    if cmd and cmd[0] == 'git':
        raise FileNotFoundError('git')
    return real(cmd, *a, **k)
subprocess.run = run
sys.path.insert(0, sys.argv[1])
import protected_branch_guard as guard
sys.exit(guard.main())
"""


def helper_without_git(cwd: Path):
    envelope = json.dumps({"cwd": str(cwd), "tool_name": "Bash", "tool_input": {"command": "ls"}})
    import sys
    environ = dict(os.environ, AFK_GUARD_TOOL_CLASS="shell", AFK_PLUGIN_ROOT=str(PLUGIN_ROOT),
                   AFK_GUARD_HINT="move.")
    return subprocess.run([sys.executable, "-c", NO_GIT, str(PLUGIN_ROOT / "hooks" / "lib")],
                          input=envelope, text=True, capture_output=True, cwd=cwd, env=environ)


def test_a_missing_git_fails_closed_inside_a_work_tree(repo):
    done = helper_without_git(repo["topic"])
    assert done.returncode == 2 and "could not compute a verdict" in done.stderr


def test_a_missing_git_outside_a_work_tree_allows(tmp_path):
    outside = tmp_path / "plain"
    outside.mkdir()
    assert helper_without_git(outside).returncode == 0


def test_an_unreadable_envelope_fails_closed_in_a_work_tree(repo):
    environ = dict(os.environ, AFK_PROVIDER="claude", AFK_PLUGIN_ROOT=str(PLUGIN_ROOT))
    done = subprocess.run([str(BASH), str(GUARD)], input='{"tool_name": "Bash", broken',
                          text=True, capture_output=True, cwd=repo["topic"], env=environ)
    assert done.returncode == 2


def test_forge_answer_decides_protection(repo, tmp_path):
    """A stubbed forge protects `topic`; no fallback notice appears."""
    git(repo["main"], "remote", "add", "origin", "https://github.com/acme/widget.git")
    binaries = tmp_path / "bin"
    binaries.mkdir()
    gh = binaries / "gh"
    gh.write_text('#!/bin/sh\ncase "$*" in *branches/topic*) echo true ;; *) echo false ;; esac\n',
                  encoding="utf-8")
    gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
    path = str(binaries) + os.pathsep + os.environ["PATH"]
    done = run("claude", repo["topic"], "Bash", {"command": "ls"}, PATH=path)
    assert done.returncode == 2 and "`topic` is protected" in done.stderr
    assert run("claude", repo["protected"], "Bash", {"command": "ls"}, PATH=path).returncode == 0


def test_fallback_notice_appears_once_per_session(repo):
    first = run("claude", repo["topic"], "Bash", {"command": "ls"})
    second = run("claude", repo["topic"], "Bash", {"command": "ls"})
    assert "default branch" in json.loads(first.stdout)["hookSpecificOutput"]["additionalContext"]
    assert second.stdout.strip() == ""
    other = run("claude", repo["topic"], "Bash", {"command": "ls"}, {"session_id": "s2"})
    assert "additionalContext" in other.stdout


def test_a_submodule_is_judged_by_its_superproject(tmp_path):
    inner = make_repo(tmp_path / "in", "topic") if (tmp_path / "in").mkdir() is None else None
    outer = tmp_path / "outer"
    outer.mkdir()
    git(outer, "init", "-q", "-b", "dev")
    git(outer, "-c", "protocol.file.allow=always", "submodule", "add", "-q", str(inner), "sub")
    git(outer, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "sub")
    # The submodule sits on `topic`, but its superproject is a main checkout.
    assert run("claude", outer / "sub", "Bash", {"command": "ls"}).returncode == 2


def test_a_path_that_does_not_exist_yet_is_judged_by_its_nearest_folder(repo):
    target = repo["main"] / "new" / "deep" / "b.md"
    assert run("claude", repo["topic"], "Write", {"file_path": str(target)}).returncode == 2
