#!/usr/bin/env python3
"""`set_instruction_files.py` merges the Claude project-instructions key.

Asserts the merge is exact and idempotent, preserves other keys and the file's
indentation, backs up before a change, tolerates a missing file and missing
parents, and never touches the real ~/.claude — every case targets a tmp file
or a tmp CLAUDE_CONFIG_DIR.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = (Path(__file__).resolve().parents[2]
          / "skills" / "afk" / "setup" / "scripts" / "set_instruction_files.py")
KEYPATH = ("pluginConfigs", "agents-md@builtin", "options", "instructionFiles")
VALUE = "claude-md-and-agents-md"


def run(*args, env=None):
    return subprocess.run([sys.executable, str(SCRIPT), *args],
                          capture_output=True, text=True, env=env)


def value_of(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    for k in KEYPATH[:-1]:
        data = data[k]
    return data[KEYPATH[-1]]


def test_check_missing_file_is_unsatisfied(tmp_path):
    r = run(str(tmp_path / "settings.json"), "--check")
    assert r.returncode == 1


def test_fix_creates_file_then_check_passes(tmp_path):
    settings = tmp_path / "settings.json"
    assert run(str(settings)).returncode == 0
    assert value_of(settings) == VALUE
    assert run(str(settings), "--check").returncode == 0


def test_preserves_other_keys_and_indentation_and_backs_up(tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps(
        {"model": "opus", "pluginConfigs": {"other@x": {"k": 1}}}, indent=4),
        encoding="utf-8")
    assert run(str(settings)).returncode == 0
    data = json.loads(settings.read_text(encoding="utf-8"))
    assert data["model"] == "opus"                       # unrelated key kept
    assert data["pluginConfigs"]["other@x"] == {"k": 1}  # sibling plugin kept
    assert value_of(settings) == VALUE
    # 4-space indentation preserved.
    assert '\n    "model"' in settings.read_text(encoding="utf-8")
    backups = list(tmp_path.glob("settings.json.bak-*"))
    assert len(backups) == 1


def test_idempotent_no_second_backup(tmp_path):
    settings = tmp_path / "settings.json"
    run(str(settings))                       # first write, no pre-existing file -> no backup
    assert not list(tmp_path.glob("settings.json.bak-*"))
    r = run(str(settings))                   # already set -> no write, no backup
    assert r.returncode == 0
    assert "already" in r.stdout
    assert not list(tmp_path.glob("settings.json.bak-*"))


def test_tolerates_missing_parents(tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text("{}", encoding="utf-8")   # no pluginConfigs at all
    assert run(str(settings)).returncode == 0
    assert value_of(settings) == VALUE


def test_non_object_parent_refused_exit_2(tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text('{"pluginConfigs": "oops"}', encoding="utf-8")
    r = run(str(settings))
    assert r.returncode == 2


def test_respects_claude_config_dir(tmp_path, monkeypatch):
    cfg = tmp_path / "cfgdir"
    env = {"CLAUDE_CONFIG_DIR": str(cfg),
           "PATH": __import__("os").environ.get("PATH", "")}
    assert run(env=env).returncode == 0
    assert value_of(cfg / "settings.json") == VALUE
