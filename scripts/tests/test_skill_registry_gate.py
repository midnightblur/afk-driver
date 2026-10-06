from __future__ import annotations

import os
import pathlib
import shutil
import subprocess


ROOT = pathlib.Path(__file__).resolve().parents[2]
GATE = ROOT / "hooks" / "skill-registry-gate.sh"


def bash_executable() -> str:
    if os.name == "nt":
        git_bash = pathlib.Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Git" / "bin" / "bash.exe"
        if git_bash.is_file():
            return str(git_bash)
    found = shutil.which("bash")
    if not found:
        raise RuntimeError("bash is required for registry gate tests")
    return found


def run_gate(plugin_root: pathlib.Path) -> subprocess.CompletedProcess[str]:
    script = r'''
afk_plugin_dir() { printf '%s\n' "$PLUGIN_FIXTURE"; }
afk_plugin_scope() { printf '\n'; }
gate_cache_key() { printf 'fixture\n'; }
gate_cache_hit() { return 1; }
gate_cache_store() { return 0; }
gate_metrics_begin() { return 0; }
gate_metrics_emit() { return 0; }
. "$GATE_FIXTURE"
gate_skill_registry
'''
    env = os.environ.copy()
    env["SKILL_REGISTRY_GATE_DISABLE"] = "0"
    env["GATE_FIXTURE"] = GATE.as_posix()
    env["PLUGIN_FIXTURE"] = plugin_root.as_posix()
    return subprocess.run(
        [bash_executable(), "-c", script],
        cwd=plugin_root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def plugin_copy(tmp_path: pathlib.Path) -> pathlib.Path:
    copy = tmp_path / "plugin"
    shutil.copytree(ROOT, copy, ignore=shutil.ignore_patterns(".git", ".claude", "__pycache__"))
    return copy


def test_clean_tree_passes() -> None:
    result = run_gate(ROOT)
    assert result.returncode == 0, result.stderr


def test_bash_special_variables_are_never_toggles(tmp_path: pathlib.Path) -> None:
    plugin = plugin_copy(tmp_path)
    (plugin / "hooks" / "zz-fixture.sh").write_text(
        '[[ x =~ (x) ]] && echo "${BASH_REMATCH[1]} $BASHPID ${PIPESTATUS[0]} $LINENO $RANDOM $SECONDS"\n',
        encoding="utf-8",
    )
    result = run_gate(plugin)
    assert result.returncode == 0, result.stderr


def test_unregistered_env_toggle_blocks(tmp_path: pathlib.Path) -> None:
    plugin = plugin_copy(tmp_path)
    (plugin / "hooks" / "zz-fixture.sh").write_text(
        '[ "${AFK_FIXTURE_UNREGISTERED_TOGGLE:-0}" = 1 ] && exit 0\n',
        encoding="utf-8",
    )
    result = run_gate(plugin)
    assert result.returncode == 2
    assert "AFK_FIXTURE_UNREGISTERED_TOGGLE" in result.stderr
