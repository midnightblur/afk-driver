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


def protection(kind: str, environ: dict, branch: str, cwd: Path):
    done = adapter(kind, environ, "branch-protection", json.dumps({"branch": branch}), cwd)
    return json.loads(done.stdout), done


# ---- the adapter verb ------------------------------------------------------

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
    body = (f'case "$*" in *rules/*) echo "[]" ;; *) if [ -e "{marker.as_posix()}" ]; '
            'then echo \'{"protected": true}\'; else echo \'{"protected": false}\'; fi ;; esac\n')
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
    started = time.monotonic()
    answer, done = lookup(environ, repo, "main")
    assert time.monotonic() - started < 8, "the cap is wall-clock"
    assert answer["source"] == "fallback" and answer["protected"] is True
    assert "did not answer" in answer["reason"]


class _Status:
    """A tiny HTTP server answering every request with one status; `seen` records the paths."""

    def __init__(self, status: int, body: str = "[]"):
        import http.server
        import threading
        seen = self.seen = []

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                seen.append(self.path)
                payload = body.encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args):
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"


@pytest.mark.parametrize("status", (401, 403))
def test_r3_2_a_refused_github_token_falls_through_to_the_cli(tmp_path, status):
    environ = stub(tmp_path, "gh", GITHUB_STUB)
    server = _Status(status)
    environ.update(GH_TOKEN="wrong-host", AFK_GITHUB_API_URL=server.url)
    repo = make_repo(tmp_path, "https://github.com/acme/widget.git")
    answer, _ = lookup(environ, repo, "release")
    server.server.shutdown()
    assert server.seen, "the token path was tried first"
    assert answer["source"] == "github" and answer["protected"] is True


def test_r3_2_a_refused_gitlab_token_falls_through_to_the_cli(tmp_path):
    environ = stub(tmp_path, "glab", GITLAB_PAGES)
    server = _Status(401)
    environ.update(GITLAB_TOKEN="wrong-host", AFK_GITLAB_API_URL=server.url)
    repo = make_repo(tmp_path, "https://gitlab.com/acme/widget.git")
    answer, _ = lookup(environ, repo, "main")
    server.server.shutdown()
    assert server.seen and answer["source"] == "gitlab" and answer["protected"] is True


def test_r3_2_the_override_of_the_other_forge_is_never_used(tmp_path):
    environ = stub(tmp_path, "glab", GITLAB_PAGES)
    server = _Status(200)
    environ.update(GITLAB_TOKEN="secret", AFK_GITHUB_API_URL=server.url)
    repo = make_repo(tmp_path, "https://gitlab.com/acme/widget.git")
    lookup(environ, repo, "main")
    server.server.shutdown()
    assert server.seen == [], "a GitLab token must not reach a URL meant for GitHub"


def test_r3_3_an_insteadof_alias_and_an_inline_comment_are_resolved_by_git(tmp_path):
    environ = stub(tmp_path, "gh", GITHUB_STUB)
    repo = make_repo(tmp_path, "gh:acme/widget.git")
    git(repo, "config", "url.https://github.com/.insteadOf", "gh:")
    answer, _ = lookup(environ, repo, "release")
    assert answer["source"] == "github" and answer["protected"] is True
    config = repo / ".git" / "config"
    text = config.read_text(encoding="utf-8").replace("url = gh:acme", "url = https://github.com/acme")
    config.write_text(text.replace(".git\n", ".git ; the mirror\n", 1), encoding="utf-8")
    answer, _ = lookup(environ, repo, "release")
    assert answer["source"] == "github"


def test_r3_5_the_cli_cap_is_wall_clock_without_a_token(tmp_path):
    environ = stub(tmp_path, "gh", "sleep 30\n")
    environ["AFK_PROTECTED_TIMEOUT"] = "1"
    repo = make_repo(tmp_path, "https://github.com/acme/widget.git")
    started = time.monotonic()
    answer, _ = lookup(environ, repo, "main")
    assert time.monotonic() - started < 6 and answer["source"] == "fallback"


def test_r4_6_the_lookups_git_reads_share_one_deadline(tmp_path, monkeypatch):
    """A git that hangs must cost the cap once, not once per read plus the forge read."""
    spec = importlib.util.spec_from_file_location("afk_lookup_deadline", LOOKUP)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    (repo / ".git" / "config").write_text(
        '[remote "origin"]\n\turl = https://github.com/o/r.git\n[url "https://github.com/"]\n\tinsteadOf = gh:\n',
        encoding="utf-8")
    for name in ("GH_TOKEN", "GITHUB_TOKEN", "GITLAB_TOKEN", "AFK_CONFIG"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AFK_PROTECTED_TIMEOUT", "1")
    real_run = subprocess.run

    def hanging(argv, **kwargs):
        if argv and argv[0] == "git":
            time.sleep(kwargs.get("timeout") or 30)
            raise subprocess.TimeoutExpired(argv, kwargs.get("timeout") or 30)
        return real_run(argv, **kwargs)

    monkeypatch.setattr(module.subprocess, "run", hanging)
    started = time.monotonic()
    answer = module.lookup("feature", repo, repo / ".git")
    assert time.monotonic() - started < 2.0
    assert answer["source"] == "fallback"
