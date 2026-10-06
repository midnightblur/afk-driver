"""Change meter + quarantine (PRD D4, A5, A6): a shell call that changes a guarded checkout
through a form the recognizer cannot see is detected after the fact and the session is held
until the change is undone or the session has moved into a worktree.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
LIB = PLUGIN_ROOT / "hooks" / "lib"
GUARD = PLUGIN_ROOT / "hooks" / "protected-branch-guard.py"
METER = PLUGIN_ROOT / "hooks" / "protected-branch-meter.py"
IDENTITY = ("-c", "user.name=t", "-c", "user.email=t@example.com")


def load(name: str):
    sys.path.insert(0, str(LIB))
    spec = importlib.util.spec_from_file_location(f"{name}_under_test", LIB / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cm = load("change_meter")


def env() -> dict:
    keep = {k: v for k, v in os.environ.items() if k not in (
        "AFK_ALLOW_PROTECTED", "CLAUDECODE", "CLAUDE_PLUGIN_ROOT", "PLUGIN_ROOT", "GH_TOKEN", "GITHUB_TOKEN",
        "GITLAB_TOKEN", "AFK_GITHUB_API_URL", "AFK_GITLAB_API_URL")}
    keep.update({"AFK_PROVIDER": "claude", "AFK_PLUGIN_ROOT": str(PLUGIN_ROOT), "AFK_MOVE_SPAWN": "0"})
    return keep


def git(cwd: Path, *args: str) -> str:
    done = subprocess.run(["git", "-C", str(cwd), *IDENTITY, *args], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> dict:
    main = tmp_path / "repo"
    main.mkdir()
    git(main, "init", "-q", "-b", "dev")
    (main / "tracked.txt").write_text("one\n", encoding="utf-8")
    (main / "other.txt").write_text("two\n", encoding="utf-8")
    git(main, "add", "-A")
    git(main, "commit", "-q", "-m", "seed")
    topic = tmp_path / "topic"
    git(main, "worktree", "add", "-q", "-b", "topic", str(topic))
    return {"main": main, "topic": topic, "tmp": tmp_path}


def call(tool: str, cwd: Path, tool_input: dict, session: str = "s1") -> dict:
    return {"session_id": session, "cwd": str(cwd), "tool_name": tool, "tool_input": tool_input}


def pre(cwd: Path, command: str, session: str = "s1", tool: str = "Bash") -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(GUARD)], input=json.dumps(call(tool, cwd, {"command": command}, session)),
                          text=True, capture_output=True, cwd=cwd, env=env(), timeout=120)


def post(cwd: Path, session: str = "s1", tool: str = "Bash", stdin: str | None = None) -> subprocess.CompletedProcess:
    payload = stdin if stdin is not None else json.dumps(call(tool, cwd, {"command": "x"}, session))
    return subprocess.run([sys.executable, str(METER)], input=payload, text=True, capture_output=True, cwd=cwd,
                          env=env(), timeout=120)


def denied(done: subprocess.CompletedProcess) -> bool:
    return done.returncode == 0 and '"permissionDecision": "deny"' in done.stdout


def context(done: subprocess.CompletedProcess) -> str:
    return json.loads(done.stdout)["hookSpecificOutput"]["additionalContext"] if done.stdout.strip() else ""


def files(main: Path, suffix: str) -> list[Path]:
    return sorted((main / ".git" / "afk-session").glob(f"*{suffix}"))


# ---------------------------------------------------------------- snapshot (A6)

def test_a_clean_tree_has_an_empty_snapshot(repo):
    assert cm.snapshot(str(repo["main"])) == {}


def test_snapshot_lists_modified_deleted_untracked_and_renamed_paths(repo):
    main = repo["main"]
    (main / "tracked.txt").write_text("changed\n", encoding="utf-8")
    (main / "other.txt").unlink()
    (main / "new.txt").write_text("n\n", encoding="utf-8")
    (main / "dir").mkdir()
    (main / "dir" / "a.txt").write_text("a\n", encoding="utf-8")
    snap = cm.snapshot(str(main))
    assert set(snap) == {"tracked.txt", "other.txt", "new.txt", "dir/"}
    assert snap["tracked.txt"]["xy"].strip() == "M" and snap["tracked.txt"]["hash"]
    assert "hash" not in snap["other.txt"] and "mtime_ns" in snap["dir/"]
    git(main, "mv", "tracked.txt", "moved.txt")
    assert "moved.txt" in cm.snapshot(str(main))


def test_a_worktree_cut_inside_the_checkout_is_not_a_change(repo):
    main = repo["main"]
    pre(main, "scripts/create-worktree --name inner")
    git(main, "worktree", "add", "-q", "-b", "inner", str(main / ".claude" / "worktrees" / "inner"))
    done = post(main)
    assert done.stdout.strip() == "" and files(main, ".quarantine") == []


def test_a_second_edit_to_an_already_dirty_file_changes_its_entry(repo):
    main = repo["main"]
    (main / "tracked.txt").write_text("first\n", encoding="utf-8")
    before = cm.snapshot(str(main))
    (main / "tracked.txt").write_text("second\n", encoding="utf-8")
    assert cm.differs(before, cm.snapshot(str(main))) == ["tracked.txt"]


def test_a_rewrite_with_the_same_content_is_not_a_change(repo):
    main = repo["main"]
    (main / "tracked.txt").write_text("first\n", encoding="utf-8")
    before = cm.snapshot(str(main))
    (main / "tracked.txt").write_text("first\n", encoding="utf-8")
    assert cm.differs(before, cm.snapshot(str(main))) == []


def test_a_file_over_the_hash_limit_falls_back_to_size_and_mtime(repo, monkeypatch):
    main = repo["main"]
    monkeypatch.setattr(cm, "MAX_HASH", 4)
    (main / "big.bin").write_bytes(b"0123456789")
    entry = cm.snapshot(str(main))["big.bin"]
    assert "hash" not in entry and entry["size"] == 10 and "mtime_ns" in entry


# ---------------------------------------------------------------- pre / post

def test_a_shell_call_in_the_main_checkout_records_the_pre_snapshot(repo):
    done = pre(repo["main"], "echo hi")
    assert not denied(done)
    [path] = files(repo["main"], ".pre")
    assert path.name == "s1.pre" and json.loads(path.read_text(encoding="utf-8"))["entries"] == {}


@pytest.mark.parametrize("where,tool,command", [
    ("topic", "Bash", "echo hi"),
    ("main", "Read", "x"),
])
def test_no_snapshot_for_an_unguarded_placement_or_a_non_shell_tool(repo, where, tool, command):
    pre(repo[where], command, tool=tool)
    assert files(repo["main"], ".pre") == []


def test_a_refused_call_records_nothing(repo):
    assert denied(pre(repo["main"], "touch f"))
    assert files(repo["main"], ".pre") == []


def test_no_change_means_no_output_and_no_quarantine(repo):
    pre(repo["main"], "echo hi")
    done = post(repo["main"])
    assert done.returncode == 0 and done.stdout.strip() == ""
    assert files(repo["main"], ".quarantine") == [] and files(repo["main"], ".pre") == []


def test_a_change_made_by_an_unrecognized_command_is_named_and_quarantined(repo):
    main = repo["main"]
    pre(main, "npm install")
    (main / "tracked.txt").write_text("changed\n", encoding="utf-8")
    (main / "generated.txt").write_text("g\n", encoding="utf-8")
    done = post(main)
    assert done.returncode == 0
    text = context(done)
    assert "tracked.txt" in text and "generated.txt" in text
    assert "git restore --staged --worktree -- tracked.txt" in text
    assert "rm -- generated.txt" in text
    assert [p.name for p in files(main, ".quarantine")] == ["s1.quarantine"] and files(main, ".pre") == []


def test_a_path_already_dirty_before_the_call_is_left_to_the_human(repo):
    main = repo["main"]
    (main / "other.txt").write_text("humans wip\n", encoding="utf-8")
    pre(main, "make")
    (main / "other.txt").write_text("humans wip, edited again\n", encoding="utf-8")
    (main / "tracked.txt").write_text("changed\n", encoding="utf-8")
    text = context(post(main))
    assert "other.txt" in text and "a human" in text.lower()
    assert "restore --staged --worktree -- other.txt" in text and "agent" in text.lower()
    allowed = pre(main, "git restore --staged --worktree -- other.txt")
    assert denied(allowed)
    assert not denied(pre(main, "git restore --staged --worktree -- tracked.txt"))


def test_the_meter_never_blocks_on_garbage(repo):
    for stdin in ("", "not json", "[]", json.dumps(call("Bash", repo["tmp"] / "gone", {}))):
        done = post(repo["main"], stdin=stdin)
        assert done.returncode == 0


def test_a_non_shell_tool_is_not_metered(repo):
    main = repo["main"]
    pre(main, "echo hi")
    (main / "new.txt").write_text("n\n", encoding="utf-8")
    assert post(main, tool="Write").stdout.strip() == ""
    assert files(main, ".quarantine") == []


# ---------------------------------------------------------------- quarantine gate

@pytest.fixture
def held(repo) -> dict:
    main = repo["main"]
    pre(main, "npm install")
    (main / "tracked.txt").write_text("changed\n", encoding="utf-8")
    (main / "generated.txt").write_text("g\n", encoding="utf-8")
    assert context(post(main))
    return repo


@pytest.mark.parametrize("command,allowed", [
    ("echo hi", False), ("ls", False), ("git status", True), ("git status && git log -1", True),
    ("git diff", True), ("git show HEAD", True), ("git log --oneline", True), ("git -C . status", True),
])
def test_the_gate_lets_only_read_only_git_through(held, command, allowed):
    assert denied(pre(held["main"], command)) is (not allowed)


@pytest.mark.parametrize("command", [
    "git status > out.txt", "git diff --output=out.diff", "git status; ls", "git status && touch f",
    "git restore tracked.txt", "git restore --staged -- tracked.txt", "git restore --staged --worktree -- other.txt",
    "git restore --staged --worktree -- tracked.txt other.txt", "git restore --staged --worktree .",
    "git restore --source=HEAD~1 --staged --worktree -- tracked.txt", "rm -- other.txt", "rm -rf generated.txt",
    "rm generated.txt generated2.txt", "git stash", "git checkout -- tracked.txt", "git reset --hard",
])
def test_the_gate_refuses_these(held, command):
    assert denied(pre(held["main"], command)), command


@pytest.mark.parametrize("command", [
    "git restore --staged --worktree -- tracked.txt", "git restore --worktree --staged -- tracked.txt",
    "rm -- generated.txt", "git status && git restore --staged --worktree -- tracked.txt && rm -- generated.txt",
    "cd . && rm -- generated.txt",
])
def test_the_gate_lets_the_named_recovery_commands_through(held, command):
    assert not denied(pre(held["main"], command)), command


def test_the_gate_refuses_edits_and_mutating_tools_but_not_reads(held):
    main = held["main"]
    edit = subprocess.run([sys.executable, str(GUARD)], text=True, capture_output=True, cwd=main, env=env(),
                          input=json.dumps(call("Write", main, {"file_path": str(held["topic"] / "a.txt")})))
    assert denied(edit)
    read = subprocess.run([sys.executable, str(GUARD)], text=True, capture_output=True, cwd=main, env=env(),
                          input=json.dumps(call("Read", main, {"file_path": str(main / "tracked.txt")})))
    assert not denied(read)
    tool = subprocess.run([sys.executable, str(GUARD)], text=True, capture_output=True, cwd=main, env=env(),
                          input=json.dumps(call("EnterWorktree", main, {"name": "x"})))
    assert not denied(tool)


def test_the_plugins_create_worktree_is_allowed_under_the_gate(held):
    script = (PLUGIN_ROOT / "scripts" / "create-worktree").as_posix()
    assert not denied(pre(held["main"], f'"{script}" --name fresh'))
    assert denied(pre(held["main"], "C:/elsewhere/create-worktree --name fresh"))


def test_the_message_names_the_paths_and_the_way_out(held):
    done = pre(held["main"], "echo hi")
    assert "tracked.txt" in done.stderr and "generated.txt" in done.stderr
    assert "worktree" in done.stderr and "restore --staged --worktree -- tracked.txt" in done.stderr


def test_another_session_and_a_worktree_session_are_not_held(held):
    assert not denied(pre(held["main"], "echo hi", session="s2"))
    assert not denied(pre(held["topic"], "touch f"))


def test_undoing_the_change_lifts_the_quarantine(held):
    main = held["main"]
    git(main, "restore", "--staged", "--worktree", "--", "tracked.txt")
    (main / "generated.txt").unlink()
    assert not denied(pre(main, "echo hi"))
    assert files(main, ".quarantine") == []


def test_a_partial_undo_keeps_the_hold(held):
    main = held["main"]
    git(main, "restore", "--staged", "--worktree", "--", "tracked.txt")
    done = pre(main, "echo hi")
    assert denied(done) and "generated.txt" in done.stderr and "tracked.txt" not in done.stderr.split("Move:")[0]


def test_the_override_lifts_the_hold(held):
    done = subprocess.run([sys.executable, str(GUARD)], text=True, capture_output=True, cwd=held["main"],
                          env=dict(env(), AFK_ALLOW_PROTECTED="1"),
                          input=json.dumps(call("Bash", held["main"], {"command": "echo hi"})))
    assert not denied(done)


# ---------------------------------------------------------------- wiring

@pytest.mark.parametrize("manifest,root_var", [("hooks.json", "CLAUDE_PLUGIN_ROOT"), ("hooks.codex.json", "PLUGIN_ROOT")])
def test_both_manifests_register_the_meter_after_tool_use(manifest, root_var):
    groups = json.loads((PLUGIN_ROOT / "hooks" / manifest).read_text(encoding="utf-8"))["hooks"]["PostToolUse"]
    commands = [h["command"] for g in groups for h in g["hooks"]]
    mine = [c for c in commands if "protected-branch-meter.py" in c]
    assert len(mine) == 1 and f"${{{root_var}}}" in mine[0]
