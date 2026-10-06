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


LAST: dict = {}


def pre(cwd: Path, command: str, session: str = "s1", tool: str = "Bash") -> subprocess.CompletedProcess:
    LAST[(str(cwd), session)] = command
    return subprocess.run([sys.executable, str(GUARD)], input=json.dumps(call(tool, cwd, {"command": command}, session)),
                          text=True, capture_output=True, cwd=cwd, env=env(), timeout=120)


def post(cwd: Path, session: str = "s1", tool: str = "Bash", stdin: str | None = None) -> subprocess.CompletedProcess:
    command = LAST.get((str(cwd), session), "x")
    payload = stdin if stdin is not None else json.dumps(call(tool, cwd, {"command": command}, session))
    return subprocess.run([sys.executable, str(METER)], input=payload, text=True, capture_output=True, cwd=cwd,
                          env=env(), timeout=120)


def denied(done: subprocess.CompletedProcess) -> bool:
    return done.returncode == 0 and '"permissionDecision": "deny"' in done.stdout


def context(done: subprocess.CompletedProcess) -> str:
    return json.loads(done.stdout)["hookSpecificOutput"]["additionalContext"] if done.stdout.strip() else ""


def files(main: Path, suffix: str) -> list[Path]:
    if suffix == ".pre":
        return cm.pre_files("s1", main)
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
    done = pre(repo["main"], "make")
    assert not denied(done)
    [path] = files(repo["main"], ".pre")
    [place] = json.loads(path.read_text(encoding="utf-8"))["places"]
    assert place["entries"] == {} and place["root"] == str(repo["main"])


@pytest.mark.parametrize("where,tool,command", [
    ("topic", "Bash", "make"),
    ("main", "Read", "x"),
])
def test_no_snapshot_for_an_unguarded_placement_or_a_non_shell_tool(repo, where, tool, command):
    pre(repo[where], command, tool=tool)
    assert files(repo["main"], ".pre") == []


def test_a_refused_call_records_nothing(repo):
    assert denied(pre(repo["main"], "touch f"))
    assert files(repo["main"], ".pre") == []


def test_no_change_means_no_output_and_no_quarantine(repo):
    pre(repo["main"], "make")
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
    assert f"git -C {main.as_posix()} restore --staged --worktree -- tracked.txt" in text
    assert f"rm -- {main.as_posix()}/generated.txt" in text
    [hold] = files(main, ".quarantine")
    assert hold.name.startswith("s1.") and files(main, ".pre") == []


def test_a_path_already_dirty_before_the_call_is_left_to_the_human(repo):
    main = repo["main"]
    (main / "other.txt").write_text("humans wip\n", encoding="utf-8")
    pre(main, "make")
    (main / "other.txt").write_text("humans wip, edited again\n", encoding="utf-8")
    (main / "tracked.txt").write_text("changed\n", encoding="utf-8")
    text = context(post(main))
    assert "other.txt" in text and "a human" in text.lower()
    assert "restore --staged --worktree -- other.txt" not in text and "agent" in text.lower()
    assert "cp -- " in text and "not restored" in text
    allowed = pre(main, "git restore --staged --worktree -- other.txt")
    assert denied(allowed)
    assert not denied(pre(main, "git restore --staged --worktree -- tracked.txt"))


def test_the_meter_never_blocks_on_garbage(repo):
    for stdin in ("", "not json", "[]", json.dumps(call("Bash", repo["tmp"] / "gone", {}))):
        done = post(repo["main"], stdin=stdin)
        assert done.returncode == 0


def test_a_non_shell_tool_is_not_metered(repo):
    main = repo["main"]
    pre(main, "make")
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


# ---------------------------------------------------------------- slice 3 review fixes (RULINGS-3)

def run_line(line: str, cwd: Path) -> None:
    """Run one printed recovery line the way a shell would."""
    import shlex
    words = shlex.split(line.strip())
    if words[0] == "cp":
        import shutil
        shutil.copyfile(words[-2], words[-1])
    else:
        subprocess.run(words, cwd=cwd, check=True, capture_output=True)


def printed(text: str, start: str) -> list[str]:
    return [line for line in text.splitlines() if line.strip().startswith(start)]


def test_o3_1_the_recovery_runs_from_a_worktree_and_clears_the_hold(held):
    main, topic = held["main"], held["topic"]
    restore = f'git -C "{main.as_posix()}" restore --staged --worktree -- tracked.txt'
    assert not denied(pre(topic, restore))
    run_line(restore.replace('"', ""), topic)
    remove = f'rm -- "{(main / "generated.txt").as_posix()}"'
    assert not denied(pre(topic, remove))
    (main / "generated.txt").unlink()
    assert not denied(pre(main, "ls")) and files(main, ".quarantine") == []


