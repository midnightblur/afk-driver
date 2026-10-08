"""afk_hook_field without jq reads a string field with bash builtins only."""
from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
LIBRARY = PLUGIN_ROOT / "hooks" / "lib" / "provider.sh"
_spec = importlib.util.spec_from_file_location("afk_run_hook", PLUGIN_ROOT / "hooks" / "run-hook.py")
_launcher = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_launcher)
BASH = _launcher.hook_bash()

pytestmark = pytest.mark.skipif(BASH is None, reason="no POSIX shell")


def field(envelope: str, path: str, tmp_path: Path) -> subprocess.CompletedProcess:
    # An empty PATH: no jq, and any process start would fail on stderr.
    env = _launcher.shell_env(BASH, {"AFK_HOOK_INPUT": envelope, "PATH": ""})
    env["PATH"] = str(tmp_path / "empty")
    return subprocess.run([str(BASH), "-c", '. "$1"; afk_hook_field "$2"', "_", LIBRARY.as_posix(), path],
                          capture_output=True, text=True, env=env, timeout=60)


@pytest.mark.parametrize("envelope,path,expected", [
    ('{"hook_event_name":"Stop"}', "hook_event_name", "Stop"),
    ('{"hook_event_name" : "PreToolUse"}', "hook_event_name", "PreToolUse"),
    (r'{"tool_input":{"command":"a \"q\" b\\c\nd\te"}}', "tool_input.command", r'a "q" b\c d e'),
    ('{"x":1}', "hook_event_name", ""),
])
def test_the_no_jq_reading_starts_no_process(tmp_path, envelope, path, expected):
    done = field(envelope, path, tmp_path)
    assert (done.returncode, done.stdout, done.stderr) == (0, expected, "")
