"""The installed-plugin lesson route: plugin-clone.sh, and the ledger's `filed`
event through lesson-append.sh (emitter) and lesson-digest.sh (parser)."""
from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

WORKFLOW = Path(__file__).resolve().parents[2]
CLONE = WORKFLOW / "skills" / "afk" / "lessons" / "scripts" / "plugin-clone.sh"
APPEND = WORKFLOW / "hooks" / "lesson-append.sh"
DIGEST = WORKFLOW / "hooks" / "lesson-digest.sh"


def _bash():
    """The shell the hook launcher uses — Git Bash on Windows, never the WSL stub."""
    spec = importlib.util.spec_from_file_location("afk_run_hook_for_lessons", WORKFLOW / "hooks" / "run-hook.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.find_bash()


BASH = _bash()
pytestmark = pytest.mark.skipif(BASH is None, reason="no POSIX shell on this machine")


def git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


def repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    git(path, "init", "-q")
    git(path, "config", "user.email", "t@example.invalid")
    git(path, "config", "user.name", "t")
    return path


def plugin(path: Path) -> Path:
    (path / ".claude-plugin").mkdir(parents=True, exist_ok=True)
    (path / ".claude-plugin" / "plugin.json").write_text('{"name":"afk"}\n')
    return path


def commit(path: Path) -> None:
    git(path, "add", "-A")
    git(path, "commit", "-qm", "c")


def clone_check(root: Path, cwd: Path, **env_overrides: str) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k != "AFK_PLUGIN_ROOT"}
    env.update(env_overrides)
    return subprocess.run([str(BASH), str(CLONE), str(root)], cwd=cwd, env=env,
                          capture_output=True, text=True)


def test_a_clone_inside_the_current_repository(tmp_path: Path):
    product = repo(tmp_path / "product")
    inner = plugin(repo(product / "vendor" / "afk"))
    commit(inner)
    result = clone_check(inner, product)
    assert result.returncode == 0 and result.stdout.startswith("PLUGIN: clone")


def test_a_plugin_tree_committed_inside_a_larger_repository(tmp_path: Path):
    product = repo(tmp_path / "product")
    inner = plugin(product / "plugin")
    commit(product)
    assert clone_check(inner, product).returncode == 0


def test_a_clone_outside_the_current_repository(tmp_path: Path):
    product = repo(tmp_path / "product")
    outside = plugin(repo(tmp_path / "afk-clone"))
    commit(outside)
    result = clone_check(outside, product)
    assert result.returncode == 0 and result.stdout.startswith("PLUGIN: clone")


def test_an_installed_copy_outside_any_repository(tmp_path: Path):
    cache = plugin(tmp_path / "cache" / "afk" / "1.0.0")
    result = clone_check(cache, tmp_path)
    assert result.returncode == 1 and result.stdout.startswith("PLUGIN: installed")


def test_an_installed_copy_nested_in_an_unrelated_repository(tmp_path: Path):
    home = repo(tmp_path / "home")
    (home / "dotfile").write_text("x\n")
    commit(home)
    cache = plugin(home / ".claude" / "plugins" / "cache" / "afk" / "1.0.0")
    assert clone_check(cache, home).returncode == 1
    (home / ".gitignore").write_text(".claude/\n")
    assert clone_check(cache, home).returncode == 1


@pytest.mark.parametrize("variable, base, managed", [
    ("HOME", "home", ".claude/plugins/marketplaces/afk-toolkit"),
    ("HOME", "home", ".claude/plugins/cache/afk-toolkit/afk/1.0.0"),
    ("HOME", "home", ".codex/plugins/cache/afk-toolkit/afk/1.0.0"),
    ("CLAUDE_CONFIG_DIR", "config", "plugins/marketplaces/afk-toolkit"),
    ("CODEX_HOME", "config", "plugins/cache/afk-toolkit/afk/1.0.0"),
])
def test_a_clone_the_harness_manages_is_installed(tmp_path: Path, variable: str, base: str,
                                                  managed: str):
    """The harness rewrites its own plugin directory, so an edit there is lost."""
    root = tmp_path / base
    market = plugin(repo(root / managed))
    commit(market)
    env = {"HOME": str(tmp_path / "home"), variable: str(root)}
    result = clone_check(market, tmp_path, **env)
    assert result.returncode == 1 and result.stdout.startswith("PLUGIN: installed"), result


