"""afk_hook_field without jq reads the member at a dotted path with bash builtins only, as jq does."""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
LIBRARY = PLUGIN_ROOT / "hooks" / "lib" / "provider.sh"
ENVELOPES = sorted((PLUGIN_ROOT / "hooks" / "tests" / "envelopes").glob("*/*.json"))
PATHS = ["hook_event_name", "tool_name", "tool_input.command", "tool_input.pattern", "tool_input.path",
         "session_id", "cwd", "source", "tool_response.stdout"]
_spec = importlib.util.spec_from_file_location("afk_run_hook", PLUGIN_ROOT / "hooks" / "run-hook.py")
_launcher = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_launcher)
BASH = _launcher.hook_bash()
JQ = shutil.which("jq")

pytestmark = pytest.mark.skipif(BASH is None, reason="no POSIX shell")


def fields(envelope: str, paths: list[str], tmp_path: Path) -> list[str]:
    # An empty PATH: no jq, and any process start would fail on stderr. The envelope comes
    # from a file, not the environment, which Linux caps at 128 KiB per string.
    source = tmp_path / "envelope.json"
    source.write_bytes(envelope.encode("utf-8"))
    env = _launcher.shell_env(BASH, {"PATH": ""})
    env["PATH"] = str(tmp_path / "empty")
    script = ('. "$1"; AFK_HOOK_INPUT=$(< "$2"); shift 2\n'
              'for p; do afk_hook_field "$p"; printf "\\36"; done')
    done = subprocess.run([str(BASH), "-c", script, "_", LIBRARY.as_posix(), source.as_posix(), *paths],
                          capture_output=True, env=env, timeout=60)
    assert (done.returncode, done.stderr) == (0, b"")
    return done.stdout.decode("utf-8").split("\x1e")[:-1]


def jq(envelope: str, path: str) -> str:
    done = subprocess.run([JQ, "-r", f".{path} // \"\""], input=envelope.encode("utf-8"), capture_output=True)
    out = done.stdout.decode("utf-8")
    if os.name == "nt":
        out = out.replace("\r\n", "\n")  # jq writes text mode on Windows
    out = out[:-1] if out.endswith("\n") else out
    return "" if done.returncode or out[:1] in ("{", "[") else out


@pytest.mark.parametrize("envelope,path,expected", [
    ('{"hook_event_name":"Stop"}', "hook_event_name", "Stop"),
    ('{"hook_event_name" : "PreToolUse"}', "hook_event_name", "PreToolUse"),
    (r'{"tool_input":{"command":"a \"q\" b\\c\nd\te\re"}}', "tool_input.command", 'a "q" b\\c\nd\te\re'),
    (r'{"tool_input":{"command":"C:\\temp C:\\new C:\\rx"}}', "tool_input.command", r"C:\temp C:\new C:\rx"),
    (r'{"tool_input":{"command":"\\\\server\\n\u00e9 a\/b"}}', "tool_input.command", "\\\\server\\n\u00e9 a/b"),
    (r'{"k":"Aé€😀\n"}', "k", "Aé€\U0001F600\n"),
    (r'{"a":"\u0001","b":"\u0002"}', "a", "\x01"),
    (r'{"a":"\u0001","b":"\u0002"}', "b", "\x02"),
    (r'{"a":"x\u0001\\\u0002\"y"}', "a", 'x\x01\\\x02"y'),
    ('{"x":1}', "hook_event_name", ""),
    ('{"a":{"b":12,"c":true,"d":false,"e":null,"f":{"g":"h"}}}', "a.b", "12"),
    ('{"a":{"b":12,"c":true,"d":false,"e":null,"f":{"g":"h"}}}', "a.c", "true"),
    ('{"a":{"b":12,"c":true,"d":false,"e":null,"f":{"g":"h"}}}', "a.d", ""),
    ('{"a":{"b":12,"c":true,"d":false,"e":null,"f":{"g":"h"}}}', "a.e", ""),
    ('{"a":["x",{"b":"in an array"}],"b":"top"}', "b", "top"),
    ('[{"a":"x"}]', "a", ""),
])
def test_the_no_jq_reading_decodes_each_escape_once_and_starts_no_process(tmp_path, envelope, path, expected):
    assert fields(envelope, [path], tmp_path) == [expected]
    if JQ is not None:
        assert jq(envelope, path) == expected


@pytest.mark.parametrize("envelope", [
    '{"tool_response":{"hook_event_name":"SessionStart","tool_input":{"command":"rm -rf /"}},'
    '"hook_event_name":"PostToolUse","tool_input":{"command":"ls"}}',
    '{"hook_event_name":"PostToolUse","tool_input":{"x":{"command":"rm -rf /"},"command":"ls"},'
    '"tool_response":{"hook_event_name":"SessionStart","command":"rm"}}',
], ids=["duplicate-before", "duplicate-after"])
def test_a_same_named_leaf_elsewhere_never_answers_for_the_requested_path(tmp_path, envelope):
    assert fields(envelope, ["hook_event_name", "tool_input.command"], tmp_path) == ["PostToolUse", "ls"]


@pytest.mark.skipif(JQ is None, reason="jq is not installed")
@pytest.mark.parametrize("envelope", ENVELOPES, ids=lambda p: f"{p.parent.name}/{p.stem}")
def test_every_checked_in_envelope_reads_as_jq_reads_it(tmp_path, envelope):
    text = envelope.read_text(encoding="utf-8")
    assert fields(text, PATHS, tmp_path) == [jq(text, path) for path in PATHS]


def quote_heavy(order: str) -> str:
    # A tool_response over 1.3 MB of escaped quotes, holding its own nested hook_event_name.
    inner = json.dumps([{f"k{i}": f'v"{i}" \\ x', "hook_event_name": "SessionStart"} for i in range(16500)])
    envelope = {"session_id": "s"}
    if order == "before":
        envelope["hook_event_name"] = "PostToolUse"
    envelope["tool_response"] = {"meta": {"hook_event_name": "SessionStart"}, "output": inner,
                                 "rows": [{"a": 'b"c', "n": i} for i in range(2000)]}
    if order == "after":
        envelope["hook_event_name"] = "PostToolUse"
    return json.dumps(envelope)


@pytest.mark.parametrize("order", ["before", "after"])
def test_a_key_beside_a_large_quote_heavy_value_reads_well_inside_the_hook_deadline(tmp_path, order):
    envelope = quote_heavy(order)
    assert len(envelope) >= 1_300_000
    started = time.monotonic()
    assert fields(envelope, ["hook_event_name"], tmp_path) == ["PostToolUse"]
    assert time.monotonic() - started < 7  # half the 14 s deadline; a quadratic scan takes minutes
