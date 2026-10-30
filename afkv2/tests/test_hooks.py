import json
import re
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[1]
REPO = PLUGIN.parent
HOOKS = PLUGIN / "hooks"
BUILT = HOOKS / "built"
sys.path.insert(0, str(PLUGIN / "scripts"))

import plugin_check  # noqa: E402

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="the hooks are Windows .cmd files")

SESSION = HOOKS / "session-start.cmd"
SUBAGENT = HOOKS / "subagent-start.cmd"
PLAIN = BUILT / plugin_check.PLAIN_VARIANT
CLAUDE_SUBAGENT = BUILT / plugin_check.CLAUDE_SUBAGENT_VARIANT
TIMING_ATTEMPTS = 5
LIMIT_SECONDS = 0.050
EMPTY_CMD = b"@echo off\r\n"
CANARY = "canary.txt"
PAYLOAD = json.dumps(
    {
        "session_id": "s-1",
        "hook_event_name": "SessionStart",
        "source": "startup",
        "tool_input": {"command": f"type nul > {CANARY}"},
    }
).encode()


def hook_env(data_root):
    return {"LOCALAPPDATA": str(data_root), "SystemRoot": "C:\\Windows", "PATH": "C:\\Windows\\System32"}


def run_hook(hook, provider, data_root, env=None):
    return subprocess.run(
        ["cmd.exe", "/d", "/c", str(hook), provider],
        input=PAYLOAD,
        capture_output=True,
        env=hook_env(data_root) if env is None else env,
        cwd=data_root,
    )


def timed_run(hook, data_root):
    start = time.perf_counter()
    done = run_hook(hook, "claude", data_root)
    elapsed = time.perf_counter() - start
    assert done.returncode == 0
    return elapsed


def normalized(data):
    return data.replace(b"\r\n", b"\n")


def folder_state(folder):
    if not folder.exists():
        return None
    return {path: path.stat().st_mtime_ns for path in [folder, *folder.iterdir()]}


CASES = [
    (SESSION, "claude", PLAIN, "session-start"),
    (SESSION, "codex", PLAIN, "session-start"),
    (SUBAGENT, "claude", CLAUDE_SUBAGENT, "subagent-start"),
    (SUBAGENT, "codex", PLAIN, "subagent-start"),
]


@pytest.mark.parametrize("hook, provider, expected, event", CASES)
def test_hook_prints_only_the_prebuilt_file(tmp_path, hook, provider, expected, event):
    done = run_hook(hook, provider, tmp_path)
    assert done.returncode == 0
    assert done.stderr == b""
    assert normalized(done.stdout) == normalized(expected.read_bytes())


@pytest.mark.parametrize("hook, provider, expected, event", CASES)
def test_hook_writes_the_fired_record_for_its_provider(tmp_path, hook, provider, expected, event):
    run_hook(hook, provider, tmp_path)
    run_hook(hook, provider, tmp_path)
    record = tmp_path / "afkv2" / f"fired-{provider}.txt"
    lines = record.read_text(encoding="ascii").splitlines()
    assert len(lines) == 1
    assert lines[0].split()[:2] == [provider, event]


def test_claude_subagent_output_is_additional_context_json(tmp_path):
    done = run_hook(SUBAGENT, "claude", tmp_path)
    answer = json.loads(done.stdout)
    assert answer["hookSpecificOutput"]["hookEventName"] == "SubagentStart"
    assert answer["hookSpecificOutput"]["additionalContext"] == PLAIN.read_text(encoding="utf-8")


def test_printed_text_is_wrapped_in_marker_lines_with_the_hash(tmp_path):
    lines = run_hook(SESSION, "claude", tmp_path).stdout.decode("utf-8").replace("\r\n", "\n").split("\n")
    assert lines[-1] == ""
    sha = plugin_check.marker_hash("\n".join(lines[1:-2]))
    assert lines[0] == f"{plugin_check.MARKER} begin {sha}"
    assert lines[-2] == f"{plugin_check.MARKER} end {sha}"


