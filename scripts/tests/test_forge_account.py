"""Every forge call acts as the repository's forge account, and no token leaves the call.

A stub `gh` / `glab` on PATH stands in for the forge and logs each call with the
token and host variables it received. The stub holds two accounts on one host,
`alice` (the repository's account) and `bob` (the default login); its tokens are
fake strings. Nothing here reaches a network, and HOME is a temporary folder.
"""
from __future__ import annotations

import importlib.util
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
HELPER = PLUGIN_ROOT / "scripts" / "forge_account.py"
LOOKUP = PLUGIN_ROOT / "scripts" / "protected-lookup.py"
TOKEN_VARIABLES = ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN",
                   "GITLAB_TOKEN", "GH_HOST", "GITLAB_HOST", "AFK_GITHUB_API_URL", "AFK_GITLAB_API_URL")


def _module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BASH = _module("afk_run_hook_for_forge_account", PLUGIN_ROOT / "hooks" / "run-hook.py").find_bash()
needs_bash = pytest.mark.skipif(BASH is None, reason="no POSIX shell on this machine")


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    folder = tmp_path / "home"
    folder.mkdir()
    for name in ("HOME", "USERPROFILE"):
        monkeypatch.setenv(name, str(folder))
    for name in (*TOKEN_VARIABLES, "AFK_CONFIG", "CLAUDE_PROJECT_DIR", "XDG_CONFIG_HOME"):
        monkeypatch.delenv(name, raising=False)
    return folder


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True,
                          check=True).stdout.strip()


def make_repo(tmp_path: Path, remote: str, account: str | None = "alice", name: str = "repo") -> Path:
    repo = tmp_path / name
    repo.mkdir()
    git(repo, "init", "-q", "-b", "feature-x")
    git(repo, "config", "user.email", "t@example.com")
    git(repo, "config", "user.name", "t")
    (repo / "f").write_text("x", encoding="utf-8")
    git(repo, "add", "f")
    git(repo, "commit", "-q", "-m", "init")
    git(repo, "remote", "add", "origin", remote)
    if account is not None:
        set_account(repo, account)
    return repo


def set_account(repo: Path, account: str) -> None:
    personal = repo / ".git" / "afk" / "config.yaml"
    personal.parent.mkdir(parents=True, exist_ok=True)
    personal.write_text(f"developer:\n  forgeAccount: {account}\n", encoding="utf-8")


GH_STUB = r"""
printf 'ARGS=%s|GH_TOKEN=%s|GITHUB_TOKEN=%s|GH_ENTERPRISE_TOKEN=%s|GH_HOST=%s\n' \
  "$(printf '%s' "$*" | tr '\n|' '  ')" "${GH_TOKEN:-}" "${GITHUB_TOKEN:-}" "${GH_ENTERPRISE_TOKEN:-}" "${GH_HOST:-}" >> "$STUB_LOG"
case "$*" in
  "auth token"*"--user alice"*) [ -n "${STUB_NO_TOKEN:-}" ] && exit 1; echo fake-token-alice ;;
  "auth token"*"--user bob"*) echo fake-token-bob ;;
  "auth token"*"--user"*) exit 1 ;;
  "auth token"*) echo fake-token-bob ;;
  "auth status"*"--jq"*) printf 'bob\nalice\n' ;;
  "auth status"*) exit 0 ;;
  "api user"*)
    case "${GH_TOKEN:-}${GH_ENTERPRISE_TOKEN:-}" in fake-token-alice) echo alice ;; *) echo bob ;; esac ;;
  *rules/branches/*) echo '[]' ;;
  *repos/*/branches/*) echo '{"protected": false}' ;;
  *) echo '{}' ;;
esac
"""

GLAB_STUB = r"""
printf 'ARGS=%s|GITLAB_HOST=%s\n' "$(printf '%s' "$*" | tr '\n|' '  ')" "${GITLAB_HOST:-}" >> "$STUB_LOG"
case "$*" in
  "api --hostname"*" user") echo "{\"username\":\"${STUB_LOGIN:-alice}\"}" ;;
  "auth status"*) exit 0 ;;
  "api user") echo '{"username":"bob"}' ;;
  *) echo '{}' ;;
esac
"""


