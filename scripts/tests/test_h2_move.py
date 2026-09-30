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
    assert done.returncode == 0 and '"permissionDecision": "deny"' in done.stdout, done.stderr
    assert time.time() - started < 15
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
        f"    sys.stdout.buffer.write({read_text!r}.encode('utf-8') + chr(10).encode())\n"
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
    herdr, log = stub_herdr(tmp_path, "\u203a\nWorking directory changed to: x")
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
    herdr, log = stub_herdr(tmp_path, "\u203a\n'/cd' is disabled while a task is in progress.")
    module.type_line(herdr, "w:p2", Path("C:/x"))
    assert len(prompts(log)) == module.ATTEMPTS


def fake_harness(tmp_path: Path) -> tuple[Path, Path]:
    bin_dir = tmp_path / "fake-bin"
    bin_dir.mkdir()
    record = tmp_path / "ran.json"
    body = ('import json, os, subprocess, sys\n'
            'branch = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True,'
            ' text=True).stdout.strip()\n'
            f'json.dump({{"cwd": os.getcwd(), "argv": sys.argv[1:], "branch": branch}}, open(r"{record}", "w"))\n'
            'if os.environ.get("FAKE_DIRTY"):\n    open("w.txt", "w").write("x")\n')
    (bin_dir / "codex.py").write_text(body, encoding="utf-8")
    if os.name == "nt":
        (bin_dir / "codex.cmd").write_text(f'@"{sys.executable}" "{bin_dir / "codex.py"}" %*\r\n', encoding="utf-8")
    else:
        (bin_dir / "codex").write_text(f'#!/bin/sh\nexec "{sys.executable}" "{bin_dir / "codex.py"}" "$@"\n',
                                       encoding="utf-8")
        (bin_dir / "codex").chmod(0o755)
    return bin_dir, record


def launch(where: Path, bin_dir: Path, *args: str, dirty: bool = False) -> subprocess.CompletedProcess:
    env = env_of(**({"FAKE_DIRTY": "1"} if dirty else {}))
    env["PATH"] = str(bin_dir) + os.pathsep + env["PATH"]
    return subprocess.run([sys.executable, str(LAUNCH), "codex", *args], capture_output=True, text=True,
                          cwd=where, env=env, timeout=600)


def test_launch_from_the_main_checkout_runs_the_harness_in_a_new_worktree(repo, tmp_path):
    bin_dir, record = fake_harness(tmp_path)
    done = launch(repo, bin_dir, "--model", "x")
    assert done.returncode == 0, done.stderr
    ran = json.loads(record.read_text(encoding="utf-8"))
    assert ran["argv"] == ["--model", "x"] and Path(ran["cwd"]).resolve() != repo.resolve()
    assert ran["branch"].startswith("worktree-session-")


def test_r5_1_a_clean_launched_worktree_is_removed_when_the_harness_exits(repo, tmp_path):
    bin_dir, record = fake_harness(tmp_path)
    assert launch(repo, bin_dir).returncode == 0
    ran = json.loads(record.read_text(encoding="utf-8"))
    assert not Path(ran["cwd"]).exists()
    assert ran["branch"] not in git(repo, "branch", "--format=%(refname:short)").split()


def test_r5_1_a_launched_worktree_with_work_is_kept_under_this_launcher_as_owner(repo, tmp_path):
    bin_dir, record = fake_harness(tmp_path)
    assert launch(repo, bin_dir, dirty=True).returncode == 0
    assert Path(json.loads(record.read_text(encoding="utf-8"))["cwd"]).is_dir()
    found = list((repo / ".git" / "afk-worktrees").glob("*.json"))
    assert len(found) == 1 and json.loads(found[0].read_text(encoding="utf-8"))["owner"]["pid"]


