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
    "git worktree add --no-checkout {t}",
    "git worktree add --end-of-options {t}",
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
    "V='worktree add ../x'; git $V",
    "git $(echo worktree) add ../x",
    "git worktree add --detach=x ../x",
    "git -c alias.wt=worktree wt add ../../out",
    "GIT_DIR=$X git worktree add ../../out",
    "env $X git worktree add ../x",
    "env -S 'git worktree add ../x'",
    "sudo $X git worktree add ../x",
    "git 'worktree add' ../../out",
    "env $X git worktree move ../x ../../y",
    "env $X create-worktree --parent ../../out --dir x",
    "$(which git) worktree add ../../out",
    "$(which git) -C . worktree add ../../out",
    "$(which git) --no-pager worktree add ../../out",
    "$(which git) -c core.x=1 worktree add ../../out",
    "$ENV -S 'git worktree add ../x'",
    "${ENV} --split-string='git worktree add ../x'",
    "$ENV -u A -S 'git worktree add ../../out'",
    "$ENV -i -S 'git worktree add ../../out'",
    "$ENV A=1 B=2 -S 'git worktree add ../../out'",
    "${ENV} -u A --split-string='git worktree add ../../out'",
    "env -a x -S 'git worktree add ../../out'",
    "env -P /bin -S 'git worktree add ../../out'",
    "env -iS 'git worktree add ../../out'",
    "env -vS 'git worktree add ../../out'",
    "env -uA -S 'git worktree add ../../out'",
    "env --split='git worktree add ../../out'",
    "env --split-s 'git worktree add ../../out'",
    "$ENV -vS 'git worktree add ../../out'",
    "$ENV --split-string 'git worktree add ../../out'",
    "$ENV -S'git worktree add ../../out'",
    "$ENV -C d -S 'git worktree add ../../out'",
    "$ENV --unset A -S 'git worktree add ../../out'",
    "$ENV --chdir=d -S 'git worktree add ../../out'",
    "$ENV --chdir d -S 'git worktree add ../../out'",
    "$ENV --argv0 x -S 'git worktree add ../../out'",
    "sudo env -S 'git worktree add ../../out'",
    "sudo -u root env -S 'git worktree add ../../out'",
    "env -S './scripts/create-worktree --parent ../../out --dir x'",
    "env --ch d -S 'git worktree add ../../out'",
    "env --un A -S 'git worktree add ../../out'",
    "$X $Y -S 'git worktree add ../../out'",
    "env - -S 'git worktree add ../../out'",
])
def test_a_target_that_cannot_be_worked_out_is_refused(world, command):
    reason, _ = guard(world, world["agent"], command)
    assert reason is not None and reason.startswith(f"{HEAD}. Cause: the guard cannot work out")
    assert f"Move: create it under {real(world['base'])}, or ask the developer." in reason


def test_a_backslash_creator_path_behind_an_unreadable_program_is_refused(world):
    reason, _ = guard(world, world["agent"], "& $X .\\scripts\\create-worktree --parent ..\\out --dir x", tool="PowerShell")
    assert reason is not None and reason.startswith(f"{HEAD}. Cause: the guard cannot work out")


def test_a_split_string_behind_an_unreadable_powershell_program_is_refused(world):
    reason, _ = guard(world, world["agent"], "& $X -S 'git worktree add ../x'", tool="PowerShell")
    assert reason is not None and reason.startswith(f"{HEAD}. Cause: the guard cannot work out")


@pytest.mark.parametrize("command", ["$GIT log --grep 'worktree add'", "$GIT commit -m 'docs: worktree add flow'",
                                     "$GIT log -S 'worktree add'", "env $X git log \"-s worktree add\"",
                                     "echo env -S 'worktree add'", "grep env -S 'worktree add x'",
                                     "ls worktree; env -S", "env -- 'worktree add x'",
                                     "$GIT log \"$X\" -S 'worktree add'", "$GIT worktree list",
                                     "$GIT remote add origin worktree"])
def test_a_quoted_worktree_phrase_behind_an_unreadable_program_passes(world, command):
    assert guard(world, world["agent"], command)[0] is None