def stub(tmp_path: Path, tool: str, body: str) -> dict[str, str]:
    """A stub CLI reachable from bash and from Python, and the environment that finds it."""
    binaries = tmp_path / "bin"
    binaries.mkdir(exist_ok=True)
    script = binaries / f"{tool}.sh"
    script.write_text("#!/bin/sh\n" + body, encoding="utf-8", newline="\n")
    wrapper = binaries / tool
    wrapper.write_text(f'#!/bin/sh\nexec sh "{script.as_posix()}" "$@"\n', encoding="utf-8", newline="\n")
    wrapper.chmod(wrapper.stat().st_mode | stat.S_IEXEC)
    if os.name == "nt":
        (binaries / f"{tool}.cmd").write_text(f'@"{BASH}" "%~dp0{tool}.sh" %*\r\n', encoding="utf-8")
    environ = dict(os.environ)
    environ["PATH"] = str(binaries) + os.pathsep + environ["PATH"]
    environ["AFK_PLUGIN_ROOT"] = str(PLUGIN_ROOT)
    environ["STUB_LOG"] = str(tmp_path / f"{tool}.log")
    return environ


def calls(environ: dict) -> list[dict]:
    log = Path(environ["STUB_LOG"])
    if not log.is_file():
        return []
    found = []
    for line in log.read_text(encoding="utf-8").splitlines():
        fields = dict(part.split("=", 1) for part in line.split("|"))
        found.append(fields)
    return found


RUNNER = '#!/bin/sh\nexec bash "$AFK_TEST_SCRIPT" "$AFK_TEST_VERB" "$AFK_TEST_PAYLOAD"\n'


def forge(kind: str, environ: dict, verb: str, payload: str, cwd: Path):
    runner = cwd.parent / "run-forge.sh"
    runner.write_text(RUNNER, encoding="utf-8", newline="\n")
    environ = {**environ, "AFK_TEST_SCRIPT": str(PLUGIN_ROOT / "adapters" / "forge" / kind / "forge.sh"),
               "AFK_TEST_VERB": verb, "AFK_TEST_PAYLOAD": payload, "AFK_FORGE_TIMEOUT": "20"}
    return subprocess.run([str(BASH), str(runner)], capture_output=True, text=True, timeout=180,
                          env=environ, cwd=str(cwd), stdin=subprocess.DEVNULL)


# ---- the helper -----------------------------------------------------------------

