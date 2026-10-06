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
    environ.update(logged_in_cli(tmp_path))
    return environ


def logged_in_cli(tmp_path: Path) -> dict[str, str]:
    """Config folders in which both CLIs are logged in to every host the remotes below use."""
    hosts = ("github.com", "gitlab.example.com", "gitlab.com")
    gh, glab = tmp_path / "gh-config", tmp_path / "glab-config"
    gh.mkdir(exist_ok=True)
    glab.mkdir(exist_ok=True)
    (gh / "hosts.yml").write_text("".join(f"{h}:\n    user: u\n" for h in hosts), encoding="utf-8")
    (glab / "config.yml").write_text("hosts:\n" + "".join(f"  {h}:\n    token: x\n" for h in hosts),
                                     encoding="utf-8")
    return {"GH_CONFIG_DIR": str(gh), "GLAB_CONFIG_DIR": str(glab)}


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


def test_gitlab_a_rule_inherited_from_the_group_protects(tmp_path):
    rules = '[{"name":"develop","inherited":true},{"name":"main","inherited":false}]'
    environ = stub(tmp_path, "glab", f"echo '{rules}'\n")
    answer, done = protection("gitlab", environ, "develop", tmp_path)
    assert answer["protected"] is True, done.stdout


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


def test_answer_is_asked_live_each_time_with_the_cache_off(tmp_path):
    """AC-010: with a TTL of 0, a branch protected after the first call is protected on the next."""
    marker = tmp_path / "second"
    body = (f'case "$*" in *rules/*) echo "[]" ;; *) if [ -e "{marker.as_posix()}" ]; '
            'then echo \'{"protected": true}\'; else echo \'{"protected": false}\'; fi ;; esac\n')
    environ = stub(tmp_path, "gh", body)
    environ["AFK_PROTECTION_CACHE_TTL"] = "0"
    repo = make_repo(tmp_path, "https://github.com/acme/widget.git")
    first, _ = lookup(environ, repo, "topic")
    marker.write_text("x", encoding="utf-8")
    second, _ = lookup(environ, repo, "topic")
    assert (first["protected"], second["protected"]) == (False, True)


# ---- the forge answer is cached for at most 5 minutes -------------------------

class _Clock:
    """Stands in for the lookup's `time` module: the test sets `time()`; `monotonic` is real."""

    def __init__(self):
        self.now = 1_000_000.0
        self.monotonic = time.monotonic

    def time(self):
        return self.now


class _Forge:
    """Stands in for the forge adapter; counts the reads and answers `self.reply`."""

    def __init__(self):
        self.calls = 0
        self.reply = {"protected": True, "via": "branch"}

    def protection(self, *args):
        self.calls += 1
        return dict(self.reply)


