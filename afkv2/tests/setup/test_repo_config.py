import re

import pytest

import repo_config

V1 = (b"# v1 config\nschema: 1\ntracker: jira\nforge: github\nnotes: repo-files\n"
      b"jira:\n  project: PROJ\n  site: 'x'\ngithub:\n  remote: origin\n"
      b"git:\n  base-branch: origin/main\nrepo-files:\n  spec-dir: 'docs/{workId}'\n"
      b"build-gates:\n  - maven\n")


def _v1(repo):
    path = repo / ".afk" / "config.yaml"
    path.parent.mkdir()
    path.write_bytes(V1)
    return path


def test_copy_once_and_v1_file_byte_identical(repo):
    v1 = _v1(repo)
    plan = repo_config.copy_plan(repo)
    assert plan["keys"] == ["tracker", "forge", "notes", "jira", "github", "repo-files", "git"]
    answer = repo_config.copy_v1_config(repo)
    assert answer["action"] == "copied"
    assert v1.read_bytes() == V1
    body = repo_config.afkv2_config(repo).read_bytes()
    assert b"jira:\n  project: PROJ\n  site: 'x'\n" in body
    assert b"build-gates" not in body and b"schema" not in body
    assert repo_config.copy_v1_config(repo)["action"] == "exists"
    assert repo_config.copy_plan(repo)["done"]


def test_no_v1_config(repo):
    assert repo_config.copy_v1_config(repo) == {"ok": True, "action": "no-v1-config"}


def test_ownership_asked_once_then_set(repo, places):
    assert repo_config.ownership_state(repo, places) == "missing"
    answer = repo_config.write_ownership(repo, places, ["src/**"], ["lib/it's/**"])
    assert answer["ok"]
    text = repo_config.afkv2_config(repo).read_text()
    assert "ownership:\n  own:\n    - 'src/**'\n  shared:\n    - 'lib/it''s/**'\n" in text
    assert repo_config.ownership_state(repo, places) == "set"
    assert repo_config.write_ownership(repo, places, ["x"], [])["error"]["code"] == "ownership-set"


def test_ownership_after_a_copy_keeps_the_copy(repo, places):
    _v1(repo)
    repo_config.copy_v1_config(repo)
    repo_config.write_ownership(repo, places, ["a/**"], [])
    text = repo_config.afkv2_config(repo).read_text()
    assert "tracker: jira" in text and text.endswith("ownership:\n  own:\n    - 'a/**'\n")


def test_skip_is_recorded_once(repo, places):
    assert repo_config.record_ownership_skip(repo, places)["action"] == "skipped"
    assert repo_config.ownership_state(repo, places) == "skipped"
    assert repo_config.record_ownership_skip(repo, places)["action"] == "unchanged"
    assert places.ownership_skips.read_text().count("\n") == 1


def test_a_crlf_config_is_copied_byte_for_byte(repo):
    crlf = V1.replace(b"\n", b"\r\n")
    path = repo / ".afk" / "config.yaml"
    path.parent.mkdir()
    path.write_bytes(crlf)
    repo_config.copy_v1_config(repo)
    body = repo_config.afkv2_config(repo).read_bytes()
    assert b"jira:\r\n  project: PROJ\r\n  site: 'x'\r\n" in body
    assert b"git:\r\n  base-branch: origin/main\r\n" in body
    assert not re.search(rb"(?<!\r)\n", body)


@pytest.mark.parametrize("line", [b"tracker: jira  # the tracker", b"tracker: 'jira' # the tracker",
                                  b'tracker: "jira"'])
def test_a_kind_key_comment_or_quote_still_brings_its_section(repo, line):
    path = repo / ".afk" / "config.yaml"
    path.parent.mkdir()
    path.write_bytes(line + b"\njira:\n  project: PROJ\n")
    assert repo_config.copy_plan(repo)["keys"] == ["tracker", "jira"]


def test_an_unindented_list_stays_in_its_block(repo):
    path = repo / ".afk" / "config.yaml"
    path.parent.mkdir()
    path.write_bytes(b"tracker: jira\njira:\n  project: P\ngit:\n- one\n- two\n")
    repo_config.copy_v1_config(repo)
    assert b"git:\n- one\n- two\n" in repo_config.afkv2_config(repo).read_bytes()


def test_ownership_after_a_crlf_copy_stays_crlf(repo, places):
    (repo / ".afk").mkdir()
    (repo / ".afk" / "config.yaml").write_bytes(V1.replace(b"\n", b"\r\n"))
    repo_config.copy_v1_config(repo)
    repo_config.write_ownership(repo, places, ["a/**"], [])
    body = repo_config.afkv2_config(repo).read_bytes()
    assert body.endswith(b"ownership:\r\n  own:\r\n    - 'a/**'\r\n")
    assert b"\n" not in body.replace(b"\r\n", b"")
    assert repo_config.ownership_state(repo, places) == "set"
