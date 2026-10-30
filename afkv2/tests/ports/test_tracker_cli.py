"""The tracker command: one object, exit 0/1/2, the verb set, the kind from the config reader."""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap

import pytest

from port_fakes import PORTS, FakeResp
from tracker import cli, jira, settings

CLI = PORTS / "tracker" / "cli.py"


def run(*argv, stdin=""):
    return subprocess.run([sys.executable, str(CLI), *argv], input=stdin, capture_output=True,
                          text=True, encoding="utf-8", timeout=120)


def call(capsys, *argv):
    code = cli.tracker_main(list(argv))
    return code, json.loads(capsys.readouterr().out)


@pytest.fixture
def reader(tmp_path, monkeypatch):
    """A recorded fake of the config reader: `read` answers one object."""
    def install(answer):
        stub = tmp_path / "reader_fake.py"
        stub.write_text(textwrap.dedent(f"""
            import json, sys
            print(json.dumps({answer!r}))
            sys.exit(0 if {answer!r}["ok"] else 1)
        """), encoding="utf-8")
        monkeypatch.setattr(settings, "READER", stub)
    return install


def test_the_verb_set_is_exactly_the_contract():
    assert set(cli.VERBS) == {"issue-get", "issue-search", "md-to-adf", "attachment-list",
                              "attachment-put", "attachment-delete", "description-put"}


@pytest.mark.parametrize("verb", ["create", "transition", "comment", "tracker_create", "tracker_transition",
                                  "tracker_comment", "issue-create", "issue-transition", "issue-comment"])
def test_there_is_no_create_transition_or_comment_verb(capsys, verb):
    code, answer = call(capsys, verb, "{}")
    assert code == 2 and answer["error"]["code"] == "unknown-verb"


def test_no_write_function_for_create_transition_or_comment_exists():
    for name in ("add_comment", "issue_create", "issue_transition", "issue_comment", "_op_create", "_op_comment", "_op_transition"):
        assert not hasattr(jira, name) and not hasattr(jira.Jira, name)


@pytest.mark.parametrize("payload", ["{bad", "[1, 2]"])
def test_a_payload_that_is_not_one_object_exits_2(payload):
    done = run("md-to-adf", payload)
    assert done.returncode == 2 and "Traceback" not in done.stderr
    assert json.loads(done.stdout)["error"]["code"] == "bad-payload"


def test_no_verb_exits_2():
    done = run(stdin="")
    assert done.returncode == 2 and json.loads(done.stdout)["ok"] is False


def test_md_to_adf_runs_as_a_real_command_with_stdin_payload():
    done = run("md-to-adf", stdin=json.dumps({"markdown": "# Hello é"}))
    answer = json.loads(done.stdout)
    assert done.returncode == 0 and answer["ok"] is True
    assert answer["content"][0]["content"][0]["text"] == "Hello é"
    assert answer["figure_token"] == "AFKV2FIGURE{}ENDFIGURE"


def test_md_to_adf_substitutes_figures(capsys):
    figure = [{"type": "mediaSingle", "content": []}]
    code, answer = call(capsys, "md-to-adf", json.dumps({
        "markdown": "AFKV2FIGURE1ENDFIGURE", "figures": {"1": figure}}))
    assert code == 0 and answer["content"] == figure and answer["block_text"] == ""


def test_md_to_adf_answers_the_text_the_receipt_covers(capsys):
    code, answer = call(capsys, "md-to-adf", json.dumps({"markdown": "# A\n\nb\n\nAFKV2FIGURE1ENDFIGURE"}))
    assert code == 0 and answer["block_text"] == "A\nb"


def test_the_preview_text_equals_the_text_of_the_later_call_with_figures(capsys):
    markdown = "# A\n\nb\n\nAFKV2FIGURE1ENDFIGURE\n\nc"
    figure = [{"type": "mediaSingle", "content": []}]
    _, preview = call(capsys, "md-to-adf", json.dumps({"markdown": markdown}))
    _, write = call(capsys, "md-to-adf", json.dumps({"markdown": markdown, "figures": {"1": figure}}))
    assert preview["block_text"] == write["block_text"] == "A\nb\nc"
    assert figure[0] in write["content"] and figure[0] not in preview["content"]


