"""The protected-branch guard's verdict per placement, per harness envelope.

Each case builds a throwaway repository: a main checkout, plus linked worktrees
nested under it the way a harness nests its own. With no remote the forge lookup
takes the fallback (`main`, `master`, the remote default branch) and nothing here
reaches a network; the forge cases talk to a local HTTP server over the token path.
"""
from __future__ import annotations

import http.server
import importlib.util
import json
import os
import re
import shlex
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
GUARD = PLUGIN_ROOT / "hooks" / "protected-branch-guard.py"
LIB = PLUGIN_ROOT / "hooks" / "lib"
PATCH = "*** Begin Patch\n*** Update File: {path}\n@@\n-a\n+b\n*** End Patch\n"


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(cwd), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


def make_repo(root: Path, branch: str, name: str = "repo") -> Path:
    main = root / name
    main.mkdir(parents=True)
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


def clean_env(harness: str, **env) -> dict:
    environ = {k: v for k, v in os.environ.items()
               if k not in ("AFK_ALLOW_PROTECTED", "CLAUDECODE", "CLAUDE_PLUGIN_ROOT", "PLUGIN_ROOT",
                            "GH_TOKEN", "GITHUB_TOKEN", "GITLAB_TOKEN", "AFK_GITHUB_API_URL", "AFK_GITLAB_API_URL")}
    environ.update({"AFK_MOVE_SPAWN": "0", "AFK_PROVIDER": harness, "AFK_PLUGIN_ROOT": str(PLUGIN_ROOT), **env})
    return environ


def envelope_of(cwd: Path, tool: str, tool_input: dict, extra=None) -> dict:
    return {"session_id": "s1", "cwd": str(cwd), "hook_event_name": "PreToolUse",
            "tool_name": tool, "tool_input": tool_input, **(extra or {})}


def denies(done) -> bool:
    """A refusal is exit 0 plus the deny JSON: the H-2 harness runs the command on exit 2."""
    return done.returncode == 0 and '"permissionDecision": "deny"' in done.stdout


def run(harness: str, cwd: Path, tool: str, tool_input: dict, envelope_extra=None, **env):
    done = subprocess.run([sys.executable, str(GUARD)],
                          input=json.dumps(envelope_of(cwd, tool, tool_input, envelope_extra)),
                          text=True, capture_output=True, cwd=cwd, env=clean_env(harness, **env),
                          timeout=120)
    if denies(done):
        done.returncode = 2  # in this file 2 reads "denied"; the raw exit is pinned by test_p2_*
    return done


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


def test_r1_1_a_session_outside_git_cannot_edit_a_main_checkout(repo):
    """R1-1: the session folder is P-5; the target lies in a main checkout."""
    outside = repo["tmp"] / "home"
    outside.mkdir()
    done = run("claude", outside, "Edit", {"file_path": str(repo["main"] / "a.txt")})
    assert done.returncode == 2 and "main checkout" in done.stderr
    assert "start the session inside the repository" in done.stderr  # R2-8: the move that can work
    done = run("claude", outside, "Edit", {"file_path": str(repo["protected"] / "a.txt")})
    assert done.returncode == 2
    assert run("claude", outside, "Edit", {"file_path": str(repo["topic"] / "a.txt")}).returncode == 0


def test_r1_1_a_worktree_session_cannot_edit_another_repositorys_main_checkout(repo):
    other = make_repo(repo["tmp"], "dev", "other")
    done = run("claude", repo["topic"], "Write", {"file_path": str(other / "a.txt")})
    assert done.returncode == 2 and "main checkout" in done.stderr


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


def test_the_live_apply_patch_envelope_with_spaces_in_absolute_paths(repo):
    """R1-5: the envelope shape a real codex session sent (PROBES P0-c)."""
    fixture = PLUGIN_ROOT / "hooks" / "tests" / "envelopes" / "codex" / "pretooluse-apply-patch.json"
    text = fixture.read_text(encoding="utf-8")
    spaced = repo["tmp"] / "cx wt"
    make_repo(repo["tmp"], "dev", "cx wt")

    def sub(value: str) -> str:
        return value.replace("C:\\work\\cx wt", str(spaced))

    envelope = json.loads(text, object_hook=lambda d: {k: sub(v) if isinstance(v, str) else v for k, v in d.items()})
    done = subprocess.run([sys.executable, str(GUARD)], input=json.dumps(envelope), text=True,
                          capture_output=True, cwd=spaced, env=clean_env("codex"), timeout=120)
    assert denies(done) and "main checkout" in done.stderr