def test_launch_from_an_unprotected_worktree_makes_no_worktree(repo, tmp_path):
    linked = tmp_path / "linked"
    git(repo, "worktree", "add", "-q", "-b", "topic", str(linked))
    bin_dir, record = fake_harness(tmp_path)
    before = git(repo, "worktree", "list", "--porcelain")
    done = launch(linked, bin_dir)
    assert done.returncode == 0, done.stderr
    assert Path(json.loads(record.read_text(encoding="utf-8"))["cwd"]).resolve() == linked.resolve()
    assert git(repo, "worktree", "list", "--porcelain") == before


def test_r5_8_the_provider_json_is_the_one_home_of_the_worktree_folder():
    for name in ("claude", "codex"):
        declared = json.loads((PLUGIN_ROOT / "hooks" / "lib" / "providers" / f"{name}.json").read_text(
            encoding="utf-8"))["worktree_folder"]
        assert declared
        shell = (PLUGIN_ROOT / "hooks" / "lib" / "providers" / f"{name}.sh").read_text(encoding="utf-8")
        assert "worktree_folder" not in shell


def test_r5_8_the_folder_override_reaches_the_promised_path_and_the_created_one(repo):
    path = Path(typed_path(refuse(repo, "sf", AFK_WORKTREE_FOLDER=".wt").stderr))
    assert path.parent.name == ".wt"
    assert wait_for(path)


def test_r5_2_a_target_outside_a_good_session_worktree_moves_nothing(repo, tmp_path):
    linked = tmp_path / "topic-wt"
    git(repo, "worktree", "add", "-q", "-b", "topic", str(linked))
    call = {"session_id": "s5", "cwd": str(linked), "hook_event_name": "PreToolUse", "tool_name": "Write",
            "tool_input": {"file_path": str(repo / "stray.txt"), "content": "x"}}
    done = subprocess.run([sys.executable, str(GUARD)], input=json.dumps(call), capture_output=True, text=True,
                          cwd=linked, env=env_of(), timeout=120)
    assert '"permissionDecision": "deny"' in done.stdout
    assert "/cd " not in done.stderr and "write inside this session's worktree" in done.stderr
    assert not list((repo / ".git").glob("afk-session/*.move"))


