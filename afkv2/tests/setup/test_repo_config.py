import json

import pytest

import recorded_config_reader as reader
import repo_config

V1 = (b"# v1 config\nschema: 1\ntracker: jira\nforge: github\nnotes: repo-files\n"
      b"jira:\n  project: PROJ\n  site: 'x'\n  issue-types:\n    bug: Bug\ngithub:\n  remote: origin\n"
      b"git:\n  base-branch: origin/main\nrepo-files:\n  spec-dir: 'docs/specs/{workId}'\n"
      b"build-gates:\n  - maven\n")


def _v1(repo, text=V1):
    path = repo.joinpath(*repo_config.setup_v1_facts.CONFIG_PATH)
    path.parent.mkdir()
    path.write_bytes(text)
    return path


def _written(repo):
    return json.loads(repo_config.afkv2_config(repo).read_text(encoding="utf-8"))


def test_the_config_file_name_is_the_frozen_one(repo):
    assert repo_config.afkv2_config(repo) == repo / ".afkv2" / "config.json"


def test_copy_once_and_v1_file_byte_identical(repo):
    v1 = _v1(repo)
    assert repo_config.copy_plan(repo)["keys"] == ["spec_folder", "tracker", "forge"]
    answer = repo_config.write_config(repo)
    assert answer["action"] == "copied" and answer["spec_folder_source"] == "v1"
    assert v1.read_bytes() == V1
    assert _written(repo) == {"spec_folder": "docs/specs", "forge": "github",
                              "tracker": {"kind": "jira", "project": "PROJ", "site": "x"}}
    assert repo_config.write_config(repo)["action"] == "exists"
    assert repo_config.copy_plan(repo)["done"]


def test_the_copy_passes_the_config_reader_rules(repo):
    _v1(repo)
    repo_config.write_config(repo)
    answer = reader.read_config(repo_config.afkv2_config(repo))
    assert answer["spec_folder"] == str(repo / "docs/specs")
    assert answer["tracker"]["kind"] == "jira"


def test_the_config_and_ownership_pass_the_reader_rules_as_lf_json(repo, places):
    repo_config.write_config(repo, "specs")
    repo_config.write_ownership(repo, places, ["src/**"], ["lib/it's/**"])
    target = repo_config.afkv2_config(repo)
    assert reader.read_config(target)["ownership"] == {"own": ["src/**"], "shared": ["lib/it's/**"]}
    assert b"\r" not in target.read_bytes()


@pytest.mark.parametrize("kind", [b"none", b"linear"])
def test_a_tracker_the_reader_refuses_is_left_out(repo, kind):
    _v1(repo, b"tracker: " + kind + b"\nrepo-files:\n  spec-dir: docs\n")
    repo_config.write_config(repo)
    assert "tracker" not in _written(repo)
    assert reader.read_config(repo_config.afkv2_config(repo))["tracker"] is None


@pytest.mark.parametrize("template,value", [
    ("docs/afkv2/{workId}", "docs/afkv2"), ("docs/afkv2/{workId}/", "docs/afkv2"), ("specs", "specs"),
    ("docs\\afkv2\\{workId}", "docs/afkv2")])
def test_the_v1_template_gives_the_parent_of_the_ticket_folders(repo, template, value):
    _v1(repo, b"repo-files:\n  spec-dir: " + template.encode() + b"  # the template\n")
    assert repo_config.spec_folder_state(repo) == {"value": value, "source": "v1"}


def test_a_crlf_v1_config_gives_the_same_values(repo):
    _v1(repo, V1.replace(b"\n", b"\r\n"))
    repo_config.write_config(repo)
    assert _written(repo)["spec_folder"] == "docs/specs"
    assert _written(repo)["tracker"]["project"] == "PROJ"


def test_no_v1_value_and_no_answer_refuses_and_writes_nothing(repo, places):
    answer = repo_config.write_config(repo)
    assert answer["ok"] is False and answer["error"]["code"] == "no-spec-folder"
    owned = repo_config.write_ownership(repo, places, ["a/**"], [])
    assert owned["ok"] is False and owned["error"]["code"] == "no-spec-folder"
    assert not (repo / ".afkv2").exists()


def test_a_v1_config_with_no_spec_dir_needs_the_developers_answer(repo):
    _v1(repo, b"tracker: jira\n")
    assert repo_config.write_config(repo)["error"]["code"] == "no-spec-folder"
    assert not (repo / ".afkv2").exists()
    answer = repo_config.write_config(repo, "specs")
    assert answer["spec_folder_source"] == "developer" and answer["keys"] == ["spec_folder", "tracker"]
    assert _written(repo) == {"tracker": {"kind": "jira"}, "spec_folder": "specs"}


@pytest.mark.parametrize("template", ["{workId}", "docs/{team}/{workId}", "docs/{workId}/specs", "../out", "/abs", "C:/abs"])
def test_a_v1_value_the_reader_refuses_is_not_copied(repo, template):
    _v1(repo, b"repo-files:\n  spec-dir: '" + template.encode() + b"'\n")
    assert "spec_folder" not in repo_config.copy_plan(repo)["keys"]
    answer = repo_config.write_config(repo)
    assert answer["error"]["code"] == "no-spec-folder" and not (repo / ".afkv2").exists()
    assert repo_config.write_config(repo, "specs")["spec_folder"] == "specs"