def test_o3_1_a_command_that_is_not_the_recovery_is_still_refused_from_a_worktree(held):
    main, topic = held["main"], held["topic"]
    assert denied(pre(topic, f'git -C "{main.as_posix()}" restore --staged --worktree -- other.txt'))
    assert denied(pre(topic, f'rm -- "{(main / "other.txt").as_posix()}"'))
    assert denied(pre(topic, f'git -C "{main.as_posix()}" commit --allow-empty -m x'))


def test_o3_1_copying_a_changed_file_out_is_allowed_from_the_held_checkout(held):
    main, topic = held["main"], held["topic"]
    assert not denied(pre(main, f"cp -- tracked.txt {(topic / 'saved.txt').as_posix()}"))
    assert not denied(pre(main, f"cp -- tracked.txt {(held['tmp'] / 'outside.txt').as_posix()}"))
    assert denied(pre(main, "cp -- tracked.txt other.txt"))
    assert denied(pre(main, f"cp -- other.txt {(topic / 'x.txt').as_posix()}"))


def test_o3_3_interleaved_calls_are_each_compared_with_their_own_snapshot(repo):
    main = repo["main"]

    def envelope(command: str, call_id: str | None) -> dict:
        return dict(call("Bash", main, {"command": command}), **({"tool_use_id": call_id} if call_id else {}))

    for id_a, id_b in (("a1", "b1"), (None, None)):
        first, second = envelope("make a", id_a), envelope("make b", id_b)
        for item in (first,):
            subprocess.run([sys.executable, str(GUARD)], input=json.dumps(item), text=True, capture_output=True,
                           cwd=main, env=env())
        (main / "from_a.txt").write_text("a\n", encoding="utf-8")
        subprocess.run([sys.executable, str(GUARD)], input=json.dumps(second), text=True, capture_output=True,
                       cwd=main, env=env())
        text = context(post(main, stdin=json.dumps(first)))
        assert "from_a.txt" in text, id_a
        assert post(main, stdin=json.dumps(second)).stdout.strip() == ""
        assert files(main, ".pre") == []
        git(main, "clean", "-fdq")
        for hold in files(main, ".quarantine"):
            hold.unlink()


def test_o3_3_a_post_without_the_id_the_pre_had_still_finds_its_record(repo):
    main = repo["main"]
    first = dict(call("Bash", main, {"command": "make"}), tool_use_id="x1")
    subprocess.run([sys.executable, str(GUARD)], input=json.dumps(first), text=True, capture_output=True, cwd=main,
                   env=env())
    (main / "new.txt").write_text("n\n", encoding="utf-8")
    assert "new.txt" in context(post(main, stdin=json.dumps(call("Bash", main, {"command": "make"}))))


def test_o3_3_a_stale_pre_record_is_swept_on_sight(repo):
    import time
    main = repo["main"]
    pre(main, "make one")
    [old] = files(main, ".pre")
    aged = time.time() - 2 * 3600
    os.utime(old, (aged, aged))
    pre(main, "make two")
    assert not old.exists() and len(files(main, ".pre")) == 1


def test_s3_001_a_path_dirty_before_the_call_is_copied_back_never_restored_to_head(repo):
    main = repo["main"]
    (main / "other.txt").write_text("humans wip\n", encoding="utf-8")
    pre(main, "make")
    (main / "other.txt").write_text("agent-overwrite\n", encoding="utf-8")
    (main / "tracked.txt").write_text("changed\n", encoding="utf-8")
    text = context(post(main))
    assert "restore --staged --worktree -- other.txt" not in text
    [copy] = printed(text, "cp --")
    for line in printed(text, "git -C"):
        assert not denied(pre(main, line.strip()))
        run_line(line, main)
    run_line(copy, main)
    assert (main / "other.txt").read_text(encoding="utf-8") == "humans wip\n"
    assert not denied(pre(main, "ls")) and files(main, ".quarantine") == []


def test_s3_001_blobs_unseen_for_a_day_are_deleted_and_a_referenced_one_is_kept(repo):
    import time
    main = repo["main"]
    (main / "other.txt").write_text("wip" + chr(10), encoding="utf-8")
    pre(main, "make")
    folder = main / ".git" / "afk-session" / "blobs"
    [kept] = list(folder.iterdir())
    orphan = folder / "deadbeef"
    orphan.write_bytes(b"x")
    aged = time.time() - 25 * 3600
    for path in (kept, orphan):
        os.utime(path, (aged, aged))
    pre(main, "make again")
    assert kept.exists() and not orphan.exists()