def test_r5_3_the_helper_starts_without_a_console_window(monkeypatch):
    spec = importlib.util.spec_from_file_location("afk_h2_move", PLUGIN_ROOT / "hooks" / "lib" / "h2_move.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    seen = {}
    monkeypatch.setattr(module.subprocess, "Popen", lambda argv, **kw: seen.update(kw))
    module.spawn(["x"])
    if os.name == "nt":
        assert seen["creationflags"] & 0x08000000 and not seen["creationflags"] & 0x00000008
    else:
        assert seen["start_new_session"] is True


def load_move():
    spec = importlib.util.spec_from_file_location("afk_move", PLUGIN_ROOT / "scripts" / "afk-move.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.SETTLE = 0
    return module


def test_r5_6_the_helper_does_not_type_over_the_humans_half_written_message(tmp_path):
    herdr, log = stub_herdr(tmp_path, "\u203a hello, I was about to ask")
    load_move().type_line(herdr, "w:p3", Path("C:/x"))
    calls = [json.loads(c) for c in log.read_text(encoding="utf-8").splitlines()]
    assert not any(c[:2] in (["agent", "prompt"], ["agent", "send-keys"]) for c in calls)


@pytest.mark.parametrize("shown", ["", "no composer on screen"])
def test_r8_4_an_unreadable_pane_gets_nothing_typed(tmp_path, shown):
    herdr, log = stub_herdr(tmp_path, shown)
    load_move().type_line(herdr, "w:p5", Path("C:/x"))
    calls = [json.loads(c) for c in log.read_text(encoding="utf-8").splitlines()]
    assert not any(c[:2] in (["agent", "prompt"], ["agent", "send-keys"]) for c in calls)


@pytest.mark.parametrize("shown", ["\u203a", "\u203a /cd C:/old"])
def test_r5_6_an_empty_composer_or_the_helpers_own_earlier_line_gets_the_line(tmp_path, shown):
    herdr, log = stub_herdr(tmp_path, shown)
    load_move().type_line(herdr, "w:p4", Path("C:/x"))
    assert prompts(log) and prompts(log)[0][3] == f"/cd {Path('C:/x')}"


def test_r5_7_a_failed_creation_is_recorded_and_later_refusals_say_why(tmp_path):
    repo = tmp_path / "strict"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    git(repo, "commit", "-q", "--allow-empty", "-m", "seed")
    (repo / ".afk").mkdir()
    (repo / ".afk" / "config.yaml").write_text("schema: 1\ngit:\n  branch-pattern: '^never/match$'\n",
                                               encoding="utf-8")
    path = typed_path(refuse(repo, "s7").stderr)
    end, marker = time.time() + 600, None
    while time.time() < end and marker is None:
        for found in (repo / ".git" / "afk-session").glob("*.move"):
            if "error" in json.loads(found.read_text(encoding="utf-8")):
                marker = found
        time.sleep(1)
    assert marker is not None, "the helper recorded why creation failed"
    second = refuse(repo, "s7")
    assert "/cd " not in second.stderr and "could not be created" in second.stderr
    assert not Path(path).exists()


def test_r5_9_a_marker_of_an_earlier_sessions_dead_worktree_is_not_reused(repo):
    first = typed_path(refuse(repo, "s9", AFK_MOVE_SPAWN="0").stderr)
    marker = next((repo / ".git" / "afk-session").glob("*.move"))
    name = json.loads(marker.read_text(encoding="utf-8"))["name"]
    Path(first).mkdir(parents=True)
    records = repo / ".git" / "afk-worktrees"
    records.mkdir()
    (records / f"{name}.json").write_text(json.dumps({"owner": {"pid": 999999, "ctime": "1"}}), encoding="utf-8")
    second = typed_path(refuse(repo, "s9", AFK_MOVE_SPAWN="0").stderr)
    assert second != first


def test_r5_10_the_creation_records_the_owner_the_guard_resolved(repo):
    spec = importlib.util.spec_from_file_location("afk_owner", PLUGIN_ROOT / "scripts" / "worktree_owner.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    pinned = f"{os.getpid()}:{module.creation_time(os.getpid())}"
    path = Path(typed_path(refuse(repo, "s10", AFK_WORKTREE_OWNER=pinned).stderr))
    assert wait_for(path)
    end = time.time() + 120
    while time.time() < end and not list((repo / ".git" / "afk-worktrees").glob("*.json")):
        time.sleep(1)  # the record is written after the worktree appears
    found = json.loads(next((repo / ".git" / "afk-worktrees").glob("*.json")).read_text(encoding="utf-8"))
    assert found["owner"]["pid"] == os.getpid()


FIXTURES = Path(__file__).resolve().parent / "fixtures"


def captured(name: str) -> str:
    return (FIXTURES / f"codex-composer-{name}.ansi").read_text(encoding="utf-8")


def test_p3_a_live_empty_composer_with_its_dim_placeholder_reads_as_empty():
    assert load_move().composer_text(captured("empty")) == ""


def test_p3_a_live_composer_with_typed_text_reads_as_that_text():
    assert load_move().composer_text(captured("typed")) == "hello I was about to ask"


def test_p3_the_helper_types_into_the_live_empty_composer(tmp_path):
    herdr, log = stub_herdr(tmp_path, captured("empty"))
    load_move().type_line(herdr, "w:p6", Path("C:/x"))
    assert prompts(log) and prompts(log)[0][3] == f"/cd {Path('C:/x')}"


def test_p3_the_helper_leaves_live_typed_text_alone(tmp_path):
    herdr, log = stub_herdr(tmp_path, captured("typed"))
    load_move().type_line(herdr, "w:p7", Path("C:/x"))
    assert not prompts(log)
