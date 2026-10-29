"""Setup's forge account check: the host is asked once, and only an accepted account is saved.

The forge CLI is faked in process (`forge_account_check._run`); git runs for real
in temporary repositories, and HOME is a temporary folder. Tokens are fake strings.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = PLUGIN_ROOT / "skills" / "afk" / "setup" / "scripts"
TOKEN_VARIABLES = ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN", "GH_HOST")


def _module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    folder = tmp_path / "home"
    folder.mkdir()
    for name in ("HOME", "USERPROFILE"):
        monkeypatch.setenv(name, str(folder))
    for name in (*TOKEN_VARIABLES, "AFK_CONFIG", "CLAUDE_PROJECT_DIR"):
        monkeypatch.delenv(name, raising=False)
    return folder


@pytest.fixture
def fac():
    return _module("afk_forge_account_check_t", SCRIPTS / "forge_account_check.py")


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True,
                          check=True).stdout.strip()


def make_repo(tmp_path: Path, forge: str, remote: str, email: str = "alice@example.com") -> Path:
    repo = tmp_path / "repo"
    (repo / ".afk").mkdir(parents=True)
    (repo / ".afk" / "config.yaml").write_text(f"schema: 1\nforge: {forge}\n", encoding="utf-8")
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.email", email)
    git(repo, "remote", "add", "origin", remote)
    return repo


def noreply(user_id: str, login: str, host: str) -> str:
    """The no-reply commit address a host gives an account."""
    return f"{user_id}+{login}@users.noreply.{host}"


def saved(repo: Path) -> str | None:
    personal = repo / ".git" / "afk" / "config.yaml"
    if not personal.is_file():
        return None
    for line in personal.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("forgeAccount:"):
            return line.split(":", 1)[1].strip()
    return None


class FakeCli:
    """Answers forge CLI calls from a table; git calls run for real."""

    def __init__(self, answers: dict):
        self.answers, self.calls = answers, []

    def __call__(self, argv, timeout, env=None, cwd=None):
        if argv[0] == "git":
            done = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
            return done.returncode, done.stdout, done.stderr
        self.calls.append((argv, timeout, {k: (env or {}).get(k) for k in TOKEN_VARIABLES if (env or {}).get(k)}))
        answer = self.answers.get(" ".join(argv[1:3]))
        if isinstance(answer, Exception):
            raise answer
        return answer if answer is not None else (1, "", "unknown command")


def github(user: dict | None = None, token=(0, "fake-token-alice\n", "")) -> dict:
    record = {"login": "alice", "id": 7, "email": None} if user is None else user
    return {"auth token": token, "api user": (0, json.dumps(record), "")}


def use(monkeypatch, fac, cli: FakeCli) -> None:
    monkeypatch.setattr(fac, "_run", cli)
    monkeypatch.setattr(fac.shutil, "which", lambda name: name)


def test_an_accepted_github_account_is_saved(tmp_path, monkeypatch, fac):
    repo = make_repo(tmp_path, "github", "https://github.com/acme/widget.git",
                     email=noreply("7", "alice", "github.com"))
    cli = FakeCli(github())
    use(monkeypatch, fac, cli)
    answer = fac.check_forge_account(repo, "alice")
    assert answer["accepted"] is True and answer["warnings"] == []
    assert saved(repo) == "alice"
    (fetch, _, fetch_env), (ask, limit, ask_env) = cli.calls[:2]
    assert fetch == ["gh", "auth", "token", "--hostname", "github.com", "--user", "alice"] and fetch_env == {}
    assert ask == ["gh", "api", "user"] and 0 < limit <= 20
    assert ask_env == {"GH_TOKEN": "fake-token-alice", "GH_HOST": "github.com"}
    assert "fake-token" not in json.dumps(answer)


def test_an_enterprise_host_gets_the_enterprise_variable(tmp_path, monkeypatch, fac):
    repo = make_repo(tmp_path, "github", "https://github.acme.test/acme/widget.git")
    cli = FakeCli(github())
    use(monkeypatch, fac, cli)
    assert fac.check_forge_account(repo, "alice")["accepted"] is True
    assert cli.calls[1][2] == {"GH_ENTERPRISE_TOKEN": "fake-token-alice", "GH_HOST": "github.acme.test"}


@pytest.mark.parametrize(("answers", "cause"), [
    (github(token=(1, "", "no account")), "gh holds no sign-in for alice on github.com"),
    ({**github(), "api user": (1, "", "HTTP 401: Bad credentials")}, "github.com refused alice: HTTP 401"),
    (github(user={"login": "bob"}), "signs in as bob"),
])
def test_a_refused_account_saves_nothing(tmp_path, monkeypatch, fac, answers, cause):
    repo = make_repo(tmp_path, "github", "https://github.com/acme/widget.git")
    personal = repo / ".git" / "afk" / "config.yaml"
    personal.parent.mkdir(parents=True)
    personal.write_text("developer:\n  forgeAccount: earlier\n", encoding="utf-8")
    use(monkeypatch, fac, FakeCli(answers))
    answer = fac.check_forge_account(repo, "alice")
    assert answer["accepted"] is False and cause in answer["cause"]
    assert saved(repo) == "earlier"


def test_an_unreachable_host_is_asked_once_and_saves_nothing(tmp_path, monkeypatch, fac):
    repo = make_repo(tmp_path, "github", "https://github.com/acme/widget.git")
    cli = FakeCli({**github(), "api user": fac.Unreachable("timed out")})
    use(monkeypatch, fac, cli)
    answer = fac.check_forge_account(repo, "alice")
    assert answer["accepted"] is False and "did not answer within 20 s" in answer["cause"]
    assert [argv[1:3] for argv, _, _ in cli.calls].count(["api", "user"]) == 1
    assert saved(repo) is None
    assert fac.TIMEOUT == 20.0


def test_glab_asks_the_host_and_refuses_a_differing_login(tmp_path, monkeypatch, fac):
    repo = make_repo(tmp_path, "gitlab", "https://gitlab.example.com/acme/widget.git")
    cli = FakeCli({"api --hostname": (0, json.dumps({"username": "carol", "id": 3}), "")})
    use(monkeypatch, fac, cli)
    answer = fac.check_forge_account(repo, "alice")
    assert cli.calls[0][0] == ["glab", "api", "--hostname", "gitlab.example.com", "user"]
    assert answer["accepted"] is False and "carol" in answer["cause"]
    assert saved(repo) is None
    cli.answers["api --hostname"] = (0, json.dumps({"username": "alice", "id": 3,
                                                    "commit_email": "alice@example.com"}), "")
    good = fac.check_forge_account(repo, "alice")
    assert good["accepted"] is True and good["warnings"] == [] and saved(repo) == "alice"


def test_a_push_sign_in_or_commit_email_mismatch_warns_naming_both(tmp_path, monkeypatch, fac):
    repo = make_repo(tmp_path, "github", "https://bob@github.com/acme/widget.git", email="bob@corp.test")
    use(monkeypatch, fac, FakeCli(github()))
    answer = fac.check_forge_account(repo, "alice")
    assert answer["accepted"] is True
    push, email = answer["warnings"]
    assert "bob" in push and "alice" in push
    assert "bob@corp.test" in email and "alice" in email


def test_the_command_line_exit_codes(tmp_path, monkeypatch, fac, capsys):
    repo = make_repo(tmp_path, "github", "https://github.com/acme/widget.git")
    cli = FakeCli(github(token=(1, "", "")))
    use(monkeypatch, fac, cli)
    assert fac.main(["--account", "alice", "--repo", str(repo)]) == 1
    assert json.loads(capsys.readouterr().out)["accepted"] is False
    cli.answers.update(github())
    assert fac.main(["--account", "alice", "--repo", str(repo)]) == 0
    assert json.loads(capsys.readouterr().out)["accepted"] is True
    assert fac.main(["--account", "alice", "--repo", str(tmp_path / "nowhere")]) == 2


def test_developer_values_set_only_removes_a_forge_account(tmp_path):
    dv = _module("afk_developer_values_t", SCRIPTS / "developer_values.py")
    repo = make_repo(tmp_path, "github", "https://github.com/acme/widget.git")
    with pytest.raises(ValueError, match="forge_account_check"):
        dv.record(repo, ["forgeAccount=alice"], machine=False)
    dv.save_forge_account(repo, "alice")
    assert saved(repo) == "alice"
    report = dv.status(repo)
    assert report["keys"]["mrAssignee"].get("suggestion") == "alice"
    dv.record(repo, ["forgeAccount="], machine=False)
    assert saved(repo) is None