@pytest.fixture
def cached(tmp_path, monkeypatch):
    """An in-process lookup on a GitHub repository whose default branch is `trunk`."""
    for name in ("GH_TOKEN", "GITHUB_TOKEN", "GITLAB_TOKEN", "AFK_CONFIG", "AFK_PROTECTION_CACHE_TTL",
                 "AFK_GITHUB_API_URL", "AFK_GITLAB_API_URL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AFK_PLUGIN_ROOT", str(PLUGIN_ROOT))
    spec = importlib.util.spec_from_file_location("afk_lookup_cache", LOOKUP)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    forge, clock, real_load = _Forge(), _Clock(), module._load
    monkeypatch.setattr(module, "_load", lambda name, path: forge if name == "afk_branch_protection"
                        else real_load(name, path))
    monkeypatch.setattr(module, "time", clock)
    repo = make_repo(tmp_path, "https://github.com/acme/widget.git")
    git(repo, "update-ref", "refs/remotes/origin/trunk", "HEAD")
    git(repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/trunk")
    common = repo / ".git"

    def ask(branch="topic"):
        return module.lookup(branch, repo, common)

    return ask, forge, clock, common / "afk" / "protection-cache.json"


def test_two_lookups_within_the_ttl_ask_the_forge_once(cached):
    ask, forge, clock, _ = cached
    first = ask()
    clock.now += 299
    assert ask() == first == {"protected": True, "source": "github"}
    assert forge.calls == 1


def test_a_lookup_after_the_ttl_asks_the_forge_again(cached):
    ask, forge, clock, _ = cached
    ask()
    clock.now += 300
    forge.reply = {"protected": False, "via": "none"}
    assert ask() == {"protected": False, "source": "github"}
    assert forge.calls == 2


@pytest.mark.parametrize("branch", ("trunk", "main", "master"))
def test_the_default_branch_main_and_master_are_always_live(cached, branch):
    ask, forge, _, cache = cached
    ask(branch)
    ask(branch)
    assert forge.calls == 2
    assert not cache.exists()


def test_a_failed_read_is_not_cached(cached):
    ask, forge, _, _ = cached
    forge.reply = {"error": True, "verb": "branch-protection", "reason": "the branch read failed"}
    assert ask()["source"] == "fallback"
    forge.reply = {"protected": True, "via": "branch"}
    assert ask() == {"protected": True, "source": "github"}
    assert forge.calls == 2


@pytest.mark.parametrize("text", ("{not json", "[]", '{"x": {"at": "soon"}}', '{"k": 1}'))
def test_an_unreadable_cache_file_asks_live(cached, text):
    ask, forge, _, cache = cached
    ask()
    cache.write_text(text, encoding="utf-8")
    assert ask() == {"protected": True, "source": "github"}
    assert forge.calls == 2
    assert len(json.loads(cache.read_text(encoding="utf-8"))) == 1, "the live answer replaced the file"


@pytest.mark.parametrize("ttl", ("0", "-5"))
def test_a_ttl_of_0_asks_live_every_time(cached, monkeypatch, ttl):
    ask, forge, _, cache = cached
    monkeypatch.setenv("AFK_PROTECTION_CACHE_TTL", ttl)
    ask()
    ask()
    assert forge.calls == 2
    assert not cache.exists()


def test_the_ttl_is_capped_at_5_minutes(cached, monkeypatch):
    ask, forge, clock, _ = cached
    monkeypatch.setenv("AFK_PROTECTION_CACHE_TTL", "3600")
    ask()
    clock.now += 300
    ask()
    assert forge.calls == 2


def test_the_cache_is_per_branch(cached):
    ask, forge, _, _ = cached
    ask("topic")
    ask("other")
    ask("topic")
    assert forge.calls == 2


def test_an_unknown_default_branch_turns_the_cache_off(cached, tmp_path):
    ask, forge, _, cache = cached
    git(tmp_path / "repo", "symbolic-ref", "--delete", "refs/remotes/origin/HEAD")
    ask("trunk")
    ask("trunk")
    ask("topic")
    ask("topic")
    assert forge.calls == 4
    assert not cache.exists()


@pytest.mark.parametrize("at", ("10" * 200, "1e400", "-1e400"))
def test_an_out_of_range_timestamp_is_a_miss(cached, at):
    ask, forge, _, cache = cached
    ask()
    entries = json.loads(cache.read_text(encoding="utf-8"))
    cache.write_text(json.dumps(entries).replace(str(next(iter(entries.values()))["at"]), at), encoding="utf-8")
    assert ask() == {"protected": True, "source": "github"}
    assert forge.calls == 2


def test_a_timestamp_in_the_future_is_a_miss(cached):
    ask, forge, clock, _ = cached
    ask()
    clock.now -= 1
    ask()
    assert forge.calls == 2


@pytest.mark.parametrize("remote", ("https://github.com/other/widget.git", "https://github.example.com/acme/widget.git"))
def test_the_cache_is_per_repository_and_host(cached, tmp_path, remote):
    ask, forge, _, _ = cached
    ask()
    git(tmp_path / "repo", "remote", "set-url", "origin", remote)
    ask()
    assert forge.calls == 2


def test_an_unreadable_cache_path_asks_live_and_still_answers(cached):
    ask, forge, _, cache = cached
    cache.mkdir(parents=True)
    assert ask() == ask() == {"protected": True, "source": "github"}
    assert forge.calls == 2
    assert cache.is_dir() and list(cache.parent.iterdir()) == [cache]


def test_a_failed_replace_still_answers_and_publishes_nothing(cached, monkeypatch):
    ask, forge, _, cache = cached
    refused = []

    def refuse(*args):
        refused.append(args)
        raise PermissionError("in use")

    monkeypatch.setattr(os, "replace", refuse)
    assert ask() == {"protected": True, "source": "github"}
    assert refused, "the cache is published through os.replace"
    assert not cache.exists() and list(cache.parent.iterdir()) == []
    ask()
    assert forge.calls == 2


def test_the_cache_write_leaves_no_temporary_file(cached):
    ask, _, _, cache = cached
    ask()
    assert [path.name for path in cache.parent.iterdir()] == ["protection-cache.json"]


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
    environ["AFK_PROTECTION_CACHE_TTL"] = "0"  # the second read must parse the edited config, not hit the cache
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


# ---- the login token is asked once and used over HTTPS ------------------------

def _serve(seen: list):
    import http.server
    import threading

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            seen.append((self.path, self.headers.get("Authorization")))
            body = b'{"protected": true}' if "/branches/" in self.path and "/rules/" not in self.path else b"[]"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def _read_module():
    spec = importlib.util.spec_from_file_location("afk_bp_token", READ)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_p4_no_env_token_asks_the_cli_once_and_reads_over_https(tmp_path, monkeypatch):
    calls = tmp_path / "calls.log"
    body = (f'echo "$*" >> "{calls.as_posix()}"\n'
            'case "$*" in "auth token"*) echo tok-from-cli ;; *) echo "gh api must not run" >&2; exit 1 ;; esac\n')
    environ = stub(tmp_path, "gh", body)
    monkeypatch.setenv("PATH", environ["PATH"])
    for name in ("GH_TOKEN", "GITHUB_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    module = _read_module()
    seen: list = []

    def reply(url, headers, deadline):
        seen.append((url, headers.get("Authorization")))
        return 200, '{"protected": true}' if "/rules/" not in url else "[]", {}

    monkeypatch.setattr(module, "_https_get", reply)
    answer = module.protection("github", "main", "o/r", str(tmp_path), 20.0, "https://api.github.com")
    assert answer == {"protected": True, "via": "branch"}, answer
    assert len(seen) == 2 and all(auth == "Bearer tok-from-cli" for _, auth in seen)
    assert calls.read_text(encoding="utf-8").splitlines() == ["auth token --hostname github.com"]


def test_r9_1_an_override_host_never_gets_the_cli_login_token(tmp_path, monkeypatch):
    calls = tmp_path / "calls.log"
    body = (f'echo "$*" >> "{calls.as_posix()}"\n'
            'case "$*" in "auth token"*) echo github-dot-com-login ;; *rules/*) echo "[]" ;; '
            '*) echo \'{"protected": true}\' ;; esac\n')
    environ = stub(tmp_path, "gh", body)
    monkeypatch.setenv("PATH", environ["PATH"])
    for name in ("GH_TOKEN", "GITHUB_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    seen: list = []
    server = _serve(seen)
    try:
        answer = _read_module().protection("github", "main", "o/r", str(tmp_path), 20.0,
                                           f"http://127.0.0.1:{server.server_port}")
    finally:
        server.shutdown()
    assert answer == {"protected": True, "via": "branch"}, answer
    assert seen == [], "no request, and so no credential, reaches the override"
    assert not any(line.startswith("auth token") for line in calls.read_text(encoding="utf-8").splitlines())


def test_p4_a_failing_token_call_falls_back_to_the_cli_reads(tmp_path, monkeypatch):
    environ = stub(tmp_path, "gh", GITHUB_STUB.replace("case", 'case "$*" in "auth token"*) exit 1 ;; esac\ncase', 1))
    monkeypatch.setenv("PATH", environ["PATH"])
    for name in ("GH_TOKEN", "GITHUB_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    answer = _read_module().protection("github", "main", "o/r", str(tmp_path), 20.0, "http://127.0.0.1:9")
    assert answer == {"protected": True, "via": "branch"}, answer


@pytest.mark.parametrize("forge,token", [("github", "GH_TOKEN"), ("gitlab", "GITLAB_TOKEN")])
def test_r10_2_no_token_goes_over_plain_http_to_another_host(tmp_path, monkeypatch, forge, token):
    body = GITHUB_STUB if forge == "github" else GITLAB_PAGES
    environ = stub(tmp_path, TOOL[forge], body)
    monkeypatch.setenv("PATH", environ["PATH"])
    monkeypatch.setenv(token, "secret")
    module = _read_module()
    sent: list = []
    monkeypatch.setattr(module, "_https_get", lambda *a, **k: sent.append(a) or (200, "[]", {}))
    answer = module.protection(forge, "main", "o/r", str(tmp_path), 20.0, "http://192.0.2.1:9")
    assert sent == [], "a token must not be sent in the clear"
    assert answer.get("protected") is True, answer


def test_r10_2_plain_http_to_loopback_still_carries_the_token(tmp_path, monkeypatch):
    environ = stub(tmp_path, "gh", "exit 1\n")
    monkeypatch.setenv("PATH", environ["PATH"])
    monkeypatch.setenv("GH_TOKEN", "secret")
    module = _read_module()
    sent: list = []
    monkeypatch.setattr(module, "_https_get", lambda url, headers, deadline: sent.append(url) or (200, "[]", {}))
    module.protection("github", "main", "o/r", str(tmp_path), 20.0, "http://127.0.0.1:9")
    assert len(sent) == 2


def cli_reads(tmp_path, monkeypatch, forge, host, logged_in, ssh_says=None):
    """Run the CLI path for `host`; return the argument lines the stubbed CLI saw."""
    calls = tmp_path / "calls.log"
    body = GITHUB_STUB if forge == "github" else GITLAB_PAGES
    environ = stub(tmp_path, TOOL[forge], f'echo "$*" >> "{calls.as_posix()}"\n' + body)
    if ssh_says is not None:
        environ = stub(tmp_path, "ssh", f'echo "hostname {ssh_says}"\n')
    config = tmp_path / "config"
    config.mkdir(exist_ok=True)
    if forge == "github":
        (config / "hosts.yml").write_text("".join(f"{h}:\n    user: u\n" for h in logged_in), encoding="utf-8")
        monkeypatch.setenv("GH_CONFIG_DIR", str(config))
    else:
        (config / "config.yml").write_text("hosts:\n" + "".join(f"  {h}:\n    token: x\n" for h in logged_in),
                                           encoding="utf-8")
        monkeypatch.setenv("GLAB_CONFIG_DIR", str(config))
    monkeypatch.setenv("PATH", environ["PATH"])
    for name in ("GH_TOKEN", "GITHUB_TOKEN", "GITLAB_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    answer = _read_module().protection(forge, "main", "o/r", str(tmp_path), 20.0, "", host)
    seen = calls.read_text(encoding="utf-8").splitlines() if calls.exists() else []
    return seen, answer


@pytest.mark.parametrize("forge", ["github", "gitlab"])
def test_r12_1_a_host_the_cli_is_logged_in_to_gets_the_flag(tmp_path, monkeypatch, forge):
    lines, _ = cli_reads(tmp_path, monkeypatch, forge, "ghe.example.com", ["ghe.example.com"])
    assert lines and all("--hostname ghe.example.com" in line for line in lines), lines


@pytest.mark.parametrize("forge", ["github", "gitlab"])
def test_r13_2_an_unknown_host_is_an_error_not_a_read_of_the_default_host(tmp_path, monkeypatch, forge):
    lines, answer = cli_reads(tmp_path, monkeypatch, forge, "never-logged-in.example.com", ["other.example.com"])
    assert lines == [], lines
    assert answer.get("error") and "not logged in to never-logged-in.example.com" in answer["reason"], answer


def test_r12_1_an_ssh_alias_resolves_to_the_real_host_the_cli_knows(tmp_path, monkeypatch):
    lines, _ = cli_reads(tmp_path, monkeypatch, "github", "github.com-work", ["ghe.example.com"],
                         ssh_says="ghe.example.com")
    assert lines and all("--hostname ghe.example.com" in line for line in lines), lines


def test_r12_1_an_ssh_alias_for_a_host_the_cli_does_not_know_is_an_error(tmp_path, monkeypatch):
    lines, answer = cli_reads(tmp_path, monkeypatch, "github", "github.com-work", ["ghe.example.com"],
                              ssh_says="elsewhere.example.org")
    assert lines == [] and answer.get("error"), (lines, answer)


def test_r13_2_an_ssh_alias_for_the_public_host_reads_the_default(tmp_path, monkeypatch):
    lines, answer = cli_reads(tmp_path, monkeypatch, "github", "github.com-work", ["ghe.example.com"],
                              ssh_says="github.com")
    assert lines and not any("--hostname" in line for line in lines) and answer.get("protected") is True


def test_r12_1_the_public_host_needs_no_flag(tmp_path, monkeypatch):
    lines, _ = cli_reads(tmp_path, monkeypatch, "github", "github.com", ["github.com"])
    assert lines and not any("--hostname" in line for line in lines), lines
