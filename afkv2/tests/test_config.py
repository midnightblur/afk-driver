import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import afkv2_config  # noqa: E402

READER = SCRIPTS / "afkv2_config.py"


def make_repo(tmp_path, config):
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    if config is not None:
        (repo / ".afkv2").mkdir()
        body = config if isinstance(config, str) else json.dumps(config)
        (repo / ".afkv2" / "config.json").write_text(body, encoding="utf-8")
    return repo


@pytest.fixture(autouse=True)
def local_app_data(tmp_path, monkeypatch):
    folder = tmp_path / "localappdata"
    monkeypatch.setenv("LOCALAPPDATA", str(folder))
    return folder


FULL = {
    "spec_folder": "docs/specs",
    "tracker": {"kind": "jira", "project": "ABC"},
    "ownership": {"own": ["src/**"], "shared": ["lib/**"]},
}


def test_resolves_spec_folder_tracker_ownership_and_data_folder(tmp_path, local_app_data):
    repo = make_repo(tmp_path, FULL)
    answer = afkv2_config.read_config(repo)
    assert answer == {
        "ok": True,
        "repo_root": str(repo),
        "config_file": str(repo / ".afkv2" / "config.json"),
        "spec_folder": str(repo / "docs" / "specs"),
        "tracker": {"kind": "jira", "project": "ABC"},
        "ownership": {"own": ["src/**"], "shared": ["lib/**"]},
        "data_folder": str(local_app_data / "afkv2"),
    }


def test_finds_the_config_from_a_subfolder(tmp_path):
    repo = make_repo(tmp_path, FULL)
    deep = repo / "a" / "b"
    deep.mkdir(parents=True)
    assert afkv2_config.read_config(deep)["repo_root"] == str(repo)


def test_stops_at_the_repository_root(tmp_path):
    outer = make_repo(tmp_path, FULL)
    inner = outer / "nested"
    (inner / ".git").mkdir(parents=True)
    answer = afkv2_config.read_config(inner)
    assert answer["ok"] is False
    assert answer["error"]["code"] == "no-config"


def test_missing_ownership_and_tracker_answer_null(tmp_path):
    repo = make_repo(tmp_path, {"spec_folder": "docs"})
    answer = afkv2_config.read_config(repo)
    assert answer["ok"] is True
    assert answer["ownership"] is None
    assert answer["tracker"] is None


@pytest.mark.parametrize(
    "config, field",
    [
        ({}, "spec_folder"),
        ({"spec_folder": ""}, "spec_folder"),
        ({"spec_folder": 3}, "spec_folder"),
        ({"spec_folder": "../outside"}, "spec_folder"),
        ({"spec_folder": "/abs"}, "spec_folder"),
        pytest.param(
            {"spec_folder": "C:/abs"},
            "spec_folder",
            marks=pytest.mark.skipif(sys.platform != "win32", reason="a drive letter is absolute only on Windows"),
        ),
        ({"spec_folder": "docs", "tracker": {"kind": "trello"}}, "tracker.kind"),
        ({"spec_folder": "docs", "tracker": "jira"}, "tracker"),
        ({"spec_folder": "docs", "ownership": {"mine": ["x"]}}, "ownership.mine"),
        ({"spec_folder": "docs", "ownership": {"own": "src/**"}}, "ownership.own"),
        ({"spec_folder": "docs", "ownership": {"own": [""]}}, "ownership.own"),
        ([], "config"),
    ],
)
def test_bad_values_are_refused_and_named(tmp_path, config, field):
    repo = make_repo(tmp_path, config)
    answer = afkv2_config.read_config(repo)
    assert answer["ok"] is False
    assert answer["error"]["code"] == "bad-value"
    assert field in answer["error"]["reason"]


def test_unparseable_config_is_unreadable(tmp_path):
    repo = make_repo(tmp_path, "{not json")
    answer = afkv2_config.read_config(repo)
    assert answer["error"]["code"] == "unreadable"


def test_missing_local_app_data_is_unreadable(tmp_path, monkeypatch):
    repo = make_repo(tmp_path, FULL)
    monkeypatch.delenv("LOCALAPPDATA")
    answer = afkv2_config.read_config(repo)
    assert answer["error"]["code"] == "no-data-folder"


def run_reader(*args, cwd):
    done = subprocess.run(
        [sys.executable, str(READER), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
    )
    return done.returncode, json.loads(done.stdout)


def test_read_command_answers_one_json_object_exit_0(tmp_path):
    repo = make_repo(tmp_path, FULL)
    code, answer = run_reader("read", cwd=repo)
    assert code == 0
    assert answer["ok"] is True
    assert answer["spec_folder"] == str(repo / "docs" / "specs")


def test_read_command_exit_1_on_refusal(tmp_path):
    repo = make_repo(tmp_path, {"spec_folder": "../x"})
    code, answer = run_reader("read", cwd=repo)
    assert code == 1
    assert answer == {"ok": False, "error": {"code": "bad-value", "reason": answer["error"]["reason"]}}


def test_read_command_exit_1_with_no_config(tmp_path):
    repo = make_repo(tmp_path, None)
    code, answer = run_reader("read", cwd=repo)
    assert code == 1
    assert answer["error"]["code"] == "no-config"


def test_read_command_exit_2_on_unreadable_input(tmp_path):
    repo = make_repo(tmp_path, "{not json")
    code, answer = run_reader("read", cwd=repo)
    assert code == 2
    assert answer["error"]["code"] == "unreadable"


def test_read_command_takes_a_start_folder(tmp_path):
    repo = make_repo(tmp_path, FULL)
    code, answer = run_reader("read", "--start", str(repo), cwd=tmp_path)
    assert code == 0
    assert answer["repo_root"] == str(repo)


@pytest.mark.parametrize("args", [("write",), ("--help",), ("read", "-h"), ()])
def test_every_usage_error_answers_json_with_exit_2(tmp_path, args):
    code, answer = run_reader(*args, cwd=tmp_path)
    assert code == 2
    assert answer["ok"] is False
    assert set(answer["error"]) == {"code", "reason"}
    assert answer["error"]["code"] == "usage"
    assert isinstance(answer["error"]["reason"], str) and answer["error"]["reason"]