def test_the_managed_path_comparison_folds_case(tmp_path: Path):
    """Windows hands one directory back under either spelling."""
    root = tmp_path / "home"
    market = plugin(repo(root / ".claude/plugins/marketplaces/afk-toolkit"))
    commit(market)
    shouted = Path(str(market).upper())
    if not shouted.is_dir():
        pytest.skip("this filesystem keeps the other spelling a different, absent directory")
    result = clone_check(shouted, tmp_path, HOME=str(root))
    assert result.returncode == 1 and result.stdout.startswith("PLUGIN: installed"), result


def test_case_folding_follows_the_filesystem(tmp_path: Path):
    """On a case-sensitive filesystem two spellings are two directories."""
    root = tmp_path / "home"
    market = plugin(repo(root / ".claude/plugins/marketplaces/afk-toolkit"))
    commit(market)
    shouted = Path(str(market).upper())
    if not shouted.is_dir():
        pytest.skip("the other spelling must name the same directory for the override to be observable")
    folded = clone_check(shouted, tmp_path, HOME=str(root), AFK_PATH_CASE_FOLD="1")
    assert folded.returncode == 1, folded
    exact = clone_check(shouted, tmp_path, HOME=str(root), AFK_PATH_CASE_FOLD="0")
    assert exact.returncode == 0 and exact.stdout.startswith("PLUGIN: clone"), exact


