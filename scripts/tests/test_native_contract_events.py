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
             f'python "${{{root_var}}}/hooks/run-hook.py" plugin worktree-create.sh', "timeout": 5}]}]


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
