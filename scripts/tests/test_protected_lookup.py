"""Which branches a forge protects, and what the lookup answers for a branch.

A stub `gh` / `glab` on PATH stands in for the forge; nothing here reaches a
network. The adapter verb is pinned for shape and pagination, the lookup for the
verdict per catalog S row (S-1 exact, S-2 wildcard over every page, S-3 fallback).
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
LOOKUP = PLUGIN_ROOT / "scripts" / "protected-lookup.py"
TOOL = {"gitlab": "glab", "github": "gh"}


def _bash():
    spec = importlib.util.spec_from_file_location(
        "afk_run_hook_for_lookup", PLUGIN_ROOT / "hooks" / "run-hook.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.find_bash()


BASH = _bash()
pytestmark = pytest.mark.skipif(BASH is None, reason="no POSIX shell on this machine")


def stub(tmp_path: Path, tool: str, body: str) -> dict[str, str]:
    binaries = tmp_path / "bin"
    binaries.mkdir(exist_ok=True)
    script = binaries / tool
    script.write_text("#!/bin/sh\n" + body, encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    environ = dict(os.environ)
    environ["PATH"] = str(binaries) + os.pathsep + environ["PATH"]
    environ["AFK_PLUGIN_ROOT"] = str(PLUGIN_ROOT)
    return environ


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True,
                          text=True, check=True).stdout.strip()


def make_repo(tmp_path: Path, remote: str | None, branch: str = "feature-x") -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", branch)
    git(repo, "config", "user.email", "t@example.com")
    git(repo, "config", "user.name", "t")
    (repo / "f").write_text("x", encoding="utf-8")
    git(repo, "add", "f")
    git(repo, "commit", "-q", "-m", "init")
    if remote:
        git(repo, "remote", "add", "origin", remote)
    return repo


def adapter(kind: str, environ: dict, verb: str, payload: str, cwd: Path):
    runner = cwd / "run-forge.sh"
    runner.write_text(
        "#!/bin/sh\nexec bash \"$AFK_TEST_SCRIPT\" \"$AFK_TEST_VERB\" \"$AFK_TEST_PAYLOAD\"\n",
        encoding="utf-8")
    environ = dict(environ)
    environ["AFK_TEST_SCRIPT"] = str(PLUGIN_ROOT / "adapters" / "forge" / kind / "forge.sh")
    environ["AFK_TEST_VERB"] = verb
    environ["AFK_TEST_PAYLOAD"] = payload
    return subprocess.run([str(BASH), str(runner)], capture_output=True, text=True,
                          timeout=60, env=environ, cwd=str(cwd), stdin=subprocess.DEVNULL)


def lookup(environ: dict, repo: Path, branch: str, *extra: str):
    environ = dict(environ)
    environ["AFK_PLUGIN_ROOT"] = str(PLUGIN_ROOT)
    done = subprocess.run(
        [sys.executable, str(LOOKUP), "--branch", branch, "--checkout", str(repo), *extra],
        capture_output=True, text=True, timeout=60, env=environ)
    return json.loads(done.stdout), done


# gh: branch flag per name, rulesets per name. glab: one paginated list.
GITHUB_STUB = """
case "$*" in
  *rules/branches/ruled*) echo '[{"type":"pull_request"}]' ;;
  *rules/branches/loose*) echo '[{"type":"creation"}]' ;;
  *rules/branches/*) echo '[]' ;;
  *branches/main*|*branches/release*) echo true ;;
  *branches/*) echo false ;;
esac
"""

GITLAB_PAGES = """
echo '[{"id":1,"name":"main"}]'
echo '[{"id":2,"name":"release/*"}]'
"""


def protection(kind: str, environ: dict, branch: str, cwd: Path):
    done = adapter(kind, environ, "branch-protection", json.dumps({"branch": branch}), cwd)
    return json.loads(done.stdout), done


# ---- the adapter verb ------------------------------------------------------

@pytest.mark.parametrize("branch,hit,via", [
    ("main", True, "branch"),
    ("ruled", True, "ruleset"),       # protected by a ruleset rule only
    ("loose", False, "none"),         # a rule that does not restrict pushes
    ("topic", False, "none"),
])
def test_github_branch_flag_or_restricting_ruleset(tmp_path, branch, hit, via):
    environ = stub(tmp_path, "gh", GITHUB_STUB)
    answer, done = protection("github", environ, branch, tmp_path)
    assert (answer["protected"], answer["via"]) == (hit, via), done.stdout


@pytest.mark.parametrize("branch,hit", [
    ("main", True), ("main2", False),
    ("release/1.0", True), ("release/1.0/hotfix", True),   # * spans "/"
    ("release", False), ("topic/x", False),
])
def test_gitlab_exact_and_wildcard_over_every_page(tmp_path, branch, hit):
    environ = stub(tmp_path, "glab", GITLAB_PAGES)
    answer, done = protection("gitlab", environ, branch, tmp_path)
    assert answer["protected"] is hit, done.stdout


def test_gitlab_wildcard_dot_is_literal(tmp_path):
    environ = stub(tmp_path, "glab", "echo '[{\"name\":\"a.b\"}]'\n")
    answer, _ = protection("gitlab", environ, "aXb", tmp_path)
    assert answer["protected"] is False


@pytest.mark.parametrize("kind", ("github", "gitlab"))
def test_failure_is_an_error_never_not_protected(tmp_path, kind):
    environ = stub(tmp_path, TOOL[kind], "echo 'no' >&2\nexit 1\n")
    answer, done = protection(kind, environ, "main", tmp_path)
    assert answer.get("error") is True and "protected" not in answer, done.stdout


def test_none_kind_answers_unsupported(tmp_path):
    done = adapter("none", dict(os.environ), "branch-protection", "{}", tmp_path)
    assert done.returncode == 3
    assert json.loads(done.stdout)["unsupported"] is True


@pytest.mark.parametrize("kind", ("github", "gitlab", "none"))
def test_manifest_declares_the_verb(kind):
    manifest = json.loads((PLUGIN_ROOT / "adapters" / "forge" / kind / "adapter.json")
                          .read_text(encoding="utf-8"))
    assert "branch-protection" in manifest["operations"]


# ---- the lookup, per catalog S row ------------------------------------------

def test_github_listed_branch_is_protected(tmp_path):
    environ = stub(tmp_path, "gh", GITHUB_STUB)
    repo = make_repo(tmp_path, "https://github.com/acme/widget.git")
    answer, _ = lookup(environ, repo, "release")
    assert answer == {"protected": True, "source": "github"}


def test_github_unlisted_branch_is_not_protected(tmp_path):
    environ = stub(tmp_path, "gh", GITHUB_STUB)
    repo = make_repo(tmp_path, "git@github.com:acme/widget.git")
    answer, _ = lookup(environ, repo, "feature-x")
    assert answer == {"protected": False, "source": "github"}


def test_github_ruleset_only_branch_is_protected(tmp_path):
    environ = stub(tmp_path, "gh", GITHUB_STUB)
    repo = make_repo(tmp_path, "https://github.com/acme/widget.git")
    answer, _ = lookup(environ, repo, "ruled")
    assert answer == {"protected": True, "source": "github"}


def test_gitlab_wildcard_on_a_later_page_is_protected(tmp_path):
    environ = stub(tmp_path, "glab", GITLAB_PAGES)
    repo = make_repo(tmp_path, "https://gitlab.example.com/grp/sub/widget.git")
    answer, _ = lookup(environ, repo, "release/2.1")
    assert answer == {"protected": True, "source": "gitlab"}


def test_gitlab_no_match_is_not_protected(tmp_path):
    environ = stub(tmp_path, "glab", GITLAB_PAGES)
    repo = make_repo(tmp_path, "https://gitlab.example.com/grp/widget.git")
    answer, _ = lookup(environ, repo, "topic/x")
    assert answer == {"protected": False, "source": "gitlab"}


def test_config_forge_wins_over_the_remote_address(tmp_path):
    environ = stub(tmp_path, "glab", GITLAB_PAGES)
    repo = make_repo(tmp_path, "https://github.com/acme/widget.git")
    (repo / ".afk").mkdir()
    (repo / ".afk" / "config.yaml").write_text("forge: gitlab\n", encoding="utf-8")
    answer, _ = lookup(environ, repo, "main")
    assert answer == {"protected": True, "source": "gitlab"}


def test_answer_is_asked_live_each_time(tmp_path):
    """AC-010: a branch protected after the first call is protected on the next."""
    marker = tmp_path / "second"
    body = f'if [ -e "{marker.as_posix()}" ]; then echo true; else echo false; fi\n'
    environ = stub(tmp_path, "gh", body)
    repo = make_repo(tmp_path, "https://github.com/acme/widget.git")
    first, _ = lookup(environ, repo, "topic")
    marker.write_text("x", encoding="utf-8")
    second, _ = lookup(environ, repo, "topic")
    assert (first["protected"], second["protected"]) == (False, True)


# ---- fallback S-3 --------------------------------------------------------------

@pytest.mark.parametrize("branch,hit", [("main", True), ("master", True), ("trunk", True),
                                        ("feature-x", False)])
def test_unknown_forge_falls_back_to_default_main_master(tmp_path, branch, hit):
    repo = make_repo(tmp_path, "https://git.example.org/team/widget.git")
    git(repo, "update-ref", "refs/remotes/origin/trunk", "HEAD")
    git(repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/trunk")
    answer, _ = lookup(dict(os.environ), repo, branch)
    assert answer["protected"] is hit
    assert answer["source"] == "fallback"
    assert answer["reason"]


def test_no_remote_falls_back(tmp_path):
    repo = make_repo(tmp_path, None)
    answer, _ = lookup(dict(os.environ), repo, "main")
    assert answer["protected"] is True and answer["source"] == "fallback"


def test_forge_error_falls_back(tmp_path):
    environ = stub(tmp_path, "gh", "exit 1\n")
    repo = make_repo(tmp_path, "https://github.com/acme/widget.git")
    answer, _ = lookup(environ, repo, "master")
    assert answer["protected"] is True and answer["source"] == "fallback"
    assert answer["reason"]


def test_missing_cli_falls_back(tmp_path):
    repo = make_repo(tmp_path, "https://github.com/acme/widget.git")
    empty = tmp_path / "empty"
    empty.mkdir()
    keep = {str(Path(shutil.which(t)).parent) for t in ("git", "bash")} | {str(Path(sys.executable).parent)}
    environ = dict(os.environ)
    environ["PATH"] = os.pathsep.join([str(empty), *keep])
    answer, _ = lookup(environ, repo, "main")
    assert answer["protected"] is True and answer["source"] == "fallback"


def test_slow_forge_times_out_into_the_fallback(tmp_path):
    environ = stub(tmp_path, "gh", "sleep 30\n")
    environ["AFK_PROTECTED_TIMEOUT"] = "1"
    repo = make_repo(tmp_path, "https://github.com/acme/widget.git")
    answer, done = lookup(environ, repo, "main")
    assert answer["source"] == "fallback" and answer["protected"] is True
    assert "timed out" in answer["reason"]
