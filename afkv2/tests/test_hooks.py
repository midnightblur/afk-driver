import json
import re
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
PAYLOAD = json.dumps(
    {
        "session_id": "s-1",
        "hook_event_name": "SessionStart",
        "source": "startup",
        "cwd": "C:\\repo",
        "tool_input": {"command": "git status && del /q *"},
    }
).encode()


def run_hook(hook, provider, data_root):
    env = {"LOCALAPPDATA": str(data_root), "SystemRoot": "C:\\Windows", "PATH": "C:\\Windows\\System32"}
    return subprocess.run(["cmd.exe", "/d", "/c", str(hook), provider], input=PAYLOAD, capture_output=True, env=env)


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
    assert done.stdout.replace(b"\r\n", b"\n") == expected.read_bytes().replace(b"\r\n", b"\n")


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
    times = []
    for _ in range(7):
        start = time.perf_counter()
        done = run_hook(hook, "claude", tmp_path)
        times.append(time.perf_counter() - start)
        assert done.returncode == 0
    assert statistics.median(times) < 0.050, times


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


def test_rule_text_reaches_a_session_only_through_the_plugin():
    marker = plugin_check.MARKER
    for instruction_file in ("CLAUDE.md", "AGENTS.md"):
        path = REPO / instruction_file
        if path.is_file():
            assert marker not in path.read_text(encoding="utf-8")
    for path in [*(PLUGIN / "scripts").glob("*.py"), *HOOKS.glob("*.cmd")]:
        text = path.read_text(encoding="utf-8")
        assert "CLAUDE.md" not in text and "AGENTS.md" not in text, path
