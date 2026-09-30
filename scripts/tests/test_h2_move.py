"""The H-2 move: a refused session gets a worktree cut detached, and the launch command.

Disposable repositories; a stub `herdr` and a stub harness stand in for the real ones.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
GUARD = PLUGIN_ROOT / "hooks" / "protected-branch-guard.py"
LAUNCH = PLUGIN_ROOT / "scripts" / "afk-launch.py"
IDENTITY = ("-c", "user.name=t", "-c", "user.email=t@example.com")
SCRUB = ("AFK_", "CLAUDE", "CODEX", "HERDR", "PLUGIN_ROOT", "GH_", "GITHUB_", "GITLAB_")


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(cwd), *IDENTITY, *args], check=True, capture_output=True,
                          text=True).stdout.strip()


def env_of(**extra: str) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith(SCRUB)}
    env.update(AFK_PLUGIN_ROOT=str(PLUGIN_ROOT), AFK_PROVIDER="codex", **extra)
    return env


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    path = tmp_path / "my repo"
    path.mkdir()
    git(path, "init", "-q", "-b", "main")
    git(path, "commit", "-q", "--allow-empty", "-m", "seed")
    return path


def refuse(cwd: Path, session: str, **extra: str) -> subprocess.CompletedProcess:
    call = {"session_id": session, "cwd": str(cwd), "hook_event_name": "PreToolUse", "tool_name": "Bash",
            "tool_input": {"command": "ls"}}
    return subprocess.run([sys.executable, str(GUARD)], input=json.dumps(call), capture_output=True, text=True,
                          cwd=cwd, env=env_of(**extra), timeout=120)


def typed_path(text: str) -> str:
    found = re.findall(r"^/cd (.+?)\s*$", text, re.M)
    assert len(found) == 1, text
    return found[0]


def wait_for(path: Path, seconds: float = 600) -> bool:
    end = time.time() + seconds
    while time.time() < end:
        if (path / ".git").exists():
            return True
        time.sleep(1)
    return False


def test_the_refusal_names_the_pending_path_at_once_and_the_worktree_appears(repo):
    started = time.time()
    done = refuse(repo, "s1")
    assert done.returncode == 2 and time.time() - started < 15, done.stderr
    path = Path(typed_path(done.stderr))
    assert path.parent.name == "worktrees" and path.parent.parent.name == ".codex"
    assert wait_for(path), "the detached creation cut the worktree"
    assert git(path, "rev-parse", "--abbrev-ref", "HEAD").startswith("worktree-session-")


def test_a_second_refusal_of_the_same_session_names_the_same_path_and_cuts_nothing_more(repo):
    first = typed_path(refuse(repo, "s2").stderr)
    second = typed_path(refuse(repo, "s2").stderr)
    assert first == second
    assert wait_for(Path(first))
    assert git(repo, "worktree", "list", "--porcelain").count("worktree ") == 2


def test_two_sessions_get_two_paths(repo):
    a, b = typed_path(refuse(repo, "sa").stderr), typed_path(refuse(repo, "sb").stderr)
    assert a != b


def stub_herdr(tmp_path: Path, read_text: str = "") -> tuple[str, Path]:
    log = tmp_path / "herdr.log"
    script = tmp_path / "herdr_stub.py"
    script.write_text(
        "import json, sys\n"
        f"open(r'{log}', 'a').write(json.dumps(sys.argv[1:]) + chr(10))\n"
        "if sys.argv[1:3] == ['agent', 'get']:\n"
        "    print(json.dumps({'result': {'agent': {'agent': 'codex', 'agent_status': 'idle'}}}))\n"
        "elif sys.argv[1:3] == ['agent', 'read']:\n"
        f"    print({read_text!r})\n"
        "else:\n"
        "    print(json.dumps({'result': {'type': 'ok'}}))\n", encoding="utf-8")
    launcher = tmp_path / ("herdr.cmd" if os.name == "nt" else "herdr")
    if os.name == "nt":
        launcher.write_text(f'@"{sys.executable}" "{script}" %*\r\n', encoding="utf-8")
    else:
        launcher.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n', encoding="utf-8")
        launcher.chmod(0o755)
    return str(launcher), log


def prompts(log: Path) -> list[list[str]]:
    if not log.exists():
        return []
    return [c for c in map(json.loads, log.read_text(encoding="utf-8").splitlines()) if c[:2] == ["agent", "prompt"]]


def test_inside_herdr_the_helper_types_the_unquoted_cd_line_once(repo, tmp_path):
    herdr, log = stub_herdr(tmp_path, "Working directory changed to: x")
    done = refuse(repo, "s3", HERDR_ENV="1", HERDR_PANE_ID="w:p1", HERDR_BIN_PATH=herdr)
    path = typed_path(done.stderr)
    end = time.time() + 600
    while time.time() < end and not prompts(log):
        time.sleep(1)
    found = prompts(log)
    assert found and found[0][2] == "w:p1" and found[0][3] == f"/cd {path}", found
    assert len(found) == 1


def test_the_helper_retries_only_when_the_harness_refused_the_line(tmp_path):
    spec = importlib.util.spec_from_file_location("afk_move", PLUGIN_ROOT / "scripts" / "afk-move.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.SETTLE = 0
    herdr, log = stub_herdr(tmp_path, "'/cd' is disabled while a task is in progress.")
    module.type_line(herdr, "w:p2", Path("C:/x"))
    assert len(prompts(log)) == module.ATTEMPTS


def fake_harness(tmp_path: Path) -> tuple[Path, Path]:
    bin_dir = tmp_path / "fake-bin"
    bin_dir.mkdir()
    record = tmp_path / "ran.json"
    body = f'import json, os, sys\njson.dump({{"cwd": os.getcwd(), "argv": sys.argv[1:]}}, open(r"{record}", "w"))\n'
    (bin_dir / "codex.py").write_text(body, encoding="utf-8")
    if os.name == "nt":
        (bin_dir / "codex.cmd").write_text(f'@"{sys.executable}" "{bin_dir / "codex.py"}" %*\r\n', encoding="utf-8")
    else:
        (bin_dir / "codex").write_text(f'#!/bin/sh\nexec "{sys.executable}" "{bin_dir / "codex.py"}" "$@"\n',
                                       encoding="utf-8")
        (bin_dir / "codex").chmod(0o755)
    return bin_dir, record


def launch(where: Path, bin_dir: Path, *args: str) -> subprocess.CompletedProcess:
    env = env_of()
    env["PATH"] = str(bin_dir) + os.pathsep + env["PATH"]
    return subprocess.run([sys.executable, str(LAUNCH), "codex", *args], capture_output=True, text=True,
                          cwd=where, env=env, timeout=600)


def test_launch_from_the_main_checkout_runs_the_harness_in_a_new_worktree(repo, tmp_path):
    bin_dir, record = fake_harness(tmp_path)
    done = launch(repo, bin_dir, "--model", "x")
    assert done.returncode == 0, done.stderr
    ran = json.loads(record.read_text(encoding="utf-8"))
    assert ran["argv"] == ["--model", "x"] and Path(ran["cwd"]).resolve() != repo.resolve()
    assert git(Path(ran["cwd"]), "rev-parse", "--abbrev-ref", "HEAD").startswith("worktree-session-")


def test_launch_from_an_unprotected_worktree_makes_no_worktree(repo, tmp_path):
    linked = tmp_path / "linked"
    git(repo, "worktree", "add", "-q", "-b", "topic", str(linked))
    bin_dir, record = fake_harness(tmp_path)
    before = git(repo, "worktree", "list", "--porcelain")
    done = launch(linked, bin_dir)
    assert done.returncode == 0, done.stderr
    assert Path(json.loads(record.read_text(encoding="utf-8"))["cwd"]).resolve() == linked.resolve()
    assert git(repo, "worktree", "list", "--porcelain") == before


def test_the_provider_json_and_shell_folder_declarations_agree():
    for name in ("claude", "codex"):
        declared = json.loads((PLUGIN_ROOT / "hooks" / "lib" / "providers" / f"{name}.json").read_text(
            encoding="utf-8"))["worktree_folder"]
        shell = (PLUGIN_ROOT / "hooks" / "lib" / "providers" / f"{name}.sh").read_text(encoding="utf-8")
        assert f"'{declared}'" in shell
