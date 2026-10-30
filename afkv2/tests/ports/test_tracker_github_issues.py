"""Ported from the v1 tracker tests: GitHub-issue reads through gh, mocked in-process."""

from __future__ import annotations

import json

import pytest

from tracker import envelope, github_issues, shell

TWO_PAGES = json.dumps([{"id": 1}, {"id": 2}]) + "\n" + json.dumps([{"id": 3}])


def test_every_page_of_a_paginated_answer_is_read():
    assert shell.pages(TWO_PAGES) == [{"id": 1}, {"id": 2}, {"id": 3}]


def test_one_page_is_still_one_value():
    assert shell.pages('{"number": 7}') == {"number": 7}


def test_text_that_is_not_json_raises():
    with pytest.raises(ValueError):
        shell.pages("not json")
    with pytest.raises(ValueError):
        shell.pages("")


def test_issue_get_keeps_the_gh_fields_inside_the_envelope(tools):
    tools.on("gh", "issue", "view", answer={"number": 7, "title": "t", "comments": [{"body": "c"}]})
    answer = github_issues.issue_get({"key": "#7", "repo": "o/r"})
    assert answer == {"ok": True, "key": "7", "number": 7, "title": "t", "comments": [{"body": "c"}]}
    args = tools.calls[0][1]
    assert args[:3] == ["issue", "view", "7"] and ["--repo", "o/r"] == args[3:5]
    assert "comments" in args[args.index("--json") + 1]


def test_a_key_that_names_a_repository_reads_that_repository(tools):
    tools.on("gh", "issue", "view", answer={"number": 7})
    github_issues.issue_get({"key": "o/r#7"})
    assert tools.calls[0][1][:5] == ["issue", "view", "7", "--repo", "o/r"]


def test_a_key_that_names_another_repository_is_refused(tools):
    with pytest.raises(envelope.Refusal) as caught:
        github_issues.issue_get({"key": "other/thing#7", "repo": "o/r"})
    assert caught.value.code == "bad-payload" and tools.calls == []


@pytest.mark.parametrize("key", ["--web", "#--web", "--web#7"])
def test_a_key_like_a_flag_is_refused(tools, key):
    with pytest.raises(envelope.Refusal) as caught:
        github_issues.issue_get({"key": key})
    assert caught.value.code == "bad-payload" and tools.calls == []


@pytest.mark.parametrize("key", ["o/r#", "#", "https://github.com/other/thing/issues/7", "7a", "\u0667"])
def test_a_key_with_no_number_of_digits_is_refused(tools, key):
    with pytest.raises(envelope.Refusal) as caught:
        github_issues.issue_get({"key": key})
    assert caught.value.code == "bad-payload" and tools.calls == []


@pytest.mark.parametrize("key,number", [("7", "7"), ("#7", "7"), ("o/r#7", "7"), (7, "7")])
def test_issue_key_spellings(tools, key, number):
    tools.on("gh", "issue", "view", answer={"number": 7})
    assert github_issues.issue_get({"key": key})["key"] == number


def test_issue_search_counts_and_limits(tools):
    tools.on("gh", "issue", "list", answer=[{"number": 1}, {"number": 2}])
    answer = github_issues.issue_search({"query": "label:x", "max_results": 2, "repo": "o/r"})
    assert answer == {"ok": True, "issues": [{"number": 1}, {"number": 2}], "count": 2}
    args = tools.calls[0][1]
    assert args[args.index("--limit") + 1] == "2" and args[args.index("--search") + 1] == "label:x"


def test_issue_search_without_a_query_lists(tools):
    tools.on("gh", "issue", "list", answer=[])
    assert github_issues.issue_search({})["count"] == 0
    assert "--search" not in tools.calls[0][1]


def test_issue_search_bad_limit_is_bad_payload(tools):
    with pytest.raises(envelope.Refusal) as caught:
        github_issues.issue_search({"max_results": "many"})
    assert caught.value.code == "bad-payload"


@pytest.mark.parametrize("stderr,code", [
    ("GraphQL: Could not resolve to an issue or pull request with the number of 7.", "not-found"),
    ("gh: Not Found (HTTP 404)", "not-found"),
    ("gh: Forbidden (HTTP 403)", "forbidden"),
    ("To get started with GitHub CLI, please run:  gh auth login", "auth"),
    ("dial tcp: i/o timeout", "cli-failed"),
])
def test_gh_failures_map_to_codes(tools, stderr, code):
    tools.on("gh", "issue", "view", answer=(1, "", stderr))
    with pytest.raises(envelope.Refusal) as caught:
        github_issues.issue_get({"key": "7"})
    assert caught.value.code == code and stderr.split(":")[0] in caught.value.reason


def test_an_answer_that_is_not_json_is_bad_answer(tools):
    tools.on("gh", "issue", "view", answer="not json")
    with pytest.raises(envelope.Refusal) as caught:
        github_issues.issue_get({"key": "7"})
    assert caught.value.code == "bad-answer"


def test_a_missing_gh_is_unavailable(monkeypatch):
    monkeypatch.setattr(shell.shutil, "which", lambda _: None)
    with pytest.raises(envelope.Refusal) as caught:
        github_issues.issue_get({"key": "7"})
    assert caught.value.code == "unavailable"
