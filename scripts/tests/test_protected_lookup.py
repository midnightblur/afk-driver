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
import time
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
    script = binaries / (tool + ".sh")
    script.write_text("#!/bin/sh\n" + body, encoding="utf-8", newline="\n")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    if os.name == "nt":
        (binaries / (tool + ".cmd")).write_text(f'@"{BASH}" "%~dp0{tool}.sh" %*\r\n', encoding="utf-8")
    else:
        (binaries / tool).write_text(f'#!/bin/sh\nexec sh "{script}" "$@"\n', encoding="utf-8")
        (binaries / tool).chmod(0o755)
    environ = {k: v for k, v in os.environ.items()
               if k not in ("GH_TOKEN", "GITHUB_TOKEN", "GITLAB_TOKEN", "AFK_GITHUB_API_URL", "AFK_GITLAB_API_URL")}
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
  *rules/branches/broken*) echo boom >&2; exit 1 ;;
  *rules/branches/notlist*) echo '{"message":"nope"}' ;;
  *rules/branches/ruled*) echo '[{"type":"pull_request"}]' ;;
  *rules/branches/loose*) echo '[{"type":"creation"}]' ;;
  *rules/branches/*) echo '[]' ;;
  *branches/main*|*branches/release*) echo '{"protected": true}' ;;
  *branches/unpushed*) echo 'gh: Not Found (HTTP 404)' >&2; exit 1 ;;
  *branches/*) echo '{"protected": false}' ;;
esac
"""

GITLAB_PAGES = """
echo '[{"id":1,"name":"main"}]'
echo '[{"id":2,"name":"release/*"}]'
"""


READ = PLUGIN_ROOT / "adapters" / "forge" / "branch_protection.py"


def protection(kind: str, environ: dict, branch: str, cwd: Path):
    done = subprocess.run([sys.executable, str(READ), kind, "--branch", branch], capture_output=True,
                          text=True, timeout=60, env=environ, cwd=str(cwd), stdin=subprocess.DEVNULL)
    return json.loads(done.stdout), done


# ---- the shared read -------------------------------------------------------

@pytest.mark.parametrize("branch,hit,via", [
    ("main", True, "branch"),
    ("ruled", True, "ruleset"),       # protected by a ruleset rule only
    ("loose", False, "none"),         # a rule that does not restrict pushes
    ("topic", False, "none"),
    ("unpushed", False, "none"),      # the branch read 404s: not classically protected
])
def test_github_branch_flag_or_restricting_ruleset(tmp_path, branch, hit, via):
    environ = stub(tmp_path, "gh", GITHUB_STUB)
    answer, done = protection("github", environ, branch, tmp_path)
    assert (answer["protected"], answer["via"]) == (hit, via), done.stdout


@pytest.mark.parametrize("branch", ("broken", "notlist"))
def test_r1_2_a_failed_or_malformed_rules_read_is_an_error(tmp_path, branch):
    environ = stub(tmp_path, "gh", GITHUB_STUB)
    answer, done = protection("github", environ, branch, tmp_path)
    assert answer.get("error") is True and "protected" not in answer, done.stdout


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


def test_r8_8_no_forge_adapter_declares_a_branch_protection_verb():
    for kind in ("github", "gitlab", "none"):
        manifest = json.loads((PLUGIN_ROOT / "adapters" / "forge" / kind / "adapter.json")
                              .read_text(encoding="utf-8"))
        assert "branch-protection" not in manifest["operations"]

