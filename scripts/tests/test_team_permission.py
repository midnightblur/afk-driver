"""The spawn permission check over real settings files, read through the real provider layer, and its setup row."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "team"))

import permission  # noqa: E402

needs_bash = pytest.mark.skipif(permission._bash() is None, reason="no POSIX shell on this machine")
needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="no git on this machine")
CLAUDE_SH = REPO / "hooks" / "lib" / "providers" / "claude.sh"


def _constant() -> str:
    found = re.search(r"^\s+local AFK_SPAWN_ALLOW_RULE='([^']+)'$", CLAUDE_SH.read_text(encoding="utf-8"), re.M)
    assert found, "claude.sh holds no single-quoted `local AFK_SPAWN_ALLOW_RULE` line"
    return found.group(1)


RULE = _constant()


def _matches(rule: str, command: str) -> bool:
    """A Bash rule ending in one ` *` matches its prefix alone, or its prefix, a space and any text."""
    inner = re.fullmatch(r"Bash\((.*) \*\)", rule, re.S)
    assert inner and "*" not in inner.group(1), f"_matches models only a single trailing ` *`: {rule}"
    return re.fullmatch(re.escape(inner.group(1)) + r"(?: .*)?", command, re.S) is not None


def _windows_shell() -> bool:
    """The same `uname -s` test the claude adapter makes, run in the check's own shell."""
    done = subprocess.run([str(permission._bash()), "-c", "uname -s"], capture_output=True, text=True, check=True)
    return done.stdout.strip().startswith(("MINGW", "MSYS", "CYGWIN"))


WINDOWS_SHELL = permission._bash() is not None and _windows_shell()
on_windows = pytest.mark.skipif(not WINDOWS_SHELL, reason="the main-checkout skip applies only on a Windows shell")
off_windows = pytest.mark.skipif(WINDOWS_SHELL, reason="a Windows shell never reads the main checkout's local file")


@pytest.fixture
def home(tmp_path: Path) -> dict:
    config, repo = tmp_path / "config", tmp_path / "repo"
    config.mkdir()
    (repo / ".claude").mkdir(parents=True)
    env = {k: v for k, v in os.environ.items()
           if k not in ("CLAUDE_CONFIG_DIR", "AFK_PROVIDER") and not k.startswith("GIT_")}
    env.update(AFK_PROVIDER="claude", CLAUDE_CONFIG_DIR=str(config), HOME=str(tmp_path / "nohome"),
               GIT_CEILING_DIRECTORIES=str(tmp_path))
    return {"env": env, "user": config / "settings.json", "repo": repo,
            "local": repo / ".claude" / "settings.local.json", "project": repo / ".claude" / "settings.json"}


def _write(path: Path, allow: list[str] = (), deny: list[str] = (), ask: list[str] = ()) -> None:
    path.write_text(json.dumps({"permissions": {"allow": list(allow), "deny": list(deny), "ask": list(ask)}}),
                    encoding="utf-8")


def _check(home: dict) -> dict:
    return permission.check_spawn_permission(home["repo"], env=home["env"])


def test_rule_covers_every_transport_verb() -> None:
    commands = permission.verb_commands()
    assert [c.split()[2] for c in commands] == ["agent-start", "agent-send", "agent-status", "agent-read",
                                               "agent-stop", "agent-list"]
    assert all(_matches(RULE, command) for command in commands)


def test_rule_matches_only_the_team_entry_script() -> None:
    assert not _matches(RULE, 'afk-python "${AFK_PLUGIN_ROOT}/scripts/afk-config.py" get x')
    assert not _matches(RULE, "afk-python -c 'print(1)'")
    assert not _matches(RULE, 'afk-python "/home/u/.claude/plugins/cache/afk/1.0.0/scripts/afk-team.py" agent-send x')


def test_rule_names_no_plugin_version() -> None:
    assert "${AFK_PLUGIN_ROOT}" in RULE and not re.search(r"\d+\.\d+\.\d+", RULE)


@needs_bash
def test_settings_without_the_rule_refuse_naming_it_and_setup(home: dict) -> None:
    _write(home["user"], allow=["Bash(git status)"])
    answer = _check(home)
    assert answer["ok"] is False and answer["problem"] == "missing"
    assert answer["rule"] == RULE and RULE in answer["says"] and "/afk:setup" in answer["says"]
    assert "nothing was started" in answer["says"]


@needs_bash
def test_no_settings_file_refuses(home: dict) -> None:
    answer = _check(home)
    assert answer["ok"] is False and answer["problem"] == "missing" and answer["files"] == []


