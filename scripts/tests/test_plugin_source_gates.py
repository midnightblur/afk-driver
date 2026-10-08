"""`hooks/plugin-source-gates.sh`: a trusted runner judges the candidate, the same way staged and in a range.

One base repository holds this checkout's tracked tree. Each fixture applies one change,
runs this checkout's runner (the judge) on the staged change, commits it, and runs it on the
base...HEAD range. Both reports must hold the same (gate, verdict, finding) tuples. The
candidate's own runner, gates and checkers are data: changing them never changes the verdict.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _bash():
    spec = importlib.util.spec_from_file_location("afk_run_hook_for_psg", ROOT / "hooks" / "run-hook.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.find_bash()


BASH = _bash()
pytestmark = pytest.mark.skipif(BASH is None, reason="no POSIX shell on this machine")
GATES = ("skill-registry", "native-contract", "genericity", "behavior-registry")


def _git(cwd, *args, check=True):
    return subprocess.run(["git", "-c", "user.email=t@example.invalid", "-c", "user.name=t",
                           "-c", "core.autocrlf=false", *args],
                          cwd=cwd, check=check, capture_output=True, text=True).stdout


def _env() -> dict[str, str]:
    env = {**os.environ, "AFK_PYTHON": sys.executable, "GATE_METRICS_DISABLE": "1"}
    for name in ("CLAUDE_PLUGIN_ROOT", "PLUGIN_ROOT", "GIT_INDEX_FILE", "GIT_DIR", "GIT_WORK_TREE",
                 "GATE_CACHE_DISABLE", *[f"{g.upper().replace('-', '_')}_GATE_DISABLE" for g in GATES]):
        env.pop(name, None)
    return env


def run_runner(repo: Path, *mode: str, judge: Path = ROOT,
               **env: str) -> tuple[int, list[tuple[str, str, str]], str]:
    report = repo.parent / f"{repo.name}-{judge.name}-{mode[0].strip('-')}.tsv"
    done = subprocess.run([str(BASH), (judge / "hooks" / "plugin-source-gates.sh").as_posix(), *mode,
                           "--report", report.as_posix()],
                          cwd=repo, env={**_env(), **env}, capture_output=True, text=True, timeout=600)
    rows = []
    if report.exists():
        for line in report.read_text(encoding="utf-8").splitlines():
            gate, verdict, finding = (line.split("\t", 2) + ["", ""])[:3]
            rows.append((gate, verdict, finding))
    return done.returncode, rows, done.stderr


def verdicts(rows) -> dict[str, str]:
    return {gate: verdict for gate, verdict, finding in rows if finding == ""}


@pytest.fixture(scope="module")
def base(tmp_path_factory) -> Path:
    repo = tmp_path_factory.mktemp("psg") / "base"
    repo.mkdir()
    listed = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True).stdout
    for rel in filter(None, listed.decode("utf-8").split("\0")):
        source = ROOT / rel
        if source.is_file():
            (repo / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, repo / rel)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    return repo


def _append(path: Path, text: str) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def deletion(repo):
    _git(repo, "rm", "-r", "-q", "skills/utils/todo")


def rename(repo):
    _git(repo, "mv", "skills/utils/todo", "skills/utils/todo-renamed")


def untracked_before_stage(repo):
    stray = repo / "skills" / "utils" / "zz-untracked" / "SKILL.md"
    stray.parent.mkdir(parents=True)
    stray.write_text("---\nname: wrong-name\n---\nNo pointer.\n", encoding="utf-8")
    _append(repo / "README.md", "\nA fixture line.\n")
    _git(repo, "add", "README.md")


def allowed_genericity(repo):
    _append(repo / "skills" / "utils" / "todo" / "SKILL.md", "\nSee HL-1 and also ZZQ-4242 here.\n")
    _git(repo, "add", "-A")


def provider_manifest(repo):
    path = repo / "hooks" / "hooks.codex.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["hooks"]["SessionStart"][0]["hooks"][0]["timeout"] = 16
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    _git(repo, "add", "-A")


def managed_behavior(repo):
    _append(repo / "BEHAVIORS.md", "\n## reply-ste100\n"
            "state: active | scope: all-repos | revision: 1 | doctrine: LANGUAGE.md §1–2\nDuplicate.\n")
    _git(repo, "add", "-A")


def registry_lockstep(repo):
    skill = repo / "skills" / "utils" / "zz-fixture" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: zz-fixture\ndescription: A fixture skill. Use in tests.\n---\n\n"
                     "> **Language:** read `LANGUAGE.md` (plugin root) first.\n", encoding="utf-8",
                     newline="\n")
    path = repo / ".claude-plugin" / "plugin.json"
    text = path.read_text(encoding="utf-8").replace('"./skills/utils/todo",',
                                                    '"./skills/utils/todo",\n    "./skills/utils/zz-fixture",')
    path.write_text(text, encoding="utf-8", newline="\n")
    _git(repo, "add", "-A")


def crash(repo):
    _append(repo / "README.md", "\nA fixture line.\n")
    _git(repo, "add", "-A")


def noop_gate(repo):
    (repo / "hooks" / "genericity-gate.sh").write_text("gate_genericity() { return 0; }\n", encoding="utf-8",
                                                       newline="\n")
    _append(repo / "skills" / "utils" / "todo" / "SKILL.md", "\nSee ZZQ-4242 here.\n")
    _git(repo, "add", "-A")


def forced_sentinel(repo):
    sentinel = repo / ".claude" / "hooks" / ".gate-disabled"
    sentinel.parent.mkdir(parents=True, exist_ok=True)
    sentinel.write_text("", encoding="utf-8")
    _append(repo / "skills" / "utils" / "todo" / "SKILL.md", "\nSee ZZQ-4242 here.\n")
    _git(repo, "add", "-A")
    _git(repo, "add", "-f", ".claude/hooks/.gate-disabled")


def _shadow(repo):
    for module in ("json", "fnmatch"):
        (repo / f"{module}.py").write_text("raise SystemExit(0)\n", encoding="utf-8", newline="\n")


def shadowed_native_contract(repo):
    _shadow(repo)
    provider_manifest(repo)


def shadowed_skill_registry(repo):
    _shadow(repo)
    registry_lockstep(repo)


FIXTURES = {f.__name__: f for f in (deletion, rename, untracked_before_stage, allowed_genericity,
                                    provider_manifest, managed_behavior, registry_lockstep, crash, noop_gate,
                                    forced_sentinel, shadowed_native_contract, shadowed_skill_registry)}


def _judge_for(base: Path, name: str) -> Path:
    """This checkout, except for the crash fixture: a copy whose behavior-registry gate explodes."""
    if name != "crash":
        return ROOT
    judge = base.parent / "crash-judge"
    if not judge.exists():
        shutil.copytree(base, judge, ignore=shutil.ignore_patterns(".git"))
        (judge / "hooks" / "behavior-registry-gate.sh").write_text(
            "gate_behavior_registry() { echo 'exploded' >&2; return 7; }\n", encoding="utf-8", newline="\n")
    return judge


def _clone(base: Path, name: str) -> Path:
    repo = base.parent / name
    _git(base.parent, "clone", "-q", "--no-hardlinks", base.as_posix(), repo.as_posix())
    return repo


def _both_modes(base: Path, name: str, change=None, judge: Path | None = None):
    repo = _clone(base, name)
    (change or FIXTURES[name])(repo)
    judge = judge or _judge_for(base, name)
    staged = run_runner(repo, "--staged", judge=judge)
    _git(repo, "commit", "-q", "-m", name)
    ranged = run_runner(repo, "--range", "origin/main", judge=judge)
    return staged, ranged


def drop_runner(repo):
    _git(repo, "rm", "-q", "hooks/plugin-source-gates.sh")


def drop_manifest(repo):
    _git(repo, "rm", "-q", ".claude-plugin/plugin.json")


def drop_gate(repo):
    _git(repo, "rm", "-q", "hooks/genericity-gate.sh")


CONTROL_DELETIONS = {f.__name__: f for f in (drop_runner, drop_manifest, drop_gate)}


@pytest.fixture(scope="module")
def results(base):
    _judge_for(base, "crash")
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {name: pool.submit(_both_modes, base, name) for name in FIXTURES}
        futures.update({name: pool.submit(_both_modes, base, name, change)
                        for name, change in CONTROL_DELETIONS.items()})
        return {name: future.result() for name, future in futures.items()}


@pytest.mark.parametrize("name", list(FIXTURES))
def test_staged_and_range_modes_return_the_same_tuples(results, name):
    (staged_rc, staged, staged_err), (range_rc, ranged, range_err) = results[name]
    assert sorted(staged) == sorted(ranged), (staged_err, range_err)
    assert staged_rc == range_rc, (staged_err, range_err)
    assert set(verdicts(staged)) == set(GATES), staged_err


def _blocked(results, name):
    rc, rows, err = results[name][0]
    return rc, {g for g, v in verdicts(rows).items() if v != "pass"}, rows, err


def test_an_empty_range_runs_no_gate(base):
    rc, rows, err = run_runner(base, "--range", "HEAD~0")
    assert rc == 0 and rows == [], err


def test_deletion_and_rename_block_the_registries(results):
    for name in ("deletion", "rename"):
        rc, blocked, _rows, err = _blocked(results, name)
        assert rc == 2 and "skill-registry" in blocked and "native-contract" in blocked, (name, err)


def test_an_untracked_file_never_reaches_a_verdict(results):
    rc, blocked, _rows, err = _blocked(results, "untracked_before_stage")
    assert rc == 0 and not blocked, err


def test_genericity_blocks_the_unlisted_token_only(results):
    rc, blocked, rows, err = _blocked(results, "allowed_genericity")
    findings = " ".join(f for g, _v, f in rows if g == "genericity")
    assert rc == 2 and blocked == {"genericity"}, err
    assert "ZZQ-4242" in findings and "HL-1" not in findings, findings


def test_provider_manifest_drift_blocks_native_contract(results):
    rc, blocked, _rows, err = _blocked(results, "provider_manifest")
    assert rc == 2 and "native-contract" in blocked, err


def test_managed_behavior_drift_blocks_the_behavior_registry(results):
    rc, blocked, _rows, err = _blocked(results, "managed_behavior")
    assert rc == 2 and "behavior-registry" in blocked, err


def test_registry_lockstep_blocks_both_registry_gates(results):
    rc, blocked, _rows, err = _blocked(results, "registry_lockstep")
    assert rc == 2 and {"skill-registry", "native-contract"} <= blocked, err


def test_a_gate_crash_blocks_in_both_modes(results):
    for rc, rows, err in results["crash"]:
        assert rc == 2, err
        assert verdicts(rows)["behavior-registry"] == "crashed", rows


def test_the_branch_cannot_replace_its_own_judge_with_a_no_op(results):
    rc, blocked, rows, err = _blocked(results, "noop_gate")
    assert rc == 2 and blocked == {"genericity"}, err
    assert "ZZQ-4242" in " ".join(f for g, _v, f in rows if g == "genericity"), rows


@pytest.mark.parametrize("name", list(CONTROL_DELETIONS))
def test_deleting_a_control_file_is_incomplete_input_in_both_modes(results, name):
    for rc, rows, err in results[name]:
        assert rc == 2 and "NOT verified" in err and "the candidate deletes" in err, err
        assert rows == [], rows


def test_a_gate_the_branch_adds_runs_under_the_branch_runner(base):
    repo = _clone(base, "new_gate")
    (repo / "hooks" / "zz-new-gate.sh").write_text("gate_zz_new() { echo 'zz-new ran' >&2; return 2; }\n",
                                                   encoding="utf-8", newline="\n")
    runner = repo / "hooks" / "plugin-source-gates.sh"
    runner.write_text(runner.read_text(encoding="utf-8").replace(
        'GATES="skill-registry native-contract genericity behavior-registry"',
        'GATES="skill-registry native-contract genericity behavior-registry zz-new"'), encoding="utf-8", newline="\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "new gate")
    rc, rows, err = run_runner(repo, "--range", "origin/main", judge=repo)
    assert rc == 2 and verdicts(rows).get("zz-new") == "blocked", err
    rc, rows, err = run_runner(repo, "--range", "origin/main")
    assert "zz-new" not in verdicts(rows), rows


def test_a_consuming_repository_never_runs_the_gates(tmp_path):
    repo = tmp_path / "consumer"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "SKILL.md").write_text("ZZQ-4242\n", encoding="utf-8")
    _git(repo, "add", "-A")
    report = tmp_path / "report.tsv"
    done = subprocess.run([str(BASH), (ROOT / "hooks" / "plugin-source-gates.sh").as_posix(), "--staged",
                           "--report", report.as_posix()], cwd=repo, env=_env(), capture_output=True,
                          text=True, timeout=120)
    assert done.returncode == 0, done.stderr
    assert not report.exists() or report.read_text(encoding="utf-8") == ""


def test_incomplete_input_blocks(base):
    rc, _rows, err = run_runner(base, "--range", "no-such-ref")
    assert rc == 2 and "NOT verified" in err, err


def test_a_committed_gate_disabled_sentinel_never_disables_the_judge(results):
    for rc, rows, err in results["forced_sentinel"]:
        assert rc == 2 and verdicts(rows).get("genericity") == "blocked", err


@pytest.mark.parametrize("name, gate", [("shadowed_native_contract", "native-contract"),
                                        ("shadowed_skill_registry", "skill-registry")])
def test_a_candidate_module_cannot_shadow_the_judges_python(results, name, gate):
    for rc, rows, err in results[name]:
        assert rc == 2 and verdicts(rows).get(gate) == "blocked", err


def test_an_interpreter_inside_the_repository_is_never_the_judge(base):
    repo = _clone(base, "inside_python")
    fake = repo / "bin" / "afk-python"
    fake.parent.mkdir()
    fake.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8", newline="\n")
    fake.chmod(0o755)
    allowed_genericity(repo)
    rc, rows, err = run_runner(repo, "--staged", AFK_PYTHON=fake.as_posix(), PYTHONPATH=repo.as_posix())
    assert rc == 2 and "no afk-python outside the repository" in err and rows == [], err