def test_s3_002_a_cd_into_the_main_checkout_from_a_worktree_is_metered(repo):
    main, topic = repo["main"], repo["topic"]
    command = f'cd "{main.as_posix()}" && make'
    assert not denied(pre(topic, command))
    (main / "tracked.txt").write_text("changed\n", encoding="utf-8")
    text = context(post(topic))
    assert "tracked.txt" in text and main.as_posix() in text
    assert denied(pre(main, "ls")) and not denied(pre(main, "git status"))


def test_s3_002_a_plain_command_in_a_worktree_is_not_metered(repo):
    pre(repo["topic"], "make")
    assert files(repo["topic"], ".pre") == []


def test_s3_003_a_staged_new_file_is_removed_with_git_rm_and_the_hold_clears(repo):
    main = repo["main"]
    pre(main, "make")
    (main / "added.txt").write_text("a\n", encoding="utf-8")
    git(main, "add", "added.txt")
    text = context(post(main))
    assert "rm -f -- added.txt" in text and "rm -- " not in text.replace("rm -f -- added.txt", "")
    assert denied(pre(main, "rm -- added.txt"))
    [line] = printed(text, "git -C")
    assert not denied(pre(main, line.strip()))
    run_line(line, main)
    assert not denied(pre(main, "ls")) and files(main, ".quarantine") == []


def test_s3_005_printed_paths_survive_a_shell(repo):
    import shlex
    main = repo["main"]
    odd = "a b$c;d`e'f.txt"
    pre(main, "make")
    (main / odd).write_text("n\n", encoding="utf-8")
    text = context(post(main))
    [line] = printed(text, "rm --")
    assert shlex.split(line.strip()) == ["rm", "--", main.as_posix() + "/" + odd]


@pytest.mark.parametrize("command", [
    "git status", "ls -la | head", "cat tracked.txt", "git log --oneline -3 && git diff", "git branch",
    "git fetch origin", "git worktree list", "rg pattern .", "find . -name x", "jq . x.json",
    "gh pr view 3", "gh api repos/x/y", "Get-ChildItem -Recurse", "echo hi", "cd sub && ls", "herdr agent list",
    "git remote -v", "sort a b", "uniq a",
])
def test_o3_5_a_known_reader_skips_the_snapshot(repo, command):
    assert not denied(pre(repo["main"], command))
    assert files(repo["main"], ".pre") == []


@pytest.mark.parametrize("command", [
    "make", "npm install", "find . -delete", "find . -exec rm {} +", "echo `touch f`", "sort -o out a",
    "uniq a b", "rg --pre ./x pat", "git branch topic2", "gh api -X POST repos/x/y", "git status; make",
    "git diff --output=out.diff", "./script.sh",
])
def test_o3_5_an_unknown_or_writing_form_is_still_metered(repo, command):
    done = pre(repo["main"], command)
    if not denied(done):
        assert len(files(repo["main"], ".pre")) == 1, command


def test_o3_5_a_post_without_a_pre_returns_at_once_and_silently(repo):
    done = post(repo["main"])
    assert done.returncode == 0 and done.stdout.strip() == ""


def test_f5_001_the_printed_recovery_lines_run_verbatim_from_another_worktree(repo):
    main, topic = repo["main"], repo["topic"]
    pre(main, "npm install")
    (main / "tracked.txt").write_text("changed\n", encoding="utf-8")
    (main / "generated.txt").write_text("g\n", encoding="utf-8")
    text = context(post(main))
    lines = [line.strip() for line in text.splitlines() if line.strip().startswith(("git ", "rm "))]
    assert len(lines) == 2 and all(str(main.as_posix()) in line for line in lines), lines
    for line in lines:
        assert not denied(pre(topic, line)), line
        run_line(line, topic)
    assert not denied(pre(main, "ls")) and files(main, ".quarantine") == []


@pytest.mark.parametrize("command", [
    "git branch --set-upstream-to=origin/main", "git branch --set-upstream-to origin/main", "git branch -u origin/main",
    "git branch --unset-upstream", "git branch --edit-description"])
def test_f5_002_branch_config_is_a_mutation_not_a_read(repo, command):
    assert denied(pre(repo["main"], command))
    assert not cm.read_only(command, repo["main"])


def test_w1_a_quarantine_unseen_for_a_day_is_swept_with_the_blobs(repo):
    import time
    main = repo["main"]
    pre(main, "make")
    (main / "tracked.txt").write_text("changed\n", encoding="utf-8")
    assert context(post(main))
    [hold] = files(main, ".quarantine")
    aged = time.time() - 25 * 3600
    os.utime(hold, (aged, aged))
    fresh = hold.with_name("other-session.0123456789.quarantine")
    fresh.write_text(hold.read_text(encoding="utf-8"), encoding="utf-8")
    pre(main, "make again", session="s2")
    assert not hold.exists() and fresh.exists()
