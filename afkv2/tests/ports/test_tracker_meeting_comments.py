"""meeting-comments and meeting-comment-put on Jira and on GitHub issues; GitHub description-put with `whole`."""

from __future__ import annotations

import hashlib
import json

import pytest

from conftest import FakeJira
from port_fakes import FakeResp
from tracker import cli, envelope, github_issues, jira

TITLE = "2026-11-20 Design review"
ME, OTHER = "acc-me", "acc-other"
NODES = [{"type": "paragraph", "content": [{"type": "text", "text": "We chose the queue."}]},
         {"type": "bulletList", "content": [{"type": "listItem", "content": [
             {"type": "paragraph", "content": [{"type": "text", "text": "Owner: the platform team"}]}]}]}]
NEW_NODES = [{"type": "paragraph", "content": [{"type": "text", "text": "We chose the stream."}]}]
MARKDOWN = "We chose the queue.\n\n- Owner: the platform team"
NEW_MARKDOWN = "We chose the stream."


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical(nodes):
    """The canonical form adf-text answers, written out here so the test does not trust the port helper."""
    return json.dumps(nodes, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def refused(call, payload):
    with pytest.raises(envelope.Refusal) as caught:
        call(payload)
    return caught.value


# Jira


def expand_doc(title, nodes, padded=False):
    pad = [{"type": "paragraph", "content": []}] if padded else []
    return {"type": "doc", "version": 1, "content": [*pad, {"type": "expand", "attrs": {"title": title}, "content": nodes}, *pad]}


class JiraTicket(FakeJira):
    """One work item's comments behind the real client: list, post, edit, myself. `keep` false drops each write."""

    def __init__(self, comments=(), keep=True):
        super().__init__()
        self.items, self.keep, self.next_id = [dict(item) for item in comments], keep, 20000

    def _req(self, method, path, data=None, headers=None, follow=True):
        self.calls.append((method, path, data))
        base = "/rest/api/3/issue/PROJ-1/comment"
        if method == "GET" and path == "/rest/api/3/myself":
            return FakeResp({"accountId": ME})
        if method == "GET" and path.startswith(base + "?"):
            return FakeResp({"comments": self.items, "startAt": 0, "maxResults": 100, "total": len(self.items)})
        if method == "POST" and path == base:
            self.next_id += 1
            if self.keep:
                self.items.append({"id": str(self.next_id), "author": {"accountId": ME}, "body": json.loads(data)["body"]})
            return FakeResp({"id": str(self.next_id)})
        if method == "PUT" and path.startswith(base + "/"):
            target = path.rsplit("/", 1)[1]
            for item in self.items:
                if item["id"] == target and self.keep:
                    item["body"] = json.loads(data)["body"]
            return FakeResp(b"")
        raise AssertionError(f"no fake route for {method} {path}")


def jira_comment(comment_id, title, nodes, author=ME, padded=False):
    return {"id": comment_id, "author": {"accountId": author}, "body": expand_doc(title, nodes, padded)}


@pytest.fixture
def ticket(monkeypatch):
    def install(comments=(), keep=True):
        fake = JiraTicket(comments, keep)
        monkeypatch.setattr(jira, "client", lambda: fake)
        return fake
    return install


def jira_put(nodes=NODES, title=TITLE, expect_hash=None, receipt=None, **extra):
    receipt = receipt or sha("PROJ-1" + title + canonical(nodes))
    return {"key": "PROJ-1", "title": title, "adf": nodes, "expect_hash": expect_hash, "receipt": receipt, **extra}


def test_jira_meeting_comments_lists_only_meeting_comments_with_own_text_and_hash(ticket):
    plain = {"id": "1", "author": {"accountId": ME}, "body": {"type": "doc", "version": 1, "content": [
        {"type": "paragraph", "content": [{"type": "text", "text": "hello"}]}]}}
    undated = jira_comment("2", "Design review", NODES)
    two = {"id": "3", "author": {"accountId": ME}, "body": {"type": "doc", "version": 1, "content": [
        expand_doc(TITLE, NODES)["content"][0], expand_doc(TITLE, NODES)["content"][0]]}}
    mine, theirs = jira_comment("4", TITLE, NODES, padded=True), jira_comment("5", "2026-11-21 Demo", NEW_NODES, OTHER)
    ticket([plain, undated, two, mine, theirs])
    answer = jira.meeting_comments({"key": "PROJ-1"})
    expected = [{"title": TITLE, "comment_id": "4", "comment_hash": sha(canonical(NODES)), "own": True,
                 "url": "https://n.test/browse/PROJ-1?focusedCommentId=4", "created": None,
                 "text": "We chose the queue.\nOwner: the platform team"},
                {"title": "2026-11-21 Demo", "comment_id": "5", "comment_hash": sha(canonical(NEW_NODES)), "own": False,
                 "url": "https://n.test/browse/PROJ-1?focusedCommentId=5", "created": None, "text": "We chose the stream."}]
    assert answer["comments"] == expected, f"comments 1-5 (plain, undated, 2 expands, mine, theirs): expected {expected}, got {answer}"
    adf_text = jira.adf_text({"adf": NODES})["block_text"]
    assert answer["comments"][0]["comment_hash"] == sha(adf_text), \
        f"hash of NODES: expected sha256 of adf-text {sha(adf_text)}, got {answer['comments'][0]['comment_hash']}"


def test_jira_posts_a_new_meeting_comment(ticket):
    fake = ticket()
    answer = jira.meeting_comment_put(jira_put())
    expected = {"ok": True, "comment_id": "20001", "url": "https://n.test/browse/PROJ-1?focusedCommentId=20001",
                "action": "posted", "comment_hash": sha(canonical(NODES))}
    assert answer == expected, f"no comments, put NODES: expected {expected}, got {answer}"
    posted = [json.loads(data)["body"] for method, _, data in fake.writes() if method == "POST"]
    assert posted == [expand_doc(TITLE, NODES)], f"POST body: expected {[expand_doc(TITLE, NODES)]}, got {posted}"


def test_jira_with_the_same_text_writes_nothing_and_answers_unchanged(ticket):
    fake = ticket([jira_comment("4", TITLE, NODES)])
    answer = jira.meeting_comment_put(jira_put(expect_hash="0" * 64))
    assert answer["action"] == "unchanged" and answer["comment_id"] == "4", \
        f"same text, other expect_hash: expected unchanged on 4, got {answer}"
    assert fake.writes() == [], f"unchanged: expected no write, got {fake.writes()}"


def test_jira_edits_the_comment_in_place(ticket):
    fake = ticket([jira_comment("4", TITLE, NODES)])
    answer = jira.meeting_comment_put(jira_put(NEW_NODES, expect_hash=sha(canonical(NODES))))
    assert answer["action"] == "edited" and answer["comment_id"] == "4", f"edit of 4: expected edited on 4, got {answer}"
    writes = [(method, path) for method, path, _ in fake.writes()]
    expected = [("PUT", "/rest/api/3/issue/PROJ-1/comment/4")]
    assert writes == expected, f"edit of 4: expected writes {expected}, got {writes}"
    assert fake.items[0]["body"] == expand_doc(TITLE, NEW_NODES), f"edit of 4: expected the new doc, got {fake.items[0]['body']}"


@pytest.mark.parametrize("comments, expect_hash", [((), "f" * 64), ((("4", NODES),), "f" * 64)])
def test_jira_refuses_stale(ticket, comments, expect_hash):
    fake = ticket([jira_comment(cid, TITLE, nodes) for cid, nodes in comments])
    error = refused(jira.meeting_comment_put, jira_put(NEW_NODES, expect_hash=expect_hash))
    assert error.code == "stale", f"{len(comments)} comments, expect_hash {expect_hash}: expected stale, got {error.code}"
    assert fake.writes() == [], f"stale: expected no write, got {fake.writes()}"


def test_jira_refuses_a_doubled_meeting(ticket):
    fake = ticket([jira_comment("4", TITLE, NODES), jira_comment("5", TITLE, NODES)])
    error = refused(jira.meeting_comment_put, jira_put(NEW_NODES, expect_hash=sha(canonical(NODES))))
    assert error.code == "duplicate-meeting", f"2 comments with one title: expected duplicate-meeting, got {error.code}"
    assert fake.writes() == [], f"duplicate: expected no write, got {fake.writes()}"


def test_jira_refuses_a_meeting_comment_of_another_account(ticket):
    fake = ticket([jira_comment("4", TITLE, NODES, OTHER)])
    error = refused(jira.meeting_comment_put, jira_put(NEW_NODES, expect_hash=sha(canonical(NODES))))
    assert error.code == "not-own", f"comment of {OTHER}: expected not-own, got {error.code}"
    assert fake.writes() == [], f"not-own: expected no write, got {fake.writes()}"


@pytest.mark.parametrize("change, code", [
    ({"receipt": "ab" * 32}, "bad-receipt"), ({"receipt": "AB" * 32}, "bad-receipt"),
    ({"title": "Design review"}, "bad-payload"), ({"title": "2026-11-20 a\nb"}, "bad-payload"),
    ({"title": "2026-11-2 x"}, "bad-payload")])
def test_jira_refuses_bad_input_before_any_call(ticket, change, code):
    fake = ticket()
    payload = {**jira_put(), **change}
    error = refused(jira.meeting_comment_put, payload)
    assert error.code == code, f"payload change {change}: expected {code}, got {error.code}"
    assert fake.calls == [], f"payload change {change}: expected no Jira call, got {fake.calls}"


def test_jira_needs_expect_hash_in_the_payload(ticket):
    payload = jira_put()
    del payload["expect_hash"]
    error = refused(jira.meeting_comment_put, payload)
    assert error.code == "bad-payload", f"no expect_hash key: expected bad-payload, got {error.code}"


def test_jira_refuses_a_write_that_does_not_read_back(ticket):
    ticket(keep=False)
    error = refused(jira.meeting_comment_put, jira_put())
    assert error.code == "read-back-mismatch", f"dropped post: expected read-back-mismatch, got {error.code}"


def test_jira_refuses_a_comment_over_the_text_limit(ticket):
    fake = ticket()
    nodes = [{"type": "paragraph", "content": [{"type": "text", "text": "x" * jira.COMMENT_TEXT_LIMIT}]}]
    error = refused(jira.meeting_comment_put, jira_put(nodes))
    assert error.code == "too-large", f"{jira.COMMENT_TEXT_LIMIT} characters: expected too-large, got {error.code}"
    assert fake.calls == [], f"too-large: expected no Jira call, got {fake.calls}"


# GitHub


class GhIssue:
    """Issue 7's comments behind gh: list, post, PATCH, user. `keep` false drops each write."""

    def __init__(self, tools, comments=(), keep=True):
        self.comments, self.keep, self.next_id = [dict(item) for item in comments], keep, 900
        tools.on("gh", "api", "user", answer={"login": "me"})
        tools.on("gh", "api", "--paginate", "--slurp", answer=lambda args, stdin: self._pages())
        tools.on("gh", "issue", "comment", answer=self._post)
        tools.on("gh", "api", "-X", "PATCH", answer=self._patch)

    def _pages(self):
        """2 comments per page, so that a list of 3 or more spans pages."""
        return [self.comments[start:start + 2] for start in range(0, len(self.comments), 2)] or [[]]

    def _post(self, args, stdin):
        self.next_id += 1
        url = f"https://github.com/o/r/issues/7#issuecomment-{self.next_id}"
        if self.keep:
            self.comments.append({"id": self.next_id, "user": {"login": "me"}, "body": stdin, "html_url": url})
        return url + "\n"

    def _patch(self, args, stdin):
        target = args[3].rsplit("/", 1)[1]
        for item in self.comments:
            if str(item["id"]) == target and self.keep:
                item["body"] = json.loads(stdin)["body"]
        return "{}"


def gh_comment(number, title, markdown, login="me", crlf=False):
    body = f"<details><summary>{title}</summary>\n\n{markdown}\n\n</details>\n"
    return {"id": number, "user": {"login": login}, "html_url": f"https://github.com/o/r/issues/7#issuecomment-{number}",
            "body": body.replace("\n", "\r\n") if crlf else body}


def gh_put(markdown=MARKDOWN, title=TITLE, expect_hash=None, **extra):
    receipt = sha("7" + title + markdown)
    return {"key": "7", "repo": "o/r", "title": title, "markdown": markdown, "expect_hash": expect_hash,
            "receipt": receipt, **extra}


def test_github_meeting_comments_lists_only_meeting_comments_with_own_text_and_hash(tools):
    plain = {"id": 1, "user": {"login": "me"}, "body": "hello", "html_url": "https://github.com/o/r/issues/7#issuecomment-1"}
    undated = gh_comment(2, "Design review", MARKDOWN)
    trailing = {**gh_comment(3, TITLE, MARKDOWN), "body": gh_comment(3, TITLE, MARKDOWN)["body"] + "after"}
    GhIssue(tools, [plain, undated, trailing, gh_comment(4, TITLE, MARKDOWN, crlf=True),
                    gh_comment(5, "2026-11-21 Demo", NEW_MARKDOWN, login="other")])
    answer = github_issues.meeting_comments({"key": "7", "repo": "o/r"})
    expected = [{"title": TITLE, "comment_id": "4", "comment_hash": sha(MARKDOWN), "own": True,
                 "url": "https://github.com/o/r/issues/7#issuecomment-4", "created": None, "text": MARKDOWN},
                {"title": "2026-11-21 Demo", "comment_id": "5", "comment_hash": sha(NEW_MARKDOWN), "own": False,
                 "url": "https://github.com/o/r/issues/7#issuecomment-5", "created": None, "text": NEW_MARKDOWN}]
    assert answer["comments"] == expected, f"comments 1-5 (plain, undated, trailing, mine CRLF, theirs): expected {expected}, got {answer}"


def test_github_posts_a_new_meeting_comment(tools):
    issue = GhIssue(tools)
    answer = github_issues.meeting_comment_put(gh_put())
    expected = {"ok": True, "comment_id": "901", "url": "https://github.com/o/r/issues/7#issuecomment-901",
                "action": "posted", "comment_hash": sha(MARKDOWN)}
    assert answer == expected, f"no comments, put MARKDOWN: expected {expected}, got {answer}"
    _, args, stdin = tools.calls_to("gh", "issue", "comment")[0]
    body = f"<details><summary>{TITLE}</summary>\n\n{MARKDOWN}\n\n</details>"
    assert args == ["issue", "comment", "7", "--repo", "o/r", "--body-file", "-"] and stdin == body, \
        f"post: expected args with --repo o/r and body {body!r}, got {args} {stdin!r}"
    assert len(issue.comments) == 1, f"post: expected 1 comment, got {issue.comments}"


def test_github_with_the_same_text_writes_nothing_and_answers_unchanged(tools):
    GhIssue(tools, [gh_comment(4, TITLE, MARKDOWN)])
    answer = github_issues.meeting_comment_put(gh_put(expect_hash="0" * 64))
    assert answer["action"] == "unchanged" and answer["comment_id"] == "4", \
        f"same text, other expect_hash: expected unchanged on 4, got {answer}"
    writes = tools.calls_to("gh", "issue", "comment") + tools.calls_to("gh", "api", "-X")
    assert writes == [], f"unchanged: expected no write, got {writes}"


@pytest.mark.parametrize("repo, path", [("o/r", "repos/o/r/issues/comments/4"), (None, "repos/{owner}/{repo}/issues/comments/4")])
def test_github_edits_the_comment_in_place(tools, repo, path):
    issue = GhIssue(tools, [gh_comment(4, TITLE, MARKDOWN)])
    payload = {**gh_put(NEW_MARKDOWN, expect_hash=sha(MARKDOWN)), "repo": repo}
    answer = github_issues.meeting_comment_put(payload)
    assert answer["action"] == "edited" and answer["comment_id"] == "4", f"edit of 4: expected edited on 4, got {answer}"
    _, args, stdin = tools.calls_to("gh", "api", "-X", "PATCH")[0]
    expected = ["api", "-X", "PATCH", path, "--input", "-"]
    assert args == expected, f"repo {repo}: expected {expected}, got {args}"
    body = f"<details><summary>{TITLE}</summary>\n\n{NEW_MARKDOWN}\n\n</details>"
    assert json.loads(stdin) == {"body": body}, f"PATCH stdin: expected body {body!r}, got {stdin!r}"
    assert tools.calls_to("gh", "issue", "comment") == [], "edit: expected no new comment"
    assert issue.comments[0]["body"] == body, f"edit: expected the new body, got {issue.comments[0]['body']!r}"


@pytest.mark.parametrize("comments", [(), ((4, MARKDOWN),)])
def test_github_refuses_stale(tools, comments):
    GhIssue(tools, [gh_comment(number, TITLE, text) for number, text in comments])
    error = refused(github_issues.meeting_comment_put, gh_put(NEW_MARKDOWN, expect_hash="f" * 64))
    assert error.code == "stale", f"{len(comments)} comments, expect_hash f*64: expected stale, got {error.code}"
    writes = tools.calls_to("gh", "issue", "comment") + tools.calls_to("gh", "api", "-X")
    assert writes == [], f"stale: expected no write, got {writes}"


def test_github_refuses_a_doubled_meeting(tools):
    GhIssue(tools, [gh_comment(4, TITLE, MARKDOWN), gh_comment(5, TITLE, MARKDOWN)])
    error = refused(github_issues.meeting_comment_put, gh_put(NEW_MARKDOWN, expect_hash=sha(MARKDOWN)))
    assert error.code == "duplicate-meeting", f"2 comments with one title: expected duplicate-meeting, got {error.code}"
    writes = tools.calls_to("gh", "issue", "comment") + tools.calls_to("gh", "api", "-X")
    assert writes == [], f"duplicate: expected no write, got {writes}"


def test_github_refuses_a_meeting_comment_of_another_account(tools):
    GhIssue(tools, [gh_comment(4, TITLE, MARKDOWN, login="other")])
    error = refused(github_issues.meeting_comment_put, gh_put(NEW_MARKDOWN, expect_hash=sha(MARKDOWN)))
    assert error.code == "not-own", f"comment of other: expected not-own, got {error.code}"
    writes = tools.calls_to("gh", "issue", "comment") + tools.calls_to("gh", "api", "-X")
    assert writes == [], f"not-own: expected no write, got {writes}"


@pytest.mark.parametrize("change, code", [
    ({"receipt": "ab" * 32}, "bad-receipt"), ({"markdown": MARKDOWN + "\nmore"}, "bad-receipt"),
    ({"title": "Design review"}, "bad-payload"), ({"title": "2026-11-20 a\r\nb"}, "bad-payload")])
def test_github_refuses_bad_input_before_any_call(tools, change, code):
    payload = {**gh_put(), **change}
    error = refused(github_issues.meeting_comment_put, payload)
    assert error.code == code, f"payload change {change}: expected {code}, got {error.code}"
    assert tools.calls == [], f"payload change {change}: expected no gh call, got {tools.calls}"


def test_github_refuses_a_comment_over_65536_characters(tools):
    text = "x" * github_issues.BODY_LIMIT
    error = refused(github_issues.meeting_comment_put, gh_put(text))
    assert error.code == "too-large", f"{len(text)} characters: expected too-large, got {error.code}"
    assert tools.calls == [], f"too-large: expected no gh call, got {tools.calls}"


def test_github_refuses_a_write_that_does_not_read_back(tools):
    GhIssue(tools, keep=False)
    error = refused(github_issues.meeting_comment_put, gh_put())
    assert error.code == "read-back-mismatch", f"dropped post: expected read-back-mismatch, got {error.code}"


# The command


@pytest.mark.parametrize("verb, name", [("meeting-comments", "meeting_comments"), ("meeting-comment-put", "meeting_comment_put")])
@pytest.mark.parametrize("kind, module", [("jira", jira), ("github-issues", github_issues)])
def test_the_meeting_verbs_go_to_the_tracker_of_the_kind(monkeypatch, verb, name, kind, module):
    seen = []
    monkeypatch.setattr(module, name, lambda payload: seen.append(payload) or {"ok": True})
    answer = cli.VERBS[verb]({"key": "7", "tracker": kind})
    assert answer == {"ok": True} and seen and seen[0]["key"] == "7", \
        f"{verb} with tracker {kind}: expected a call of {module.__name__}.{name}, got {seen}"


# GitHub description-put with whole


class Body:
    def __init__(self, tools, body=""):
        self.body, self.edits = body, []
        tools.on("gh", "issue", "view", answer=lambda args, stdin: {"number": 7, "body": self.body})
        tools.on("gh", "issue", "edit", answer=self._edit)

    def _edit(self, args, stdin):
        self.body = stdin
        self.edits.append(args)
        return ""


def whole_put(preview, issue, text=MARKDOWN, expect_hash=None, **extra):
    seen = github_issues.body_hash(issue.body) if expect_hash is None else expect_hash
    path, receipt, _ = preview(key="7", description_hash=seen, pictures=(), text=github_issues.block_text(text))
    return github_issues.description_put({"key": "7", "repo": "o/r", "markdown": text, "expect_hash": seen,
                                          "receipt": receipt, "preview": path, "whole": True, **extra})


def test_github_whole_writes_the_whole_body_and_reads_back(tools, preview):
    old = f"Above.\n{github_issues.BEGIN_LINE}\nold\n{github_issues.END_LINE}"
    issue = Body(tools, old)
    answer = whole_put(preview, issue, MARKDOWN + "  \r\n\n")
    block = {"family": "whole", "text": MARKDOWN, "media_ids": []}
    assert issue.body == MARKDOWN, f"whole over a body with a block: expected body {MARKDOWN!r}, got {issue.body!r}"
    assert answer == {"ok": True, "key": "7", "replaced": "afkv2", "block": block}, \
        f"whole answer: expected replaced afkv2 and {block}, got {answer}"
    read = github_issues.issue_get({"key": "7", "repo": "o/r"})
    assert read["whole"] == answer["block"], f"issue-get whole after write: expected {answer['block']}, got {read['whole']}"


def test_github_whole_on_a_body_without_a_block_answers_replaced_none(tools, preview):
    issue = Body(tools, "text of the human")
    answer = whole_put(preview, issue)
    assert answer["replaced"] is None and issue.body == MARKDOWN, f"plain body: expected replaced None, got {answer}"


def test_github_whole_refuses_stale(tools, preview):
    issue = Body(tools, "old")
    path, receipt, _ = preview(key="7", description_hash=github_issues.body_hash("old"), pictures=(), text=MARKDOWN)
    issue.body = "a human edited this"
    error = refused(github_issues.description_put, {"key": "7", "repo": "o/r", "markdown": MARKDOWN, "whole": True,
                                                    "expect_hash": github_issues.body_hash("old"), "receipt": receipt,
                                                    "preview": path})
    assert error.code == "stale" and issue.edits == [], f"body changed after preview: expected stale, no edit; got {error.code}, {issue.edits}"


def test_github_whole_refuses_a_block_line_in_the_new_text(tools, preview):
    issue = Body(tools)
    text = f"x\n{github_issues.END_LINE}"
    error = refused(lambda payload: whole_put(preview, issue, text), None)
    assert error.code == "bad-block" and issue.edits == [], f"text with an end line: expected bad-block, got {error.code}"


def test_github_whole_refuses_text_the_receipt_does_not_cover(tools, preview):
    issue = Body(tools)
    path, receipt, _ = preview(key="7", description_hash=github_issues.body_hash(""), pictures=(), text=MARKDOWN)
    error = refused(github_issues.description_put, {"key": "7", "repo": "o/r", "markdown": MARKDOWN + "\nmore",
                                                    "whole": True, "expect_hash": github_issues.body_hash(""),
                                                    "receipt": receipt, "preview": path})
    assert error.code == "bad-receipt" and issue.edits == [], f"other text: expected bad-receipt, got {error.code}"


def test_github_whole_refuses_a_body_over_the_limit(tools, preview):
    issue = Body(tools)
    error = refused(lambda payload: whole_put(preview, issue, "a" * (github_issues.BODY_LIMIT + 1)), None)
    assert error.code == "too-large" and issue.edits == [], f"{github_issues.BODY_LIMIT + 1} characters: expected too-large, got {error.code}"


def test_github_issue_get_answers_whole(tools):
    Body(tools, "line  \r\nnext\n\n")
    answer = github_issues.issue_get({"key": "7", "repo": "o/r"})
    expected = {"family": "whole", "text": "line\nnext", "media_ids": []}
    assert answer["whole"] == expected, f"body 'line  \\r\\nnext\\n\\n': expected whole {expected}, got {answer.get('whole')}"


def test_meeting_comments_come_oldest_meeting_first(tools):
    later = {**gh_comment(10, "2026-11-21 Demo", NEW_MARKDOWN), "created_at": "2026-11-21T10:00:00Z"}
    earlier = {**gh_comment(11, TITLE, MARKDOWN), "created_at": "2026-11-22T09:00:00Z"}
    GhIssue(tools, [later, earlier])
    answer = cli.VERBS["meeting-comments"]({"key": "7", "repo": "o/r"})
    titles = [item["title"] for item in answer["comments"]]
    assert titles == [TITLE, "2026-11-21 Demo"], f"titles of 2 meetings posted out of date order: expected the earlier meeting first, got {titles}"


def test_github_sees_a_duplicate_on_a_later_page(tools):
    others = [{"id": number, "user": {"login": "me"}, "body": "hello",
               "html_url": f"https://github.com/o/r/issues/7#issuecomment-{number}"} for number in range(20, 24)]
    GhIssue(tools, [gh_comment(1, TITLE, MARKDOWN), *others, gh_comment(2, TITLE, MARKDOWN)])
    with pytest.raises(envelope.Refusal) as refused:
        cli.VERBS["meeting-comment-put"](gh_put(NEW_MARKDOWN, expect_hash=sha(MARKDOWN)))
    assert refused.value.code == "duplicate-meeting", f"a duplicate on page 3 of 3: expected duplicate-meeting, got {refused.value.code}"