def test_no_home_directory_fails_closed(tmp_path: Path):
    """Undecidable is not `not managed`: an edit the harness erases costs more
    than an issue filed against a clone."""
    mine = plugin(repo(tmp_path / "work" / "afk-driver"))
    commit(mine)
    # Sourced, not spawned: a fresh shell rebuilds HOME from the account, and a
    # Windows process environment cannot carry an empty variable either.
    script = 'unset HOME USERPROFILE CLAUDE_CONFIG_DIR CODEX_HOME; . "$1" "$2"'
    result = subprocess.run([str(BASH), "-c", script, "sh", str(CLONE), str(mine)],
                            cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 1 and result.stdout.startswith("PLUGIN: installed"), result


def test_no_provider_adapter_fails_closed(tmp_path: Path):
    """No adapter is as unanswerable as an adapter that cannot answer."""
    tree = plugin(repo(tmp_path / "afk"))
    for rel in ("hooks/lib/provider.sh", "skills/afk/lessons/scripts/plugin-clone.sh"):
        (tree / rel).parent.mkdir(parents=True, exist_ok=True)
        (tree / rel).write_text((WORKFLOW / rel).read_text(encoding="utf-8"), encoding="utf-8")
    (tree / "hooks" / "lib" / "providers").mkdir()
    commit(tree)
    result = subprocess.run(
        [str(BASH), str(tree / "skills/afk/lessons/scripts/plugin-clone.sh"), str(tree)],
        cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 1 and result.stdout.startswith("PLUGIN: installed"), result


def test_a_maintainer_clone_elsewhere_stays_a_clone(tmp_path: Path):
    fake_home = tmp_path / "home"
    (fake_home / ".claude" / "plugins").mkdir(parents=True)
    mine = plugin(repo(tmp_path / "work" / "afk-driver"))
    commit(mine)
    result = clone_check(mine, tmp_path, HOME=str(fake_home))
    assert result.returncode == 0 and result.stdout.startswith("PLUGIN: clone"), result


def test_a_directory_without_a_manifest_is_a_usage_error(tmp_path: Path):
    assert clone_check(tmp_path, tmp_path).returncode == 2


def test_this_checkout_is_a_clone():
    assert clone_check(WORKFLOW, WORKFLOW).returncode == 0


@pytest.fixture
def ledger(tmp_path: Path, monkeypatch) -> Path:
    path = tmp_path / "LEDGER.jsonl"
    monkeypatch.setenv("LESSON_LEDGER_FILE", str(path))
    monkeypatch.delenv("LESSON_LEDGER_DISABLE", raising=False)
    return path


def sh(script: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([str(BASH), str(script), *args], capture_output=True, text=True)


def test_filed_records_the_issue_and_leaves_the_open_list(ledger: Path):
    lid = sh(APPEND, "opened", "--class", "missing-instruction", "--target", "skills/afk/x/SKILL.md",
             "--summary", "s", "--draft", "d", "--writer", "lessons").stdout.strip()
    url = "https://github.com/midnightblur/afk-driver/issues/9"
    assert sh(APPEND, "filed", "--id", lid, "--issue", url, "--writer", "lessons").stdout.strip() == lid
    last = json.loads(ledger.read_text().splitlines()[-1])
    assert last["event"] == "filed" and last["issue"] == url
    assert sh(DIGEST, "--count").stdout.strip() == "0"
    everything = sh(DIGEST, "--all").stdout
    assert "filed=1" in everything and f"| issue: {url}" in everything


def test_filed_without_an_issue_writes_nothing(ledger: Path):
    sh(APPEND, "opened", "--class", "missing-instruction", "--target", "t", "--summary", "s", "--draft", "d")
    before = ledger.read_text()
    result = sh(APPEND, "filed", "--id", "L-0001")
    assert result.returncode == 0 and "filed requires --issue" in result.stderr
    assert ledger.read_text() == before


LOCK = "lesson-append.lock"


def opened(summary: str, env: dict[str, str] | None = None) -> subprocess.Popen:
    return subprocess.Popen([str(BASH), str(APPEND), "opened", "--class", "missing-instruction",
                             "--target", "t", "--summary", summary], env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def finish(procs: list[subprocess.Popen]) -> list[str]:
    outs = [proc.communicate(timeout=120) for proc in procs]
    assert all(proc.returncode == 0 for proc in procs), outs
    return [out.strip() for out, _ in outs]


def ledger_ids(ledger: Path) -> list[str]:
    return sorted(json.loads(line)["id"] for line in ledger.read_text().splitlines())


def test_parallel_appends_get_distinct_ids(ledger: Path):
    ids = finish([opened(f"s{n}") for n in range(8)])
    assert sorted(ids) == [f"L-{n:04d}" for n in range(1, 9)], ids
    assert ledger_ids(ledger) == sorted(ids)
    stamps = [json.loads(line)["ts"] for line in ledger.read_text().splitlines()]
    assert all(re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", ts) for ts in stamps), stamps
    assert not list(ledger.parent.glob(LOCK + "*"))


@pytest.mark.parametrize("owner", [True, False])
def test_a_lock_left_by_a_closed_pane_is_taken_over_once_stale(ledger: Path, owner: bool):
    """A pane closed with no trap leaves its lock; once older than 10 s the next mint takes it."""
    assert finish([opened("first")]) == ["L-0001"]
    lock = ledger.parent / LOCK
    lock.mkdir()
    if owner:
        (lock / "owner").write_text("4242.1.2\n")
    stale = time.time() - 11
    os.utime(lock, (stale, stale))
    assert finish([opened("second")]) == ["L-0002"]
    assert ledger_ids(ledger) == ["L-0001", "L-0002"]
    assert not list(ledger.parent.glob(LOCK + "*"))


def test_a_lock_of_unreadable_age_is_never_taken_and_the_wait_ends_at_30_s(ledger: Path):
    """No stat reads the age, so even a 2 h old lock stays; the mint gives up with exit 0."""
    lock = ledger.parent / LOCK
    lock.mkdir(parents=True)
    (lock / "owner").write_text("4242.1.2\n")
    stale = time.time() - 7200
    os.utime(lock, (stale, stale))
    began = time.monotonic()
    # An exported function shadows every stat on PATH, GNU and BSD alike.
    proc = subprocess.Popen([str(BASH), "-c", 'stat() { return 1; }; export -f stat; exec "$BASH" "$@"', "sh",
                             str(APPEND), "opened", "--class", "missing-instruction", "--target", "t",
                             "--summary", "blocked"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    out, err = proc.communicate(timeout=120)
    assert proc.returncode == 0 and out == "" and "gave up after 30 s" in err, (out, err)
    assert 28 <= time.monotonic() - began < 60
    assert lock.is_dir() and not ledger.exists()


def shadowed(name: str, body: str, env: dict[str, str]) -> subprocess.Popen:
    """An append that runs the given shell function in place of the command it names."""
    return subprocess.Popen([str(BASH), "-c", f'{name}() {{ {body} }}; export -f {name}; exec "$BASH" "$@"', "sh",
                             str(APPEND), "opened", "--class", "missing-instruction", "--target", "t",
                             "--summary", "s"], env={**os.environ, **env},
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def test_a_holder_that_lost_its_lock_takes_it_again_and_mints_again(ledger: Path, tmp_path: Path):
    """A rival takes the lock over and appends L-0005 after the first mint; the holder mints L-0006."""
    lost = tmp_path / "lost"
    proc = shadowed("awk", 'local n; n=$(command awk "$@"); [ -e "$LOST" ] || { : > "$LOST"; '
                    'rm -rf "$LOCK_DIR"; echo "$RIVAL" >> "$LESSON_LEDGER_FILE"; }; echo "$n";',
                    {"LOST": lost.as_posix(), "LOCK_DIR": (ledger.parent / LOCK).as_posix(),
                     "RIVAL": '{"ts":"","id":"L-0005","event":"opened"}'})
    assert finish([proc]) == ["L-0006"]
    assert lost.exists() and ledger_ids(ledger) == ["L-0005", "L-0006"]
    assert json.loads(ledger.read_text().splitlines()[-1])["ts"].endswith("Z")
    assert not list(ledger.parent.glob(LOCK + "*"))


def test_a_signal_while_the_lock_is_held_frees_it_and_writes_nothing(ledger: Path):
    proc = shadowed("awk", 'kill -TERM $$; command awk "$@";', {})
    out, err = proc.communicate(timeout=120)
    assert proc.returncode == 143 and out == "", (out, err)
    assert not list(ledger.parent.glob(LOCK + "*")) and not ledger.exists()


def test_a_late_waiter_hands_back_a_fresh_lock_it_moved(ledger: Path, tmp_path: Path):
    """Between this waiter's age read and its mv, a rival takes the stale lock over."""
    lock, swapped = ledger.parent / LOCK, tmp_path / "swapped"
    lock.mkdir(parents=True)
    (lock / "owner").write_text("4242.1.2\n")
    proc = shadowed("stat", '[ -e "$SWAPPED" ] && { command stat "$@"; return; }; : > "$SWAPPED"; '
                    'rm -rf "$LOCK_DIR"; mkdir "$LOCK_DIR"; echo rival > "$LOCK_DIR/owner"; echo 1000;',
                    {"SWAPPED": swapped.as_posix(), "LOCK_DIR": lock.as_posix()})
    deadline = time.monotonic() + 20
    while not swapped.exists() and time.monotonic() < deadline:
        time.sleep(0.1)
    time.sleep(1)
    assert (lock / "owner").read_text().strip() == "rival"
    shutil.rmtree(lock)
    assert finish([proc]) == ["L-0001"]
    assert not list(ledger.parent.glob(LOCK + "*"))


SITE = '''
import fnmatch, os, pathlib, shutil
_scandir = os.scandir
def scandir(path="."):
    """A lesson append frees its lock between the walk's listing of a folder and its scan."""
    marker = os.environ.get("VANISH_MARKER")
    if isinstance(path, int):
        return _scandir(path)
    name = os.path.basename(os.path.normpath(os.fspath(path)))
    if marker and name == "lesson-append.lock" and not os.path.exists(marker):
        open(marker, "w").close()
        shutil.rmtree(path)
    return _scandir(path)
os.scandir = scandir
if os.environ.get("RGLOB_BEFORE_312") == "1":
    def rglob(self, pattern):
        """CPython 3.8 to 3.11: a scan catches only PermissionError."""
        def folders(path):
            yield path
            try:
                with os.scandir(path) as it:
                    entries = list(it)
            except PermissionError:
                return
            for entry in entries:
                if entry.is_dir() and not entry.is_symlink():
                    yield from folders(path / entry.name)
        for folder in folders(self):
            try:
                with os.scandir(folder) as it:
                    entries = list(it)
            except PermissionError:
                continue
            for entry in entries:
                if fnmatch.fnmatchcase(entry.name, pattern):
                    yield folder / entry.name
    pathlib.Path.rglob = rglob
'''

GATE = (". hooks/lib/provider.sh; . hooks/lib/config.sh; . hooks/gate-context.sh; . hooks/gate-cache.sh; "
        ". hooks/gate-metrics.sh; . hooks/native-contract-gate.sh; "
        "afk_plugin_dir() { echo .; }; afk_plugin_scope() { echo; }; "
        "GATE_CACHE_DISABLE=1 gate_native_contract")


@pytest.mark.parametrize("before_312", [True, False], ids=["python-before-3.12", "python-3.12-on"])
def test_lesson_appends_run_in_parallel_with_the_native_contract_walk(tmp_path: Path, before_312: bool):
    """V18: the gate's walk meets a lock freed mid-walk while appends run, and finishes."""
    tree = tmp_path / "tree"
    for rel in ("hooks/lib/provider.sh", "hooks/lib/config.sh", "hooks/gate-context.sh",
                "hooks/gate-cache.sh", "hooks/gate-metrics.sh", "hooks/native-contract-gate.sh",
                "hooks/lib/lavish_direct.py", "hooks/lib/shell_mutations.py", ".claude-plugin/plugin.json"):
        (tree / rel).parent.mkdir(parents=True, exist_ok=True)
        (tree / rel).write_bytes((WORKFLOW / rel).read_bytes())
    repo(tree)
    site = tmp_path / "site"
    site.mkdir()
    (site / "sitecustomize.py").write_text(SITE, encoding="utf-8")
    ledger = tree / ".claude" / "lessons" / "LEDGER.jsonl"
    lock = ledger.parent / LOCK
    lock.mkdir(parents=True)
    (lock / "owner").write_text("4242.1.2\n")
    marker = tmp_path / "vanished"
    env = {**os.environ, "LESSON_LEDGER_FILE": str(ledger)}
    env.pop("LESSON_LEDGER_DISABLE", None)
    appends = [opened(f"s{n}", env) for n in range(4)]
    gate_env = {**env, "AFK_PYTHON": sys.executable, "PYTHONPATH": str(site),
                "VANISH_MARKER": str(marker), "RGLOB_BEFORE_312": "1" if before_312 else "0"}
    done = subprocess.run([str(BASH), "-c", GATE], cwd=tree, env=gate_env,
                          capture_output=True, text=True, timeout=300)
    ids = finish(appends)
    output = done.stdout + done.stderr
    assert marker.exists(), output
    assert "Traceback" not in output and "FileNotFoundError" not in output, output
    assert "missing the `## Supported harnesses` registry" in output, output
    assert sorted(ids) == ledger_ids(ledger) == [f"L-{n:04d}" for n in range(1, 5)]


def test_lesson_appends_run_in_parallel_with_create_worktree(tmp_path: Path):
    """V18: create-worktree copies .claude while appends wait on the lock, and skips the lock folder."""
    main = repo(tmp_path / "main")
    (main / ".gitignore").write_text(".claude/\n")
    (main / "README.md").write_text("seed\n")
    commit(main)
    ledger = main / ".claude" / "lessons" / "LEDGER.jsonl"
    env = {**os.environ, "LESSON_LEDGER_FILE": str(ledger), "AFK_PLUGIN_ROOT": str(WORKFLOW)}
    env.pop("LESSON_LEDGER_DISABLE", None)
    assert finish([opened("seed", env)]) == ["L-0001"]
    lock = ledger.parent / LOCK
    lock.mkdir()
    (lock / "owner").write_text("4242.1.2\n")
    grave = ledger.parent / f"{LOCK}.4243.1.2"
    grave.mkdir()
    (grave / "owner").write_text("4243.1.2\n")
    appends = [opened(f"s{n}", env) for n in range(4)]
    base = subprocess.run(["git", "-C", str(main), "rev-parse", "--abbrev-ref", "HEAD"],
                          capture_output=True, text=True, check=True).stdout.strip()
    made = subprocess.run([str(BASH), str(WORKFLOW / "scripts" / "create-worktree"), "--branch", "feat/x",
                           "--base", base, "--dir", "wt", "--repo", str(main), "--parent",
                           str(tmp_path / "wts"), "--no-open"], env=env, capture_output=True, text=True,
                          timeout=300)
    shutil.rmtree(lock)
    ids = finish(appends)
    assert made.returncode == 0, made.stdout + made.stderr
    copied = tmp_path / "wts" / "wt" / ".claude" / "lessons"
    assert (copied / "LEDGER.jsonl").is_file(), made.stdout + made.stderr
    assert not list(copied.glob(LOCK + "*")), list(copied.iterdir())
    assert sorted(ids) == ledger_ids(ledger)[1:] == [f"L-{n:04d}" for n in range(2, 6)]