def test_a_tracker_kind_that_is_no_word_is_bad_payload(capsys):
    code, answer = call(capsys, "issue-get", json.dumps({"key": "x", "tracker": {"kind": "jira"}}))
    assert code == 2 and answer["error"]["code"] == "bad-payload"


def test_md_to_adf_needs_markdown(capsys):
    code, answer = call(capsys, "md-to-adf", "{}")
    assert code == 2 and answer["error"]["code"] == "bad-payload"


def test_a_refusal_exits_1_and_never_shows_the_token(capsys, monkeypatch):
    monkeypatch.delenv("JIRA_BASE_URL", raising=False)
    monkeypatch.delenv("JIRA_EMAIL", raising=False)
    monkeypatch.setenv("JIRA_API_TOKEN", "tok-secret")
    monkeypatch.setattr(jira.Path, "home", lambda: PORTS / "no-such-home")
    code, answer = call(capsys, "attachment-list", '{"key":"PROJ-1"}')
    assert code == 1 and answer["error"]["code"] == "no-credentials"
    assert "tok-secret" not in json.dumps(answer)


def test_issue_get_goes_to_jira_when_the_config_says_jira(capsys, reader, fake_jira):
    reader({"ok": True, "tracker": {"kind": "jira"}})
    fake_jira({("GET", "/rest/api/3/issue/PROJ-1"): FakeResp({"key": "PROJ-1", "fields": {}})})
    code, answer = call(capsys, "issue-get", '{"key":"PROJ-1"}')
    assert code == 0 and answer["key"] == "PROJ-1" and "description_hash" in answer


def test_issue_get_goes_to_github_when_the_config_says_github(capsys, reader, tools):
    reader({"ok": True, "tracker": {"kind": "github-issues", "repo": "o/r"}})
    tools.on("gh", "issue", "view", answer={"number": 7})
    code, answer = call(capsys, "issue-get", '{"key":"7"}')
    assert code == 0 and answer["number"] == 7
    assert ["--repo", "o/r"] == tools.calls[0][1][3:5]


def test_the_payload_repo_wins_over_the_config_repo(capsys, reader, tools):
    reader({"ok": True, "tracker": {"kind": "github-issues", "repo": "o/r"}})
    tools.on("gh", "issue", "view", answer={"number": 7})
    call(capsys, "issue-get", '{"key":"7","repo":"x/y"}')
    assert ["--repo", "x/y"] == tools.calls[0][1][3:5]


def test_the_payload_tracker_wins_over_the_config(capsys, reader, tools):
    reader({"ok": True, "tracker": {"kind": "jira"}})
    tools.on("gh", "issue", "view", answer={"number": 7})
    code, answer = call(capsys, "issue-get", '{"key":"7","tracker":"github-issues"}')
    assert code == 0 and answer["number"] == 7


def test_issue_search_on_jira_is_unsupported(capsys, reader):
    reader({"ok": True, "tracker": {"kind": "jira"}})
    code, answer = call(capsys, "issue-search", "{}")
    assert code == 1 and answer["error"]["code"] == "unsupported"


@pytest.mark.parametrize("config", [
    {"ok": True, "tracker": None},
    {"ok": False, "error": {"code": "no-config", "reason": "no file"}},
])
def test_no_kind_is_a_named_refusal(capsys, reader, config):
    reader(config)
    code, answer = call(capsys, "issue-get", '{"key":"7"}')
    assert code == 1 and answer["error"]["code"] == "no-tracker"


def test_an_absent_reader_is_a_named_refusal(capsys, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "READER", tmp_path / "absent.py")
    code, answer = call(capsys, "issue-get", '{"key":"7"}')
    assert code == 1 and answer["error"]["code"] == "no-tracker"


def test_an_unknown_kind_is_a_named_refusal(capsys):
    code, answer = call(capsys, "issue-get", '{"key":"7","tracker":"linear"}')
    assert code == 1 and answer["error"]["code"] == "no-tracker"
