from __future__ import annotations

import os
import pathlib
import shutil
import subprocess


ROOT = pathlib.Path(__file__).resolve().parents[2]
GATE = ROOT / "hooks" / "behavior-registry-gate.sh"


def bash_executable() -> str:
    if os.name == "nt":
        git_bash = pathlib.Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Git" / "bin" / "bash.exe"
        if git_bash.is_file():
            return str(git_bash)
    found = shutil.which("bash")
    if not found:
        raise RuntimeError("bash is required for behavior gate tests")
    return found


def run_gate(plugin_root: pathlib.Path, *, disabled: bool = False) -> subprocess.CompletedProcess[str]:
    script = r'''
afk_plugin_dir() { printf '%s\n' "$PLUGIN_FIXTURE"; }
afk_plugin_scope() { printf '\n'; }
gate_cache_key() { printf 'fixture\n'; }
gate_cache_hit() { return 1; }
gate_cache_store() { return 0; }
gate_metrics_begin() { return 0; }
gate_metrics_emit() { return 0; }
. "$GATE_FIXTURE"
gate_behavior_registry
'''
    env = os.environ.copy()
    env["BEHAVIOR_REGISTRY_GATE_DISABLE"] = "1" if disabled else "0"
    env["GATE_FIXTURE"] = GATE.as_posix()
    env["PLUGIN_FIXTURE"] = plugin_root.as_posix()
    return subprocess.run(
        [bash_executable(), "-c", script],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_behavior_gate_passes_blocks_and_disables(tmp_path: pathlib.Path) -> None:
    assert run_gate(ROOT).returncode == 0

    plugin_copy = tmp_path / "plugin"
    shutil.copytree(ROOT, plugin_copy, ignore=shutil.ignore_patterns(".git", ".claude"))
    with (plugin_copy / "BEHAVIORS.md").open("a", encoding="utf-8") as registry:
        registry.write(
            "\n## reply-ste100\n"
            "state: active | scope: all-repos | revision: 1 | doctrine: LANGUAGE.md §1–2\n"
            "Duplicate.\n"
        )

    blocked = run_gate(plugin_copy)
    assert blocked.returncode == 2
    assert "behavior registry gate blocked" in blocked.stderr
    assert run_gate(plugin_copy, disabled=True).returncode == 0


def test_plugin_source_runner_dispatches_behavior_registry() -> None:
    runner = (ROOT / "hooks" / "plugin-source-gates.sh").read_text(encoding="utf-8")
    assert 'GATES="skill-registry native-contract genericity behavior-registry"' in runner