def test_helper_answers_host_and_account_and_never_a_token(tmp_path):
    helper = _module("afk_forge_account_t1", HELPER)
    repo = make_repo(tmp_path, "https://github.com/acme/widget.git")
    assert helper.host_and_account(repo) == ("github.com", "alice")
    done = subprocess.run([sys.executable, str(HELPER), "--checkout", str(repo)],
                          capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr
    assert done.stdout.splitlines() == ["github.com", "alice", "GH_TOKEN"]
    other = make_repo(tmp_path, "git@github.acme.test:acme/widget.git", account=None, name="other")
    assert helper.host_and_account(other) == ("github.acme.test", "")


@pytest.mark.parametrize(("host", "variable"), [
    ("github.com", "GH_TOKEN"), ("ghe.com", "GH_TOKEN"), ("acme.ghe.com", "GH_TOKEN"),
    ("github.acme.test", "GH_ENTERPRISE_TOKEN"), ("", "GH_TOKEN")])
def test_token_variable_follows_the_host_kind(host, variable):
    assert _module("afk_forge_account_t2", HELPER).token_variable(host) == variable


def test_unreadable_settings_fail_closed(tmp_path):
    helper = _module("afk_forge_account_t3", HELPER)
    repo = make_repo(tmp_path, "https://github.com/acme/widget.git", account=None)
    personal = repo / ".git" / "afk" / "config.yaml"
    personal.parent.mkdir(parents=True)
    personal.write_text("developer: {forgeAccount: alice}\n", encoding="utf-8")
    with pytest.raises(helper.AccountError):
        helper.host_and_account(repo)
    done = subprocess.run([sys.executable, str(HELPER), "--checkout", str(repo)],
                          capture_output=True, text=True, timeout=60)
    assert done.returncode == 2 and done.stdout == ""


# ---- the GitHub wrapper ---------------------------------------------------------

GITHUB_VERBS = [
    ("change-view", '{"id":"7"}'), ("change-diff", '{"id":"7"}'), ("change-state", '{"id":"7"}'),
    ("change-fetch", '{"id":"7"}'), ("change-create-draft", '{"title":"t","body":"b","assignee":"none"}'),
    ("change-ready", '{"id":"7"}'), ("change-reviewers", '{"id":"7","reviewers":"carol"}'),
    ("change-update-body", '{"id":"7","body":"b"}'), ("change-comment", '{"id":"7","text":"x"}'),
    ("change-close", '{"id":"7"}'), ("note-list", '{"id":"7"}'), ("commit-changes", '{"sha":"abc"}'),
    ("thread-list", '{"id":"7"}'), ("thread-reply", '{"id":"7","thread":"1","text":"x"}'),
    ("thread-resolve", '{"id":"7","thread":"1","resolved":true}'), ("ci-status", '{"id":"7"}'),
    ("ci-wait", '{"id":"7","budget":"1","interval":"1"}'), ("auth-status", "{}"),
]


@needs_bash
@pytest.mark.parametrize(("remote", "host", "variable"), [
    ("https://github.com/acme/widget.git", "github.com", "GH_TOKEN"),
    ("https://github.acme.test/acme/widget.git", "github.acme.test", "GH_ENTERPRISE_TOKEN")])
def test_every_github_verb_acts_as_the_account(tmp_path, remote, host, variable):
    repo = make_repo(tmp_path, remote)
    environ = stub(tmp_path, "gh", GH_STUB)
    for verb, payload in GITHUB_VERBS:
        forge("github", environ, verb, payload, repo)
    seen = calls(environ)
    fetches = [c for c in seen if c["ARGS"].startswith("auth token")]
    work = [c for c in seen if not c["ARGS"].startswith("auth ")]
    assert fetches and work
    assert all(c["ARGS"] == f"auth token --hostname {host} --user alice" for c in fetches)
    assert all(not (c["GH_TOKEN"] or c["GITHUB_TOKEN"] or c["GH_ENTERPRISE_TOKEN"]) for c in fetches)
    for c in work:
        assert c[variable] == "fake-token-alice", c
        assert c["GH_HOST"] == host
        assert "fake-token-bob" not in c.values()
        other = {"GH_TOKEN", "GH_ENTERPRISE_TOKEN"} - {variable}
        assert all(not c[name] for name in other) and not c["GITHUB_TOKEN"]
    assert not any("--assignee" in c["ARGS"] for c in seen)
    assert not any("--repo" in c["ARGS"] for c in work if c["ARGS"].startswith("pr view"))


@needs_bash
def test_github_auth_status_with_the_account(tmp_path):
    repo = make_repo(tmp_path, "https://github.com/acme/widget.git")
    environ = stub(tmp_path, "gh", GH_STUB)
    done = forge("github", environ, "auth-status", "{}", repo)
    answer = json.loads(done.stdout)
    assert done.returncode == 0, done.stderr
    assert answer == {"authenticated": True, "user": "alice", "account": "alice",
                      "host": "github.com", "accounts": ["alice", "bob"]}
    assert "fake-token" not in done.stdout + done.stderr


@needs_bash
def test_github_auth_status_without_the_token_never_uses_the_default_login(tmp_path):
    repo = make_repo(tmp_path, "https://github.com/acme/widget.git")
    environ = {**stub(tmp_path, "gh", GH_STUB), "STUB_NO_TOKEN": "1"}
    done = forge("github", environ, "auth-status", "{}", repo)
    assert done.returncode != 0
    answer = json.loads(done.stdout)
    assert answer["authenticated"] is False and answer["reason"].startswith("account not available")
    assert [c["ARGS"] for c in calls(environ)] == ["auth token --hostname github.com --user alice"]
    view = forge("github", environ, "change-view", '{"id":"7"}', repo)
    assert "account not available" in view.stdout + view.stderr
    assert all(c["ARGS"].startswith("auth token") for c in calls(environ))


@needs_bash
def test_github_auth_status_without_an_account_is_unchanged(tmp_path):
    repo = make_repo(tmp_path, "https://github.com/acme/widget.git", account=None)
    environ = stub(tmp_path, "gh", GH_STUB)
    done = forge("github", environ, "auth-status", "{}", repo)
    assert done.returncode == 0, done.stderr
    answer = json.loads(done.stdout)
    assert answer["authenticated"] is True and answer["user"] == "bob"
    assert not any(c["ARGS"].startswith("auth token") for c in calls(environ))
    assert all(not c["GH_TOKEN"] and not c["GH_HOST"] for c in calls(environ))


# ---- the GitLab wrapper ---------------------------------------------------------

@needs_bash
def test_gitlab_calls_name_the_host_and_auth_status_checks_the_login(tmp_path):
    repo = make_repo(tmp_path, "https://gitlab.example.com/acme/widget.git")
    environ = stub(tmp_path, "glab", GLAB_STUB)
    for verb in ("change-view", "note-list", "change-comment"):
        forge("gitlab", environ, verb, '{"id":"7","text":"x"}', repo)
    work = calls(environ)
    assert work and all(c["GITLAB_HOST"] == "gitlab.example.com" for c in work)
    assert not any(" -R " in f' {c["ARGS"]} ' or "--repo" in c["ARGS"] for c in work)
    good = forge("gitlab", environ, "auth-status", "{}", repo)
    assert good.returncode == 0 and json.loads(good.stdout)["user"] == "alice"
    assert calls(environ)[-1]["ARGS"] == "api --hostname gitlab.example.com user"
    other = forge("gitlab", {**environ, "STUB_LOGIN": "carol"}, "auth-status", "{}", repo)
    answer = json.loads(other.stdout)
    assert other.returncode != 0
    assert answer["reason"].startswith("account not available") and "carol" in answer["reason"]


@needs_bash
def test_gitlab_without_an_account_sets_no_host(tmp_path):
    repo = make_repo(tmp_path, "https://gitlab.example.com/acme/widget.git", account=None)
    environ = stub(tmp_path, "glab", GLAB_STUB)
    done = forge("gitlab", environ, "auth-status", "{}", repo)
    assert done.returncode == 0 and json.loads(done.stdout)["user"] == "bob"
    assert all(not c["GITLAB_HOST"] for c in calls(environ))


# ---- branch protection and its cache ----------------------------------------------

def gh_hosts(tmp_path: Path, *hosts: str) -> dict:
    folder = tmp_path / "gh-config"
    folder.mkdir(exist_ok=True)
    (folder / "hosts.yml").write_text("".join(f"{h}:\n    user: bob\n" for h in hosts), encoding="utf-8")
    return {"GH_CONFIG_DIR": str(folder)}


@needs_bash
@pytest.mark.parametrize(("host", "variable"), [("github.com", "GH_TOKEN"),
                                                ("github.acme.test", "GH_ENTERPRISE_TOKEN")])
def test_branch_protection_reads_as_the_account(tmp_path, monkeypatch, host, variable):
    environ = {**stub(tmp_path, "gh", GH_STUB), **gh_hosts(tmp_path, "github.com", host)}
    for key, value in environ.items():
        monkeypatch.setenv(key, value)
    protection = _module("afk_branch_protection_t", PLUGIN_ROOT / "adapters" / "forge" / "branch_protection.py")
    answer = protection.protection("github", "feature-x", "acme/widget", str(tmp_path), 30.0, "", host, "alice")
    assert answer.get("protected") is False, answer
    seen = calls(environ)
    assert seen[0]["ARGS"] == f"auth token --hostname {host} --user alice"
    reads = [c for c in seen if c["ARGS"].startswith("api ")]
    assert reads and all(c[variable] == "fake-token-alice" and c["GH_HOST"] == host for c in reads)
    monkeypatch.setenv("STUB_NO_TOKEN", "1")
    missing = protection.protection("github", "feature-x", "acme/widget", str(tmp_path), 30.0, "", host, "alice")
    assert missing.get("error") and "account not available" in missing["reason"]


@needs_bash
def test_protection_cache_holds_one_entry_per_account(tmp_path):
    repo = make_repo(tmp_path, "https://github.com/acme/widget.git")
    (repo / ".git" / "refs" / "remotes" / "origin").mkdir(parents=True)
    (repo / ".git" / "refs" / "remotes" / "origin" / "HEAD").write_text(
        "ref: refs/remotes/origin/main\n", encoding="utf-8")
    environ = {**stub(tmp_path, "gh", GH_STUB), **gh_hosts(tmp_path, "github.com"),
               "AFK_GITHUB_API_URL": "http://127.0.0.1:9"}
    for account in ("alice", "bob"):
        set_account(repo, account)
        done = subprocess.run([sys.executable, str(LOOKUP), "--branch", "feature-x", "--checkout", str(repo)],
                              capture_output=True, text=True, timeout=120, env=environ)
        assert json.loads(done.stdout)["source"] == "github", done.stdout + done.stderr
    cache = json.loads((repo / ".git" / "afk" / "protection-cache.json").read_text(encoding="utf-8"))
    keys = [json.loads(key) for key in (cache.get("entries") or cache)]
    assert sorted(key[4] for key in keys) == ["alice", "bob"]


# ---- the GitHub Issues tracker --------------------------------------------------

def test_github_issues_acts_as_the_account(tmp_path, monkeypatch):
    repo = make_repo(tmp_path, "https://github.com/acme/widget.git")
    monkeypatch.chdir(repo)
    api = _module("afk_github_issues_t", PLUGIN_ROOT / "adapters" / "tracker" / "github-issues" / "api.py")
    real, seen = subprocess.run, []

    def fake(argv, *args, **kwargs):
        if argv[0] != "gh":
            return real(argv, *args, **kwargs)
        env = kwargs.get("env") or {}
        seen.append((argv[1:], {k: env.get(k) for k in TOKEN_VARIABLES if env.get(k)}))
        out = "fake-token-alice" if argv[1:3] == ["auth", "token"] and not os.environ.get("NO_TOKEN") else ""
        code = 1 if argv[1:3] == ["auth", "token"] and not out else 0
        return subprocess.CompletedProcess(argv, code, out or '{"number": 1}', "")

    monkeypatch.setattr(api.shutil, "which", lambda name: name)
    monkeypatch.setattr(api.subprocess, "run", fake)
    answer = api.call("tracker_get", {"ticket_key": "1"})
    assert answer.get("number") == 1, answer
    assert seen[0] == (["auth", "token", "--hostname", "github.com", "--user", "alice"], {})
    assert seen[1][0][:2] == ["issue", "view"]
    assert seen[1][1] == {"GH_TOKEN": "fake-token-alice", "GH_HOST": "github.com"}
    monkeypatch.setenv("NO_TOKEN", "1")
    seen.clear()
    refused = api.call("tracker_get", {"ticket_key": "1"})
    assert refused.get("error") and "account not available" in refused["reason"]
    assert [argv[:2] for argv, _ in seen] == [["auth", "token"]]


def test_the_plugin_issue_reporter_keeps_the_default_login():
    folder = PLUGIN_ROOT / "skills" / "utils" / "report-issue" / "scripts"
    text = "".join(path.read_text(encoding="utf-8") for path in folder.glob("*.sh"))
    assert "forge_account" not in text and "--user" not in text and "forge.sh" not in text