def test_the_v1_value_wins_over_the_answer_and_the_answer_says_so(repo):
    _v1(repo)
    answer = repo_config.write_config(repo, "other")
    assert answer["spec_folder"] == "docs/specs" and answer["spec_folder_source"] == "v1"


@pytest.mark.parametrize("given", ["", "   ", "../out", "/abs", "C:/abs", "a/../../b", "a/{workId}"])
def test_a_bad_answer_refuses_and_writes_nothing(repo, given):
    answer = repo_config.write_config(repo, given)
    assert answer["error"]["code"] == "bad-spec-folder" and not (repo / ".afkv2").exists()


def test_a_backslash_answer_stays_a_relative_path_on_each_system(repo):
    assert repo_config.write_config(repo, "docs\\specs")["spec_folder"] == "docs/specs"


def test_declining_the_copy_writes_only_the_spec_folder(repo):
    _v1(repo)
    answer = repo_config.write_config(repo, with_v1=False)
    assert answer["action"] == "written" and _written(repo) == {"spec_folder": "docs/specs"}


def test_an_existing_config_keeps_its_values(repo):
    target = repo_config.afkv2_config(repo)
    target.parent.mkdir()
    target.write_text(json.dumps({"spec_folder": "mine", "extra": 1}), encoding="utf-8")
    assert repo_config.spec_folder_state(repo) == {"value": "mine", "source": "config"}
    assert repo_config.write_config(repo, "other")["action"] == "exists"
    assert _written(repo) == {"spec_folder": "mine", "extra": 1}


def test_a_config_with_no_spec_folder_gets_one_and_keeps_the_rest(repo):
    target = repo_config.afkv2_config(repo)
    target.parent.mkdir()
    target.write_text(json.dumps({"ownership": {"own": ["a"]}}), encoding="utf-8")
    repo_config.write_config(repo, "specs")
    assert _written(repo) == {"ownership": {"own": ["a"]}, "spec_folder": "specs"}


def test_a_config_that_is_not_one_object_stops_the_verb(repo):
    target = repo_config.afkv2_config(repo)
    target.parent.mkdir()
    target.write_text("[1]", encoding="utf-8")
    with pytest.raises(ValueError):
        repo_config.write_config(repo, "specs")
    assert target.read_text(encoding="utf-8") == "[1]"


def test_ownership_asked_once_then_set(repo, places):
    repo_config.write_config(repo, "specs")
    assert repo_config.ownership_state(repo, places) == "missing"
    assert repo_config.write_ownership(repo, places, ["src/**"], [])["ok"]
    assert _written(repo)["ownership"] == {"own": ["src/**"]}
    assert repo_config.ownership_state(repo, places) == "set"
    assert repo_config.write_ownership(repo, places, ["x"], [])["error"]["code"] == "ownership-set"


def test_ownership_with_no_config_takes_the_v1_spec_folder(repo, places):
    _v1(repo)
    assert repo_config.write_ownership(repo, places, ["a/**"], [])["ok"]
    assert _written(repo) == {"spec_folder": "docs/specs", "ownership": {"own": ["a/**"]}}


def test_ownership_after_a_copy_keeps_the_copy(repo, places):
    _v1(repo)
    repo_config.write_config(repo)
    repo_config.write_ownership(repo, places, ["a/**"], [])
    assert _written(repo)["tracker"]["kind"] == "jira" and _written(repo)["ownership"] == {"own": ["a/**"]}


@pytest.mark.parametrize("own,shared", [([], []), ([""], []), (["a"], ["  "])])
def test_ownership_refuses_what_the_reader_refuses(repo, places, own, shared):
    repo_config.write_config(repo, "specs")
    assert not repo_config.write_ownership(repo, places, own, shared)["ok"]
    assert "ownership" not in _written(repo)


def test_skip_is_recorded_once_and_writes_no_config(repo, places):
    assert repo_config.record_ownership_skip(repo, places)["action"] == "skipped"
    assert repo_config.ownership_state(repo, places) == "skipped"
    assert repo_config.record_ownership_skip(repo, places)["action"] == "unchanged"
    assert places.ownership_skips.read_text().count("\n") == 1
    assert not (repo / ".afkv2").exists()


@pytest.mark.parametrize("line", [b"tracker: jira  # the tracker", b"tracker: 'jira' # the tracker",
                                  b'tracker: "jira"'])
def test_a_kind_key_comment_or_quote_still_brings_its_section(repo, line):
    _v1(repo, line + b"\njira:\n  project: PROJ\n")
    repo_config.write_config(repo, "specs")
    assert _written(repo)["tracker"] == {"kind": "jira", "project": "PROJ"}


def test_a_section_value_named_kind_cannot_change_the_kind(repo):
    _v1(repo, b"tracker: jira\njira:\n  kind: other\n")
    repo_config.write_config(repo, "specs")
    assert _written(repo)["tracker"]["kind"] == "jira"
