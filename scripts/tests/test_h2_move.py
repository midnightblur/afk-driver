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


@pytest.fixture(autouse=True)
def sandbox_home(tmp_path, monkeypatch):
    """The guard and the creator read ~/.afk: every test gets an empty home of its own."""
    home = tmp_path / "sandbox-home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    return home


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    path = tmp_path / "my repo"
    path.mkdir()
    git(path, "init", "-q", "-b", "main")
    git(path, "commit", "-q", "--allow-empty", "-m", "seed")
    return path


def refuse(cwd: Path, session: str, **extra: str) -> subprocess.CompletedProcess:
    call = {"session_id": session, "cwd": str(cwd), "hook_event_name": "PreToolUse", "tool_name": "Bash",
            "tool_input": {"command": "touch changed"}}
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


def stub_herdr(tmp_path: Path, read_text: str = "", working_polls: int = 0, kind: str = "codex",
               session: str | None = "sess", cwd: str = "C:/main", switch_after: int = 10**6) -> tuple[str, Path]:
    log = tmp_path / "herdr.log"
    script = tmp_path / "herdr_stub.py"
    script.write_text(
        "import json, sys\n"
        f"open(r'{log}', 'a').write(json.dumps(sys.argv[1:]) + chr(10))\n"
        "if sys.argv[1:3] == ['agent', 'get']:\n"
        f"    polls = sum(1 for l in open(r'{log}') if json.loads(l)[:2] == ['agent', 'get'])\n"
        f"    status = 'working' if polls <= {working_polls} else 'idle'\n"
        f"    who = {kind!r} if polls <= {switch_after} else 'claude'\n"
        f"    agent = {{'agent': who, 'agent_status': status, 'cwd': {cwd!r}, 'terminal_title': '\\u271d \\u2733'}}\n"
        f"    if {session is not None}: agent['agent_session'] = {{'value': {session!r}}}\n"
        "    body = {'result': {'agent': agent}}\n"
        "    sys.stdout.buffer.write(json.dumps(body, ensure_ascii=False).encode('utf-8') + chr(10).encode())\n"
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
    herdr, log = stub_herdr(tmp_path, "\u203a\nWorking directory changed to: x", session="s3", cwd=str(repo))
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
    module.configure("codex")
    module.WHO.update(provider="codex", session="sess", cwd="C:/main")
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


def test_a_helper_with_a_log_appends_both_streams_to_it(tmp_path):
    spec = importlib.util.spec_from_file_location("afk_h2_move", PLUGIN_ROOT / "hooks" / "lib" / "h2_move.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    log = tmp_path / "setup.log"
    log.write_text("before\n", encoding="utf-8")
    module.spawn([sys.executable, "-c", "import sys; print('out', flush=True); print('err', file=sys.stderr)"],
                 log=str(log))
    end = time.monotonic() + 30
    while time.monotonic() < end and "err" not in log.read_text(encoding="utf-8"):
        time.sleep(0.1)
    assert log.read_text(encoding="utf-8").split() == ["before", "out", "err"]


def load_move():
    spec = importlib.util.spec_from_file_location("afk_move", PLUGIN_ROOT / "scripts" / "afk-move.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.SETTLE = 0
    module.configure("codex")
    module.WHO.update(provider="codex", session="sess", cwd="C:/main")
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
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_p3_a_live_empty_composer_with_its_dim_placeholder_reads_as_empty():
    assert load_move().composer_text(captured("codex-composer-empty.ansi")) == ""


def test_p3_a_live_composer_with_typed_text_reads_as_that_text():
    assert load_move().composer_text(captured("codex-composer-typed.ansi")) == "hello I was about to ask"


def test_p3_the_helper_types_into_the_live_empty_composer(tmp_path):
    herdr, log = stub_herdr(tmp_path, captured("codex-composer-empty.ansi"))
    load_move().type_line(herdr, "w:p6", Path("C:/x"))
    assert prompts(log) and prompts(log)[0][3] == f"/cd {Path('C:/x')}"


def test_p3_the_helper_leaves_live_typed_text_alone(tmp_path):
    herdr, log = stub_herdr(tmp_path, captured("codex-composer-typed.ansi"))
    load_move().type_line(herdr, "w:p7", Path("C:/x"))
    assert not prompts(log)


class FakeClock:
    """Time that only `sleep` moves, so a ten-minute wait takes no real time."""

    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds

    def strftime(self, fmt):
        return "00:00:00"


def test_p7_the_helper_waits_out_a_long_turn_before_typing(tmp_path, monkeypatch):
    module = load_move()
    monkeypatch.setattr(module, "time", FakeClock())
    herdr, log = stub_herdr(tmp_path, "\u203a", working_polls=300)
    module.type_line(herdr, "w:p8", Path("C:/x"))
    assert prompts(log) and prompts(log)[0][3] == f"/cd {Path('C:/x')}", "a long turn must not make it give up"


def test_p7_the_wait_for_idle_budget_is_at_least_ten_minutes():
    assert load_move().WAIT_IDLE >= 600


def test_p7_every_step_and_the_exit_reason_reach_the_moves_log(tmp_path, monkeypatch):
    module = load_move()
    monkeypatch.setattr(module, "LOG", tmp_path / "move.log")
    herdr, _ = stub_herdr(tmp_path, "\u203a hello, I was about to ask")
    module.type_line(herdr, "w:p9", Path("C:/x"))
    text = (tmp_path / "move.log").read_text(encoding="utf-8")
    assert "wait: agent status 'idle'" in text and "stop: the human is typing" in text


def test_p7_a_crash_of_the_helper_is_logged_with_its_traceback(repo, monkeypatch):
    module = load_move()
    name = "session-crash"
    monkeypatch.setattr(module, "run", lambda args: 1 // 0)
    with pytest.raises(ZeroDivisionError):
        module.main(["--repo", str(repo), "--name", name])
    text = (repo / ".git" / "afk-worktrees" / f"{name}.log").read_text(encoding="utf-8")
    assert "ZeroDivisionError" in text and text.rstrip().endswith("exit")


def test_p7_a_repo_that_is_not_one_gets_no_log_folder_in_the_current_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert load_move().log_path(str(tmp_path / "missing"), "x") is None
    assert not (tmp_path / "afk-worktrees").exists()


def test_r11_4_the_log_names_the_composer_class_never_the_humans_text(tmp_path, monkeypatch):
    module = load_move()
    monkeypatch.setattr(module, "LOG", tmp_path / "move.log")
    herdr, _ = stub_herdr(tmp_path, "› hunter2-secret-words")
    module.type_line(herdr, "w:p10", Path("C:/x"))
    text = (tmp_path / "move.log").read_text(encoding="utf-8")
    assert "hunter2" not in text and "human text (20 chars)" in text


def test_r11_5_a_new_move_starts_its_log_empty(repo):
    module = load_move()
    first = module.log_path(str(repo), "session-reuse")
    first.write_text("old run\n", encoding="utf-8")
    assert module.log_path(str(repo), "session-reuse").read_text(encoding="utf-8") == ""


def test_p8_agent_output_with_bytes_the_locale_code_page_cannot_decode_still_parses(tmp_path):
    herdr, log = stub_herdr(tmp_path, "\u203a")
    module = load_move()
    answer = module.herdr_json(herdr, "agent", "get", "w:p11")
    assert answer["result"]["agent"]["terminal_title"] == "\u271d \u2733"
    module.type_line(herdr, "w:p11", Path("C:/x"))
    assert prompts(log), "the helper must get past the first agent get and type"


def test_p8_an_empty_or_missing_answer_is_no_answer_not_a_crash(monkeypatch):
    module = load_move()

    class Done:
        stdout = None

    monkeypatch.setattr(module.subprocess, "run", lambda *a, **k: Done())
    assert module.herdr_json("x", "agent", "get", "p") is None


def test_p10_a_pane_of_another_agent_kind_gets_nothing_typed(tmp_path, monkeypatch):
    module = load_move()
    monkeypatch.setattr(module, "LOG", tmp_path / "move.log")
    herdr, log = stub_herdr(tmp_path, "\u203a", kind="claude")
    module.type_line(herdr, "w:pA", Path("C:/x"))
    assert not prompts(log)
    text = (tmp_path / "move.log").read_text(encoding="utf-8")
    assert "belongs to another agent (claude/sess/C:/main): nothing typed" in text


def test_p10_a_pane_of_the_right_kind_but_another_session_gets_nothing_typed(tmp_path):
    module = load_move()
    herdr, log = stub_herdr(tmp_path, "\u203a", session="someone-else")
    module.type_line(herdr, "w:pB", Path("C:/x"))
    assert not prompts(log)


def test_p10_a_pane_in_another_directory_gets_nothing_typed(tmp_path):
    module = load_move()
    herdr, log = stub_herdr(tmp_path, "\u203a", cwd="C:/elsewhere")
    module.type_line(herdr, "w:pC", Path("C:/x"))
    assert not prompts(log)


@pytest.mark.skipif(os.name != "nt", reason="drive-letter case and backslash spellings are one path only on Windows")
def test_p10_the_matching_pane_is_typed_into_and_a_reported_cwd_compares_normalised(tmp_path):
    module = load_move()
    herdr, log = stub_herdr(tmp_path, "\u203a", cwd="c:\\MAIN\\")
    module.type_line(herdr, "w:pD", Path("C:/x"))
    assert prompts(log)


def test_r15_1_a_pane_with_no_reported_session_gets_nothing_typed_and_the_log_says_so(tmp_path, monkeypatch):
    module = load_move()
    monkeypatch.setattr(module, "LOG", tmp_path / "move.log")
    herdr, log = stub_herdr(tmp_path, "\u203a", session=None)
    module.type_line(herdr, "w:pE", Path("C:/x"))
    assert not prompts(log)
    text = (tmp_path / "move.log").read_text(encoding="utf-8")
    assert "nothing typed" in text
    assert "herdr reports no session for pane w:pE; install herdr's integration for codex to get the line typed" in text


def test_r15_2_two_sessions_sharing_an_inherited_pane_id_each_get_their_own_worktree(repo):
    first = typed_path(refuse(repo, "child-1", HERDR_ENV="1", HERDR_PANE_ID="w:parent").stderr)
    second = typed_path(refuse(repo, "child-2", HERDR_ENV="1", HERDR_PANE_ID="w:parent").stderr)
    assert first != second
    assert wait_for(Path(first)) and wait_for(Path(second))
    assert len(list((repo / ".git" / "afk-session").glob("*.move"))) == 2


def test_p10_the_check_is_redone_after_the_idle_wait(tmp_path, monkeypatch):
    module = load_move()
    monkeypatch.setattr(module, "time", FakeClock())
    herdr, log = stub_herdr(tmp_path, "\u203a", working_polls=5, switch_after=3)
    module.type_line(herdr, "w:pF", Path("C:/x"))
    assert not prompts(log)


# --- the hint takes its path from the creator's own placement call ----------------------

def _h2_module():
    spec = importlib.util.spec_from_file_location("afk_h2_move_for_placement", PLUGIN_ROOT / "hooks" / "lib" / "h2_move.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_bash():
    spec = importlib.util.spec_from_file_location("afk_run_hook_for_h2", PLUGIN_ROOT / "hooks" / "run-hook.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    found = module.find_bash()
    if found is None:
        pytest.skip("no POSIX shell on this machine")
    return found


@pytest.fixture
def listed_repo(repo, tmp_path, monkeypatch):
    """`repo` in the repository list of a temporary home, under a confirmed root."""
    home, root = tmp_path / "home", tmp_path / "root"
    (home / ".afk").mkdir(parents=True)
    root.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    (home / ".afk" / "config.yaml").write_text(f"developer:\n  worktreeRoot: '{root.as_posix()}'\n",
                                               encoding="utf-8")
    spec = importlib.util.spec_from_file_location("afk_repo_list_for_h2", PLUGIN_ROOT / "scripts" / "repo_list.py")
    repo_list = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = repo_list
    spec.loader.exec_module(repo_list)
    repo_list.add_repository(repo, root, short_name="my-repo")
    return repo, home, root


def _place(repo: Path) -> dict:
    return {"common": str(repo / ".git"), "root": str(repo)}


def test_the_hint_path_equals_the_creators_path_for_the_same_name(listed_repo, monkeypatch):
    repo, home, root = listed_repo
    monkeypatch.setenv("AFK_MOVE_SPAWN", "0")
    chosen = _h2_module().plan(_place(repo), {"session_id": "s-same", "cwd": str(repo)}, {})
    assert "error" not in chosen and Path(chosen["path"]).parent == root / "my-repo", chosen
    env = env_of(HOME=str(home), USERPROFILE=str(home), AFK_PYTHON=sys.executable)
    done = subprocess.run([str(_load_bash()), str(PLUGIN_ROOT / "scripts" / "create-worktree"), "--repo",
                           repo.as_posix(), "--name", chosen["name"], "--session", "s-same"],
                          capture_output=True, text=True, cwd=repo, env=env, timeout=600)
    last = done.stdout.strip().splitlines()[-1] if done.stdout.strip() else ""
    assert done.returncode == 0 and last.startswith("WORKTREE_PATH="), done.stdout + done.stderr
    assert os.path.normcase(Path(last.removeprefix("WORKTREE_PATH="))) == os.path.normcase(Path(chosen["path"]))


def test_a_refused_root_returns_the_refusal_and_starts_nothing(listed_repo, monkeypatch):
    repo, home, root = listed_repo
    (home / ".afk" / "config.yaml").write_text("developer:\n  worktreeRoot: relative/root\n", encoding="utf-8")
    spawned: list = []
    module = _h2_module()
    monkeypatch.setattr(module, "spawn", lambda *a, **k: spawned.append(a))
    chosen = module.plan(_place(repo), {"session_id": "s-ref", "cwd": str(repo)}, {})
    assert chosen["error"].startswith("worktree root: R-01 ") and chosen["error"].endswith(" - run /afk:setup")
    assert not spawned and not list((repo / ".git" / "afk-session").glob("*.move"))


def test_an_unreadable_machine_file_returns_the_placement_error_and_starts_nothing(listed_repo, monkeypatch):
    repo, home, root = listed_repo
    (home / ".afk" / "config.yaml").write_text("developer: text\n", encoding="utf-8")
    spawned: list = []
    module = _h2_module()
    monkeypatch.setattr(module, "spawn", lambda *a, **k: spawned.append(a))
    chosen = module.plan(_place(repo), {"session_id": "s-bad", "cwd": str(repo)}, {})
    assert chosen["error"].startswith("placement: ") and chosen["path"] == "", chosen
    assert not spawned and not list((repo / ".git" / "afk-session").glob("*.move"))


def test_the_owner_calls_work_without_placement_and_a_move_needs_it(repo, tmp_path, monkeypatch):
    bare = tmp_path / "plugin-without-placement"
    (bare / "scripts").mkdir(parents=True)
    (bare / "scripts" / "worktree_owner.py").write_bytes((PLUGIN_ROOT / "scripts" / "worktree_owner.py").read_bytes())
    module = _h2_module()
    monkeypatch.setattr(module, "PLUGIN_ROOT", bare)
    monkeypatch.setenv("AFK_WORKTREE_OWNER", "4242:1")
    assert module.owner_env() == {"AFK_WORKTREE_OWNER": "4242:1"}
    (repo / ".git" / "afk-worktrees").mkdir()
    (repo / ".git" / "afk-worktrees" / "gone.json").write_text(
        json.dumps({"owner": {"pid": 2147483000, "ctime": "1"}}), encoding="utf-8")
    assert module.owner_is_dead(repo / ".git", "gone") is True
    monkeypatch.setenv("AFK_MOVE_SPAWN", "0")
    chosen = module.plan(_place(repo), {"session_id": "s-load", "cwd": str(repo)}, {})
    assert chosen["error"].startswith("placement: "), chosen


def test_a_repeat_call_returns_the_recorded_move_without_loading_placement(listed_repo, monkeypatch):
    repo, home, root = listed_repo
    monkeypatch.setenv("AFK_MOVE_SPAWN", "0")
    module = _h2_module()
    first = module.plan(_place(repo), {"session_id": "s-again", "cwd": str(repo)}, {})
    assert "error" not in first, first
    (home / ".afk" / "config.yaml").write_text("developer: text\n", encoding="utf-8")
    monkeypatch.setattr(module, "target", lambda *a: pytest.fail("a repeat call loaded placement"))
    assert module.plan(_place(repo), {"session_id": "s-again", "cwd": str(repo)}, {}) == first


def _marker(repo: Path, session: str) -> Path:
    folder = repo / ".git" / "afk-session"
    folder.mkdir(exist_ok=True)
    return folder / f"{session}.move"


def test_a_marker_still_being_written_is_kept_and_starts_nothing(listed_repo, monkeypatch):
    repo, home, root = listed_repo
    marker = _marker(repo, "s-young")
    marker.write_text("{\"name\": ", encoding="utf-8")
    spawned: list = []
    module = _h2_module()
    monkeypatch.delenv("AFK_MOVE_SPAWN", raising=False)
    monkeypatch.setattr(module, "spawn", lambda argv, env: spawned.append(argv))
    chosen = module.plan(_place(repo), {"session_id": "s-young", "cwd": str(repo)}, {})
    assert chosen["error"].startswith("move record: another call is still writing it") and chosen["path"] == "", chosen
    assert marker.read_text(encoding="utf-8") == "{\"name\": " and not spawned


def test_a_marker_dropped_before_it_is_read_is_planned_again(listed_repo, monkeypatch):
    repo, home, root = listed_repo
    marker = _marker(repo, "s-gone")
    marker.write_text(json.dumps({"name": "session-gone", "path": "x", "pane": ""}), encoding="utf-8")
    spawned: list = []
    module = _h2_module()
    monkeypatch.delenv("AFK_MOVE_SPAWN", raising=False)
    monkeypatch.setattr(module, "spawn", lambda argv, env: spawned.append(argv))
    real = Path.read_text

    def vanishing(self, *args, **kwargs):
        if self == marker and not getattr(vanishing, "done", False):
            vanishing.done = True
            self.unlink()  # another call dropped it between the existence check and the read
            raise FileNotFoundError(str(self))
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", vanishing)
    chosen = module.plan(_place(repo), {"session_id": "s-gone", "cwd": str(repo)}, {})
    assert "error" not in chosen and chosen["name"] != "session-gone", chosen
    assert len(spawned) == 1 and spawned[0][spawned[0].index("--name") + 1] == chosen["name"], spawned


def test_a_corrupt_marker_is_replaced_and_its_new_move_is_started(listed_repo, monkeypatch):
    repo, home, root = listed_repo
    marker = _marker(repo, "s-torn")
    marker.write_text("{not json", encoding="utf-8")
    spawned: list = []
    module = _h2_module()
    old = time.time() - module.WRITING - 60
    os.utime(marker, (old, old))
    monkeypatch.delenv("AFK_MOVE_SPAWN", raising=False)
    monkeypatch.setattr(module, "spawn", lambda argv, env: spawned.append(argv))
    chosen = module.plan(_place(repo), {"session_id": "s-torn", "cwd": str(repo)}, {})
    assert "error" not in chosen and Path(chosen["path"]).parent == root / "my-repo", chosen
    assert json.loads(marker.read_text(encoding="utf-8")) == chosen
    assert len(spawned) == 1 and spawned[0][spawned[0].index("--name") + 1] == chosen["name"], spawned
    assert [p.name for p in marker.parent.iterdir()] == [marker.name]


def test_the_helper_writes_its_outcome_into_the_marker_whole(tmp_path, monkeypatch):
    folder = tmp_path / "afk-session"
    folder.mkdir()
    marker = folder / "s.move"
    marker.write_text(json.dumps({"name": "n", "path": "p", "error": "old"}), encoding="utf-8")
    module = load_move()
    replaced: list = []
    real = os.replace
    monkeypatch.setattr(module.os, "replace", lambda a, b: (replaced.append(Path(b)), real(a, b)))
    module.record(str(marker), created="p")
    assert json.loads(marker.read_text(encoding="utf-8")) == {"name": "n", "path": "p", "created": "p"}
    assert replaced == [marker] and [p.name for p in folder.iterdir()] == ["s.move"]


def test_a_swap_a_reader_keeps_blocking_leaves_the_old_marker_whole(tmp_path, monkeypatch):
    folder = tmp_path / "afk-session"
    folder.mkdir()
    marker = folder / "s.move"
    before = json.dumps({"name": "n", "path": "p"})
    marker.write_text(before, encoding="utf-8")
    module = load_move()
    tries: list = []

    def blocked(a, b):
        tries.append(b)
        raise PermissionError("the marker is open in another process")

    monkeypatch.setattr(module.os, "replace", blocked)
    monkeypatch.setattr(module.time, "sleep", lambda seconds: None)
    module.record(str(marker), created="p")
    assert marker.read_text(encoding="utf-8") == before and len(tries) == module.REPLACE_TRIES
    assert [p.name for p in folder.iterdir()] == ["s.move"]


def test_a_marker_that_cannot_be_read_returns_an_error_and_starts_nothing(listed_repo, monkeypatch):
    repo, home, root = listed_repo
    _marker(repo, "s-locked").mkdir()
    spawned: list = []
    module = _h2_module()
    monkeypatch.delenv("AFK_MOVE_SPAWN", raising=False)
    monkeypatch.setattr(module, "spawn", lambda argv, env: spawned.append(argv))
    chosen = module.plan(_place(repo), {"session_id": "s-locked", "cwd": str(repo)}, {})
    assert chosen["error"].startswith("move record: ") and chosen["path"] == "", chosen
    assert not spawned


def test_a_stale_marker_of_a_missing_worktree_is_started_again(listed_repo, monkeypatch):
    repo, home, root = listed_repo
    module = _h2_module()
    marker = _marker(repo, "s-stale")
    recorded = {"name": "session-old", "path": str(root / "my-repo" / "session-old"), "pane": "", "marker": str(marker)}
    marker.write_text(json.dumps(recorded), encoding="utf-8")
    old = time.time() - module.RETRY_AFTER - 60
    os.utime(marker, (old, old))
    spawned: list = []
    monkeypatch.delenv("AFK_MOVE_SPAWN", raising=False)
    monkeypatch.setattr(module, "spawn", lambda argv, env: spawned.append(argv))
    assert module.plan(_place(repo), {"session_id": "s-stale", "cwd": str(repo)}, {}) == recorded
    assert len(spawned) == 1 and spawned[0][spawned[0].index("--name") + 1] == "session-old", spawned
    assert marker.stat().st_mtime > old + 30


def test_a_move_another_call_recorded_first_is_the_one_returned(listed_repo, monkeypatch):
    repo, home, root = listed_repo
    monkeypatch.setenv("AFK_MOVE_SPAWN", "0")
    module = _h2_module()
    marker = _marker(repo, "s-race")
    rival = {"name": "session-rival", "path": str(root / "my-repo" / "session-rival"), "pane": "", "marker": str(marker)}
    real_fresh = module.fresh

    def racing_fresh(*args):
        chosen = real_fresh(*args)
        marker.write_text(json.dumps(rival), encoding="utf-8")  # the other call wins the create
        return chosen

    monkeypatch.setattr(module, "fresh", racing_fresh)
    assert module.plan(_place(repo), {"session_id": "s-race", "cwd": str(repo)}, {}) == rival
