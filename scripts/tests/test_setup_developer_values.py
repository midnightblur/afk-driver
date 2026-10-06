"""`developer_values.py` reports and records developer values without changing another repository's.

Drives `status` and `set` against real git repositories that share one machine
file, the way an agent runs them after asking the human in session.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "skills" / "afk" / "setup" / "scripts" / "developer_values.py"
sys.path.insert(0, str(SCRIPT.parent))
import developer_values as dv  # noqa: E402


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    h = tmp_path / "home"
    h.mkdir()
    for name in ("HOME", "USERPROFILE"):
        monkeypatch.setenv(name, str(h))
    monkeypatch.delenv("AFK_CONFIG", raising=False)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.delenv("CLAUDECODE", raising=False)
    return h


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


def make_repo(tmp_path, name, forge="none", tracker="none"):
    repo = tmp_path / name
    (repo / ".afk").mkdir(parents=True)
    (repo / ".afk" / "config.yaml").write_text(
        f"schema: 1\ntracker: {tracker}\nforge: {forge}\n", encoding="utf-8")
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.email", "t@example.com")
    git(repo, "config", "user.name", "T")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "init")
    return repo


def cli(cwd, *args):
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
    return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=str(cwd), env=env,
                          capture_output=True, text=True, timeout=120)


def test_a_repository_without_a_forge_keeps_the_machine_reviewer(tmp_path, home):
    a = make_repo(tmp_path, "a", forge="github")
    assert cli(a, "set", "mrReviewer=rev", "mrAssignee=me", "--machine").returncode == 0
    machine = home / ".afk" / "config.yaml"
    before = machine.read_text(encoding="utf-8")

    b = make_repo(tmp_path, "b")
    report = json.loads(cli(b, "status").stdout)
    assert report["keys"]["mrReviewer"]["need"] == "n/a"
    assert "mrReviewer" not in report["missing"]
    assert cli(b, "set", "ideBinary=/opt/ide").returncode == 0
    assert machine.read_text(encoding="utf-8") == before
    assert json.loads(cli(a, "status").stdout)["keys"]["mrReviewer"]["value"] == "rev"


def test_status_names_what_is_missing_and_where_a_value_comes_from(tmp_path, home):
    repo = make_repo(tmp_path, "a", forge="gitlab")
    report = json.loads(cli(repo, "status").stdout)
    assert report["missing"] == ["mrReviewer"]
    assert report["keys"]["mrReviewer"]["suggestion"] is None
    assert report["keys"]["worktreeBasePath"]["source"] == "derived"

    dv.write_block(home / ".afk" / "config.yaml", {"mrReviewer": "rev"})
    report = json.loads(cli(repo, "status").stdout)
    assert report["missing"] == []
    assert report["keys"]["mrReviewer"]["source"] == "machine"


def test_a_value_recorded_in_a_worktree_is_read_by_the_main_checkout(tmp_path):
    main = make_repo(tmp_path, "a", forge="github")
    linked = tmp_path / "a-worktrees" / "task"
    git(main, "worktree", "add", "-q", str(linked))
    assert cli(linked, "set", "mrReviewer=rev").returncode == 0
    for checkout in (main, linked):
        keys = json.loads(cli(checkout, "status").stdout)["keys"]
        assert keys["mrReviewer"] == {"need": "required", "value": "rev", "source": "repository"}
    assert (main / ".git" / "afk" / "config.yaml").is_file()


def test_none_assignee_overrides_the_machine_assignee(tmp_path, home):
    repo = make_repo(tmp_path, "a", forge="github")
    dv.write_block(home / ".afk" / "config.yaml", {"mrAssignee": "me"})
    assert cli(repo, "set", "mrAssignee=none").returncode == 0
    assert json.loads(cli(repo, "status").stdout)["keys"]["mrAssignee"]["value"] is None


def test_a_worktree_location_is_refused_for_the_machine_file(tmp_path, home):
    repo = make_repo(tmp_path, "a")
    out = cli(repo, "set", "worktreeBasePath=/somewhere", "--machine")
    assert out.returncode == 2 and "worktreeBasePath" in out.stderr
    assert not (home / ".afk" / "config.yaml").exists()


def test_machine_values_are_reported_as_inherited(tmp_path, home):
    repo = make_repo(tmp_path, "a", forge="github")
    dv.write_block(home / ".afk" / "config.yaml",
                   {"mrReviewer": "rev", "worktreeBasePath": "/elsewhere"})
    report = json.loads(cli(repo, "status").stdout)
    assert report["inherited"] == ["mrReviewer", "worktreeBasePath"]
    assert report["keys"]["worktreeBasePath"]["derived"].endswith("/a-worktrees")

    assert cli(repo, "set", "worktreeBasePath=", "--machine").returncode == 0
    report = json.loads(cli(repo, "status").stdout)
    assert report["inherited"] == ["mrReviewer"]
    assert report["keys"]["worktreeBasePath"]["source"] == "derived"


def test_an_empty_value_removes_only_that_key(tmp_path):
    repo = make_repo(tmp_path, "a", forge="github")
    cli(repo, "set", "mrReviewer=rev", "mrAssignee=me")
    assert cli(repo, "set", "mrAssignee=").returncode == 0
    assert dv.read_block(repo / ".git" / "afk" / "config.yaml") == {"mrReviewer": "rev"}


def test_an_unknown_key_is_refused(tmp_path):
    out = cli(make_repo(tmp_path, "a"), "set", "reviewer=rev")
    assert out.returncode == 2 and "KEY=VALUE" in out.stderr


def test_the_key_order_covers_the_readers_key_set():
    assert set(dv.ORDER) == dv.ac.DEVELOPER_KEYS


def test_other_lines_of_the_file_survive_a_write(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("tracker: jira\n# note\ndeveloper:\n  mrReviewer: old\nforge: gitlab\n",
                    encoding="utf-8")
    dv.write_block(path, {"mrReviewer": "new"})
    text = path.read_text(encoding="utf-8")
    assert "tracker: jira" in text and "# note" in text and "forge: gitlab" in text
    assert dv.read_block(path) == {"mrReviewer": "new"}


@pytest.mark.parametrize("value", ["123", "true", "null", "1.5", "a: b", 'say "hi"',
                                   r"C:\Program Files\idea64.exe", "plain.name"])
def test_a_written_value_reads_back_as_the_same_string(tmp_path, value):
    path = tmp_path / "config.yaml"
    dv.write_block(path, {"mrReviewer": value})
    assert dv.read_block(path) == {"mrReviewer": value}
    config = dv.ac.parse(path.read_text(encoding="utf-8"), str(path))
    assert dv.ac.developer_value(config, "mrReviewer") == value
    assert not dv.ac.validate({"schema": 1, **config})
