"""The UI lint gate: which files it lints, and from which workspace.

The gate is sourced into bash with its shared-context, cache and metrics
helpers stubbed, and `npm.lint` pointed at a stub linter that records each
call. No npm, ESLint or git is needed.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
GATE = PLUGIN_ROOT / "adapters" / "build-gate" / "npm" / "ui-lint-gate.sh"
_spec = importlib.util.spec_from_file_location("afk_run_hook", PLUGIN_ROOT / "hooks" / "run-hook.py")
_launcher = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_launcher)
# The hooks' own bash: never the Windows WSL stub that `bash` can resolve to.
BASH = _launcher.find_bash()

pytestmark = pytest.mark.skipif(BASH is None, reason="bash is not on PATH")

LINTER = """#!/usr/bin/env bash
[ "$1" = "--version" ] && exit 0
printf '%s|%s\\n' "$(basename "$PWD")" "$*" >> "$LINT_LOG"
exit 1
"""

HARNESS = """
gate_ctx_filter() { printf '%s\\n' $CHANGED; }
gate_cache_key() { echo key; }
gate_cache_hit() { return 1; }
gate_cache_store() { :; }
gate_metrics_begin() { :; }
gate_metrics_emit() { :; }
. "$GATE"
gate_ui_lint
"""


def run_gate(repo: Path, changed: list[str], workspace_root: str = ".") -> tuple[int, list[str]]:
    linter = repo.parent / "linter.sh"
    linter.write_text(LINTER, encoding="utf-8", newline="\n")
    log = repo.parent / "lint.log"
    env = {
        **os.environ,
        "GATE": GATE.as_posix(),
        "CHANGED": " ".join(changed),
        "LINT_LOG": log.as_posix(),
        "AFK_CFG_NPM_LINT": f"bash {linter.as_posix()}",
        "AFK_CFG_NPM_WORKSPACE_ROOT": workspace_root,
    }
    proc = subprocess.run([BASH, "-c", HARNESS], cwd=repo, env=env,
                          capture_output=True, text=True)
    calls = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
    return proc.returncode, calls


def write(repo: Path, path: str, text: str = "") -> None:
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    return root


def test_a_file_no_configuration_covers_is_not_linted(repo):
    write(repo, "package.json", '{"workspaces": ["ui"]}')
    write(repo, "ui/.eslintrc.js", "module.exports = {};")
    write(repo, "verification/api/check.mjs")

    code, calls = run_gate(repo, ["verification/api/check.mjs"], workspace_root=".")

    assert code == 0
    assert calls == []


def test_a_file_is_linted_from_its_nearest_configuration(repo):
    write(repo, "ui/.eslintrc.js", "module.exports = {};")
    write(repo, "ui/src/page.ts")

    code, calls = run_gate(repo, ["ui/src/page.ts"])

    assert code == 2
    assert calls == ["ui|src/page.ts"]


def test_a_root_configuration_covers_the_whole_repository(repo):
    write(repo, "eslint.config.js", "export default [];")
    write(repo, "tools/script.mjs")

    code, calls = run_gate(repo, ["tools/script.mjs"])

    assert code == 2
    assert calls == ["repo|tools/script.mjs"]


def test_a_package_json_eslint_config_counts_as_a_configuration(repo):
    write(repo, "package.json", '{"eslintConfig": {"root": true}}')
    write(repo, "tools/script.mjs")

    code, calls = run_gate(repo, ["tools/script.mjs"])

    assert code == 2
    assert calls == ["repo|tools/script.mjs"]


def test_a_package_json_without_eslint_config_is_not_a_configuration(repo):
    write(repo, "package.json", '{"name": "root", "workspaces": ["ui"]}')
    write(repo, "tools/script.mjs")

    code, calls = run_gate(repo, ["tools/script.mjs"])

    assert code == 0
    assert calls == []
