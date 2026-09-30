from __future__ import annotations

import os
import pathlib
import re
import shutil
import subprocess


ROOT = pathlib.Path(__file__).resolve().parents[2]
GATE = ROOT / "hooks" / "native-contract-gate.sh"


def bash_executable() -> str:
    if os.name == "nt":
        git_bash = pathlib.Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Git" / "bin" / "bash.exe"
        if git_bash.is_file():
            return str(git_bash)
    found = shutil.which("bash")
    if not found:
        raise RuntimeError("bash is required for gate tests")
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
gate_native_contract
'''
    env = os.environ.copy()
    env["GATE_FIXTURE"] = GATE.as_posix()
    env["PLUGIN_FIXTURE"] = plugin_root.as_posix()
    return subprocess.run(
        [bash_executable(), "-c", script],
        cwd=ROOT, env=env, text=True, capture_output=True, check=False,
    )


def make_copy(tmp_path: pathlib.Path) -> pathlib.Path:
    dst = tmp_path / "plugin"
    shutil.copytree(ROOT, dst, ignore=shutil.ignore_patterns(".git", ".claude", "__pycache__", ".pytest_cache"))
    return dst


def edit(path: pathlib.Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text, f"{old!r} not in {path}"
    path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="")


def test_committed_tree_agrees_with_the_tier_table() -> None:
    result = run_gate(ROOT)
    assert result.returncode == 0, result.stderr


def test_claude_agent_model_drift_names_file_and_home(tmp_path: pathlib.Path) -> None:
    plugin = make_copy(tmp_path)
    edit(plugin / "agents/afk-reader.md", "model: sonnet", "model: opus")
    result = run_gate(plugin)
    assert result.returncode == 2
    assert "agents/afk-reader.md" in result.stderr
    assert "expected 'sonnet'" in result.stderr and "got 'opus'" in result.stderr
    assert "PROVIDERS.md" in result.stderr


def test_pinning_a_codex_cell_names_every_follower(tmp_path: pathlib.Path) -> None:
    plugin = make_copy(tmp_path)
    edit(plugin / "PROVIDERS.md", "| Frontier | `opus` | `gpt-6-sol` |", "| Frontier | `opus` | `gpt-5.6-sol` |")
    result = run_gate(plugin)
    assert result.returncode == 2
    assert "providers/codex/agents/afk-afk-tracer.toml" in result.stderr
    assert "afk-afk-reader.toml" not in result.stderr


def test_codex_effort_drift_fails(tmp_path: pathlib.Path) -> None:
    plugin = make_copy(tmp_path)
    edit(plugin / "providers/codex/agents/afk-afk-tracer.toml",
         'model_reasoning_effort = "high"', 'model_reasoning_effort = "low"')
    result = run_gate(plugin)
    assert result.returncode == 2
    assert "afk-afk-tracer.toml" in result.stderr and "effort" in result.stderr


def test_agent_without_table_row_fails(tmp_path: pathlib.Path) -> None:
    plugin = make_copy(tmp_path)
    text = (plugin / "PROVIDERS.md").read_text(encoding="utf-8")
    text = re.sub(r"(?m)^\| `afk-runner-lite` \|.*\n", "", text)
    (plugin / "PROVIDERS.md").write_text(text, encoding="utf-8", newline="")
    result = run_gate(plugin)
    assert result.returncode == 2
    assert "afk-runner-lite" in result.stderr
