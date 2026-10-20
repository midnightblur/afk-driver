"""The spawn permission check over real settings files, read through the real provider layer, and its setup row."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "team"))

import permission  # noqa: E402

needs_bash = pytest.mark.skipif(permission._bash() is None, reason="no POSIX shell on this machine")
CLAUDE_SH = REPO / "hooks" / "lib" / "providers" / "claude.sh"


def _constant() -> str:
    found = re.search(r"^AFK_SPAWN_ALLOW_RULE='([^']+)'$", CLAUDE_SH.read_text(encoding="utf-8"), re.M)
    assert found, "claude.sh holds no single-quoted AFK_SPAWN_ALLOW_RULE line"
    return found.group(1)


RULE = _constant()


def _matches(rule: str, command: str) -> bool:
    """A Bash rule's documented wildcard match: `*` is any text; a lone trailing ` *` also takes the bare command."""
    inner = re.fullmatch(r"Bash\((.*)\)", rule, re.S)
    assert inner, rule
    pattern = inner.group(1)
    if pattern.endswith(":*"):
        pattern = pattern[:-2] + " *"
    regex = ".*".join(re.escape(part) for part in pattern.split("*"))
    if pattern.endswith(" *") and pattern.count("*") == 1:
        regex = re.escape(pattern[:-2]) + "(?: .*)?"
    return re.fullmatch(regex, command, re.S) is not None


@pytest.fixture
def home(tmp_path: Path) -> dict:
    config, repo = tmp_path / "config", tmp_path / "repo"
    config.mkdir()
    (repo / ".claude").mkdir(parents=True)
    env = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_CONFIG_DIR", "AFK_PROVIDER")}
    env.update(AFK_PROVIDER="claude", CLAUDE_CONFIG_DIR=str(config), HOME=str(tmp_path / "nohome"))
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
def test_a_rule_naming_an_old_plugin_path_is_stale(home: dict) -> None:
    _write(home["user"], allow=['Bash(afk-python "/home/u/.claude/plugins/cache/afk/1.0.0/scripts/afk-team.py" *)'])
    answer = _check(home)
    assert answer["ok"] is False and answer["problem"] == "stale" and "/afk:setup" in answer["says"]


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
    assert answer["ok"] is True and str(home["user"]).replace("\\", "/") not in answer["files"]


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


@needs_bash
def test_the_check_reads_the_one_constant(home: dict) -> None:
    answer = _check(home)
    assert answer["rule"] == RULE


def _cli(home: dict, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(REPO / "scripts" / "team" / "permission.py"), *args],
                          cwd=str(home["repo"]), env=home["env"], capture_output=True, text=True, check=False)


@needs_bash
def test_cli_prints_the_rule_and_answers_by_exit_code(home: dict) -> None:
    assert _cli(home, "rule").stdout.strip() == RULE
    assert json.loads(_cli(home, "rule", "--json").stdout) == RULE
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