def test_env_chdir_before_an_unreadable_program_moves_the_folder_once(world):
    nested = world["agent"] / "sub" / "sub"  # an unlisted repository where a second `-C sub` would land
    nested.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(nested)], check=True)
    reason, _ = guard(world, world["agent"], "env -C sub $X git worktree add ../x")
    assert reason is not None and reason.startswith(f"{HEAD}. Cause: the guard cannot work out")


@pytest.mark.parametrize("command", [
    "bash -c 'git worktree add ../../out'",
    "git work\\tree add ../../out",
    "git 'worktree' \"add\" ../../out",
    "if true; then git worktree add ../../out; fi",
    "for n in a; do git worktree add ../../out; done",
    "while true; do git worktree add ../../out; done",
    "! git worktree add ../../out",
    "eval 'git worktree add ../../out'",
    "eval -- 'git worktree add ../../out'",
    "if true; then bash -c 'git worktree add ../../out'; fi",
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


def test_a_folder_outside_git_meets_the_rule_only_for_a_named_listed_repository(world):
    plain = world["tmp"] / "plain"
    plain.mkdir()
    assert guard(world, plain, "git worktree add ../beside")[0] is None
    reason, _ = guard(world, plain, f"git -C {world['a'].as_posix()} worktree add ../beside")
    assert_outside(reason, world["a"].parent / "beside", world["base"])


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
    command = f"git worktree add -q -b devown {target.as_posix()}"
    assert guard(world, world["agent"], command, detector=False)[0] is None
    git(world["agent"], "worktree", "add", "-q", "-b", "devown", str(target))
    assert target.is_dir()


def test_a_git_dir_naming_an_unlisted_repository_leaves_the_rule_silent(world):
    """The rest of the guard may still refuse a write to Z's main checkout; this rule judges Z, not A."""
    reason, _ = guard(world, world["agent"], f"GIT_DIR={(world['z'] / '.git').as_posix()} git worktree add ../../out")
    assert reason is None or HEAD not in reason


def test_git_settings_behind_a_control_word_reach_the_rule(world):
    """`env GIT_DIR=` and `env -C` behind `then` change the repository and folder the rule judges."""
    z_git = (world["z"] / ".git").as_posix()
    reason, _ = guard(world, world["agent"], f"if true; then env GIT_DIR={z_git} git worktree add ../../out; fi")
    assert reason is None or HEAD not in reason
    reason, _ = guard(world, world["agent"],
                      f"if true; then env -C {world['a'].as_posix()} git worktree add ../beside; fi")
    assert_outside(reason, world["a"].parent / "beside", world["base"])


@pytest.mark.parametrize("config, start", [
    ("developer:\n  worktreeRoot: 'relative/root'\n", f"{HEAD}. Cause: worktree root: "),
    ("developer: x\n", f"{HEAD}. Cause: placement has no answer ("),
])
def test_an_unsound_root_or_placement_error_is_refused(world, config, start):
    (world["home"] / ".afk" / "config.yaml").write_text(config, encoding="utf-8")
    reason, _ = guard(world, world["agent"], "git worktree add ../inside")
    assert reason is not None and reason.startswith(start)
    assert reason.endswith("Move: run /afk:setup, or ask the developer.")


def test_a_fault_inside_the_rule_refuses_a_worktree_command(world, monkeypatch):
    sys.path.insert(0, str(PLUGIN_ROOT / "hooks" / "lib"))
    try:
        rule = load(PLUGIN_ROOT / "hooks" / "lib" / "worktree_placement_rule.py", "afk_placement_rule_fault")
    finally:
        sys.path.remove(str(PLUGIN_ROOT / "hooks" / "lib"))

    def broken(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(rule, "worktree_refusal", broken)
    reason = rule.refusal("git worktree add ../x", world["agent"])
    assert reason == f"{HEAD}. Cause: the guard could not read this command (boom). Move: ask the developer."


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


def test_a_move_inside_still_meets_the_older_move_rules(world):
    """An inside destination leaves the verdict to the rest of the guard: its forced-move refusal still runs."""
    moved = world["base"] / "movable"
    git(world["a"], "worktree", "add", "-q", "-b", "mv1", str(moved))
    reason, _ = guard(world, world["agent"],
                      f"git worktree move --force {moved.as_posix()} {(world['base'] / 'm3').as_posix()}")
    assert reason is not None and "forced worktree moves can override a worktree lock" in reason
    assert HEAD not in reason


def test_move_inside_passes(world):
    moved = world["base"] / "movable"
    git(world["a"], "worktree", "add", "-q", "-b", "mv1", str(moved))
    reason, _ = guard(world, world["agent"], f"git worktree move {moved.as_posix()} {(world['base'] / 'm2').as_posix()}")
    assert reason is None


@pytest.mark.parametrize("form", [
    "git worktree add {t}",
    "Set-Location {a}; git worktree add {t}",
    "git worktree add `\n  {t}",
])
def test_the_powershell_tool_reading_is_refused_too(world, form):
    target = world["tmp"] / "outside"
    command = form.format(t=target.as_posix(), a=world["agent"].as_posix())
    reason, _ = guard(world, world["agent"], command, tool="PowerShell")
    assert_outside(reason, target, world["base"])


def test_the_powershell_tool_move_and_creator_are_refused(world):
    moved = world["base"] / "movable"
    git(world["a"], "worktree", "add", "-q", "-b", "mv1", str(moved))
    target = world["tmp"] / "moved-out"
    reason, _ = guard(world, world["agent"], f"git worktree move {moved.as_posix()} {target.as_posix()}",
                      tool="PowerShell")
    assert_outside(reason, target, world["base"])
    parent = world["tmp"] / "par"
    reason, _ = guard(world, world["agent"], f"bash {CREATOR} --branch x --dir d --parent {parent.as_posix()}",
                      tool="PowerShell")
    assert_outside(reason, parent / "d", world["base"])


# ------------------------------------------------------------------ the creator call

def test_creator_parent_outside_is_refused(world):
    parent = world["tmp"] / "par"
    reason, _ = guard(world, world["agent"], f"bash {CREATOR} --branch x --dir d --parent {parent.as_posix()}")
    assert_outside(reason, parent / "d", world["base"])


def test_creator_behind_a_loop_word_is_refused(world):
    parent = world["tmp"] / "par"
    reason, _ = guard(world, world["agent"],
                      f"for n in a; do bash {CREATOR} --branch x --dir d --parent {parent.as_posix()}; done")
    assert_outside(reason, parent / "d", world["base"])


def test_creator_with_a_variable_name_and_a_parent_is_refused(world):
    reason, _ = guard(world, world["agent"],
                      f"bash {CREATOR} --name \"$N\" --parent {(world['tmp'] / 'par').as_posix()}")
    assert reason is not None and reason.startswith(f"{HEAD}. Cause: the guard cannot work out")


def test_creator_repo_flag_judges_the_named_repository(world):
    parent = world["tmp"] / "par"
    reason, _ = guard(world, world["z_agent"],
                      f"bash {CREATOR} --repo {world['a'].as_posix()} --branch x --dir d --parent {parent.as_posix()}")
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
    ("PowerShell", "$v = '{n}'; [Environment]::SetEnvironmentVariable($v, '1')"),
    ("PowerShell", "[Environment]::SetEnvironmentVariable([string]'{n}', '1')"),
    ("PowerShell", "[Environment]::SetEnvironmentVariable('{n}' + '', '1')"),
    ("PowerShell", "[Environment]::SetEnvironmentVariable('{n}'.Trim(), '1')"),
    ("PowerShell", "${{env:{n}}} = '1'"),
    ("PowerShell", "$env:{n} += '1'"),
    ("PowerShell", "Set-Content Env:{n} 1"),
    ("PowerShell", "Add-Content -Path env:{n} -Value 1"),
    ("Bash", "eval 'export {n}=1'"),
    ("Bash", "if true; then export {n}=1; fi"),
    ("Bash", "set {n}=1"),
    ("PowerShell", "set {n}=1"),
    ("Bash", "export {n}"),
    ("PowerShell", "iex '$env:{n} = 1'"),
    ("PowerShell", "sc Env:{n} 1"),
    ("PowerShell", "ac Env:{n} 1"),
    ("PowerShell", "$env:{n}+='1'"),
    ("PowerShell", "$v = '{n}'; [Environment]::SetEnvironmentVariable(($v), '1')"),
    ("PowerShell", "$env:{n} ??= '1'"),
    ("PowerShell", "Copy-Item env:PATH env:{n}"),
    ("PowerShell", "Rename-Item -Path env:FOO -NewName {n}"),
    ("PowerShell", "New-Item -Path env: -Name {n} -Value 1"),
    ("PowerShell", "[Environment]::SetEnvironmentVariable.Invoke('{n}', '1')"),
    ("PowerShell", "[Environment].GetMethod('SetEnvironmentVariable', [type[]]@([string], [string])).Invoke($null, @('{n}', '1'))"),
    ("PowerShell", "[Environment]::SetEnvironmentVariable(@('{n}')[0], '1')"),
    ("PowerShell", "Set-Item -V 1 -Pa env:{n}"),
    ("PowerShell", "Set-Content -ErrorAction Stop Env:{n} 1"),
    ("PowerShell", "Set-Content -ea SilentlyContinue Env:{n} 1"),
    ("PowerShell", "Set-Content -Path:Env:{n} 1"),
    ("PowerShell", "Set-Content -Encoding utf8 Env:{n} 1"),
    ("PowerShell", "Set-Content -Force Env:{n} 1"),
    ("PowerShell", "Invoke-Expression -Command '$env:{n}=1'"),
    ("PowerShell", "iex -c '$env:{n}=1'"),
    ("PowerShell", "$env:{n}??='1'"),
    ("PowerShell", "ren env:FOO {n}"),
    ("PowerShell", "rni env:FOO {n}"),
    ("PowerShell", "cpi env:PATH env:{n}"),
    ("PowerShell", "mi env:PATH env:{n}"),
    ("PowerShell", "Move-Item -Destination env:{n} -Path env:PATH"),
    ("PowerShell", "ni env:{n} -Value 1"),
    ("PowerShell", "$n = '{n}'; ([type]('System.Env' + 'ironment'))::SetEnvironmentVariable($n, '1')"),
    ("PowerShell", "$n = '{n}'; $t = [type]::GetType('System.' + 'Environment'); $t::SetEnvironmentVariable($n, '1')"),
    ("PowerShell", "$n = '{n}'; $t = 'Environment'; [System.$t]::SetEnvironmentVariable($n, '1')"),
    ("PowerShell", "cp env:PATH env:{n}"),
    ("PowerShell", "copy env:PATH env:{n}"),
    ("PowerShell", "mv env:FOO env:{n}"),
    ("PowerShell", "move env:FOO env:{n}"),
    ("PowerShell", "Copy-Item -Path env:PATH env:{n}"),
    ("PowerShell", "Move-Item -Path env:PATH env:{n}"),
    ("PowerShell", "Set-Content -Bogus x Env:{n} 1"),
    ("PowerShell", "Copy-Item -Bogus env:PATH env:{n}"),
    ("PowerShell", "Set-Content -n Env:{n} 1"),
    ("PowerShell", "Set-Content -Path env:OTHER,env:{n} 1"),
    ("PowerShell", "Set-Location env:; Set-Content {n} 1"),
    ("PowerShell", "cd env:; ni {n} -Value x"),
    ("PowerShell", "Invoke-Expression -Command:'$env:{n}=1'"),
    ("PowerShell", "iex -c:'$env:{n}=1'"),
    ("Bash", "git commit --allow-empty -m 'refuse SetEnvironmentVariable, {n}'"),
    ("Bash", "git commit --allow-empty -m 'refuse SetEnvironmentVariable(...) of {n}'"),
    ("Bash", "rg -n 'SetEnvironmentVariable\\(.*{n}' hooks"),
    ("Bash", "rg 'SetEnvironmentVariable.*{n}' hooks"),
    ("Bash", "git commit --allow-empty -m 'document SetEnvironmentVariable and {n}'"),
    ("PowerShell", "[Environment]::SetEnvironmentVariable('X', '1'); "
                   "[Environment].GetMethod('SetEnvironmentVariable').Invoke($null, @('{n}', '1'))"),
    ("PowerShell", "[Environment]::SetEnvironmentVariable('X', '1'); "
                   "[Environment]::SetEnvironmentVariable.Invoke('{n}', '1')"),
    ("PowerShell", "Set-Content Env:OTHER, Env:{n} 1"),
    ("PowerShell", "Set-Content -Path env:OTHER, env:{n} 1"),
    ("PowerShell", "Set-Content @('Env:OTHER','Env:{n}') 1"),
    ("PowerShell", "Set-Location -Path:env:; Set-Content {n} 1"),
    ("PowerShell", "Set-Content -Bogus x Env:{n} 1 -Force"),
    ("PowerShell", "Rename-Item -Path OTHER, env:FOO -NewName {n}"),
    ("PowerShell", "Set-Content -Path ('Env:{n}') -Value 1"),
    ("PowerShell", "Set-Content -Path:('Env:{n}') x"),
    ("PowerShell", "Set-Content ('Env:{n}') 1"),
    ("PowerShell", "New-Item -Path ('Env:{n}') -Value 1"),
    ("PowerShell", "Set-Content @('Env:OTHER'; 'Env:{n}') 1"),
    ("PowerShell", "Set-Content @(\n'Env:OTHER'\n'Env:{n}') 1"),
    ("PowerShell", "Set-Content Env:OTHER , Env:{n} 1"),
    ("PowerShell", "Set-Content Env:OTHER ,Env:{n} 1"),
    ("PowerShell", "Set-Content $('Env:OTHER','Env:{n}') 1"),
    ("PowerShell", "Set-Content -Path $('Env:OTHER','Env:{n}') 1"),
    ("PowerShell", "si env:{n} 1"),
    ("PowerShell", "$r = New-Item env:{n} -Value 1"),
    ("PowerShell", "$null = Set-Content env:{n} 1"),
    ("PowerShell", "$x=New-Item env:{n} -Value 1"),
    ("PowerShell", "$x += Set-Content env:{n} 1"),
    ("PowerShell", "return Set-Item env:{n} 1"),
    ("PowerShell", "foreach ($i in 1) {{ $x = New-Item env:{n} -Value 1 }}"),
    ("PowerShell", "$x = ni env:{n} -Value 1"),
    ("PowerShell", "Write-Output {n} | % {{ Set-Item \"env:$_\" 1 }}"),
    ("PowerShell", "$x = $env:{n} = '1'"),
    ("PowerShell", "$env:{n} *= 2"),
    ("PowerShell", "$ExecutionContext.SessionState.InvokeProvider.Item.New('env:', '{n}', $null, '1')"),
    ("PowerShell", "$ExecutionContext.SessionState.PSVariable.Set('env:{n}', '1')"),
    ("PowerShell", "Microsoft.PowerShell.Management\\Set-Item env:{n} 1"),
    ("Bash", "pwsh -c 'sc env:{n} 1'"),
    ("Bash", "pwsh -Command '$x = ni env:{n} -Value 1'"),
    ("PowerShell", "$env:{n}, $b = '1', '2'"),
    ("PowerShell", "$env:{n} , $b = '1', '2'"),
    ("PowerShell", "$env:{n}++"),
    ("PowerShell", "++$env:{n}"),
    ("Bash", "'C:\\Program Files\\PowerShell\\7\\pwsh.exe' -c 'cd env:; sc {n} 1'"),
    ("Bash", "\"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe\" -Command \"cd env:; ni {n} -Value 1\""),
    ("Bash", "pwsh-preview -c 'cd env:; sc {n} 1'"),
    ("Bash", "powershell -c 'cp env:{n} env:OTHER'"),
    ("PowerShell", "$env:{n} -= 1"), ("PowerShell", "$env:{n} /= 1"), ("PowerShell", "$env:{n} %= 1"),
    ("PowerShell", "$Env:{n} = '1'"), ("PowerShell", "${{ENV:{n}}} = '1'"), ("PowerShell", "--$env:{n}"),
    ("PowerShell", "$env:{n}--"), ("PowerShell", "$env:{n} ++"), ("PowerShell", "$env:{n} --"),
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
    ("PowerShell", "[Environment]::GetEnvironmentVariable('{n}')"),
    ("PowerShell", "[Environment]::SetEnvironmentVariable('OTHER', '{n}')"), ("PowerShell", "$env:{n}_OLD = '1'"),
    ("PowerShell", "Write-Output xcp {n}"), ("PowerShell", "Write-Output cpx {n}"), ("PowerShell", "Write-Output cp-x {n}"),
    ("PowerShell", "Write-Output $cp {n}"), ("PowerShell", "Write-Output x-cp {n}"), ("PowerShell", "Write-Output a.cp {n}"),
    ("PowerShell", "Write-Output cp.txt {n}"), ("PowerShell", "Write-Output x:cp {n}"), ("PowerShell", "Write-Output cp:x {n}"),
    ("Bash", "cp a b; grep -n {n} pwsh-notes.md"), ("Bash", "grep -n 'env:{n}' hooks"),
    ("Bash", "cp a b; grep -n {n} README.md"), ("Bash", "mv notes/{n}.md notes/old.md"), ("Bash", "sc query {n}"),
])
def test_reading_or_removing_a_rule_variable_passes(world, name, tool, form):
    reason, _ = guard(world, world["agent"], form.format(n=name), tool=tool)
    assert reason is None


@pytest.mark.parametrize("name", ["AFK_WORKTREE_FOLDER", "AFK_ALLOW_PROTECTED"])
@pytest.mark.parametrize("form", [
    "Set-Content -Path out.txt -Value $env:{n}", "Add-Content log.txt \"$env:{n}\"", "Add-Content log.txt $env:{n}",
    "Set-Content -Value $env:{n} out.txt", "Copy-Item env:{n} out.txt", "Copy-Item env:{n} env:OTHER",
    "Rename-Item env:{n} OTHER", "Move-Item env:{n} env:OTHER", "New-Item env:OTHER -Value $env:{n}",
    "Set-Content -NoNewline out.txt $env:{n}", "Add-Content -Force log.txt \"$env:{n}\"",
    "Set-Content out.txt $env:{n} -NoNewline", "Set-Location env:; Set-Location C:\\; Set-Content {n} 1",
    "Add-Content log.txt $($env:{n})", "Set-Content out.txt $(Get-Content env:{n})",
])
def test_an_item_writer_beside_a_rule_variable_is_refused_even_when_it_reads(world, name, form):
    """D-76: an item writer and the name in one command count as a write, whatever the operand spelling."""
    reason, _ = guard(world, world["agent"], form.format(n=name), tool="PowerShell")
    assert reason is not None and reason.startswith(f"refused to set {name} in an agent command. Cause: ")


@pytest.mark.parametrize("name", ["AFK_WORKTREE_FOLDER", "AFK_ALLOW_PROTECTED"])
@pytest.mark.parametrize("form", [
    "Remove-Item env:{n}", "Write-Output $env:{n}", "Get-Content env:{n}", "if ($env:{n} -eq '1') {{ Write-Output y }}",
    "ls $env:{n} -- README.md", "$b,$env:{n} = 1,2", "$b,$env:{n}=1,2", "($b,$env:{n}) = 1,2",
    "$null,${{env:{n}}} = 1,2", "[int]$env:{n}=1", "[string]$env:{n} = '1'", "foreach ($env:{n} in 1,2) {{ }}",
])
def test_the_env_drive_spelling_of_a_rule_variable_is_refused_even_when_it_reads(world, name, form):
    """D-78: `$env:NAME`, `${env:NAME}` and `env:NAME` refuse the command, whatever surrounds them."""
    reason, _ = guard(world, world["agent"], form.format(n=name), tool="PowerShell")
    assert reason is not None and reason.startswith(f"refused to set {name} in an agent command. Cause: ")


def test_eval_drops_the_escapes_bash_drops(world):
    reason, _ = guard(world, world["agent"], "eval AFK_ALLOW_\\PROTECTED=1 ls")
    assert reason is not None and reason.startswith("refused to set AFK_ALLOW_PROTECTED")


@pytest.mark.parametrize("command", ["iex 'git worktree add ../../out'",
                                     "Invoke-Expression \"git worktree add ../../out\""])
def test_invoke_expression_is_read_like_eval(world, command):
    reason, _ = guard(world, world["agent"], command, tool="PowerShell")
    assert_outside(reason, world["root"] / "out", world["base"])


def test_the_bench_times_the_refusal_path_it_names(tmp_path):
    """The bench exits 1 when a scenario answers from another path; its guard scenarios answer from the refusal."""
    done = subprocess.run([sys.executable, str(PLUGIN_ROOT / "hooks" / "tests" / "bench-hooks.py"), "--runs", "1",
                           "--only", "bash-listed", "bash-worktree-add", "bash-worktree-move"], cwd=PLUGIN_ROOT,
                          capture_output=True, text=True, timeout=600)
    assert done.returncode == 0, done.stdout + done.stderr
    assert done.stdout.count("added over bash-listed:") == 2, done.stdout


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