@pytest.mark.parametrize("where", ["user", "project", "local"])
@needs_bash
def test_settings_with_the_rule_give_ok(home: dict, where: str) -> None:
    _write(home[where], allow=["Bash(git status)", RULE])
    answer = _check(home)
    assert answer["ok"] is True and answer["problem"] is None and answer["rule"] == RULE


def _linked_worktree(home: dict, tmp_path: Path, *init: str) -> tuple[Path, Path]:
    """A main checkout whose `.claude/settings.local.json` holds the rule, and a linked worktree of it."""
    main, tree = tmp_path / "main", tmp_path / "tree"
    git_env = dict(home["env"], GIT_CONFIG_NOSYSTEM="1")
    subprocess.run(["git", "init", "-q", *init, str(main)], cwd=tmp_path, env=git_env, check=True, capture_output=True)
    for args in (["-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-q", "--allow-empty", "-m",
                  "init"], ["worktree", "add", "-q", str(tree)]):
        subprocess.run(["git", *args], cwd=main, env=git_env, check=True, capture_output=True, text=True)
    (main / ".claude").mkdir()
    _write(main / ".claude" / "settings.local.json", allow=[RULE])
    return main, tree


def _assert_main_file_unread(tree: Path, env: dict) -> None:
    listed = permission._adapter(tree.resolve(), env, subprocess.run)["files"]
    # The listing is the discriminating assertion: no settings file exists under a foreign entry.
    assert len(listed) == 3,f"the adapter lists only the user file and the worktree's two files: {listed}"
    answer = permission.check_spawn_permission(tree, env=env)
    assert answer["ok"] is False and answer["problem"] == "missing" and answer["files"] == []


@needs_bash
@needs_git
@off_windows
def test_a_linked_worktree_reads_the_main_checkout_local_file(home: dict, tmp_path: Path) -> None:
    _, tree = _linked_worktree(home, tmp_path)
    answer = permission.check_spawn_permission(tree, env=home["env"])
    assert answer["ok"] is True and answer["problem"] is None
    tail = "main/.claude/settings.local.json"
    assert [f[-len(tail):] for f in answer["files"]] == [tail]


@needs_bash
@needs_git
@on_windows
def test_a_linked_worktree_on_windows_skips_the_main_checkout_local_file(home: dict, tmp_path: Path) -> None:
    _, tree = _linked_worktree(home, tmp_path)
    _assert_main_file_unread(tree, home["env"])


@needs_bash
@needs_git
@off_windows
def test_a_main_checkout_at_the_home_directory_is_not_read(home: dict, tmp_path: Path) -> None:
    main, tree = _linked_worktree(home, tmp_path)
    _assert_main_file_unread(tree, dict(home["env"], HOME=str(main)))


@needs_bash
@needs_git
@off_windows
def test_a_git_dir_not_named_dot_git_is_not_read(home: dict, tmp_path: Path) -> None:
    _, tree = _linked_worktree(home, tmp_path, "--separate-git-dir", str(tmp_path / "store"))
    _assert_main_file_unread(tree, home["env"])


def _foreign_dir() -> Path:
    foreign = Path(shutil.which("sh") or "").parent
    if not hasattr(os, "getuid") or not foreign.is_dir() or foreign.stat().st_uid == os.getuid():
        pytest.skip("no directory owned by another user to link to")
    return foreign


def _git_naming(tmp_path: Path, env: dict, top: Path) -> dict:
    stub = tmp_path / "bin"
    stub.mkdir()
    (stub / "git").write_text(f"#!/bin/sh\nprintf '%s\\n' '{top}/.git'\n", encoding="utf-8", newline="\n")
    (stub / "git").chmod(0o755)
    return dict(env, PATH=f"{stub}{os.pathsep}{env.get('PATH', '')}")


@needs_bash
@needs_git
@off_windows
def test_a_main_checkout_claude_dir_owned_by_another_user_is_not_read(home: dict, tmp_path: Path) -> None:
    foreign = _foreign_dir()
    main, tree = _linked_worktree(home, tmp_path)
    shutil.rmtree(main / ".claude")
    (main / ".claude").symlink_to(foreign, target_is_directory=True)
    _assert_main_file_unread(tree, home["env"])


@pytest.mark.parametrize("entry", ["root", "git dir"])
@needs_bash
@off_windows
def test_a_main_checkout_root_or_git_dir_owned_by_another_user_is_not_read(home: dict, tmp_path: Path,
                                                                         entry: str) -> None:
    foreign = _foreign_dir()
    top = foreign if entry == "root" else tmp_path / "top"
    if entry == "git dir":
        top.mkdir()
        (top / ".git").symlink_to(foreign, target_is_directory=True)
    # A stub git names that checkout, so an entry can belong to another user without root rights.
    _assert_main_file_unread(home["repo"], _git_naming(tmp_path, home["env"], top))


