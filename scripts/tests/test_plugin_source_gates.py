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
    dropped = {name.upper() for name in (
        "CLAUDE_PLUGIN_ROOT", "PLUGIN_ROOT", "GIT_INDEX_FILE", "GIT_DIR", "GIT_WORK_TREE",
        "NoDefaultCurrentDirectoryInExePath",
        "GATE_CACHE_DISABLE", *[f"{g.upper().replace('-', '_')}_GATE_DISABLE" for g in GATES])}
    # Windows hands os.environ keys back upper-cased, so match names case-insensitively.
    return {key: value for key, value in env.items() if key.upper() not in dropped}


def run_runner(repo: Path, *mode: str, judge: Path = ROOT, path_first: Path | None = None,
               cwd: Path | None = None, **env: str) -> tuple[int, list[tuple[str, str, str]], str]:
    report = repo.parent / f"{repo.name}-{judge.name}-{mode[0].strip('-')}.tsv"
    # path_first is prepended inside bash, as a project-aware shell does, ahead of the shell's own folders.
    prefix = [] if path_first is None else [
        "-c", 'PATH="$(cygpath -u "$1" 2>/dev/null || printf %s "$1"):$PATH"; shift; exec "$BASH" "$@"',
        "_", path_first.as_posix()]
    done = subprocess.run([str(BASH), *prefix, (judge / "hooks" / "plugin-source-gates.sh").as_posix(), *mode,
                           "--report", report.as_posix()],
                          cwd=cwd or repo, env={**_env(), **env}, capture_output=True, text=True, timeout=600)
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


def _alias(repo: Path, kind: str, tmp_path: Path) -> Path:
    """Another spelling of the repository's bin folder: letter case swapped, or a link from outside."""
    if kind == "mixed-case":
        return Path((repo / "bin").as_posix().swapcase())
    link = tmp_path / "linked-bin"
    if sys.platform == "win32":
        import _winapi
        _winapi.CreateJunction(str(repo / "bin"), str(link))
    else:
        link.symlink_to(repo / "bin", target_is_directory=True)
    return link


@pytest.mark.parametrize("via", ["PATH", "AFK_PYTHON"])
@pytest.mark.parametrize("kind", ["mixed-case", "symlink"])
def test_an_aliased_interpreter_inside_the_repository_is_never_the_judge(base, tmp_path, kind, via):
    if kind == "mixed-case" and sys.platform not in ("win32", "darwin"):
        pytest.skip("this filesystem keeps letter case apart")
    marker = tmp_path / "aliased-python-ran"
    repo = _clone(base, f"alias_{kind}_{via}".replace("-", "_"))
    fake = repo / "bin" / "afk-judge-probe"
    fake.parent.mkdir()
    fake.write_text(f"#!/usr/bin/env bash\necho ran >'{marker.as_posix()}'\nexit 1\n",
                    encoding="utf-8", newline="\n")
    fake.chmod(0o755)
    allowed_genericity(repo)
    alias = _alias(repo, kind, tmp_path)
    if via == "PATH":
        env = {"AFK_PYTHON": "afk-judge-probe", "PATH": f"{alias}{os.pathsep}{os.environ['PATH']}"}
    else:
        env = {"AFK_PYTHON": f"{alias.as_posix()}/afk-judge-probe"}
    rc, rows, err = run_runner(repo, "--staged", **env)
    assert not marker.exists(), err
    assert rc == 2 and "no afk-python outside the repository" in err and rows == [], err


def test_a_linked_interpreter_resolves_with_a_readlink_that_lacks_dash_f(base, tmp_path):
    calls = tmp_path / "readlink-calls"
    shadow = tmp_path / "shadow"
    shadow.mkdir()
    (shadow / "readlink").write_text(
        f"#!/usr/bin/env bash\necho \"$*\" >>'{calls.as_posix()}'\n"
        "for a; do [ \"$a\" = -f ] && { echo 'readlink: illegal option -- f' >&2; exit 1; }; done\n"
        "exec /usr/bin/readlink \"$@\"\n", encoding="utf-8", newline="\n")
    (shadow / "readlink").chmod(0o755)
    links = tmp_path / "links"
    links.mkdir()
    (links / "real-python").write_text(f"#!/usr/bin/env bash\nexec '{Path(sys.executable).as_posix()}' \"$@\"\n",
                                       encoding="utf-8", newline="\n")
    (links / "real-python").chmod(0o755)
    (links / "hop").symlink_to(links / "real-python")
    (links / "afk-python").symlink_to("hop")
    repo = _clone(base, "linked_python")
    _append(repo / "README.md", "\nA fixture line.\n")
    _git(repo, "add", "README.md")
    rc, rows, err = run_runner(repo, "--staged", path_first=shadow,
                               AFK_PYTHON=(links / "afk-python").as_posix())
    assert calls.exists() and "-f" not in calls.read_text(encoding="utf-8").split(), err
    assert rc == 0 and verdicts(rows) == {gate: "pass" for gate in GATES}, err


