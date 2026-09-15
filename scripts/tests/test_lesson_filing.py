"""The installed-plugin lesson route: plugin-clone.sh, and the ledger's `filed`
event through lesson-append.sh (emitter) and lesson-digest.sh (parser)."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
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
    result = clone_check(shouted, tmp_path, HOME=str(root))
    assert result.returncode == 1 and result.stdout.startswith("PLUGIN: installed"), result


def test_case_folding_follows_the_filesystem(tmp_path: Path):
    """On a case-sensitive filesystem two spellings are two directories."""
    root = tmp_path / "home"
    market = plugin(repo(root / ".claude/plugins/marketplaces/afk-toolkit"))
    commit(market)
    shouted = Path(str(market).upper())
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
