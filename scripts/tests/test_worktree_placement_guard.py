"""The guard's worktree placement rule, driven through the real hook with harness envelopes.

Each case runs in a sandbox home: repository A is listed under a worktree root, Z is not.
The agent works in a linked worktree of A under `<root>/<short name>`, so only this rule refuses.
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
GUARD = PLUGIN_ROOT / "hooks" / "protected-branch-guard.py"
CREATOR = (PLUGIN_ROOT / "scripts" / "create-worktree").as_posix()
HEAD = "refused to create a worktree outside the worktree root"
DETECTORS = ("AFK_PROVIDER", "CLAUDECODE", "CLAUDE_PLUGIN_ROOT", "PLUGIN_ROOT", "AFK_PLUGIN_ROOT")


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True).stdout.strip()


def make_repo(path: Path) -> Path:
    path.mkdir(parents=True)
    git(path, "init", "-q", "-b", "dev")
    git(path, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "seed")
    return path


def real(path: Path | str) -> str:
    return os.path.realpath(path)


@pytest.fixture(autouse=True)
def sandbox_home(tmp_path, monkeypatch):
    """Every test gets an empty home of its own: nothing here reads or writes the real ~/.afk."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    return home


@pytest.fixture
def world(tmp_path, sandbox_home):
    """A listed (main checkout, agent worktree inside the root), Z unlisted (its own linked worktree)."""
    root = tmp_path / "wtroot"
    root.mkdir()
    (sandbox_home / ".afk").mkdir()
    (sandbox_home / ".afk" / "config.yaml").write_text(f"developer:\n  worktreeRoot: '{root.as_posix()}'\n",
                                                       encoding="utf-8")
    a = make_repo(tmp_path / "src" / "proj")
    repo_list = load(PLUGIN_ROOT / "scripts" / "repo_list.py", "afk_repo_list_for_guard_test")
    repo_list.add_repository(a, root)
    base = root / "proj"
    agent = base / "agent"
    git(a, "worktree", "add", "-q", "-b", "topic", str(agent))
    z = make_repo(tmp_path / "src" / "other")
    z_agent = z / ".claude" / "worktrees" / "t"
    git(z, "worktree", "add", "-q", "-b", "zt", str(z_agent))
    return {"root": root, "a": a, "base": base, "agent": agent, "z": z, "z_agent": z_agent,
            "tmp": tmp_path, "home": sandbox_home}


def harness_env(home: Path, detector: bool, **extra) -> dict:
    env = {k: v for k, v in os.environ.items() if k not in DETECTORS + ("AFK_ALLOW_PROTECTED",)}
    env.update({"HOME": str(home), "USERPROFILE": str(home), "AFK_MOVE_SPAWN": "0"})
    if detector:
        env["AFK_PROVIDER"] = "claude"
    env.update(extra)
    return env


def guard(world, cwd: Path, command: str, tool: str = "Bash", detector: bool = True, **extra):
    """(the deny reason or None, the finished hook process)."""
    envelope = {"session_id": "s-place", "cwd": str(cwd), "hook_event_name": "PreToolUse",
                "tool_name": tool, "tool_input": {"command": command}}
    done = subprocess.run([sys.executable, str(GUARD)], input=json.dumps(envelope), text=True,
                          capture_output=True, cwd=cwd, env=harness_env(world["home"], detector, **extra),
                          timeout=120)
    assert done.returncode == 0, done.stderr
    reason = None
    for line in done.stdout.splitlines():
        try:
            answer = json.loads(line)
        except ValueError:
            continue
        out = answer.get("hookSpecificOutput", {})
        if out.get("permissionDecision") == "deny":
            reason = out["permissionDecisionReason"]
    return reason, done


def outside_text(target: Path | str, base: Path) -> str:
    return (f"{HEAD}. Cause: {real(target)} is outside {real(base)}. "
            f"Move: create it under {real(base)}, or ask the developer.")


def assert_outside(reason, target, base):
    assert reason == outside_text(target, base)
    assert "AFK_ALLOW_PROTECTED" not in reason  # no bypass line


# ------------------------------------------------------------------ git worktree add

