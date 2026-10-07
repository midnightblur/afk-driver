"""Rule E of the native-contract gate: a provider-specific event lives in its provider's manifest only."""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[2]


def _bash():
    spec = importlib.util.spec_from_file_location("afk_run_hook", PLUGIN_ROOT / "hooks" / "run-hook.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.find_bash()


BASH = _bash()
pytestmark = pytest.mark.skipif(BASH is None, reason="no POSIX shell on this machine")

GATE = (". hooks/lib/provider.sh; . hooks/lib/config.sh; . hooks/gate-context.sh; . hooks/gate-cache.sh; "
        ". hooks/gate-metrics.sh; . hooks/native-contract-gate.sh; "
        "afk_plugin_dir() { echo .; }; afk_plugin_scope() { echo; }; "
        "GATE_CACHE_DISABLE=1 gate_native_contract")


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    """A copy of the plugin tree as its own git repository."""
    names = subprocess.run(["git", "-C", str(PLUGIN_ROOT), "ls-files", "-z", "--cached", "--others",
                            "--exclude-standard"], capture_output=True, text=True, check=True).stdout
    copy = tmp_path / "plugin"
    for name in filter(None, names.split("\0")):
        source = PLUGIN_ROOT / name
        if source.is_file():
            (copy / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(source, copy / name)
    for command in (["init", "-q"], ["config", "user.email", "t@t"], ["config", "user.name", "t"],
                    ["add", "-A"], ["commit", "-q", "-m", "copy"]):
        subprocess.run(["git", "-C", str(copy), *command], capture_output=True, check=True)
    return copy


def gate(tree: Path):
    return subprocess.run([str(BASH), "-c", GATE], cwd=tree, capture_output=True, text=True, timeout=300)


def hook_entry(root_var: str) -> list:
    return [{"hooks": [{"type": "command", "command":
             f'afk-python "${{{root_var}}}/hooks/run-hook.py" --deadline 4 plugin worktree-create.sh', "timeout": 5}]}]


def test_the_declared_event_passes_in_its_own_manifest(tree):
    done = gate(tree)
    assert done.returncode == 0, done.stderr + done.stdout


def test_the_declared_event_is_refused_in_the_other_manifest(tree):
    path = tree / "hooks" / "hooks.codex.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["hooks"]["WorktreeCreate"] = hook_entry("PLUGIN_ROOT")
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    done = gate(tree)
    assert done.returncode != 0
    assert "hooks/hooks.codex.json" in done.stderr + done.stdout and "WorktreeCreate" in done.stderr + done.stdout


def test_an_undeclared_event_is_refused_even_in_the_claude_manifest(tree):
    path = tree / "hooks" / "hooks.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["hooks"]["WorktreeElsewhere"] = hook_entry("CLAUDE_PLUGIN_ROOT")
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    done = gate(tree)
    assert done.returncode != 0 and "WorktreeElsewhere" in done.stderr + done.stdout


# ---- check M: bounded hooks ----------------------------------------------------

def _stop_entry(tree: Path, manifest_name: str = "hooks.json") -> tuple[Path, dict, dict]:
    path = tree / "hooks" / manifest_name
    manifest = json.loads(path.read_text(encoding="utf-8"))
    return path, manifest, manifest["hooks"]["Stop"][0]["hooks"][0]


def _refused(done, needle: str) -> None:
    assert done.returncode == 2, done.stderr + done.stdout
    assert needle in done.stderr + done.stdout


@pytest.mark.parametrize("manifest_name", ["hooks.json", "hooks.codex.json"])
def test_an_entry_without_a_deadline_is_refused(tree, manifest_name):
    path, manifest, entry = _stop_entry(tree, manifest_name)
    entry["command"] = entry["command"].replace(" --deadline 285", "")
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    _refused(gate(tree), "has no --deadline")


def test_a_deadline_equal_to_the_timeout_is_refused(tree):
    path, manifest, entry = _stop_entry(tree)
    entry["command"] = entry["command"].replace("--deadline 285", "--deadline 300")
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    _refused(gate(tree), "is not below")


def test_an_entry_without_a_timeout_is_refused(tree):
    path, manifest, entry = _stop_entry(tree)
    del entry["timeout"]
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    _refused(gate(tree), "no explicit timeout")


def test_an_entry_outside_the_launcher_needs_an_allow_entry(tree):
    path, manifest, entry = _stop_entry(tree)
    entry["command"] = 'afk-python "${CLAUDE_PLUGIN_ROOT}/hooks/other-guard.py"'
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    _refused(gate(tree), "bypasses run-hook.py")


def test_a_raw_repository_scan_in_a_gate_is_refused(tree):
    scan = "git " + "grep -o -F -e token"
    (tree / "hooks" / "x-gate.sh").write_text(
        f"#!/usr/bin/env bash\ngate_x() {{\n  {scan}\n}}\n", encoding="utf-8", newline="\n")
    _refused(gate(tree), "hooks/x-gate.sh:3: repository-wide content scan")


def test_the_bounded_scanner_itself_may_scan(tree):
    done = gate(tree)
    assert done.returncode == 0, done.stderr + done.stdout


# ---- check J: one runtime, one launch mechanism -------------------------------------

PY = "py" + "thon"  # spelled apart, so check J does not flag this file's own plants

def _write(tree: Path, rel: str, text: str) -> None:
    (tree / rel).parent.mkdir(parents=True, exist_ok=True)
    (tree / rel).write_text(text, encoding="utf-8", newline="\n")


def _command_named(tree: Path, interpreter: str) -> None:
    path, manifest, entry = _stop_entry(tree)
    entry["command"] = entry["command"].replace("afk-python ", interpreter + " ", 1)
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def _mcp_named(tree: Path, interpreter: str) -> None:
    path = tree / ".mcp.codex.json"
    servers = json.loads(path.read_text(encoding="utf-8"))
    for server in servers["mcpServers"].values():
        server["command"] = interpreter
    path.write_text(json.dumps(servers, indent=2), encoding="utf-8")


def _twin_drift(tree: Path) -> None:
    path, manifest, entry = _stop_entry(tree, "hooks.codex.json")
    entry["timeout"] += 1
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


@pytest.mark.parametrize("plant, needle", [
    (lambda t: _command_named(t, "python"), "command must be afk-python"),
    (lambda t: _mcp_named(t, "python"), "command must be afk-python, got 'python'"),
    (_twin_drift, "differ beyond the root variable"),
    (lambda t: _write(t, "hooks/lib/x.py", f"#!/usr/bin/env {PY}3\n"), "hooks/lib/x.py:1: python source"),
    (lambda t: _write(t, "hooks/lib/x.py", f'argv = ["{PY}", "-c", "pass"]\n'), "hooks/lib/x.py:1: python source"),
    (lambda t: _write(t, "hooks/x.sh", "#!/bin/sh\npython tool.py\n"), "hooks/x.sh:2: shell command"),
    (lambda t: _write(t, "hooks/x.sh", '#!/bin/sh\n"$AFK_' + 'PY" tool.py\n'), "hooks/x.sh:2: shell command"),
    (lambda t: _write(t, ".github/workflows/x.yml", "steps:\n  - uses: actions/setup-python@v5\n"),
     ".github/workflows/x.yml:2: CI step"),
    (lambda t: _write(t, "skills/x/SKILL.md", "Run `python tool.py` first.\n"), "skills/x/SKILL.md:1: prose command"),
    (lambda t: _write(t, "skills/x/SKILL.md", "```sh\npy -3 tool.py\n```\n"), "skills/x/SKILL.md:2: prose command"),
], ids=["manifest", "mcp", "twin", "shebang", "argv", "shell", "afk-py", "ci", "prose", "fenced"])
def test_check_j_refuses_a_second_runtime_on_a_live_surface(tree, plant, needle):
    plant(tree)
    _refused(gate(tree), needle)


def test_check_j_passes_explanatory_text_and_an_allowed_interpreter_line(tree):
    _write(tree, "skills/x/SKILL.md", "afk-python is the only python this plugin runs.\nRun `python tool.py` once.\n")
    _write(tree, "hooks/x.sh", "#!/bin/sh\nprintf '%s' '{\"python\": \"3\", \"ok\": 1}'\n")
    with (tree / "hooks" / "native-contract-allow.txt").open("a", encoding="utf-8", newline="\n") as allow:
        allow.write("skills/x/SKILL.md\tinterpreter\tRun `python tool\\.py` once\tA test names the interpreter.\n")
    done = gate(tree)
    assert done.returncode == 0, done.stderr + done.stdout