@needs_bash
def test_a_rule_for_the_start_alone_is_not_enough(home: dict) -> None:
    start_only = RULE[:-len(" *)")] + " agent-start *)"
    assert _matches(start_only, permission.verb_commands()[0])
    assert not _matches(start_only, permission.verb_commands()[1])
    _write(home["user"], allow=[start_only])
    answer = _check(home)
    assert answer["ok"] is False and answer["problem"] == "stale" and start_only in answer["says"]
    assert RULE in answer["says"]


@needs_bash
def test_the_current_rule_beside_an_old_entry_gives_ok(home: dict) -> None:
    old = 'Bash(afk-python "/opt/plugins/afk/1.0.0/scripts/afk-team.py" *)'
    _write(home["user"], allow=[old])
    _write(home["local"], allow=[RULE])
    answer = _check(home)
    assert answer["ok"] is True and answer["problem"] is None and answer["rule"] == RULE
    tails = ["config/settings.json", "repo/.claude/settings.local.json"]
    assert [f.replace("\\", "/")[-len(t):] for f, t in zip(answer["files"], tails)] == tails
    assert len(answer["files"]) == 2


@needs_bash
def test_a_rule_naming_an_old_plugin_path_is_stale(home: dict) -> None:
    _write(home["user"], allow=['Bash(afk-python "/home/u/.claude/plugins/cache/afk/1.0.0/scripts/afk-team.py" *)'])
    answer = _check(home)
    assert answer["ok"] is False and answer["problem"] == "stale" and "/afk:setup" in answer["says"]


@pytest.mark.parametrize("where, suffix", [("project", "repo/.claude/settings.json"),
                                           ("local", "repo/.claude/settings.local.json")])
@needs_bash
def test_a_stale_refusal_names_the_file_that_holds_the_entry(home: dict, where: str, suffix: str) -> None:
    _write(home["user"], allow=["Bash(git status)"])
    _write(home[where], allow=['Bash(afk-python "/old/scripts/afk-team.py" *)'])
    answer = _check(home)
    assert answer["problem"] == "stale"
    assert f"{suffix} permissions.allow holds `Bash(afk-python \"/old/scripts/afk-team.py\" *)`" in answer["says"]
    assert "config/settings.json" not in answer["says"]


@pytest.mark.parametrize("listed", ["deny", "ask"])
@needs_bash
def test_the_rule_in_a_block_list_refuses(home: dict, listed: str) -> None:
    _write(home["user"], allow=[RULE])
    _write(home["local"], **{listed: [RULE]})
    answer = _check(home)
    assert answer["ok"] is False and answer["problem"] == "blocked" and f"permissions.{listed}" in answer["says"]


@needs_bash
def test_an_unreadable_settings_file_is_skipped(home: dict) -> None:
    home["user"].write_text("{not json", encoding="utf-8")
    _write(home["local"], allow=[RULE])
    answer = _check(home)
    assert answer["ok"] is True and len(answer["files"]) == 1
    assert answer["files"][0].endswith("repo/.claude/settings.local.json")


@needs_bash
def test_a_harness_with_no_rule_needs_none(home: dict) -> None:
    home["env"]["AFK_PROVIDER"] = "codex"
    answer = _check(home)
    assert answer["ok"] is True and answer["provider"] == "codex" and answer["rule"] == ""


@needs_bash
def test_an_undetected_harness_checks_no_rule(home: dict) -> None:
    home["env"]["AFK_PROVIDER"] = "no-such-harness"
    answer = _check(home)
    assert answer["ok"] is True and answer["provider"] == "unknown" and "AFK_PROVIDER" in answer["says"]


_PRINTS_RULE = "afk_newharness_spawn_allow_rule() { printf '%s\\n' 'Bash(x *)'; }\n"


