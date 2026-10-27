from __future__ import annotations

import os
import pathlib
import re
import shutil
import subprocess

import pytest


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


def diagnose_doctrine_problems(text: str) -> list[str]:
    problems = []
    if "\n## Phase 2.5 — Trace the path\n" not in text:
        problems.append("doctrine heading missing")
    description = next((line for line in text.splitlines() if line.startswith("description:")), "")
    if re.search(r"→\s*fix\b|\bfix\s*→", description, re.IGNORECASE):
        problems.append("description promises a fix step")
    if re.search(r"regression[- ]test", description, re.IGNORECASE):
        problems.append("description promises a regression test")
    for removed in ("Phase 5 — Fix", "Phase 6 reports"):
        if removed in text:
            problems.append(f"names removed text {removed!r}")
    return problems


def diagnose_doc(description: str, body: str = "") -> str:
    return f'---\nname: diagnose\ndescription: "{description}"\n---\n\n## Phase 2.5 — Trace the path\n\n{body}\n'


def test_diagnose_keeps_its_doctrine_home_and_promises_no_fix() -> None:
    text = (ROOT / "skills" / "utils" / "diagnose" / "SKILL.md").read_text(encoding="utf-8")
    assert diagnose_doctrine_problems(text) == []


@pytest.mark.parametrize(
    ("description", "body", "problem"),
    [
        ("Loop: reproduce → fix → done.", "", "description promises a fix step"),
        ("Loop: reproduce → root cause → Fix.", "", "description promises a fix step"),
        ("Loop: reproduce → regression-test.", "", "description promises a regression test"),
        ("Loop: reproduce, then add a Regression Test.", "", "description promises a regression test"),
        ("Diagnosis without a fix.", "Phase 6 reports it.", "names removed text 'Phase 6 reports'"),
        ("Diagnosis without a fix.", "See Phase 5 — Fix.", "names removed text 'Phase 5 — Fix'"),
    ],
)
def test_the_diagnose_pin_catches_each_fixing_promise(description: str, body: str, problem: str) -> None:
    assert diagnose_doctrine_problems(diagnose_doc(description, body)) == [problem]


def test_the_diagnose_pin_passes_a_fix_proposal_and_catches_a_renamed_heading() -> None:
    clean = diagnose_doc("Diagnosis without a fix: root cause → DIAGNOSIS.md with a fix proposal.")
    assert diagnose_doctrine_problems(clean) == []
    assert diagnose_doctrine_problems(clean.replace("## Phase 2.5", "## Phase 2.6")) == ["doctrine heading missing"]
