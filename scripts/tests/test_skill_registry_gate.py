from __future__ import annotations

import os
import pathlib
import json
import shutil
import subprocess
import sys

import pytest

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


@pytest.mark.parametrize("name", ["BASH_PROJECT_GATE_DISABLE", "COMP_PROJECT_MODE"])
def test_a_toggle_with_a_bash_like_prefix_still_blocks(tmp_path: pathlib.Path, name: str) -> None:
    plugin = plugin_copy(tmp_path)
    (plugin / "hooks" / "zz-fixture.sh").write_text(f'[ "${{{name}:-0}}" = 1 ] && exit 0\n', encoding="utf-8")
    result = run_gate(plugin)
    assert result.returncode == 2
    assert name in result.stderr


# ---- check E: a CONTRACT.md names each verb whole ----------------------------
CHECK_E = ROOT / "hooks" / "lib" / "adapter_registry_check.py"


def check_e(tmp_path: pathlib.Path, operations: list[str], contract_verbs: list[str]) -> str:
    kind = tmp_path / "adapters" / "fam" / "one"
    kind.mkdir(parents=True)
    (kind / "api.py").write_text("", encoding="utf-8")
    (kind / "adapter.json").write_text(json.dumps(
        {"operations": operations, "runner": {"type": "cli", "entry": "api.py"}}), encoding="utf-8")
    (kind / "CONTRACT.md").write_text(
        "## Verbs\n\n" + "".join(f"- `{v}`\n" for v in contract_verbs), encoding="utf-8")
    (tmp_path / "CONFIG.md").write_text("| `fam` | `one` | x |\n", encoding="utf-8")
    done = subprocess.run([sys.executable, str(CHECK_E), str(tmp_path)],
                          capture_output=True, text=True, check=True)
    return done.stdout


@pytest.mark.parametrize("declared, listed", [
    (["tracker_attach"], ["tracker_attachments"]),
    (["tracker_attachments"], ["tracker_attach"]),
])
def test_check_e_matches_a_verb_name_whole(tmp_path: pathlib.Path, declared, listed) -> None:
    assert f"CONTRACT.md never names {declared[0]}" in check_e(tmp_path, declared, listed)


def test_check_e_passes_when_both_verbs_are_named(tmp_path: pathlib.Path) -> None:
    both = ["tracker_attach", "tracker_attachments"]
    assert check_e(tmp_path, both, both) == ""
