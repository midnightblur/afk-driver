"""Ported from the v1 forge tests: what each forge answers, with gh and glab mocked in-process."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from forge import cli, common

KINDS = ("gitlab", "github")
TOOL = {"gitlab": "glab", "github": "gh"}
VIEW = {"gitlab": ("mr", "view"), "github": ("pr", "view")}


def call(capsys, kind, verb, **payload):
    code = cli.forge_main([verb, json.dumps({"forge": kind, **payload})])
    return code, json.loads(capsys.readouterr().out)


def good(capsys, kind, verb, **payload):
    code, answer = call(capsys, kind, verb, **payload)
    assert code == 0 and answer["ok"] is True, answer
    return answer


def refused(capsys, kind, verb, **payload):
    code, answer = call(capsys, kind, verb, **payload)
    assert code == 1 and answer["ok"] is False, answer
    return answer["error"]


def github_project(tools):
    tools.on("gh", "repo", "view", answer={"nameWithOwner": "acme/widget"})
    tools.on("gh", "pr", "view", answer={"number": 7, "headRefOid": "head7"})


def gitlab_project(tools):
    tools.on("glab", "mr", "view", answer={"iid": 7, "web_url": "https://gitlab.example/acme/widget/-/merge_requests/7",
                                           "diff_refs": {"base_sha": "base", "start_sha": "start", "head_sha": "head"}})
    tools.on("glab", "api", "projects/:id", answer={"path_with_namespace": "acme/widget"})


def gitlab_edits(*note_ids, edited=()):
    return {"data": {"project": {"mergeRequest": {"notes": {"nodes": [
        {"id": f"gid://gitlab/Note/{ident}", "author": {"id": "gid://gitlab/User/1"},
         "lastEditedBy": {"id": "gid://gitlab/User/9"} if ident in edited else None} for ident in note_ids]}}}}}


def github_threads(*groups):
    return {"data": {"repository": {"pullRequest": {"reviewThreads": {"nodes": [
        {"id": f"RT{root}", "isResolved": resolved, "comments": {"nodes": [{"databaseId": root, "lastEditedAt": None}]}}
        for root, resolved in groups]}}}}}


def test_every_forge_answers_the_same_verb_set():
    from forge import github, gitlab
    assert set(github.VERBS) == set(gitlab.VERBS) == {
        "auth-status", "change-view", "change-diff", "change-create-draft", "change-update-body",
        "change-ready", "change-comment", "note-list", "thread-list", "ci-status", "ci-wait"}


@pytest.mark.parametrize("verb", ["change-fetch", "change-state", "change-reviewers", "change-close",
                                  "thread-reply", "thread-resolve", "commit-changes", "no-such-verb"])
def test_a_verb_the_chain_does_not_call_is_unknown(capsys, verb):
    code, answer = call(capsys, "github", verb)
    assert code == 2 and answer["error"]["code"] == "unknown-verb"


POSITION = {"new_line": 5, "new_path": "a.txt", "old_path": "a.txt"}


def gitlab_pages(tools):
    gitlab_project(tools)
    tools.on("glab", "api", "graphql", answer=gitlab_edits(1, 2))
    note = '{"id":%d,"body":"b","author":{"username":"x"},"position":{"new_line":5,"new_path":"a.txt"}}'
    tools.on("glab", "api", "--paginate", answer=(
        '[{"id":"a","notes":[' + note % 1 + ']}]\n'
        '[{"id":"b","notes":[' + note % 2 + ']}]\n'))


def github_pages(tools):
    github_project(tools)
    tools.on("gh", "api", "graphql", answer=github_threads((1, False), (2, False)))
    tools.on("gh", "api", "--paginate", answer=(
        '[{"id":1,"body":"one","path":"a.txt","user":{"login":"x"}}]\n'
        '[{"id":2,"body":"two","path":"b.txt","user":{"login":"y"}}]\n'))


TWO_PAGES = {"gitlab": gitlab_pages, "github": github_pages}


@pytest.mark.parametrize("kind", KINDS)
def test_thread_list_reads_every_page(capsys, tools, kind):
    TWO_PAGES[kind](tools)
    assert good(capsys, kind, "thread-list", id="7")["count"] == 2


def gitlab_note_pages(tools, nodes):
    gitlab_project(tools)
    tools.on("glab", "api", "graphql", answer=nodes)
    tools.on("glab", "api", "--paginate", answer=(
        '[{"id":2,"body":"later","author":{"username":"b"},"created_at":"2025-02-02","updated_at":"2025-02-02","system":false}]\n'
        '[{"id":1,"body":"first","author":{"username":"a"},"created_at":"2025-02-01","updated_at":"2025-02-01","system":false},'
        '{"id":3,"body":"system","system":true}]\n'))


def github_note_pages(tools, nodes):
    github_project(tools)
    tools.on("gh", "api", "graphql", answer=nodes)
    tools.on("gh", "api", "--paginate", answer=(
        '[{"id":2,"body":"later","user":{"login":"b"},"created_at":"2025-02-02","updated_at":"2025-02-02"}]\n'
        '[{"id":1,"body":"first","user":{"login":"a"},"created_at":"2025-02-01","updated_at":"2025-02-01"}]\n'))


def github_comment_nodes(*nodes):
    return {"data": {"repository": {"pullRequest": {"comments": {"nodes": list(nodes)}}}}}


NOTE_PAGES = {"gitlab": gitlab_note_pages, "github": github_note_pages}
EDITED_NOTES = {
    "gitlab": gitlab_edits(1, 2, edited=(1,)),
    "github": github_comment_nodes({"databaseId": 2, "lastEditedAt": None}, {"databaseId": 1, "lastEditedAt": "2025-02-03T00:00:00Z"}),
}
NOTE_MISSING_EDIT_FIELD = {
    "gitlab": {"data": {"project": {"mergeRequest": {"notes": {"nodes": [
        {"id": "gid://gitlab/Note/1", "lastEditedBy": None, "author": {"id": "gid://gitlab/User/1"}},
        {"id": "gid://gitlab/Note/2", "author": {"id": "gid://gitlab/User/1"}}]}}}}},
    "github": github_comment_nodes({"databaseId": 1, "lastEditedAt": None}, {"databaseId": 2}),
}


@pytest.mark.parametrize("kind", KINDS)
def test_note_list_is_paginated_normalized_and_oldest_first(capsys, tools, kind):
    NOTE_PAGES[kind](tools, EDITED_NOTES[kind])
    assert good(capsys, kind, "note-list", id="7") == {
        "ok": True, "count": 2,
        "notes": [
            {"id": "1", "author": "a", "body": "first", "created_at": "2025-02-01", "updated_at": "2025-02-01", "edited": True},
            {"id": "2", "author": "b", "body": "later", "created_at": "2025-02-02", "updated_at": "2025-02-02", "edited": False},
        ]}


@pytest.mark.parametrize("kind", KINDS)
def test_a_note_without_an_edit_state_is_refused(capsys, tools, kind):
    NOTE_PAGES[kind](tools, {"gitlab": gitlab_edits(), "github": github_comment_nodes()}[kind])
    assert refused(capsys, kind, "note-list", id="7")["code"] == "bad-answer"


@pytest.mark.parametrize("kind", KINDS)
def test_note_list_fails_when_the_graphql_call_fails(capsys, tools, kind):
    NOTE_PAGES[kind](tools, (1, "", "gh: Bad credentials (HTTP 401)"))
    answer = refused(capsys, kind, "note-list", id="7")
    assert answer["code"] == "auth"


@pytest.mark.parametrize("kind", KINDS)
def test_note_list_fails_when_graphql_omits_the_edit_field(capsys, tools, kind):
    NOTE_PAGES[kind](tools, NOTE_MISSING_EDIT_FIELD[kind])
    assert refused(capsys, kind, "note-list", id="7")["code"] == "bad-answer"


@pytest.mark.parametrize("kind,errored", [
    ("gitlab", {**gitlab_edits(1, 2), "errors": [{"message": "no"}]}),
    ("github", {**github_comment_nodes({"databaseId": 1, "lastEditedAt": None}, {"databaseId": 2, "lastEditedAt": None}),
                "errors": [{"message": "no"}]}),
])
def test_a_graphql_answer_with_errors_is_a_bad_answer(capsys, tools, kind, errored):
    NOTE_PAGES[kind](tools, errored)
    assert refused(capsys, kind, "note-list", id="7")["code"] == "bad-answer"


def gitlab_line_thread(tools, edits):
    gitlab_project(tools)
    tools.on("glab", "api", "graphql", answer=edits)
    tools.on("glab", "api", "--paginate", answer=[{"id": "d1", "notes": [
        {"id": 1, "type": "DiffNote", "resolved": False, "body": "x", "created_at": "2025-03-01", "position": POSITION},
        {"id": 2, "type": "DiffNote", "resolved": True, "body": "y", "created_at": "2025-03-02", "position": POSITION}]}])


def github_line_thread(tools, nodes):
    github_project(tools)
    tools.on("gh", "api", "graphql", answer=nodes)
    tools.on("gh", "api", "--paginate", answer=[
        {"id": 1, "body": "x", "path": "a.txt", "line": 5, "side": "RIGHT", "created_at": "2025-03-01", "user": {"login": "a"}},
        {"id": 2, "in_reply_to_id": 1, "body": "y", "path": "a.txt", "line": 5, "side": "RIGHT", "created_at": "2025-03-02",
         "user": {"login": "b"}}])


def github_thread_nodes(*comments, resolved=False):
    return {"data": {"repository": {"pullRequest": {"reviewThreads": {"nodes": [
        {"id": "T1", "isResolved": resolved, "comments": {"nodes": list(comments)}}]}}}}}


LINE_THREAD = {"gitlab": gitlab_line_thread, "github": github_line_thread}
FIRST_NOTE_EDITED = {
    "gitlab": gitlab_edits(1, 2, edited=(1,)),
    "github": github_thread_nodes({"databaseId": 1, "lastEditedAt": "2025-03-03T00:00:00Z"}, {"databaseId": 2, "lastEditedAt": None}),
}
THREAD_MISSING_EDIT_FIELD = {
    "gitlab": NOTE_MISSING_EDIT_FIELD["gitlab"],
    "github": github_thread_nodes({"databaseId": 1, "lastEditedAt": None}, {"databaseId": 2}),
}


@pytest.mark.parametrize("kind", KINDS)
def test_thread_list_carries_the_forge_edit_flag_per_note(capsys, tools, kind):
    LINE_THREAD[kind](tools, FIRST_NOTE_EDITED[kind])
    thread = good(capsys, kind, "thread-list", id="7")["threads"][0]
    assert [(note["id"], note["edited"]) for note in thread["notes"]] == [(1, True), (2, False)]


@pytest.mark.parametrize("kind", KINDS)
def test_thread_list_fails_when_the_graphql_call_fails(capsys, tools, kind):
    LINE_THREAD[kind](tools, (1, "", "gh: Bad credentials (HTTP 401)"))
    assert refused(capsys, kind, "thread-list", id="7")["code"] == "auth"


@pytest.mark.parametrize("kind", KINDS)
def test_thread_list_fails_when_graphql_omits_the_edit_field(capsys, tools, kind):
    LINE_THREAD[kind](tools, THREAD_MISSING_EDIT_FIELD[kind])
    assert refused(capsys, kind, "thread-list", id="7")["code"] == "bad-answer"


def test_gitlab_thread_is_resolved_when_a_note_is(capsys, tools):
    gitlab_line_thread(tools, gitlab_edits(1, 2))
    assert good(capsys, "gitlab", "thread-list", id="7")["threads"][0]["resolved"] is True


def test_github_replies_join_their_root_in_time_order(capsys, tools):
    github_line_thread(tools, github_thread_nodes({"databaseId": 1, "lastEditedAt": None}, {"databaseId": 2, "lastEditedAt": None}))
    answer = good(capsys, "github", "thread-list", id="7")
    assert answer["count"] == 1 and [note["body"] for note in answer["threads"][0]["notes"]] == ["x", "y"]


def test_gitlab_note_list_holds_replies_and_leaves_out_line_and_system_notes(capsys, tools):
    gitlab_project(tools)
    tools.on("glab", "mr", "view", answer={"iid": 7})
    tools.on("glab", "api", "graphql", answer=gitlab_edits(1, 2, 3, 4))
    tools.on("glab", "api", "--paginate", answer=[
        {"id": 1, "type": None, "body": "plain"},
        {"id": 2, "type": "DiscussionNote", "body": "reply"},
        {"id": 3, "type": "DiffNote", "body": "on a line"},
        {"id": 4, "system": True, "body": "system"}])
    assert [note["body"] for note in good(capsys, "gitlab", "note-list", id="7")["notes"]] == ["plain", "reply"]


def test_gitlab_thread_list_leaves_out_plain_and_system_notes(capsys, tools):
    gitlab_project(tools)
    tools.on("glab", "api", "graphql", answer=gitlab_edits(1, 2, 3))
    tools.on("glab", "api", "--paginate", answer=[
        {"id": "plain", "individual_note": True, "notes": [{"id": 1, "type": None, "body": "p"}]},
        {"id": "system", "individual_note": True, "notes": [{"id": 2, "system": True, "body": "s"}]},
        {"id": "line", "notes": [{"id": 3, "type": "DiffNote", "body": "l", "position": POSITION}]}])
    answer = good(capsys, "gitlab", "thread-list", id="7")
    assert answer["count"] == 1 and answer["threads"][0]["id"] == "line"


@pytest.mark.parametrize("by,author,edited", [
    ({"id": "gid://gitlab/User/9"}, {"id": "gid://gitlab/User/1"}, True),
    (None, {"id": "gid://gitlab/User/1"}, False),
    ({"id": "gid://gitlab/User/9"}, None, True),
])
def test_gitlab_edit_state_reads_the_editor_alone(capsys, tools, by, author, edited):
    gitlab_note_pages(tools, {"data": {"project": {"mergeRequest": {"notes": {"nodes": [
        {"id": "gid://gitlab/Note/1", "lastEditedBy": by, "author": author},
        {"id": "gid://gitlab/Note/2", "lastEditedBy": None, "author": {"id": "gid://gitlab/User/1"}}]}}}}})
    assert good(capsys, "gitlab", "note-list", id="7")["notes"][0]["edited"] is edited


def test_gitlab_hidden_authors_are_named(capsys, tools):
    gitlab_project(tools)
    tools.on("glab", "api", "graphql", answer={"data": {"project": {"mergeRequest": {"notes": {"nodes": [
        {"id": "gid://gitlab/Note/1", "author": None, "lastEditedBy": None}]}}}}})
    tools.on("glab", "api", "--paginate", answer='[{"id":1,"body":"x"}]')
    assert "cannot read users" in refused(capsys, "gitlab", "note-list", id="7")["reason"]


CHANGE_META = {
    "github": {"number": 7, "url": "https://github.example/acme/widget/pull/7", "headRefOid": "head7", "baseRefOid": "base7",
               "headRefName": "topic", "baseRefName": "main", "isCrossRepository": True, "state": "OPEN", "isDraft": True,
               "title": "t", "author": {"login": "a"}, "headRepository": {"nameWithOwner": "fork/widget"}},
    "gitlab": {"iid": 7, "web_url": "https://gitlab.example/acme/widget/-/merge_requests/7", "sha": "head7",
               "diff_refs": {"base_sha": "base7", "head_sha": "head7"}, "source_branch": "topic", "target_branch": "main",
               "source_project_id": 8, "target_project_id": 9, "state": "opened", "draft": True, "title": "t",
               "author": {"username": "a"}, "source_project": {"web_url": "https://gitlab.example/fork/widget"}},
}


@pytest.mark.parametrize("kind", KINDS)
def test_change_view_carries_immutable_refs_and_blob_source(capsys, tools, kind):
    tools.on(TOOL[kind], *VIEW[kind], answer=CHANGE_META[kind])
    answer = good(capsys, kind, "change-view", id="7")
    assert answer["head_sha"] == "head7" and answer["base_sha"] == "base7"
    assert answer["head_ref"] == {"github": "pull/7/head", "gitlab": "merge-requests/7/head"}[kind]
    assert answer["cross_fork"] is True
    assert answer["blob_base"] == {"github": "https://github.com/fork/widget/blob",
                                   "gitlab": "https://gitlab.example/fork/widget/-/blob"}[kind]


@pytest.mark.parametrize("kind", KINDS)
def test_change_view_has_the_same_shape_and_words_on_both_forges(capsys, tools, kind):
    tools.on(TOOL[kind], *VIEW[kind], answer=CHANGE_META[kind])
    answer = good(capsys, kind, "change-view", id="7")
    assert set(answer) == {"ok", "id", "url", "title", "draft", "state", "source", "target", "author", "head_sha",
                           "base_sha", "head_ref", "cross_fork", "blob_base", "pipeline"}
    assert answer["state"] == "opened" and answer["draft"] is True and answer["id"] == "7"


@pytest.mark.parametrize("state,word", [("OPEN", "opened"), ("MERGED", "merged"), ("CLOSED", "closed")])
def test_github_state_words_are_the_gitlab_words(capsys, tools, state, word):
    tools.on("gh", "pr", "view", answer={"number": 7, "state": state})
    assert good(capsys, "github", "change-view", id="7")["state"] == word


@pytest.mark.parametrize("title", ["Draft: x", "WIP: x"])
def test_gitlab_draft_title_prefix_counts(capsys, tools, title):
    tools.on("glab", "mr", "view", answer={"iid": 7, "title": title})
    assert good(capsys, "gitlab", "change-view", id="7")["draft"] is True


@pytest.mark.parametrize("kind,stderr", [("github", "no pull requests found for branch x"),
                                         ("gitlab", "no open merge request available for x"),
                                         ("gitlab", "404 Not Found")])
def test_a_missing_change_is_not_found(capsys, tools, kind, stderr):
    tools.on(TOOL[kind], *VIEW[kind], answer=(1, "", stderr))
    error = refused(capsys, kind, "change-view", id="x")
    assert error["code"] == "not-found" and stderr in error["reason"]


def test_gitlab_change_view_resolves_the_source_project_blob_prefix(capsys, tools):
    tools.on("glab", "mr", "view", answer={"iid": 7, "sha": "head7", "diff_refs": {"base_sha": "base7"},
                                           "source_project_id": 8, "target_project_id": 9})
    tools.on("glab", "api", "projects/8", answer={"web_url": "https://gitlab.example/fork/widget"})
    assert good(capsys, "gitlab", "change-view", id="7")["blob_base"] == "https://gitlab.example/fork/widget/-/blob"


def _two_commit_repo(path: Path) -> tuple[str, str]:
    def git(*args):
        return subprocess.run(["git", "-C", str(path), *args], check=True, capture_output=True, text=True).stdout.strip()
    path.mkdir()
    git("init", "-q")
    git("config", "user.email", "t@example.invalid")
    git("config", "user.name", "t")
    (path / "f.txt").write_text("one\n", encoding="utf-8")
    git("add", "f.txt")
    git("commit", "-qm", "base")
    base = git("rev-parse", "HEAD")
    (path / "f.txt").write_text("one\ntwo\n", encoding="utf-8")
    git("commit", "-qam", "head")
    return base, git("rev-parse", "HEAD")


def test_github_change_diff_builds_the_diff_from_local_commits(capsys, tools, tmp_path, monkeypatch):
    base, head = _two_commit_repo(tmp_path / "repo")
    monkeypatch.chdir(tmp_path / "repo")
    tools.on("gh", "pr", "view", answer={"baseRefOid": base, "headRefOid": head})
    tools.on("gh", "pr", "diff", answer=(1, "", "stream error"))
    answer = good(capsys, "github", "change-diff", id="7")
    assert "diff --git a/f.txt b/f.txt" in answer["diff"] and "\n+two\n" in answer["diff"]
    assert answer["lines"] == answer["diff"].count("\n")


def test_github_change_diff_falls_back_to_the_forge_without_the_commits(capsys, tools, tmp_path, monkeypatch):
    base, _ = _two_commit_repo(tmp_path / "repo")
    monkeypatch.chdir(tmp_path / "repo")
    tools.on("gh", "pr", "view", answer={"baseRefOid": base, "headRefOid": "f" * 40})
    tools.on("gh", "pr", "diff", answer="forge diff body\n")
    assert good(capsys, "github", "change-diff", id="7")["diff"] == "forge diff body\n"


def test_github_change_diff_reports_the_forge_error_text(capsys, tools, tmp_path, monkeypatch):
    base, _ = _two_commit_repo(tmp_path / "repo")
    monkeypatch.chdir(tmp_path / "repo")
    tools.on("gh", "pr", "view", answer={"baseRefOid": base, "headRefOid": "f" * 40})
    tools.on("gh", "pr", "diff", answer=(1, "diff text", "stream CANCEL"))
    assert refused(capsys, "github", "change-diff", id="7")["reason"] == "stream CANCEL"


def test_gitlab_change_diff_keeps_the_text(capsys, tools):
    tools.on("glab", "mr", "diff", answer="diff é\n")
    answer = good(capsys, "gitlab", "change-diff", id="7")
    assert answer == {"ok": True, "diff": "diff é\n", "lines": 1, "bytes": 7}
    assert "--color=never" in tools.calls[0][1]


def posted(tools, tool="gh"):
    call_ = [c for c in tools.calls if c[0] == tool and c[1][:3] == ["api", "-X", "POST"]][-1]
    return call_[1], json.loads(call_[2])


def test_github_change_comment_maps_old_side_and_returns_ids(capsys, tools):
    github_project(tools)
    tools.on("gh", "api", "-X", answer={"id": 41, "html_url": "https://github.example/c/41"})
    answer = good(capsys, "github", "change-comment", id="7", text="x", old_path="before.txt", new_path="after.txt",
                  old_line=8, side="old")
    assert answer == {"ok": True, "inline": True, "thread": "41", "comment": "41", "url": "https://github.example/c/41"}
    args, sent = posted(tools)
    assert "repos/acme/widget/pulls/7/comments" in args
    assert sent == {"body": "x", "commit_id": "head7", "path": "before.txt", "line": 8, "side": "LEFT"}


@pytest.mark.parametrize("side", ["new", "context"])
def test_github_change_comment_maps_new_and_context_to_right(capsys, tools, side):
    github_project(tools)
    tools.on("gh", "api", "-X", answer={"id": 41, "html_url": "u"})
    good(capsys, "github", "change-comment", id="7", text="x", old_path="before.txt", new_path="after.txt",
         line=9, old_line=8, side=side)
    _, sent = posted(tools)
    assert (sent["path"], sent["line"], sent["side"]) == ("after.txt", 9, "RIGHT")


def test_github_plain_comment_uses_issue_comment_api(capsys, tools):
    github_project(tools)
    tools.on("gh", "api", "-X", answer={"id": 42, "html_url": "https://github.example/n/42"})
    assert good(capsys, "github", "change-comment", id="7", text="plain") == {
        "ok": True, "inline": False, "thread": "", "comment": "42", "url": "https://github.example/n/42"}
    args, sent = posted(tools)
    assert "repos/acme/widget/issues/7/comments" in args and sent == {"body": "plain"}


def test_github_comment_text_reaches_gh_on_stdin_never_on_the_command_line(capsys, tools):
    github_project(tools)
    tools.on("gh", "api", "-X", answer={"id": 42})
    good(capsys, "github", "change-comment", id="7", text="secret é text")
    args, _ = posted(tools)
    assert not any("secret" in arg for arg in args)


REJECTED = {"github": "gh: Validation Failed (HTTP 422): line must be part of the diff",
            "gitlab": "glab: 400 Bad Request: line_code can't be blank"}
INLINE_PATH = {"github": "pulls/7/comments", "gitlab": "merge_requests/7/discussions"}


def reject_the_position(tools, kind):
    """The forge refuses the post at a line, and takes a plain note."""
    def answer(args, _):
        if any(INLINE_PATH[kind] in arg for arg in args):
            return (1, "", REJECTED[kind])
        return {"id": 90, "html_url": "https://forge.example/n/90", "web_url": "https://forge.example/n/90"}
    {"github": github_project, "gitlab": gitlab_project}[kind](tools)
    tools.on(TOOL[kind], "api", "-X", answer=answer)


@pytest.mark.parametrize("kind", KINDS)
def test_a_rejected_position_with_require_inline_leaves_no_comment(capsys, tools, kind):
    reject_the_position(tools, kind)
    error = refused(capsys, kind, "change-comment", id="7", text="x", file="a.txt", line=9, require_inline=True)
    assert error["code"] == "position-rejected"
    assert len([call_ for call_ in tools.calls if call_[1][:3] == ["api", "-X", "POST"]]) == 1


@pytest.mark.parametrize("kind", KINDS)
def test_a_rejected_position_without_require_inline_lands_as_a_plain_note(capsys, tools, kind):
    reject_the_position(tools, kind)
    answer = good(capsys, kind, "change-comment", id="7", text="x", file="a.txt", line=9)
    assert answer["inline"] is False and answer["thread"] == "" and answer["comment"] == "90"
    assert answer["url"] == "https://forge.example/n/90" and "plain note" in answer["reason"]


@pytest.mark.parametrize("kind", KINDS)
def test_a_forge_failure_at_a_line_is_not_a_rejected_position(capsys, tools, kind):
    {"github": github_project, "gitlab": gitlab_project}[kind](tools)
    tools.on(TOOL[kind], "api", "-X", answer=(1, "", "HTTP 500: server error"))
    assert refused(capsys, kind, "change-comment", id="7", text="x", file="a.txt", line=9)["code"] == "server-error"


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("fields", [
    {"file": "a.txt"},
    {"file": "a.txt", "line": "many"},
    {"file": "a.txt", "line": 0},
    {"file": "a.txt", "side": "old", "line": 9},
    {"file": "a.txt", "side": "context", "line": 9},
    {"file": "a.txt", "side": "left", "line": 9},
])
def test_a_bad_position_is_refused_before_anything_is_posted(capsys, tools, kind, fields):
    assert refused(capsys, kind, "change-comment", id="7", text="x", **fields)["code"] == "bad-position"
    assert tools.calls == []


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("verb,payload", [
    ("change-view", {}), ("change-comment", {"id": "7"}), ("change-create-draft", {}), ("change-update-body", {"id": "7"}),
    ("change-view", {"id": "--web"}),
])
def test_missing_or_flag_like_arguments_are_bad_payload(capsys, tools, kind, verb, payload):
    code, answer = call(capsys, kind, verb, **payload)
    assert code == 2 and answer["error"]["code"] == "bad-payload" and tools.calls == []


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("body", ["", "   \n", None, 7])
def test_change_update_body_never_wipes_the_body(capsys, tools, kind, body):
    code, answer = call(capsys, kind, "change-update-body", id="7", body=body)
    assert code == 2 and answer["error"]["code"] == "bad-payload" and tools.calls == []


def test_github_change_update_body_goes_on_stdin(capsys, tools):
    tools.on("gh", "pr", "view", answer={"isDraft": True})
    tools.on("gh", "pr", "edit", answer="")
    assert good(capsys, "github", "change-update-body", id="7", body="new é") == {
        "ok": True, "id": "7", "was_draft": "true", "draft_restored": False}
    edit = tools.calls_to("gh", "pr", "edit")[0]
    assert edit[2] == "new é" and "--body-file" in edit[1]


@pytest.mark.parametrize("kind", KINDS)
def test_a_failed_first_read_of_the_draft_flag_writes_nothing(capsys, tools, kind):
    tools.on(TOOL[kind], *VIEW[kind], answer=lambda *_: (1, "", "boom"))
    assert refused(capsys, kind, "change-update-body", id="7", body="new")["code"] == "cli-failed"
    assert all(call_[1][1] != ("edit" if kind == "github" else "update") for call_ in tools.calls)


def test_gitlab_a_failed_read_after_the_write_sets_the_flag_again(capsys, tools):
    views = iter([{"iid": 7, "draft": True}, (1, "", "boom")])
    tools.on("glab", "mr", "view", answer=lambda *_: next(views))
    tools.on("glab", "mr", "update", answer="")
    assert good(capsys, "gitlab", "change-update-body", id="7", body="new")["draft_restored"] is True
    assert ["mr", "update", "7", "--draft"] in [call_[1] for call_ in tools.calls]


def test_gitlab_change_update_body_restores_the_draft_flag(capsys, tools):
    views = iter([{"iid": 7, "draft": True}, {"iid": 7, "draft": False}])
    tools.on("glab", "mr", "view", answer=lambda *_: next(views))
    tools.on("glab", "mr", "update", answer="")
    assert good(capsys, "gitlab", "change-update-body", id="7", body="new") == {
        "ok": True, "id": "7", "was_draft": "true", "draft_restored": True}
    assert ["mr", "update", "7", "--draft"] in [call_[1] for call_ in tools.calls]
    assert ["mr", "update", "7", "--description", "new"] in [call_[1] for call_ in tools.calls]


def test_gitlab_a_failed_draft_restore_is_refused(capsys, tools):
    views = iter([{"iid": 7, "draft": True}, {"iid": 7, "draft": False}])
    tools.on("glab", "mr", "view", answer=lambda *_: next(views))
    tools.on("glab", "mr", "update", answer=lambda args, _: (1, "", "nope") if "--draft" in args else "")
    error = refused(capsys, "gitlab", "change-update-body", id="7", body="new")
    assert error["code"] == "draft-lost" and error["id"] == "7" and "glab mr update 7 --draft" in error["reason"]


def test_gitlab_a_kept_draft_flag_needs_no_restore(capsys, tools):
    tools.on("glab", "mr", "view", answer={"iid": 7, "draft": True})
    tools.on("glab", "mr", "update", answer="")
    assert good(capsys, "gitlab", "change-update-body", id="7", body="new")["draft_restored"] is False
    assert not any("--draft" in call_[1] for call_ in tools.calls)


def test_gitlab_change_update_body_leaves_a_ready_change_ready(capsys, tools):
    tools.on("glab", "mr", "view", answer={"iid": 7, "draft": False})
    tools.on("glab", "mr", "update", answer="")
    assert good(capsys, "gitlab", "change-update-body", id="7", body="new")["draft_restored"] is False
    assert not any("--draft" in call_[1] for call_ in tools.calls)


def test_gitlab_context_comment_sends_both_lines_and_paths(capsys, tools):
    gitlab_project(tools)
    tools.on("glab", "api", "-X", answer={"id": "discussion-1", "notes": [
        {"id": 51, "type": "DiffNote", "web_url": "https://gitlab.example/n/51"}]})
    assert good(capsys, "gitlab", "change-comment", id="7", text="x", old_path="before.txt", new_path="after.txt",
                line=9, old_line=8, side="context") == {
        "ok": True, "inline": True, "thread": "discussion-1", "comment": "51", "url": "https://gitlab.example/n/51"}
    args, sent = posted(tools, "glab")
    assert "projects/:id/merge_requests/7/discussions" in args and "--input" in args
    position = sent["position"]
    assert position["old_path"] == "before.txt" and position["new_path"] == "after.txt"
    assert position["old_line"] == 8 and position["new_line"] == 9
    assert (position["base_sha"], position["start_sha"], position["head_sha"]) == ("base", "start", "head")


@pytest.mark.parametrize("side,present,absent", [("new", "new_line", "old_line"), ("old", "old_line", "new_line")])
def test_gitlab_change_comment_maps_each_one_sided_line(capsys, tools, side, present, absent):
    gitlab_project(tools)
    tools.on("glab", "api", "-X", answer={"id": "d", "notes": [{"id": 51, "type": "DiffNote"}]})
    good(capsys, "gitlab", "change-comment", id="7", text="x", old_path="before.txt", new_path="after.txt",
         line=9, old_line=8, side=side)
    position = posted(tools, "glab")[1]["position"]
    assert present in position and absent not in position


def test_gitlab_payload_repo_reaches_the_api_path(capsys, tools):
    gitlab_project(tools)
    tools.on("glab", "api", "-X", answer={"id": 55})
    good(capsys, "gitlab", "change-comment", id="7", text="x", repo="acme/widget")
    args, _ = posted(tools, "glab")
    assert "projects/acme%2Fwidget/merge_requests/7/notes" in args


def test_gitlab_required_inline_degradation_is_deleted(capsys, tools):
    gitlab_project(tools)
    tools.on("glab", "api", "-X", "POST", answer={"id": "discussion-1", "notes": [{"id": 52, "type": None}]})
    tools.on("glab", "api", "-X", "DELETE", answer="{}")
    error = refused(capsys, "gitlab", "change-comment", id="7", text="x", file="a.txt", line=9, require_inline=True)
    assert error["code"] == "position-rejected" and error["cleaned"] is True
    assert "/notes/52" in tools.calls_to("glab", "api", "-X", "DELETE")[0][1][3]


def test_gitlab_required_inline_cleanup_failure_reports_orphan_note(capsys, tools):
    gitlab_project(tools)
    tools.on("glab", "api", "-X", "POST", answer={"id": "discussion-1", "notes": [{"id": 53, "type": None}]})
    tools.on("glab", "api", "-X", "DELETE", answer=(1, "", "nope"))
    error = refused(capsys, "gitlab", "change-comment", id="7", text="x", file="a.txt", line=9, require_inline=True)
    assert error == {"code": "position-rejected", "note": "53",
                     "reason": "the position degraded to a plain note and cleanup failed"}


def test_gitlab_degraded_position_reports_a_written_plain_note(capsys, tools):
    gitlab_project(tools)
    tools.on("glab", "api", "-X", answer={"id": "discussion-1", "notes": [
        {"id": 54, "type": None, "web_url": "https://gitlab.example/n/54"}]})
    answer = good(capsys, "gitlab", "change-comment", id="7", text="x", file="a.txt", line=9)
    assert answer["inline"] is False and answer["thread"] == "" and answer["comment"] == "54" and "reason" in answer


def test_gitlab_plain_comment_builds_a_canonical_note_url(capsys, tools):
    gitlab_project(tools)
    tools.on("glab", "api", "-X", answer={"id": 55, "body": "x"})
    assert good(capsys, "gitlab", "change-comment", id="7", text="x") == {
        "ok": True, "inline": False, "thread": "", "comment": "55",
        "url": "https://gitlab.example/acme/widget/-/merge_requests/7#note_55"}


@pytest.mark.parametrize("kind", KINDS)
def test_a_comment_answer_without_an_id_is_a_bad_answer(capsys, tools, kind):
    {"github": github_project, "gitlab": gitlab_project}[kind](tools)
    tools.on(TOOL[kind], "api", "-X", answer={})
    assert refused(capsys, kind, "change-comment", id="7", text="x")["code"] == "bad-answer"


def test_gitlab_thread_list_exposes_locator_url_and_note_times(capsys, tools):
    gitlab_project(tools)
    tools.on("glab", "api", "graphql", answer=gitlab_edits(61))
    tools.on("glab", "api", "--paginate", answer=[{"id": "d1", "notes": [{
        "id": 61, "type": "DiffNote", "resolved": False, "body": "x", "created_at": "2025-03-01", "updated_at": "2025-03-02",
        "web_url": "https://gitlab.example/n/61",
        "position": {"new_line": 5, "old_line": 4, "old_path": "old.txt", "new_path": "new.txt"}}]}])
    thread = good(capsys, "gitlab", "thread-list", id="7")["threads"][0]
    assert {key: thread[key] for key in ("side", "line", "old_line", "old_path", "new_path", "url")} == {
        "side": "context", "line": 5, "old_line": 4, "old_path": "old.txt", "new_path": "new.txt",
        "url": "https://gitlab.example/n/61"}
    note = thread["notes"][0]
    assert (note["created_at"], note["updated_at"], note["edited"]) == ("2025-03-01", "2025-03-02", False)


def test_github_thread_list_joins_graphql_resolution(capsys, tools):
    github_project(tools)
    tools.on("gh", "api", "graphql", answer=github_threads((71, True)))
    tools.on("gh", "api", "--paginate", answer=[
        {"id": 71, "body": "root", "path": "a.txt", "line": 5, "original_line": 4, "side": "RIGHT", "created_at": "2025-03-01",
         "updated_at": "2025-03-02", "html_url": "https://github.example/c/71", "user": {"login": "a"}}])
    thread = good(capsys, "github", "thread-list", id="7")["threads"][0]
    assert thread["id"] == "71" and thread["resolved"] is True
    assert thread["side"] == "new" and thread["line"] == 5
    assert thread["new_path"] == "a.txt" and thread["url"] == "https://github.example/c/71"
    assert thread["notes"][0]["created_at"] == "2025-03-01"


def test_github_thread_list_uses_all_graphql_pages(capsys, tools):
    github_project(tools)
    tools.on("gh", "api", "graphql", answer=json.dumps(github_threads((71, False))) + "\n" + json.dumps(github_threads((72, True))))
    tools.on("gh", "api", "--paginate", answer=[
        {"id": 71, "body": "one", "path": "a.txt", "line": 5, "side": "RIGHT", "user": {"login": "a"}},
        {"id": 72, "body": "two", "path": "b.txt", "line": 6, "side": "RIGHT", "user": {"login": "a"}}])
    assert [(t["id"], t["resolved"]) for t in good(capsys, "github", "thread-list", id="7")["threads"]] == [
        ("71", False), ("72", True)]


@pytest.mark.parametrize("comment,expected", [
    ({"line": 5, "original_line": 4, "side": "RIGHT"}, {"line": 5, "old_line": None}),
    ({"line": 5, "original_line": 4, "side": "LEFT"}, {"line": None, "old_line": 5}),
    ({"line": None, "original_line": 4, "side": "LEFT"}, {"line": None, "old_line": 4}),
])
def test_github_thread_list_normalizes_lines_by_side(capsys, tools, comment, expected):
    github_project(tools)
    tools.on("gh", "api", "graphql", answer=github_threads((71, False)))
    tools.on("gh", "api", "--paginate", answer=[{"id": 71, "body": "root", "path": "a.txt", "user": {"login": "a"}, **comment}])
    thread = good(capsys, "github", "thread-list", id="7")["threads"][0]
    assert {"line": thread["line"], "old_line": thread["old_line"]} == expected


def test_github_a_root_comment_without_a_thread_is_refused(capsys, tools):
    github_project(tools)
    tools.on("gh", "api", "graphql", answer=github_threads())
    tools.on("gh", "api", "--paginate", answer=[{"id": 71, "body": "root"}])
    assert "71" in refused(capsys, "github", "thread-list", id="7")["reason"]


def ci_answer(kind, status):
    if kind == "gitlab":
        return {"iid": 7, "head_pipeline": {"status": status, "web_url": "https://gitlab.example/p/1"}}
    return {"number": 7, "url": "https://github.example/pull/7", "statusCheckRollup": [{"conclusion": status}]}


RUNNING_WORD = {"gitlab": "running", "github": "IN_PROGRESS"}


@pytest.fixture
def no_sleep(monkeypatch):
    slept = []
    monkeypatch.setattr(common.time, "sleep", slept.append)
    return slept


@pytest.mark.parametrize("kind", KINDS)
def test_ci_wait_with_no_budget_still_reads_once(capsys, tools, no_sleep, kind):
    tools.on(TOOL[kind], *VIEW[kind], answer=ci_answer(kind, RUNNING_WORD[kind]))
    answer = good(capsys, kind, "ci-wait", id="7", budget=0)
    assert answer["status"] == "running" and "budget" in answer["reason"]
    assert len(tools.calls) == 1 and no_sleep == []


@pytest.mark.parametrize("kind,word", [("gitlab", "success"), ("github", "SUCCESS")])
def test_ci_wait_with_no_budget_answers_a_final_status(capsys, tools, no_sleep, kind, word):
    tools.on(TOOL[kind], *VIEW[kind], answer=ci_answer(kind, word))
    assert good(capsys, kind, "ci-wait", id="7", budget=0)["status"] == "success"


@pytest.mark.parametrize("kind", KINDS)
def test_ci_wait_reads_once_more_when_the_budget_ends_and_never_sleeps_past_it(capsys, tools, no_sleep, kind):
    reads = iter([ci_answer(kind, RUNNING_WORD[kind]), ci_answer(kind, {"gitlab": "failed", "github": "FAILURE"}[kind])])
    tools.on(TOOL[kind], *VIEW[kind], answer=lambda *_: next(reads))
    answer = good(capsys, kind, "ci-wait", id="7", budget=100, interval=180)
    assert answer["status"] == "failed" and answer["elapsed"] == 100 and no_sleep == [100]


@pytest.mark.parametrize("kind", KINDS)
def test_ci_wait_spends_the_budget_then_stops(capsys, tools, no_sleep, kind):
    tools.on(TOOL[kind], *VIEW[kind], answer=ci_answer(kind, RUNNING_WORD[kind]))
    answer = good(capsys, kind, "ci-wait", id="7", budget=3, interval=1)
    assert answer["status"] == "running" and answer["elapsed"] == 3 and no_sleep == [1, 1, 1]


@pytest.mark.parametrize("kind", KINDS)
def test_ci_wait_with_no_budget_and_no_status_is_unreadable(capsys, tools, no_sleep, kind):
    tools.on(TOOL[kind], *VIEW[kind], answer="")
    assert refused(capsys, kind, "ci-wait", id="7", budget=0)["code"] == "unreadable"
    assert len(tools.calls) == 1


def test_ci_wait_on_a_change_with_no_checks_is_unreadable_when_the_budget_ends(capsys, tools, no_sleep):
    tools.on("glab", "mr", "view", answer={"iid": 7})
    assert refused(capsys, "gitlab", "ci-wait", id="7", budget=1, interval=1)["code"] == "unreadable"
    assert no_sleep == [1]


@pytest.mark.parametrize("kind", KINDS)
def test_ci_wait_reports_an_unreadable_pipeline(capsys, tools, no_sleep, kind):
    tools.on(TOOL[kind], *VIEW[kind], answer="")
    error = refused(capsys, kind, "ci-wait", id="7", budget=30, interval=1)
    assert error["code"] == "unreadable" and len(no_sleep) == 2


def test_ci_wait_a_good_read_resets_the_error_count(capsys, tools, no_sleep):
    reads = iter(["", "", ci_answer("gitlab", "running"), "", "", ci_answer("gitlab", "success")])
    tools.on("glab", "mr", "view", answer=lambda *_: next(reads))
    assert good(capsys, "gitlab", "ci-wait", id="7", budget=30, interval=1)["status"] == "success"


@pytest.mark.parametrize("kind,conclusion", [("gitlab", "success"), ("github", "SUCCESS")])
def test_ci_wait_reports_success(capsys, tools, no_sleep, kind, conclusion):
    tools.on(TOOL[kind], *VIEW[kind], answer=ci_answer(kind, conclusion))
    assert good(capsys, kind, "ci-wait", id="7", budget=30, interval=1)["status"] == "success"


@pytest.mark.parametrize("kind,conclusion,status", [("gitlab", "failed", "failed"), ("github", "FAILURE", "failed"),
                                                    ("gitlab", "canceled", "canceled"), ("github", "CANCELLED", "canceled")])
def test_ci_wait_a_failed_run_is_a_readable_answer(capsys, tools, no_sleep, kind, conclusion, status):
    tools.on(TOOL[kind], *VIEW[kind], answer=ci_answer(kind, conclusion))
    assert good(capsys, kind, "ci-wait", id="7", budget=30, interval=1)["status"] == status


def test_ci_wait_a_zero_interval_still_advances_the_clock(capsys, tools, no_sleep):
    tools.on("glab", "mr", "view", answer=ci_answer("gitlab", "running"))
    assert good(capsys, "gitlab", "ci-wait", id="7", budget=2, interval=0)["elapsed"] == 2


def test_ci_wait_bad_numbers_are_bad_payload(capsys, tools):
    code, answer = call(capsys, "gitlab", "ci-wait", id="7", budget="soon")
    assert code == 2 and answer["error"]["code"] == "bad-payload"


def test_ci_wait_stops_at_once_when_the_command_is_absent(capsys, monkeypatch, no_sleep):
    from tracker import shell
    monkeypatch.setattr(shell.shutil, "which", lambda _: None)
    assert refused(capsys, "gitlab", "ci-wait", id="7", budget=30, interval=1)["code"] == "unavailable"
    assert no_sleep == []


@pytest.mark.parametrize("kind,checks,status", [
    ("github", [], ""),
    ("github", [{"conclusion": "SUCCESS"}, {"status": "IN_PROGRESS"}], "running"),
    ("github", [{"conclusion": "SUCCESS"}, {"conclusion": "NEUTRAL"}], "success"),
    ("github", [{"conclusion": "FAILURE"}, {"status": "IN_PROGRESS"}], "failed"),
    ("github", [{"conclusion": "SUCCESS"}, {"conclusion": "SKIPPED"}], "success"),
    ("github", [{"state": "SUCCESS"}], "success"),
    ("github", [{"state": "ERROR"}], "failed"),
    ("github", [{"conclusion": "STALE"}], "failed"),
    ("github", [{"conclusion": "ACTION_REQUIRED"}], "running"),
    ("github", [{"state": "EXPECTED"}], "running"),
    ("github", [{"conclusion": "A_NEW_WORD"}], "running"),
    ("github", [{"conclusion": "SUCCESS"}, {"state": "PENDING"}], "running"),
    ("github", [{"conclusion": "CANCELLED"}, {"conclusion": "SUCCESS"}], "canceled"),
])
def test_github_rollup(capsys, tools, kind, checks, status):
    tools.on("gh", "pr", "view", answer={"number": 7, "url": "u", "statusCheckRollup": checks})
    assert good(capsys, kind, "ci-status", id="7") == {"ok": True, "status": status, "url": "u"}


@pytest.mark.parametrize("word,status", [
    ("success", "success"), ("skipped", "success"), ("failed", "failed"), ("canceled", "canceled"),
    ("created", "running"), ("waiting_for_resource", "running"), ("preparing", "running"), ("waiting_for_callback", "running"),
    ("pending", "running"), ("running", "running"), ("canceling", "running"), ("manual", "running"), ("scheduled", "running"),
    ("a_new_word", "running"), ("", ""),
])
def test_gitlab_pipeline_words_become_the_contract_words(capsys, tools, word, status):
    tools.on("glab", "mr", "view", answer=ci_answer("gitlab", word))
    assert good(capsys, "gitlab", "ci-status", id="7")["status"] == status
    assert good(capsys, "gitlab", "change-view", id="7")["pipeline"] == {"status": status}


@pytest.mark.parametrize("word,status", [("skipped", "success"), ("failed", "failed"), ("canceled", "canceled")])
def test_gitlab_ci_wait_ends_on_a_final_contract_word(capsys, tools, no_sleep, word, status):
    tools.on("glab", "mr", "view", answer=ci_answer("gitlab", word))
    assert good(capsys, "gitlab", "ci-wait", id="7", budget=30, interval=1)["status"] == status
    assert no_sleep == []


def test_gitlab_ci_wait_keeps_waiting_on_a_manual_pipeline(capsys, tools, no_sleep):
    tools.on("glab", "mr", "view", answer=ci_answer("gitlab", "manual"))
    assert good(capsys, "gitlab", "ci-wait", id="7", budget=2, interval=1)["status"] == "running"


def test_gitlab_ci_status_reads_the_head_pipeline(capsys, tools):
    tools.on("glab", "mr", "view", answer=ci_answer("gitlab", "running"))
    assert good(capsys, "gitlab", "ci-status", id="7") == {"ok": True, "status": "running", "url": "https://gitlab.example/p/1"}


@pytest.mark.parametrize("kind,url", [("gitlab", "https://gitlab.example/x/y/-/merge_requests/7"), ("github", "https://github.com/x/y/pull/7")])
def test_change_create_draft_passes_the_assignee_when_set(capsys, tools, kind, url):
    verb = ("mr", "create") if kind == "gitlab" else ("pr", "create")
    tools.on(TOOL[kind], *verb, answer=f"created\n{url}\n")
    answer = good(capsys, kind, "change-create-draft", title="t", target="main", source="b", body="x", assignee="octocat")
    assert answer == {"ok": True, "url": url, "id": "7", "draft": True}
    args = tools.calls[0][1]
    assert args[args.index("--assignee") + 1] == "octocat" and "--draft" in args
    assert args[args.index("--title") + 1] == "t"
    target, source = {"github": ("--base", "--head"), "gitlab": ("--target-branch", "--source-branch")}[kind]
    assert args[args.index(target) + 1] == "main" and args[args.index(source) + 1] == "b"


def test_github_change_create_draft_sends_the_body_on_stdin(capsys, tools):
    tools.on("gh", "pr", "create", answer="https://github.com/x/y/pull/7")
    good(capsys, "github", "change-create-draft", title="t", body="the body")
    assert tools.calls[0][2] == "the body" and "--body-file" in tools.calls[0][1]


def test_gitlab_change_create_draft_sends_the_description(capsys, tools):
    tools.on("glab", "mr", "create", answer="https://gitlab.example/x/y/-/merge_requests/7")
    good(capsys, "gitlab", "change-create-draft", title="t", body="the body")
    args = tools.calls[0][1]
    assert args[args.index("--description") + 1] == "the body"


@pytest.mark.parametrize("kind,url", [("gitlab", "https://gitlab.example/x/y/-/merge_requests/7"), ("github", "https://github.com/x/y/pull/7")])
def test_change_create_draft_omits_the_assignee_when_unset(capsys, tools, kind, url):
    verb = ("mr", "create") if kind == "gitlab" else ("pr", "create")
    tools.on(TOOL[kind], *verb, answer=url)
    good(capsys, kind, "change-create-draft", title="t", body="x")
    assert "--assignee" not in tools.calls[0][1]


@pytest.mark.parametrize("kind", KINDS)
def test_change_create_draft_joins_a_reviewer_list(capsys, tools, kind):
    verb = ("mr", "create") if kind == "gitlab" else ("pr", "create")
    url = "https://x.test/a/-/merge_requests/7" if kind == "gitlab" else "https://x.test/a/pull/7"
    tools.on(TOOL[kind], *verb, answer=url)
    good(capsys, kind, "change-create-draft", title="t", reviewer=["a", "b"])
    args = tools.calls[0][1]
    assert args[args.index("--reviewer") + 1] == "a,b"


@pytest.mark.parametrize("kind", KINDS)
def test_change_create_draft_without_a_url_is_a_bad_answer(capsys, tools, kind):
    verb = ("mr", "create") if kind == "gitlab" else ("pr", "create")
    tools.on(TOOL[kind], *verb, answer="done")
    assert refused(capsys, kind, "change-create-draft", title="t")["code"] == "bad-answer"


@pytest.mark.parametrize("kind", KINDS)
def test_change_ready(capsys, tools, kind):
    tools.on(TOOL[kind], "pr" if kind == "github" else "mr", answer="")
    assert good(capsys, kind, "change-ready", id="7") == {"ok": True, "id": "7", "draft": False}
    assert {"github": "ready", "gitlab": "--ready"}[kind] in tools.calls[0][1]


@pytest.mark.parametrize("kind", KINDS)
def test_auth_status(capsys, tools, kind):
    tools.on(TOOL[kind], "auth", "status", answer="logged in")
    tools.on(TOOL[kind], "api", "user", answer={{"github": "login", "gitlab": "username"}[kind]: "me"})
    assert good(capsys, kind, "auth-status") == {"ok": True, "authenticated": True, "user": "me"}


@pytest.mark.parametrize("kind", KINDS)
def test_auth_status_not_logged_in_is_an_answer_not_a_refusal(capsys, tools, kind):
    tools.on(TOOL[kind], "auth", "status", answer=(1, "", "not logged in"))
    answer = good(capsys, kind, "auth-status")
    assert answer["authenticated"] is False and "auth login" in answer["reason"]


@pytest.mark.parametrize("kind", KINDS)
def test_payload_repo_reaches_the_command(capsys, tools, kind):
    tools.on(TOOL[kind], *VIEW[kind], answer=CHANGE_META[kind])
    good(capsys, kind, "change-view", id="7", repo="o/r")
    args = tools.calls[0][1]
    assert args[args.index("--repo" if kind == "github" else "-R") + 1] == "o/r"


@pytest.mark.parametrize("kind", KINDS)
def test_an_answer_keeps_text_outside_the_console_encoding(tools, capsys, kind):
    tools.on(TOOL[kind], *VIEW[kind], answer={**CHANGE_META[kind], "title": "emoji \U0001f389"})
    assert good(capsys, kind, "change-view", id="7")["title"] == "emoji \U0001f389"
