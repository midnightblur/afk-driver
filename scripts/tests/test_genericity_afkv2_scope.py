"""The genericity gate leaves afkv2/ and docs/afk/afkv2/ alone and judges every other path as before."""
from __future__ import annotations

import importlib.util
import os
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

GATE = r'''
afk_plugin_dir() { printf '.\n'; }
afk_plugin_scope() { printf '\n'; }
gate_cache_key() { printf 'fixture\n'; }
gate_cache_hit() { return 1; }
gate_cache_store() { return 0; }
gate_metrics_begin() { return 0; }
gate_metrics_emit() { return 0; }
gate_ctx_mergebase() { return 0; }
gate_ctx_filter() { return 0; }
. "$GATE_FIXTURE"
gate_genericity
'''
TOKEN = "ZZQ" + "-123"


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True).stdout


def _gate(repo: Path, base: str):
    env = {"GATE_FIXTURE": (PLUGIN_ROOT / "hooks" / "genericity-gate.sh").as_posix(), "AFK_CTX_MERGEBASE": base}
    return subprocess.run([str(BASH), "-c", GATE], cwd=repo, capture_output=True, text=True, timeout=120,
                          env={**os.environ, **env})


@pytest.fixture
def repo(tmp_path: Path):
    root = tmp_path / "plugin"
    (root / "skills").mkdir(parents=True)
    (root / "hooks" / "lib").mkdir(parents=True)
    shutil.copy(PLUGIN_ROOT / "hooks" / "lib" / "sensitive-patterns.tsv", root / "hooks" / "lib")
    (root / "README.md").write_text("Fixture.\n", encoding="utf-8")
    for command in (["init", "-q"], ["config", "user.email", "t@t"], ["config", "user.name", "t"],
                    ["add", "-A"], ["commit", "-q", "-m", "base"]):
        _git(root, *command)
    return root, _git(root, "rev-parse", "HEAD").strip()


def _add(root: Path, rel: str) -> None:
    (root / rel).parent.mkdir(parents=True, exist_ok=True)
    (root / rel).write_text(f"See {TOKEN} here.\n", encoding="utf-8", newline="\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", rel)


@pytest.mark.parametrize("rel", ["afkv2/x.md", "docs/afk/afkv2/x.md"])
def test_an_afkv2_path_is_out_of_scope(repo, rel):
    root, base = repo
    _add(root, rel)
    done = _gate(root, base)
    assert done.returncode == 0, done.stderr + done.stdout


def test_the_same_line_under_a_v1_path_is_refused(repo):
    root, base = repo
    _add(root, "afkv2/x.md")
    _add(root, "docs/afk/other/x.md")
    done = _gate(root, base)
    assert done.returncode == 2, done.stderr + done.stdout
    assert f"docs/afk/other/x.md: ticket ID `{TOKEN}`" in done.stderr
    assert "afkv2/x.md" not in done.stderr
