"""The guard's lavish rule: a direct `lavish-axi` run or a `LAVISH_AXI_HOST` setting is refused."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GUARD = ROOT / "hooks" / "protected-branch-guard.py"
sys.path.insert(0, str(ROOT / "hooks" / "lib"))

import lavish_direct  # noqa: E402

WRAPPER = 'afk-python "/plugin/scripts/lavish_show.py"'


def refused(command: str) -> str | None:
    return lavish_direct.refusal(command, "/plugin")


@pytest.mark.parametrize("command", [
    "lavish-axi page.html",
    "lavish-axi page.html --no-open",
    "lavish-axi poll 'my page.html' --agent-reply \"done\"",
    "lavish-axi share page.html",
    "lavish-axi setup hooks",
    "lavish-axi update",
    "lavish-axi stop",
    "/usr/local/bin/lavish-axi page.html",
    '"C:\\nvm4w\\nodejs\\lavish-axi.cmd" poll x.html',
    "& 'C:\\nvm4w\\nodejs\\lavish-axi.ps1' end x.html",
    "LAVISH-AXI poll x.html",
    "env lavish-axi x.html",
    "env -i PATH=/bin lavish-axi x.html",
    "command lavish-axi x.html",
    "exec lavish-axi x.html",
    "nohup lavish-axi poll x.html &",
    "cd docs && lavish-axi x.html",
    "echo ok; lavish-axi x.html",
    "true || lavish-axi x.html",
    "ls | lavish-axi x.html",
    "npx lavish-axi x.html",
    "npx -y lavish-axi@0.1.63 share x.html",
    "bash -c 'lavish-axi share x.html'",
    "sh -lc \"lavish-axi x.html\"",
    "pwsh -NoProfile -Command \"lavish-axi share x.html\"",
    "powershell -c 'lavish-axi x.html'",
    "(lavish-axi x.html)",
    "echo $(lavish-axi share x.html)",
    "echo \"$(lavish-axi share x.html)\"",
    "npx.cmd lavish-axi share x.html",
    "C:\\nvm4w\\nodejs\\npx.cmd -y lavish-axi share x.html",
    "& 'C:\\nvm4w\\nodejs\\npx.ps1' lavish-axi x.html",
    "npx.ps1 lavish-axi x.html",
    "echo ok # docs\nlavish-axi share x.html",
])
def test_a_direct_run_is_refused_and_points_at_the_wrapper(command):
    reason = refused(command)
    assert reason and "lavish_show.py" in reason and "/plugin/scripts/" in reason


@pytest.mark.parametrize("command", [
    "LAVISH_AXI_HOST=0.0.0.0 afk-python /plugin/scripts/lavish_show.py x.html",
    "LAVISH_AXI_HOST= lavish-axi x.html",
    "export LAVISH_AXI_HOST=0.0.0.0",
    "export FOO=1 LAVISH_AXI_HOST=0.0.0.0",
    "declare -x LAVISH_AXI_HOST=1",
    "env LAVISH_AXI_HOST=1 node x.js",
    "$env:LAVISH_AXI_HOST = '0.0.0.0'",
    "$env:LAVISH_AXI_HOST='0.0.0.0'",
    "$Env:lavish_axi_host = 1",
    "Set-Item -Path env:LAVISH_AXI_HOST -Value 1",
    "setx LAVISH_AXI_HOST 0.0.0.0",
    "bash -c 'export LAVISH_AXI_HOST=1'",
])
def test_setting_the_host_is_refused_and_points_at_the_wrapper(command):
    reason = refused(command)
    assert reason and "LAVISH_AXI_HOST" in reason
    assert "lavish_show.py" in reason and "/plugin/scripts/" in reason


@pytest.mark.parametrize("command", [
    f"{WRAPPER} x.html --no-open",
    f"{WRAPPER} poll x.html --agent-reply 'see lavish-axi share docs'",
    "grep -rn lavish-axi LAVISH.md",
    "rg 'lavish-axi share' .",
    "which lavish-axi",
    "command -v lavish-axi",
    "Get-Command lavish-axi",
    "echo lavish-axi share x.html",
    "echo \"lavish-axi share\"",
    "git log --grep lavish-axi",
    "lavish-axi --version",
    "npm i -g lavish-axi@0.1.63",
    "npx lavish-axi --version",
    "cat ~/.lavish-axi/state.json",
    "echo $LAVISH_AXI_HOST",
    "$env:LAVISH_AXI_HOST",
    "unset LAVISH_AXI_HOST",
    "env -u LAVISH_AXI_HOST node x.js",
    "Remove-Item env:LAVISH_AXI_HOST",
    "printenv LAVISH_AXI_HOST",
    "\"$tool\" share x.html",
    "eval \"$cmd\"",
    "",
    "echo ok # docs; lavish-axi share x.html",
    "# lavish-axi share x.html",
    "ls # $(lavish-axi share x.html)",
    "echo '$(lavish-axi share x.html)'",
    "declare -p LAVISH_AXI_HOST",
    "typeset -p LAVISH_AXI_HOST",
    "export -p",
    "export -n LAVISH_AXI_HOST",
    "declare +x LAVISH_AXI_HOST",
    "npx.cmd lavish-axi --version",
])
def test_searches_mentions_and_unreadable_forms_pass(command):
    assert refused(command) is None


def guard(cwd: Path, tool: str, command: str, **env) -> subprocess.CompletedProcess:
    environ = {k: v for k, v in os.environ.items() if k not in ("AFK_ALLOW_PROTECTED", "LAVISH_AXI_HOST")}
    environ.update({"AFK_PROVIDER": "claude", "AFK_MOVE_SPAWN": "0", **env})
    envelope = {"session_id": "s1", "cwd": str(cwd), "hook_event_name": "PreToolUse",
                "tool_name": tool, "tool_input": {"command": command}}
    return subprocess.run([sys.executable, str(GUARD)], input=json.dumps(envelope), text=True,
                          capture_output=True, cwd=cwd, env=environ, timeout=120)


def denied(done: subprocess.CompletedProcess) -> bool:
    return done.returncode == 0 and '"permissionDecision": "deny"' in done.stdout


def silently_allowed(done: subprocess.CompletedProcess) -> bool:
    """A clean allow: the guard ran, exited 0, and said nothing; a crash or a notice is not one."""
    return done.returncode == 0 and done.stdout == "" and done.stderr == ""


@pytest.mark.parametrize("tool", ["Bash", "PowerShell"])
def test_the_guard_process_refuses_outside_git_and_under_the_launch_flag(tmp_path, tool):
    assert denied(guard(tmp_path, tool, "lavish-axi share x.html"))
    done = guard(tmp_path, tool, "lavish-axi x.html", AFK_ALLOW_PROTECTED="1")
    assert denied(done) and "lavish_show.py" in done.stdout


@pytest.mark.parametrize("tool,command", [
    ("Bash", f"{WRAPPER} x.html --no-open"),
    ("Bash", "grep -n lavish-axi LAVISH.md"),
    ("Bash", "echo ok # docs; lavish-axi share x.html"),
    ("Bash", "declare -p LAVISH_AXI_HOST"),
    ("PowerShell", "Get-Command lavish-axi"),
    ("Grep", "lavish-axi share x.html"),
])
def test_the_guard_process_silently_allows_the_wrapper_reads_and_other_tools(tmp_path, tool, command):
    done = guard(tmp_path, tool, command)
    assert silently_allowed(done), (done.returncode, done.stdout, done.stderr)


def test_a_missing_guard_is_not_mistaken_for_an_allow(tmp_path, monkeypatch):
    monkeypatch.setattr(sys.modules[__name__], "GUARD", tmp_path / "missing-guard.py")
    assert not silently_allowed(guard(tmp_path, "Bash", "grep -n lavish-axi LAVISH.md"))