ADD_FORMS = [
    "git worktree add {t}",
    "git worktree add -b n1 {t}",
    "git worktree add {t} -b n1",
    "git worktree add -bn1 {t}",
    "git worktree add -B n1 {t}",
    "git worktree add -fB n1 {t}",
    "git worktree add --orphan -b n1 {t}",
    "git worktree add {t} --orphan",
    "git worktree add --lock --reason why {t}",
    "git worktree add --lock --reason=why {t}",
    "git worktree add --reason why --lock {t} dev",
    "git worktree add --detach -- {t}",
    "git worktree add --lo {t}",
]


@pytest.mark.parametrize("form", ADD_FORMS)
def test_add_outside_is_refused_in_every_option_position(world, form):
    target = world["tmp"] / "outside"
    reason, _ = guard(world, world["agent"], form.format(t=target.as_posix()))
    assert_outside(reason, target, world["base"])


@pytest.mark.parametrize("written", ["../../beside", "~/wt", "../../../beside"])
def test_add_resolves_relative_and_home_targets(world, written):
    target = (world["home"] / "wt") if written.startswith("~") else (world["agent"] / written)
    reason, _ = guard(world, world["agent"], f"git worktree add {written}")
    assert_outside(reason, os.path.normpath(target), world["base"])


def test_add_resolves_against_the_c_folder(world):
    reason, _ = guard(world, world["agent"], f"git -C {world['a'].as_posix()} worktree add ../beside")
    assert_outside(reason, world["a"].parent / "beside", world["base"])


def test_add_through_a_cd_resolves_against_the_new_folder(world):
    reason, _ = guard(world, world["agent"], f"cd {world['a'].as_posix()} && git worktree add inner")
    assert_outside(reason, world["a"] / "inner", world["base"])


def test_add_through_a_link_pointing_outside_is_refused(world):
    outside = world["tmp"] / "far"
    outside.mkdir()
    door = world["base"] / "door"
    try:
        os.symlink(outside, door, target_is_directory=True)
    except OSError:
        if os.name != "nt":
            pytest.skip("this machine refuses to create a symbolic link")
        import _winapi
        _winapi.CreateJunction(str(outside), str(door))
    reason, _ = guard(world, world["agent"], f"git worktree add {(door / 'x').as_posix()}")
    assert_outside(reason, outside / "x", world["base"])


@pytest.mark.skipif(os.name != "nt", reason="drive letters are a Windows form")
def test_add_inside_with_other_drive_letter_case_passes(world):
    text = str(world["base"] / "cased")
    swapped = text[0].swapcase() + text[1:]
    reason, _ = guard(world, world["agent"], f"git worktree add '{swapped}'")
    assert reason is None


@pytest.mark.parametrize("command", [
    "git worktree add \"$TARGET\"",
    "git worktree add -b $B ../x",
    "git worktree add $T",
    "git worktree \"$SUB\" ../x",
    "git worktree add --unknown-flag ../x",
    "git -C \"$D\" worktree add ../x",
])
def test_a_target_that_cannot_be_worked_out_is_refused(world, command):
    reason, _ = guard(world, world["agent"], command)
    assert reason is not None and reason.startswith(f"{HEAD}. Cause: the guard cannot work out")
    assert f"Move: create it under {real(world['base'])}, or ask the developer." in reason


@pytest.mark.parametrize("command", [
    "bash -c 'git worktree add ../../out'",
    "git work\\tree add ../../out",
    "git 'worktree' \"add\" ../../out",
])
def test_nested_and_quoted_forms_are_refused(world, command):
    reason, _ = guard(world, world["agent"], command)
    assert_outside(reason, world["root"] / "out", world["base"])


def test_add_inside_the_folder_passes(world):
    for command in ("git worktree add ../inside", f"git worktree add -b n2 {(world['base'] / 'in2').as_posix()}"):
        reason, done = guard(world, world["agent"], command)
        assert reason is None, (command, done.stdout)


def test_an_unlisted_repository_keeps_a_plain_add_passing(world):
    """The kept half of the "plain add passes" pin: an unlisted repository is unchanged."""
    reason, _ = guard(world, world["z_agent"], "git worktree add ../../../beside")
    assert reason is None


def test_a_listed_repository_reverses_the_plain_add_pin(world):
    """The reversed half: the same plain add in a listed repository is refused."""
    reason, _ = guard(world, world["agent"], "git worktree add ../../beside")
    assert_outside(reason, world["root"] / "beside", world["base"])


