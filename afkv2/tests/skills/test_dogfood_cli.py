"""dogfood.py start outside herdr, as a child process: plan rows VR-005 and VR-006 (environment E-CI-SUB).

Each test runs the real script by an argument list with its own environment: a scratch LOCALAPPDATA with an install
record that has the source line, no inherited herdr variable, and a PATH that holds no herdr.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

AFKV2 = Path(__file__).resolve().parents[2]
DOGFOOD = AFKV2 / "skills" / "dogfood" / "scripts" / "dogfood.py"
ASK = "step 4 of small-change is unclear"  # D-ASK WE-01
LIMIT_S = 60


@pytest.fixture
def world(tmp_path):
    """D-REC with source: a plugin source folder, its install record line, and the WE-01 ask file."""
    source = tmp_path / "df-src"
    (source / "afkv2" / ".claude-plugin").mkdir(parents=True)
    (source / "afkv2" / ".claude-plugin" / "plugin.json").write_text('{"name": "afkv2"}', encoding="utf-8")
    data = tmp_path / "local" / "afkv2"
    data.mkdir(parents=True)
    (data / "install.txt").write_text(f"installed 2026-11-26T00:00:00+00:00\npython {sys.executable}\n"
                                      f"source {source}\n", encoding="utf-8")
    ask = tmp_path / "ask.txt"
    ask.write_text(ASK, encoding="utf-8")
    return {"tmp": tmp_path, "data": data, "ask": ask}


def child_env(world, **extra):
    """The child's whole environment: built, never inherited, so no herdr variable of this shell leaks in. PATH holds
    only the folder of this Python; SystemRoot lets Python start on Windows."""
    env = {"PATH": str(Path(sys.executable).parent), "LOCALAPPDATA": str(world["tmp"] / "local"),
           "USERPROFILE": str(world["tmp"] / "home"), "HOME": str(world["tmp"] / "home")}
    for name in ("SystemRoot", "SYSTEMROOT", "TEMP", "TMP"):
        if os.environ.get(name):
            env[name] = os.environ[name]
    env.update(extra)
    return env


def start(world, env):
    done = subprocess.run([sys.executable, str(DOGFOOD), "start", "--ask-file", str(world["ask"])], env=env,
                          cwd=str(world["tmp"]), capture_output=True, text=True, encoding="utf-8",
                          stdin=subprocess.DEVNULL, timeout=LIMIT_S)
    lines = done.stdout.strip().splitlines()
    assert len(lines) == 1, f"not 1 JSON line: {done.stdout!r} {done.stderr!r}"
    return done.returncode, json.loads(lines[0])


def assert_outside_herdr(world, code, answer):
    assert code == 1
    assert answer["ok"] is False and answer["error"]["code"] == "outside-herdr"
    reason = answer["error"]["reason"]
    assert "start herdr" in reason and "run the skill again" in reason
    assert not list(world["data"].glob("dogfood-*.json")), "a state file was written"
    assert sorted(path.name for path in world["data"].iterdir()) == ["install.txt"]


def test_vr005_start_with_no_herdr_env_refuses_outside_herdr_and_writes_no_state(world):
    code, answer = start(world, child_env(world))
    assert_outside_herdr(world, code, answer)


def test_vr006_start_with_herdr_env_but_no_herdr_on_path_refuses_outside_herdr_and_writes_no_state(world):
    env = child_env(world, HERDR_ENV="1", HERDR_PANE_ID="w1:p1")
    assert not any((Path(folder) / name).exists() for folder in env["PATH"].split(os.pathsep)
                   for name in ("herdr", "herdr.exe", "herdr.cmd")), "herdr is on the child PATH"
    code, answer = start(world, env)
    assert_outside_herdr(world, code, answer)