@pytest.mark.parametrize("hook", [SESSION, SUBAGENT])
@pytest.mark.parametrize("provider", ["", "other", "..\\..\\x"])
def test_unknown_provider_prints_nothing_and_writes_nothing(tmp_path, hook, provider):
    done = run_hook(hook, provider, tmp_path)
    assert done.returncode == 2
    assert done.stdout == b""
    assert not (tmp_path / "afkv2").exists()


@pytest.mark.parametrize("hook", [SESSION, SUBAGENT])
def test_hook_median_of_7_runs_is_under_50_ms(tmp_path, hook):
    floor_hook = tmp_path / "empty.cmd"
    floor_hook.write_bytes(EMPTY_CMD)
    run_hook(hook, "claude", tmp_path)
    run_hook(floor_hook, "claude", tmp_path)
    attempts = []
    for _ in range(TIMING_ATTEMPTS):
        hook_times, floor_times = [], []
        for _ in range(7):
            floor_times.append(timed_run(floor_hook, tmp_path))
            hook_times.append(timed_run(hook, tmp_path))
        attempts.append((statistics.median(hook_times), statistics.median(floor_times)))
        if attempts[-1][0] < LIMIT_SECONDS and attempts[-1][1] < LIMIT_SECONDS:
            return
    if all(floor >= LIMIT_SECONDS for _, floor in attempts):
        pytest.skip(f"no verdict: an empty .cmd takes over 50 ms on this machine now: {attempts}")
    pytest.fail(f"median over 50 ms with a usable floor, (hook, floor) per attempt: {attempts}")


@pytest.mark.parametrize("hook", [SESSION, SUBAGENT])
def test_hook_does_not_run_the_command_in_its_input(tmp_path, hook):
    assert run_hook(hook, "claude", tmp_path).returncode == 0
    assert not (tmp_path / CANARY).exists()