def test_the_detector_off_passes(world):
    reason, _ = guard(world, world["agent"], "git worktree add ../../beside", detector=False)
    assert reason is None


def test_the_launch_flag_lifts_the_rule(world):
    for command in ("git worktree add ../../beside", "AFK_WORKTREE_FOLDER=x git status"):
        reason, _ = guard(world, world["agent"], command, AFK_ALLOW_PROTECTED="1")
        assert reason is None, command


def test_the_developer_runs_a_plain_add_anywhere(world):
    target = world["tmp"] / "dev-own"
    git(world["a"], "worktree", "add", "-q", "-b", "devown", str(target))
    assert target.is_dir()


# ------------------------------------------------------------------ git worktree move

def test_move_to_outside_is_refused(world):
    moved = world["base"] / "movable"
    git(world["a"], "worktree", "add", "-q", "-b", "mv1", str(moved))
    target = world["tmp"] / "moved-out"
    reason, _ = guard(world, world["agent"], f"git worktree move {moved.as_posix()} {target.as_posix()}")
    assert_outside(reason, target, world["base"])


def test_move_into_an_existing_folder_lands_under_the_source_name(world):
    moved = world["base"] / "movable"
    git(world["a"], "worktree", "add", "-q", "-b", "mv1", str(moved))
    into = world["tmp"] / "existing"
    into.mkdir()
    reason, _ = guard(world, world["agent"], f"git worktree move --force {moved.as_posix()} {into.as_posix()}")
    assert_outside(reason, into / "movable", world["base"])


def test_move_inside_passes(world):
    moved = world["base"] / "movable"
    git(world["a"], "worktree", "add", "-q", "-b", "mv1", str(moved))
    reason, _ = guard(world, world["agent"], f"git worktree move {moved.as_posix()} {(world['base'] / 'm2').as_posix()}")
    assert reason is None


# ------------------------------------------------------------------ the creator call

def test_creator_parent_outside_is_refused(world):
    parent = world["tmp"] / "par"
    reason, _ = guard(world, world["agent"], f"bash {CREATOR} --branch x --dir d --parent {parent.as_posix()}")
    assert_outside(reason, parent / "d", world["base"])


def test_creator_dir_outside_is_refused(world):
    reason, _ = guard(world, world["agent"], f'"$AFK_PLUGIN_ROOT/scripts/create-worktree" --branch x --dir ../../d')
    assert reason is not None and reason.startswith(f"{HEAD}. Cause: ")
    assert reason.endswith(f"Move: create it under {real(world['base'])}, or ask the developer.")


def test_creator_inside_and_by_name_pass(world):
    for command in (f"bash {CREATOR} --branch x --dir d --parent {world['base'].as_posix()}",
                    f"bash {CREATOR} --branch x --dir d", f"bash {CREATOR} --name n1"):
        reason, _ = guard(world, world["agent"], command)
        assert reason is None, command


def test_creator_in_an_unlisted_repository_and_detector_off_pass(world):
    command = f"bash {CREATOR} --branch x --dir d --parent {(world['tmp'] / 'par').as_posix()}"
    assert guard(world, world["z_agent"], command)[0] is None
    assert guard(world, world["agent"], command, detector=False)[0] is None


# ------------------------------------------------------------------ inline variables

SETTING_FORMS = [
    ("Bash", "{n}=x git status"),
    ("Bash", "env {n}=1 git status"),
    ("Bash", "export {n}=1 && git status"),
    ("Bash", "export FOO=1 {n}=1"),
    ("Bash", "{n}=1; export {n}"),
    ("Bash", "declare -x {n}=1"),
    ("Bash", "typeset {n}=1"),
    ("Bash", "setx {n} 1"),
    ("Bash", "bash -c 'export {n}=1'"),
    ("Bash", "echo \"$(export {n}=1)\""),
    ("PowerShell", "$env:{n} = '1'"),
    ("PowerShell", "$env:{n}='1'"),
    ("PowerShell", "Set-Item -Path env:{n} -Value 1"),
    ("PowerShell", "[Environment]::SetEnvironmentVariable('{n}', '1')"),
]