def test_refusal_names_cause_and_move_per_harness_class(repo):
    claude = run("claude", repo["main"], "Bash", {"command": "ls"})
    assert "main checkout" in claude.stderr and "EnterWorktree" in claude.stderr
    codex = run("codex", repo["protected"], "Bash", {"command": "ls"})
    assert "`main` is protected" in codex.stderr and "/cd" in codex.stderr
    assert re.search(r"^/cd .+\.codex.worktrees.session-[0-9a-f]{8}\s*$", codex.stderr, re.M), codex.stderr
    decision = json.loads(claude.stdout)["hookSpecificOutput"]
    assert decision["permissionDecision"] == "deny"
    assert "main checkout" in decision["permissionDecisionReason"]


@pytest.mark.parametrize("tool", ["Read", "Grep", "Glob", "EnterWorktree", "WebFetch", "Agent",
                                  "AskUserQuestion", "ToolSearch", "Skill"])
def test_read_and_worktree_tools_are_allowed_in_the_main_checkout(repo, tool):
    """AC-004 (A-3, A-4)."""
    assert run("claude", repo["main"], tool, {"file_path": "x"}).returncode == 0


@pytest.mark.parametrize("tool,code", [
    ("mcp__docs__search", 0), ("mcp__db__query", 0), ("mcp__settings__get_page", 0),
    ("mcp__assets__list", 0), ("mcp__git__prune_list", 0),
    ("mcp__docs__update_page", 2), ("mcp__ide__reformat_file", 2), ("mcp__fs__remove-file", 2),
    ("mcp__fs__writeFile", 2), ("mcp__chat__send_message", 2), ("mcp__kv__put", 2),
    ("mcp__x__saveDraft", 2), ("mcp__db__drop_table", 2),
])
def test_r1_8_mcp_tools_are_judged_by_whole_verb_tokens_of_the_tool_part(repo, tool, code):
    assert run("claude", repo["main"], tool, {}).returncode == code


def test_r1_8_the_server_name_is_ignored(repo):
    assert run("claude", repo["main"], "mcp__write_things__read_page", {}).returncode == 0


def test_an_unknown_builtin_is_refused_in_the_main_checkout(repo):
    assert run("claude", repo["main"], "SomeNewTool", {}).returncode == 2
    assert run("claude", repo["topic"], "SomeNewTool", {}).returncode == 0


def test_allowed_tools_start_no_git(repo):
    """The classification comes before any subprocess: a git that fails must not matter."""
    done = helper("claude", repo["main"], "Read", raise_for_git=True)
    assert done.returncode == 0


WRAPPER = """
import subprocess, sys
real_run, real_popen = subprocess.run, subprocess.Popen
mode = sys.argv[2]
def run(cmd, *a, **k):
    if cmd and cmd[0] == 'git':
        if mode == 'missing':
            raise FileNotFoundError('git')
        if mode == 'fatal':
            return subprocess.CompletedProcess(cmd, 128, '', 'fatal: cannot lock ref')
        raise AssertionError('git was started')
    return real_run(cmd, *a, **k)
subprocess.run = run
sys.path.insert(0, sys.argv[1])
import protected_branch_guard as guard
sys.exit(guard.main())
"""


def helper(harness: str, cwd: Path, tool: str, mode="missing", raise_for_git=False, **env):
    """The judge in a process whose `git` is missing, fatal, or forbidden."""
    envelope = json.dumps(envelope_of(cwd, tool, {"command": "ls"}))
    return subprocess.run([sys.executable, "-c", WRAPPER, str(LIB), "forbid" if raise_for_git else mode],
                          input=envelope, text=True, capture_output=True, cwd=cwd,
                          env=clean_env(harness, **env), timeout=120)


def test_a_missing_git_outside_a_work_tree_allows(tmp_path):
    outside = tmp_path / "plain"
    outside.mkdir()
    assert helper("claude", outside, "Bash").returncode == 0


def test_the_layout_reader_needs_no_git_for_a_plain_placement(repo):
    """A14: no git process starts on the ordinary linked or main layout."""
    done = helper("claude", repo["main"], "Bash", raise_for_git=True)
    assert denies(done) and "main checkout" in done.stderr
    done = helper("claude", repo["topic"], "Bash", raise_for_git=True)
    assert done.returncode == 0