@pytest.mark.parametrize("case", ["relative-git-dir", "relative-common-dir", "outside-without-work-tree"])
def test_an_unknowable_repository_is_refused(base, tmp_path, case):
    repo = _clone(base, f"unknowable_{case.replace('-', '_')}")
    start, env = repo, {"GIT_COMMON_DIR" if case == "relative-common-dir" else "GIT_DIR": ".git"}
    if case == "outside-without-work-tree":
        start = tmp_path / "outside"
        start.mkdir()
        env = {"GIT_DIR": (repo / ".git").as_posix()}
    rc, rows, err = run_runner(repo, "--staged", cwd=start, **env)
    assert rc == 2 and "cannot tell which repository git will use" in err and rows == [], err


@pytest.mark.parametrize("where", ["checkout", "outside", "linked-worktree", "main-checkout-bin", "gitfile",
                                   "core-worktree"])
def test_candidate_programs_first_on_the_inherited_path_never_run(base, tmp_path, where):
    """outside: started elsewhere with GIT_DIR and GIT_WORK_TREE; linked-worktree: the variables git gives a hook;
    main-checkout-bin: the programs sit in the main checkout of that linked worktree; gitfile: GIT_DIR names the
    worktree's .git file; core-worktree: the repository config moves the work tree elsewhere (GIT_DIR as a hook gets)."""
    marker = tmp_path / "candidate-program-ran"
    repo = _clone(base, f"candidate_path_{where.replace('-', '_')}")
    work, start, env, programs = repo, repo, {}, repo / "bin"
    if where in ("linked-worktree", "main-checkout-bin", "gitfile"):
        work = start = repo.parent / f"{repo.name}_wt"
        _git(repo, "worktree", "add", "-q", "-b", "side", work.as_posix())
        programs = work / "bin" if where == "linked-worktree" else programs
    _append(work / "README.md", "\nA fixture line.\n")
    _git(work, "add", "README.md")
    if where == "outside":
        start = tmp_path / "outside"
        start.mkdir()
        env = {"GIT_DIR": (repo / ".git").as_posix(), "GIT_WORK_TREE": repo.as_posix()}
    elif where in ("linked-worktree", "main-checkout-bin"):
        git_dir = _git(work, "rev-parse", "--absolute-git-dir").strip()
        env = {"GIT_DIR": git_dir, "GIT_INDEX_FILE": f"{git_dir}/index"}
    elif where == "gitfile":
        env = {"GIT_DIR": (work / ".git").as_posix()}
    elif where == "core-worktree":
        programs = tmp_path / "elsewhere" / "bin"
        _git(repo, "config", "core.worktree", programs.parent.as_posix())
        env = {"GIT_DIR": (repo / ".git").as_posix()}
    programs.mkdir(parents=True)
    for name in ("grep", "git"):
        stub = programs / name
        stub.write_text(f"#!/usr/bin/env bash\necho {name} >>'{marker.as_posix()}'\nexit 1\n",
                        encoding="utf-8", newline="\n")
        stub.chmod(0o755)
    staged = run_runner(work, "--staged", path_first=programs, cwd=start, **env)
    _git(work, "commit", "-q", "-m", "fixture line")
    ranged = run_runner(work, "--range", "origin/main", path_first=programs, cwd=start, **env)
    for rc, rows, err in (staged, ranged):
        assert not marker.exists(), err
        assert rc == 0 and verdicts(rows) == {gate: "pass" for gate in GATES}, err


@pytest.mark.skipif(sys.platform != "win32", reason="Windows searches the current folder for a bare program")
def test_a_candidate_git_exe_never_runs_under_the_judge(base, tmp_path):
    marker = tmp_path / "candidate-git-ran"
    repo = _clone(base, "candidate_git")
    home = Path(sys.base_prefix)
    shutil.copy2(home / "Lib" / "venv" / "scripts" / "nt" / "venvlauncher.exe", repo / "git.exe")
    (repo / "pyvenv.cfg").write_text(f"home = {home}\n", encoding="utf-8")
    (repo / "ls-files").write_text(f"open(r'{marker}', 'w').write('ran')\nraise SystemExit(1)\n",
                                   encoding="utf-8")
    provider_manifest(repo)
    staged = run_runner(repo, "--staged")
    _git(repo, "commit", "-q", "-m", "candidate git")
    ranged = run_runner(repo, "--range", "origin/main")
    for rc, rows, err in (staged, ranged):
        assert not marker.exists(), err
        assert rc == 2 and verdicts(rows).get("native-contract") == "blocked", err