@pytest.mark.parametrize("name", ["AFK_WORKTREE_FOLDER", "AFK_ALLOW_PROTECTED"])
@pytest.mark.parametrize("tool, form", SETTING_FORMS)
def test_setting_a_rule_variable_is_refused_naming_it(world, name, tool, form):
    reason, _ = guard(world, world["agent"], form.format(n=name), tool=tool)
    assert reason is not None and reason.startswith(f"refused to set {name} in an agent command. Cause: ")
    assert reason.endswith(f"Move: run the command without {name}, or ask the developer.")


@pytest.mark.parametrize("name", ["AFK_WORKTREE_FOLDER", "AFK_ALLOW_PROTECTED"])
@pytest.mark.parametrize("tool, form", [
    ("Bash", "grep -rn {n} hooks"), ("Bash", "echo ${n}"), ("Bash", "unset {n}"), ("Bash", "env -u {n} ls"),
    ("Bash", "printenv {n}"), ("Bash", "declare -p {n}"), ("Bash", "export -n {n}"),
    ("PowerShell", "Remove-Item env:{n}"), ("PowerShell", "Write-Output $env:{n}"),
])
def test_reading_or_removing_a_rule_variable_passes(world, name, tool, form):
    reason, _ = guard(world, world["agent"], form.format(n=name), tool=tool)
    assert reason is None


def test_setting_a_rule_variable_in_an_unlisted_repository_is_refused(world):
    reason, _ = guard(world, world["z_agent"], "AFK_ALLOW_PROTECTED=1 git status")
    assert reason is not None and reason.startswith("refused to set AFK_ALLOW_PROTECTED")


def test_setting_a_rule_variable_with_the_detector_off_passes(world):
    assert guard(world, world["agent"], "AFK_ALLOW_PROTECTED=1 git status", detector=False)[0] is None


# ------------------------------------------------------------------ cost

PROBE = r'''
import json, os, sys
guard, out = sys.argv[1:3]
events = {"rule": [], "placement": 0, "connects": 0}
def in_rule():
    frame = sys._getframe(2)
    while frame is not None:
        if frame.f_code.co_filename.endswith("worktree_placement_rule.py"):
            return True
        frame = frame.f_back
    return False
def hook(event, args):
    if event == "open" and isinstance(args[0], (str, bytes, os.PathLike)):
        path = os.fsdecode(args[0])
        if os.path.basename(path).startswith(("placement.py", "placement.cpython")):
            events["placement"] += 1
        if in_rule():
            events["rule"].append(path)
    elif event == "subprocess.Popen" and in_rule():
        events["rule"].append(" ".join(map(str, args[1] or [])))
    elif event in ("socket.connect", "socket.getaddrinfo"):
        events["connects"] += 1
sys.addaudithook(hook)
sys.argv = [guard]
try:
    exec(compile(open(guard, encoding="utf-8").read(), guard, "exec"), {"__name__": "__main__", "__file__": guard})
except SystemExit:
    pass
with open(out, "w", encoding="utf-8") as sink:
    json.dump(events, sink)
'''


def audited(world, command: str) -> dict:
    """The files the rule opens and the processes it starts, and every network call, in one guard run."""
    probe, out = world["tmp"] / "probe.py", world["tmp"] / "events.json"
    probe.write_text(PROBE, encoding="utf-8")
    envelope = {"session_id": "s-cost", "cwd": str(world["agent"]), "hook_event_name": "PreToolUse",
                "tool_name": "Bash", "tool_input": {"command": command}}
    done = subprocess.run([sys.executable, str(probe), str(GUARD), str(out)],
                          input=json.dumps(envelope), text=True, capture_output=True, cwd=world["agent"],
                          env=harness_env(world["home"], True), timeout=120)
    assert out.is_file(), done.stderr
    return json.loads(out.read_text(encoding="utf-8"))


@pytest.mark.parametrize("command", ["git status", "ls -la", "touch a.txt", "git commit -m x",
                                     "AFK_ALLOW_PROTECTED=1 git status", "git worktree list"])
def test_other_commands_make_no_new_read(world, command):
    events = audited(world, command)
    assert events["rule"] == [] and events["placement"] == 0, events


def test_add_and_move_make_no_network_call(world):
    for command in ("git worktree add ../../beside", "git worktree move ../x ../../far"):
        events = audited(world, command)
        assert events["connects"] == 0, events
        assert events["placement"] >= 1 and events["rule"], events
