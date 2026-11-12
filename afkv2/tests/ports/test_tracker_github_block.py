"""The managed PRD block of a GitHub issue body: read, write, refusals. gh is mocked in-process."""

from __future__ import annotations

import pytest

from tracker import cli, envelope, github_issues

BEGIN, END = github_issues.BEGIN_LINE, github_issues.END_LINE
TEXT = "# PRD\n\n```mermaid\ngraph TD\n  A --> B\n```\n\n- R-1 the user can sign in"


class Issue:
    """One issue body behind `gh issue view` and `gh issue edit --body-file -`."""

    def __init__(self, tools, body=""):
        self.body, self.edits = body, []
        tools.on("gh", "issue", "view", answer=lambda args, stdin: {"number": 7, "body": self.body})
        tools.on("gh", "issue", "edit", answer=self._edit)

    def _edit(self, args, stdin):
        assert args[args.index("--body-file") + 1] == "-"
        self.body = stdin
        self.edits.append(args)
        return ""


def put(preview, issue, text=TEXT, **extra):
    path, receipt, _ = preview(key="7", description_hash=github_issues.body_hash(issue.body), pictures=(),
                               text=github_issues.block_text(text))
    payload = {"key": "7", "repo": "o/r", "markdown": text, "expect_hash": github_issues.body_hash(issue.body),
               "receipt": receipt, "preview": path, **extra}
    return github_issues.description_put(payload)


def refused(call):
    with pytest.raises(envelope.Refusal) as caught:
        call()
    return caught.value


def test_a_first_publish_appends_the_block_and_keeps_the_body(tools, preview):
    issue = Issue(tools, "Text of the human.\r\n\r\n")
    answer = put(preview, issue)
    assert issue.body == f"Text of the human.\n\n{BEGIN}\n{TEXT}\n{END}"
    assert answer["replaced"] is None and answer["block"] == {"family": "afkv2", "text": TEXT, "media_ids": []}
    assert issue.edits[0][:5] == ["issue", "edit", "7", "--repo", "o/r"]


def test_an_empty_body_gets_only_the_block(tools, preview):
    issue = Issue(tools)
    put(preview, issue)
    assert issue.body == f"{BEGIN}\n{TEXT}\n{END}"


def test_a_republish_changes_only_the_lines_inside_the_block(tools, preview):
    issue = Issue(tools, f"Above.\n{BEGIN}\nold text\n{END}\nBelow.")
    answer = put(preview, issue)
    assert issue.body == f"Above.\n{BEGIN}\n{TEXT}\n{END}\nBelow."
    assert answer["replaced"] == "afkv2"


def test_the_mermaid_fence_stays_a_fence(tools, preview):
    issue = Issue(tools)
    put(preview, issue)
    assert "```mermaid\ngraph TD" in issue.body


def test_issue_get_reads_the_block_back(tools, preview):
    issue = Issue(tools, "Above.")
    put(preview, issue)
    answer = github_issues.issue_get({"key": "7", "repo": "o/r", "fields": "number"})
    assert answer["block"] == {"family": "afkv2", "text": TEXT, "media_ids": []}
    assert answer["description_hash"] == github_issues.body_hash(issue.body)
    assert answer["length_without_block"] == len("Above.\n")
    assert "body" in tools.calls_to("gh", "issue", "view")[-1][1][-1]


def test_issue_get_of_a_body_with_no_block_answers_none(tools):
    Issue(tools, "only text")
    answer = github_issues.issue_get({"key": "7", "repo": "o/r"})
    assert answer["block"] is None and "block_problem" not in answer


@pytest.mark.parametrize("body", [
    f"{BEGIN}\na\n{END}\n{BEGIN}\nb\n{END}",
    f"{BEGIN}\nno end",
    f"no begin\n{END}",
    f"{END}\nx\n{BEGIN}",
    f"text {BEGIN} inside a line",
])
def test_a_broken_block_is_named_on_read_and_refused_on_write(tools, preview, body):
    issue = Issue(tools, body)
    assert github_issues.issue_get({"key": "7", "repo": "o/r"})["block_problem"]
    assert refused(lambda: put(preview, issue)).code == "bad-block"
    assert issue.edits == []


def test_a_marker_inside_a_code_fence_is_no_block(tools):
    Issue(tools, f"```\n{BEGIN}\n```")
    answer = github_issues.issue_get({"key": "7", "repo": "o/r"})
    assert answer["block"] is None and "block_problem" not in answer


def test_a_body_changed_after_the_preview_is_stale(tools, preview):
    issue = Issue(tools, "old")
    path, receipt, _ = preview(key="7", description_hash=github_issues.body_hash("old"), pictures=(),
                               text=github_issues.block_text(TEXT))
    issue.body = "a human edited this"
    code = refused(lambda: github_issues.description_put({
        "key": "7", "repo": "o/r", "markdown": TEXT, "expect_hash": github_issues.body_hash("old"),
        "receipt": receipt, "preview": path})).code
    assert code == "stale" and issue.edits == []


def test_text_the_receipt_does_not_cover_is_refused(tools, preview):
    issue = Issue(tools)
    path, receipt, _ = preview(key="7", description_hash=github_issues.body_hash(""), pictures=(), text=TEXT)
    code = refused(lambda: github_issues.description_put({
        "key": "7", "repo": "o/r", "markdown": TEXT + "\nmore", "expect_hash": github_issues.body_hash(""),
        "receipt": receipt, "preview": path})).code
    assert code == "bad-receipt" and issue.edits == []


def test_a_hash_that_is_not_the_preview_hash_is_refused(tools, preview):
    issue = Issue(tools)
    path, receipt, _ = preview(key="7", description_hash=github_issues.body_hash(""), pictures=(), text=TEXT)
    code = refused(lambda: github_issues.description_put({
        "key": "7", "repo": "o/r", "markdown": TEXT, "expect_hash": "0" * 64,
        "receipt": receipt, "preview": path})).code
    assert code == "bad-receipt" and issue.edits == []


def test_new_text_with_a_block_line_is_refused(tools, preview):
    issue = Issue(tools)
    assert refused(lambda: put(preview, issue, text=f"x {END}")).code == "bad-block"
    assert issue.edits == []


def test_a_body_over_the_github_limit_is_refused(tools, preview):
    issue = Issue(tools, "a" * github_issues.BODY_LIMIT)
    assert refused(lambda: put(preview, issue)).code == "too-large"
    assert issue.edits == []


def test_block_text_is_the_canonical_form():
    assert github_issues.block_text("\r\n\nline  \r\nnext\n\n") == "line\nnext"


def test_the_cli_sends_description_put_to_the_configured_kind(tools, preview, monkeypatch):
    issue = Issue(tools)
    monkeypatch.setattr(cli.settings, "read_config", lambda: {"tracker": {"kind": "github-issues", "repo": "o/r"}})
    path, receipt, _ = preview(key="7", description_hash=github_issues.body_hash(""), pictures=(), text=TEXT)
    answer = cli.VERBS["description-put"]({"key": "7", "markdown": TEXT, "expect_hash": github_issues.body_hash(""),
                                           "receipt": receipt, "preview": path})
    assert answer["ok"] and issue.edits[0][3:5] == ["--repo", "o/r"]