@pytest.mark.parametrize("hook", [SESSION, SUBAGENT])
def test_parallel_hook_runs_all_succeed_and_print_the_full_text(tmp_path, hook):
    env = hook_env(tmp_path)
    expected = normalized(CLAUDE_SUBAGENT.read_bytes() if hook == SUBAGENT else PLAIN.read_bytes())
    for _ in range(5):
        runs = [
            subprocess.Popen(
                ["cmd.exe", "/d", "/c", str(hook), "claude"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                cwd=tmp_path,
            )
            for _ in range(24)
        ]
        results = [(*run.communicate(), run.returncode) for run in runs]
        assert [code for _, _, code in results] == [0] * 24
        assert [normalized(out) for out, _, _ in results] == [expected] * 24
        assert [err for _, err, _ in results] == [b""] * 24


@pytest.mark.parametrize("hook", [SESSION, SUBAGENT])
def test_data_folder_path_with_brackets_gets_the_record(tmp_path, hook):
    data_root = tmp_path / "a (x) b"
    data_root.mkdir()
    done = run_hook(hook, "codex", data_root)
    assert done.returncode == 0
    assert done.stderr == b""
    assert (data_root / "afkv2" / "fired-codex.txt").is_file()


@pytest.mark.parametrize("hook", [SESSION, SUBAGENT])
@pytest.mark.parametrize("name, value", [("DATE", "Thu (10/30/2026)"), ("TIME", "12:00 (x)")])
def test_bracket_in_date_or_time_cannot_fail_the_hook(tmp_path, hook, name, value):
    done = run_hook(hook, "codex", tmp_path, env={**hook_env(tmp_path), name: value})
    assert done.returncode == 0
    assert done.stderr == b""
    assert value in (tmp_path / "afkv2" / "fired-codex.txt").read_text(encoding="ascii")


@pytest.mark.parametrize("hook", [SESSION, SUBAGENT])
def test_hook_without_a_data_folder_prints_the_text_and_writes_no_record(tmp_path, hook):
    work = tmp_path / "work"
    work.mkdir()
    root_folder = Path(tmp_path.anchor) / "afkv2"
    before = folder_state(root_folder)
    env = {key: value for key, value in hook_env(work).items() if key != "LOCALAPPDATA"}
    done = run_hook(hook, "codex", work, env=env)
    assert done.returncode == 0
    assert done.stderr == b""
    assert normalized(done.stdout) == normalized(PLAIN.read_bytes())
    assert list(work.iterdir()) == []
    assert folder_state(root_folder) == before


@pytest.mark.parametrize("hook", [SESSION, SUBAGENT])
def test_hook_with_no_prebuilt_file_fails_and_writes_no_record(tmp_path, hook):
    copy = tmp_path / "hooks"
    copy.mkdir()
    shutil.copy(hook, copy / hook.name)
    done = run_hook(copy / hook.name, "codex", tmp_path)
    assert done.returncode == 1
    assert done.stdout == b""
    assert not (tmp_path / "afkv2").exists()


@pytest.mark.parametrize("hook", [SESSION, SUBAGENT])
def test_hook_reads_no_input_and_parses_no_command(hook):
    text = hook.read_text(encoding="ascii").lower()
    for reader in ("set /p", "more", "findstr", "for /f", "find ", "python", "powershell", "bash"):
        assert reader not in text, reader


@pytest.mark.parametrize("hook", [SESSION, SUBAGENT])
def test_hook_sets_only_afkv2_prefixed_variables(hook):
    names = re.findall(r'set "([^=]+)=', hook.read_text(encoding="ascii"), flags=re.IGNORECASE)
    assert names
    assert all(name.startswith("AFKV2_") for name in names), names


def registrations():
    return json.loads((HOOKS / "hooks.json").read_text(encoding="utf-8"))["hooks"]


@pytest.mark.parametrize("source", ["startup", "resume", "clear", "compact"])
def test_session_start_runs_on_every_session_source(source):
    (group,) = registrations()["SessionStart"]
    assert re.fullmatch(group["matcher"], source)


def test_session_start_skips_a_fork_that_already_holds_the_text():
    (group,) = registrations()["SessionStart"]
    assert not re.fullmatch(group["matcher"], "fork")


@pytest.mark.parametrize("event, hook", [("SessionStart", SESSION), ("SubagentStart", SUBAGENT)])
def test_each_event_runs_its_cmd_hook_per_provider(event, hook):
    (group,) = registrations()[event]
    (handler,) = group["hooks"]
    assert handler["command"] == "cmd.exe"
    assert handler["args"] == ["/d", "/c", "${CLAUDE_PLUGIN_ROOT}\\hooks\\" + hook.name, "claude"]
    assert handler["commandWindows"] == f'"%PLUGIN_ROOT%\\hooks\\{hook.name}" codex'


def test_subagent_start_matches_every_agent_type():
    (group,) = registrations()["SubagentStart"]
    assert "matcher" not in group


def rule_lines():
    source = (PLUGIN / plugin_check.CORE_SOURCE).read_text(encoding="utf-8")
    return [line for line in source.splitlines() if len(line) >= 20]


def test_core_source_has_rule_lines_to_compare():
    assert rule_lines()


@pytest.mark.parametrize("instruction_file", ["CLAUDE.md", "AGENTS.md"])
def test_auto_loaded_instruction_file_holds_no_rule_text(instruction_file):
    text = (REPO / instruction_file).read_text(encoding="utf-8")
    assert plugin_check.MARKER not in text
    assert [line for line in rule_lines() if line in text] == []


def test_plugin_code_does_not_touch_instruction_files():
    for path in [*(PLUGIN / "scripts").glob("*.py"), *HOOKS.glob("*.cmd")]:
        text = path.read_text(encoding="utf-8")
        assert "CLAUDE.md" not in text and "AGENTS.md" not in text, path