def load_guard():
    spec = importlib.util.spec_from_file_location("guard_under_test", LIB / "protected_branch_guard.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_r1_3_a_git_fatal_error_is_a_fault_not_a_detached_head(repo, monkeypatch):
    guard = load_guard()
    fatal = subprocess.CompletedProcess([], 128, "", "fatal: cannot lock ref")
    monkeypatch.setattr(guard, "git", lambda *a, **k: fatal)
    with pytest.raises(guard.Fault):
        guard._git_branch(str(repo["topic"]))
    detached = subprocess.CompletedProcess([], 1, "", "")
    monkeypatch.setattr(guard, "git", lambda *a, **k: detached)
    assert guard._git_branch(str(repo["topic"])) is None


def test_r1_3_a_broken_gitdir_pointer_fails_closed(repo):
    (repo["topic"] / ".git").unlink()
    (repo["topic"] / ".git").write_text("gitdir: " + str(repo["tmp"] / "gone" / "worktrees" / "x") + "\n",
                                        encoding="utf-8")
    done = run("claude", repo["topic"], "Bash", {"command": "ls"})
    assert done.returncode == 2 and "could not compute a verdict" in done.stderr


def test_r1_4_a_tag_with_the_branch_name_does_not_hide_the_protected_branch(repo):
    git(repo["main"], "tag", "main")
    done = run("claude", repo["protected"], "Bash", {"command": "ls"})
    assert done.returncode == 2 and "`main` is protected" in done.stderr


def test_r1_4_the_git_fallback_reads_the_full_ref(repo):
    git(repo["main"], "tag", "main")
    guard = load_guard()
    assert guard._git_branch(str(repo["protected"])) == "main"


def test_r1_11_an_old_git_that_echoes_the_option_is_named_not_recursed(repo, monkeypatch):
    guard = load_guard()
    echoed = subprocess.CompletedProcess([], 0, "--path-format=absolute\n.git\n.git\nfalse\n/x\n", "")
    monkeypatch.setattr(guard, "git", lambda *a, **k: echoed)
    with pytest.raises(guard.Fault, match="older than 2.31"):
        guard.by_git(repo["topic"], 0)


def test_the_superproject_chain_is_capped(repo, monkeypatch):
    guard = load_guard()
    endless = subprocess.CompletedProcess(
        [], 0, f"{repo['tmp']}/g\n{repo['tmp']}/g\nfalse\n{repo['tmp']}\n{repo['tmp']}\n", "")
    monkeypatch.setattr(guard, "git", lambda *a, **k: endless)
    monkeypatch.setattr(guard, "by_layout", lambda directory: None)
    (repo["tmp"] / ".git").mkdir()
    with pytest.raises(guard.Fault, match="too deep"):
        guard.by_git(repo["tmp"], 0)


def test_an_unreadable_envelope_fails_closed_in_a_work_tree(repo):
    done = subprocess.run([sys.executable, str(GUARD)], input='{"tool_name": "Bash", broken',
                          text=True, capture_output=True, cwd=repo["topic"], env=clean_env("claude"))
    assert denies(done)


def test_an_unloadable_judge_still_refuses_inside_a_work_tree(repo, tmp_path):
    """R1-6: a missing helper file is a refusal in a work tree, an allow outside."""
    copy = tmp_path / "plugin" / "hooks"
    copy.mkdir(parents=True)
    (copy / "protected-branch-guard.py").write_text(GUARD.read_text(encoding="utf-8"), encoding="utf-8")
    stdin = json.dumps(envelope_of(repo["topic"], "Bash", {"command": "ls"}))
    done = subprocess.run([sys.executable, str(copy / "protected-branch-guard.py")], input=stdin, text=True,
                          capture_output=True, cwd=repo["topic"], env=clean_env("claude"))
    assert denies(done) and "could not load" in done.stderr
    assert json.loads(done.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
    outside = tmp_path / "plain"
    outside.mkdir()
    stdin = json.dumps(envelope_of(outside, "Bash", {"command": "ls"}))
    done = subprocess.run([sys.executable, str(copy / "protected-branch-guard.py")], input=stdin, text=True,
                          capture_output=True, cwd=outside, env=clean_env("claude"))
    assert done.returncode == 0


@pytest.mark.parametrize("manifest,root_var", [("hooks.json", "CLAUDE_PLUGIN_ROOT"), ("hooks.codex.json", "PLUGIN_ROOT")])
def test_r1_5_the_registered_command_denies_from_a_main_checkout(repo, manifest, root_var):
    """Drive the command string each manifest registers, as a harness would."""
    groups = json.loads((PLUGIN_ROOT / "hooks" / manifest).read_text(encoding="utf-8"))["hooks"]["PreToolUse"]
    command = groups[-1]["hooks"][0]["command"]
    assert "protected-branch-guard.py" in command, "A22: the guard is the last PreToolUse group"
    argv = shlex.split(command.replace(f"${{{root_var}}}", str(PLUGIN_ROOT).replace("\\", "/")))
    argv[0] = sys.executable
    done = subprocess.run(argv, input=json.dumps(envelope_of(repo["main"], "Bash", {"command": "ls"})),
                          text=True, capture_output=True, cwd=repo["main"],
                          env=clean_env("claude" if root_var.startswith("CLAUDE") else "codex"), timeout=120)
    assert denies(done)
    assert json.loads(done.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


@pytest.mark.parametrize("harness", ["claude", "codex"])
def test_p2_a_refusal_is_exit_zero_with_the_deny_json_never_exit_two(repo, harness):
    """PROBES P-2: the H-2 harness treats a PreToolUse exit 2 as a failed hook and runs the command."""
    call = json.dumps(envelope_of(repo["main"], "Bash", {"command": "ls"}))
    raw = subprocess.run([sys.executable, str(GUARD)], input=call, text=True, capture_output=True,
                         cwd=repo["main"], env=clean_env(harness), timeout=120)
    assert raw.returncode == 0
    assert json.loads(raw.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_the_guard_is_the_last_pretooluse_group_in_both_manifests():
    for manifest in ("hooks.json", "hooks.codex.json"):
        groups = json.loads((PLUGIN_ROOT / "hooks" / manifest).read_text(encoding="utf-8"))["hooks"]["PreToolUse"]
        commands = [h["command"] for g in groups for h in g["hooks"]]
        assert commands[-1].endswith('protected-branch-guard.py"'), manifest
        assert sum("protected-branch-guard" in c for c in commands) == 1


class Forge(http.server.BaseHTTPRequestHandler):
    """A stand-in for the GitHub API: `routes` maps a path fragment to (status, body, delay)."""
    routes: dict = {}
    seen: list = []

    def do_GET(self):
        Forge.seen.append(self.path)
        for fragment, (status, body, delay) in sorted(Forge.routes.items(), key=lambda item: -len(item[0])):
            if fragment in self.path:
                time.sleep(delay)
                payload = json.dumps(body).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return
        self.send_response(404)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *args):
        pass


@pytest.fixture
def forge(repo):
    Forge.routes, Forge.seen = {}, []
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Forge)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    git(repo["main"], "remote", "add", "origin", "https://github.com/acme/widget.git")
    yield {"routes": Forge.routes, "seen": Forge.seen, "env": {
        "GH_TOKEN": "t", "AFK_GITHUB_API_URL": f"http://127.0.0.1:{server.server_address[1]}"}}
    server.shutdown()


def test_the_forge_answer_decides_protection(repo, forge):
    forge["routes"]["branches/topic"] = (200, {"protected": True}, 0)
    forge["routes"]["rules/branches"] = (200, [], 0)
    done = run("claude", repo["topic"], "Bash", {"command": "ls"}, **forge["env"])
    assert done.returncode == 2 and "`topic` is protected" in done.stderr
    forge["routes"].clear()
    forge["routes"]["branches/"] = (200, {"protected": False}, 0)
    forge["routes"]["rules/branches"] = (200, [], 0)
    done = run("claude", repo["topic"], "Bash", {"command": "ls"}, **forge["env"])
    assert done.returncode == 0 and done.stdout.strip() == ""


def test_a15_an_unpushed_branch_404_is_unprotected_and_a_rule_protects_it(repo, forge):
    forge["routes"]["rules/branches"] = (200, [{"type": "copilot_code_review"}], 0)
    done = run("claude", repo["topic"], "Bash", {"command": "ls"}, **forge["env"])
    assert done.returncode == 0 and done.stdout.strip() == ""
    forge["routes"]["rules/branches"] = (200, [{"type": "pull_request"}], 0)
    done = run("claude", repo["topic"], "Bash", {"command": "ls"}, **forge["env"])
    assert done.returncode == 2 and "`topic` is protected" in done.stderr


@pytest.mark.parametrize("answer", [(500, {"message": "boom"}, 0), (200, {"message": "not a list"}, 0)])
def test_r1_2_a_failed_or_malformed_rules_read_takes_the_fallback(repo, forge, answer):
    forge["routes"]["rules/branches"] = answer
    forge["routes"]["branches/"] = (200, {"protected": False}, 0)
    done = run("claude", repo["protected"], "Bash", {"command": "ls"}, **forge["env"])
    assert done.returncode == 2 and "`main` is protected" in done.stderr and "could not answer" in done.stderr
    done = run("claude", repo["topic"], "Bash", {"command": "ls"}, {"session_id": "s9"}, **forge["env"])
    assert done.returncode == 0
    assert "could not answer" in json.loads(done.stdout)["hookSpecificOutput"]["additionalContext"]


def test_a15_the_two_reads_run_at_once(repo, forge):
    forge["routes"]["branches/"] = (200, {"protected": False}, 1.5)
    forge["routes"]["rules/branches"] = (200, [], 1.5)
    started = time.monotonic()
    done = run("claude", repo["topic"], "Bash", {"command": "ls"}, **forge["env"])
    assert done.returncode == 0
    assert time.monotonic() - started < 1.5 + 1.2  # in series two 1.5 s reads cost 3.0 s before start-up


def test_r1_5_the_cap_is_wall_clock(repo, forge):
    """PROBES #10: a 5 s cap once took 9.7 s. A slow forge now costs the cap plus start-up."""
    forge["routes"]["branches/"] = (200, {"protected": False}, 12)
    forge["routes"]["rules/branches"] = (200, [], 12)
    started = time.monotonic()
    done = run("claude", repo["topic"], "Bash", {"command": "ls"}, AFK_PROTECTED_TIMEOUT="1", **forge["env"])
    elapsed = time.monotonic() - started
    assert done.returncode == 0 and "could not answer" in done.stdout
    assert elapsed < 6.0, elapsed


def test_fallback_notice_appears_once_per_session(repo):
    first = run("claude", repo["topic"], "Bash", {"command": "ls"})
    second = run("claude", repo["topic"], "Bash", {"command": "ls"})
    assert "default branch" in json.loads(first.stdout)["hookSpecificOutput"]["additionalContext"]
    assert second.stdout.strip() == ""
    other = run("claude", repo["topic"], "Bash", {"command": "ls"}, {"session_id": "s2"})
    assert "additionalContext" in other.stdout


def make_submodule_repo(tmp_path: Path):
    inner = make_repo(tmp_path, "topic", "in")
    outer = make_repo(tmp_path, "dev", "outer")
    git(outer, "-c", "protocol.file.allow=always", "submodule", "add", "-q", str(inner), "sub")
    git(outer, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "sub")
    return outer


def test_a_submodule_of_a_main_checkout_is_refused(tmp_path):
    outer = make_submodule_repo(tmp_path)
    assert run("claude", outer / "sub", "Bash", {"command": "ls"}).returncode == 2


def test_r0_13_a_submodule_inside_a_p4_worktree_is_allowed(tmp_path):
    """The pre-fix bug read a submodule as a main checkout, so the linked case is the real test."""
    outer = make_submodule_repo(tmp_path)
    linked = add_worktree(outer, "topic", "topic")
    git(linked, "-c", "protocol.file.allow=always", "submodule", "update", "--init", "-q")
    assert (linked / "sub" / ".git").exists()
    assert run("claude", linked / "sub", "Bash", {"command": "ls"}).returncode == 0
    assert run("claude", linked / "sub", "Edit", {"file_path": str(linked / "sub" / "a.txt")}).returncode == 0


def test_a_path_that_does_not_exist_yet_is_judged_by_its_nearest_folder(repo):
    target = repo["main"] / "new" / "deep" / "b.md"
    assert run("claude", repo["topic"], "Write", {"file_path": str(target)}).returncode == 2


def guard_module():
    import importlib.util
    spec = importlib.util.spec_from_file_location("guard_under_test", PLUGIN_ROOT / "hooks" / "lib" / "protected_branch_guard.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_r3_1_a_git_call_past_the_deadline_is_a_fault(repo):
    module = guard_module()
    module.deadline[0] = time.monotonic() - 1
    with pytest.raises(module.Fault, match="ran out of time"):
        module.git(repo["topic"], "rev-parse", "HEAD")


def test_r3_4_with_no_provider_matched_reads_are_still_allowed(repo):
    environ = clean_env("none")
    environ.pop("AFK_PROVIDER")
    for tool, wanted in (("Read", 0), ("Grep", 0), ("Edit", "deny")):
        done = subprocess.run([sys.executable, str(GUARD)], text=True, capture_output=True, cwd=repo["main"],
                              input=json.dumps(envelope_of(repo["main"], tool, {"file_path": str(repo["main"] / "a")})),
                              env=environ, timeout=120)
        assert (denies(done) if wanted == "deny" else done.returncode == wanted and not denies(done)), (tool, done.stderr)
