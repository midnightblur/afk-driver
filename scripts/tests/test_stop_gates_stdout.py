import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _bash():
    spec = importlib.util.spec_from_file_location("afk_run_hook_for_stdout", ROOT / "hooks" / "run-hook.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.find_bash()


BASH = _bash()
pytestmark = pytest.mark.skipif(BASH is None, reason="no POSIX shell on this machine")

FAKE_GATE = """set -u
gate_{fn}() {{
  printf 'noise on stdout from {name}\\n'
  {body}
}}
"""


def _git(cwd, *args):
    return subprocess.run(["git", "-c", "user.email=t@example.invalid", "-c", "user.name=t", *args],
                          cwd=cwd, check=True, capture_output=True, text=True).stdout


def _fixture(tmp_path):
    repo = tmp_path / "plugin"
    repo.mkdir()
    shutil.copytree(ROOT / "hooks", repo / "hooks", ignore=shutil.ignore_patterns("tests", "__pycache__"))
    gates = {
        "wiring": "return 0",
        "skill-registry": "return 0",
        "native-contract": "printf 'fixture finding\\n' >&2; return 2",
        "genericity": "return 0",
        "behavior-registry": "return 0",
    }
    for name, body in gates.items():
        (repo / "hooks" / f"{name}-gate.sh").write_text(
            FAKE_GATE.format(fn=name.replace("-", "_"), name=name, body=body), encoding="utf-8", newline="\n")
    _git(repo, "init", "-q")
    (repo / "changed.md").write_text("x\n", encoding="utf-8")
    return repo


@pytest.mark.parametrize("provider", ["claude", "codex"])
def test_stop_stdout_is_exactly_one_json_document_when_a_gate_prints(tmp_path, provider):
    repo = _fixture(tmp_path)
    env = {**os.environ, "AFK_PROVIDER": provider, "GATE_CACHE_DISABLE": "1", "GATE_METRICS_DISABLE": "1"}
    for name in ("CLAUDE_PLUGIN_ROOT", "PLUGIN_ROOT", "CODEX_PLUGIN_ROOT"):
        env.pop(name, None)
    result = subprocess.run([str(BASH), str(repo / "hooks" / "stop-gates.sh")], cwd=repo, env=env,
                            input=json.dumps({"hook_event_name": "Stop", "session_id": "s-1"}),
                            capture_output=True, text=True, timeout=300)
    assert result.stdout.lstrip().startswith("{"), (result.stdout, result.stderr)
    document, end = json.JSONDecoder().raw_decode(result.stdout.strip())
    assert result.stdout.strip()[end:] == "", result.stdout
    assert document.get("decision") == "block", (result.stdout, result.stderr)
    assert "fixture finding" in document.get("reason", "")