@pytest.mark.parametrize("adapter, missing, rule", [
    ("", "afk_newharness_spawn_allow_rule", ""),
    (_PRINTS_RULE, "afk_newharness_spawn_rule_files", "Bash(x *)"),
    (_PRINTS_RULE + "afk_newharness_spawn_rule_files() { printf '%s\\n' /nowhere; }\n",
     "afk_newharness_spawn_rule_lists", "Bash(x *)"),
])
@needs_bash
def test_a_detected_harness_without_the_spawn_functions_refuses(home: dict, tmp_path: Path, monkeypatch,
                                                                adapter: str, missing: str, rule: str) -> None:
    core = tmp_path / "plugin" / "hooks" / "lib"
    (core / "providers").mkdir(parents=True)
    shutil.copy(REPO / "hooks" / "lib" / "provider.sh", core / "provider.sh")
    (core / "providers" / "newharness.sh").write_text(adapter, encoding="utf-8", newline="\n")
    bash = permission._bash()
    monkeypatch.setattr(permission, "PLUGIN", tmp_path / "plugin")
    monkeypatch.setattr(permission, "_bash", lambda: bash)
    home["env"]["AFK_PROVIDER"] = "newharness"
    answer = _check(home)
    assert answer["ok"] is False and answer["problem"] == "provider-layer" and answer["provider"] == "newharness"
    assert missing in answer["says"] and 'PROVIDERS.md "Spawn allow rule"' in answer["says"]
    assert "/afk:setup" in answer["says"]
    assert answer["rule"] == rule


def _fake(returncode: int = 0, stdout: str = "", stderr: str = "", raises: Exception | None = None):
    def run(*_args, **_kwargs):
        if raises is not None:
            raise raises
        return subprocess.CompletedProcess([], returncode, stdout, stderr)
    return run


def _layer_refusal(home: dict, run) -> dict:
    answer = permission.check_spawn_permission(home["repo"], env=home["env"], run=run)
    assert answer["ok"] is False and answer["problem"] == "provider-layer"
    assert answer["says"].endswith("; run /afk:setup; nothing was started")
    return answer


@needs_bash
def test_a_provider_layer_timeout_refuses(home: dict) -> None:
    answer = _layer_refusal(home, _fake(raises=subprocess.TimeoutExpired(cmd="bash", timeout=30)))
    assert "timed out" in answer["says"] and answer["rule"] == ""


@needs_bash
def test_a_provider_layer_failure_refuses_with_its_stderr(home: dict) -> None:
    answer = _layer_refusal(home, _fake(returncode=2, stderr="adapter broke here"))
    assert "exited 2" in answer["says"] and "adapter broke here" in answer["says"]


@needs_bash
def test_a_provider_layer_failure_keeps_the_printed_rule(home: dict) -> None:
    answer = _layer_refusal(home, _fake(returncode=2, stdout=f"provider\tclaude\nrule\t{RULE}\n"))
    assert answer["provider"] == "claude" and answer["rule"] == RULE and "exited 2" in answer["says"]


def test_no_posix_shell_refuses(home: dict, monkeypatch) -> None:
    monkeypatch.setattr(permission, "_bash", lambda: None)
    answer = _layer_refusal(home, _fake(raises=AssertionError("run must not be called")))
    assert "no POSIX shell" in answer["says"]


@needs_bash
def test_the_check_reads_the_one_constant(home: dict) -> None:
    answer = _check(home)
    assert answer["rule"] == RULE


def _cli(home: dict, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(REPO / "scripts" / "team" / "permission.py"), *args],
                          cwd=str(home["repo"]), env=home["env"], capture_output=True, text=True, check=False)


@needs_bash
def test_cli_rule_prints_the_rule_as_text_and_json(home: dict) -> None:
    assert _cli(home, "rule").stdout.strip() == RULE
    assert json.loads(_cli(home, "rule", "--json").stdout) == RULE


@needs_bash
def test_cli_check_answers_by_exit_code(home: dict) -> None:
    refused = _cli(home, "check")
    assert refused.returncode == 1 and json.loads(refused.stdout)["problem"] == "missing"
    _write(home["user"], allow=[RULE])
    assert _cli(home, "check").returncode == 0


def test_setup_offers_the_rule_and_never_writes_it() -> None:
    text = (REPO / "skills" / "afk" / "setup" / "MANIFEST.md").read_text(encoding="utf-8")
    rows = [r for r in re.split(r"\n(?=### )", text) if "scripts/team/permission.py" in r]
    assert len(rows) == 1, "exactly one register row runs the spawn permission check"
    row = rows[0]
    assert "**[opt-in]**" in row.splitlines()[0]
    assert re.search(r"\*\*Probe:\*\* .*permission\.py\" check", row)
    assert re.search(r"\*\*Fix:\*\* `human:`", row) and "permission.py\" rule" in row
    assert "never writes" in row and "no human present" in row
    assert "`provider-layer`" in row and "needs-human: <cause>" in row
    assert "skip this row unless the probe refused" in row
    tier = text.split("**Opt-in tier.**", 1)[1].split("\n\n", 1)[0]
    assert "names another status for that" in tier and "with or without a human present" in tier
