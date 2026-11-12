"""comment-put: 1 proof comment with pictures on Jira and on GitHub issues, keyed by the preview receipt."""

from __future__ import annotations

import json

import pytest

from port_fakes import FakeResp, http_error
from tracker import envelope, github_issues, jira

RECEIPT = "ab" * 32
SHORT = RECEIPT[:8]
UUID = "0123abcd-4567-89ab-cdef-0123456789ab"
BODY = f"afkv2 proof v1 {RECEIPT}\nVR-001 · login · high · pass · The page showed the name.\nHead abc"
META = ("GET", "/rest/api/3/attachment/meta")
COMMENTS = ("GET", "/rest/api/3/issue/PROJ-1/comment")
ATTACHED = ("GET", "/rest/api/3/issue/PROJ-1?")
UPLOAD = ("POST", "/rest/api/3/issue/PROJ-1/attachments")
MEDIA = ("GET", "/rest/api/3/attachment/content/9001")
POST = ("POST", "/rest/api/3/issue/PROJ-1/comment")


@pytest.fixture
def picture(tmp_path):
    def make(name="login.png", size=None, data=b"\x89PNG one"):
        path = tmp_path / name
        if size is None:
            path.write_bytes(data)
        else:
            with open(path, "wb") as file:
                file.truncate(size)
        return str(path)
    return make


def jira_routes(comments=(), attachments=(), limit=10_000_000):
    return {META: FakeResp({"enabled": True, "uploadLimit": limit}),
            COMMENTS: FakeResp({"comments": list(comments), "startAt": 0, "maxResults": 100, "total": len(comments)}),
            ATTACHED: FakeResp({"fields": {"attachment": list(attachments)}}),
            UPLOAD: FakeResp(b'[{"id":"9001"}]'),
            MEDIA: http_error(303, location=f"https://api.media.atlassian.com/file/{UUID}/binary"),
            POST: FakeResp({"id": "10500"})}


def adf_comment(first_line, comment_id="10400"):
    return {"id": comment_id, "body": {"type": "doc", "version": 1, "content": [
        {"type": "paragraph", "content": [{"type": "text", "text": first_line}]}]}}


def refused(call, payload):
    with pytest.raises(envelope.Refusal) as caught:
        call(payload)
    return caught.value


# Jira


def test_jira_attaches_the_pictures_then_posts_one_adf_comment_that_links_them(fake_jira, picture):
    client = fake_jira(jira_routes())
    answer = jira.comment_put({"key": "PROJ-1", "body": BODY, "pictures": [picture()], "receipt": RECEIPT})
    name = f"afkv2-proof-{SHORT}-1.png"
    assert answer == {"ok": True, "comment_id": "10500", "url": "https://n.test/browse/PROJ-1?focusedCommentId=10500",
                      "attached": [name], "posted": True}
    writes = client.writes()
    assert [(method, path) for method, path, _ in writes] == [UPLOAD, POST]
    assert f'filename="{name}"'.encode() in writes[0][2]
    document = json.loads(writes[1][2])["body"]
    assert jira.node_text(document["content"][0]) == f"afkv2 proof v1 {RECEIPT}"
    media = [node for node in document["content"] if node["type"] == "mediaSingle"]
    assert media[0]["content"][0]["attrs"]["id"] == UUID


def test_jira_with_a_comment_that_holds_the_receipt_posts_nothing_and_names_it(fake_jira, picture):
    client = fake_jira(jira_routes(comments=[adf_comment("other"), adf_comment(f"afkv2 proof v1 {RECEIPT}")]))
    answer = jira.comment_put({"key": "PROJ-1", "body": BODY, "pictures": [picture()], "receipt": RECEIPT})
    assert answer["posted"] is False and answer["comment_id"] == "10400" and answer["attached"] == []
    assert client.writes() == []


def test_jira_reuses_a_picture_a_failed_post_already_attached(fake_jira, picture):
    path = picture()
    name = f"afkv2-proof-{SHORT}-1.png"
    routes = jira_routes(attachments=[{"id": "9001", "filename": name, "size": len(b"\x89PNG one")}])
    client = fake_jira(routes)
    answer = jira.comment_put({"key": "PROJ-1", "body": BODY, "pictures": [path], "receipt": RECEIPT})
    assert answer["attached"] == [name]
    assert [(method, path) for method, path, _ in client.writes()] == [POST]


def test_jira_refuses_a_picture_over_the_site_limit(fake_jira, picture):
    client = fake_jira(jira_routes(limit=4))
    error = refused(jira.comment_put, {"key": "PROJ-1", "body": BODY, "pictures": [picture()], "receipt": RECEIPT})
    assert error.code == "too-large" and client.writes() == []


def test_jira_refuses_a_comment_over_1_mb_of_text(fake_jira):
    client = fake_jira(jira_routes())
    body = BODY + "\n" + "x" * 1_000_001
    error = refused(jira.comment_put, {"key": "PROJ-1", "body": body, "pictures": [], "receipt": RECEIPT})
    assert error.code == "too-large" and client.writes() == []


def test_jira_with_attachments_off_refuses_pictures(fake_jira, picture):
    routes = jira_routes()
    routes[META] = FakeResp({"enabled": False, "uploadLimit": 0})
    client = fake_jira(routes)
    error = refused(jira.comment_put, {"key": "PROJ-1", "body": BODY, "pictures": [picture()], "receipt": RECEIPT})
    assert error.code == "not-supported" and client.writes() == []


# Both trackers: the receipt and the input


@pytest.mark.parametrize("change", [{"receipt": "AB" * 32}, {"receipt": "ab"}, {"receipt": None},
                                    {"body": "no proof line\nrest"}, {"body": f"afkv2 proof v1 {'cd' * 32}\nrest"}])
@pytest.mark.parametrize("tracker", ["jira", "github"])
def test_a_receipt_that_is_not_on_the_first_line_is_refused(fake_jira, tools, tracker, change):
    client = fake_jira(jira_routes())
    payload = {"key": "PROJ-1" if tracker == "jira" else "7", "body": BODY, "pictures": [], "receipt": RECEIPT, **change}
    put = jira.comment_put if tracker == "jira" else github_issues.comment_put
    assert refused(put, payload).code == "bad-receipt"
    assert client.calls == [] and tools.calls == []


@pytest.mark.parametrize("tracker", ["jira", "github"])
def test_a_missing_picture_file_is_bad_payload(fake_jira, tools, tmp_path, tracker):
    fake_jira(jira_routes())
    payload = {"key": "PROJ-1" if tracker == "jira" else "7", "body": BODY, "receipt": RECEIPT,
               "pictures": [str(tmp_path / "gone.png")]}
    put = jira.comment_put if tracker == "jira" else github_issues.comment_put
    assert refused(put, payload).code == "bad-payload"


# GitHub


def gh_ready(tools, version="2.99.0", permission="WRITE", url="https://github.com/o/r", comments=()):
    tools.on("gh", "--version", answer=f"gh version {version} (2026-09-01)\nhttps://github.com/cli/cli/releases\n")
    tools.on("gh", "repo", "view", answer={"url": url, "viewerPermission": permission})
    tools.on("gh", "issue", "view", answer={"comments": list(comments)})
    tools.on("gh", "issue", "comment", answer="https://github.com/o/r/issues/7#issuecomment-555\n")
    return tools


def test_github_posts_one_comment_with_each_picture_attached(tools, picture):
    gh_ready(tools)
    png, clip = picture("login.png"), picture("run.mp4")
    answer = github_issues.comment_put({"key": "7", "repo": "o/r", "body": BODY, "pictures": [png, clip], "receipt": RECEIPT})
    assert answer == {"ok": True, "comment_id": "555", "url": "https://github.com/o/r/issues/7#issuecomment-555",
                      "attached": ["login.png", "run.mp4"], "posted": True}
    tool, args, stdin = tools.calls_to("gh", "issue", "comment")[0]
    assert args[:3] == ["issue", "comment", "7"] and args[args.index("--repo") + 1] == "o/r"
    assert args[args.index("--body-file") + 1] == "-" and stdin == BODY
    attaches = [args[index + 1] for index, value in enumerate(args) if value == "--attach"]
    assert attaches == [f"{png}#login.png", clip]


def test_github_with_a_comment_that_holds_the_receipt_posts_nothing_and_names_it(tools, picture):
    gh_ready(tools, comments=[{"id": "IC_1", "body": "hello", "url": "https://github.com/o/r/issues/7#issuecomment-1"},
                              {"id": "IC_2", "body": f"afkv2 proof v1 {RECEIPT}\nmore",
                               "url": "https://github.com/o/r/issues/7#issuecomment-2"}])
    answer = github_issues.comment_put({"key": "7", "repo": "o/r", "body": BODY, "pictures": [picture()], "receipt": RECEIPT})
    assert answer == {"ok": True, "comment_id": "2", "url": "https://github.com/o/r/issues/7#issuecomment-2",
                      "attached": [], "posted": False}
    assert tools.calls_to("gh", "issue", "comment") == []


@pytest.mark.parametrize("version", ["2.92.0", "2.98.9", "1.100.0"])
def test_github_with_gh_older_than_2_99_refuses_gh_too_old(tools, picture, version):
    gh_ready(tools, version=version)
    error = refused(github_issues.comment_put, {"key": "7", "repo": "o/r", "body": BODY, "pictures": [picture()], "receipt": RECEIPT})
    assert error.code == "gh-too-old" and tools.calls_to("gh", "issue", "comment") == []


@pytest.mark.parametrize("permission", ["READ", "TRIAGE", None])
def test_github_without_push_access_refuses_no_push_access(tools, picture, permission):
    gh_ready(tools, permission=permission)
    error = refused(github_issues.comment_put, {"key": "7", "repo": "o/r", "body": BODY, "pictures": [picture()], "receipt": RECEIPT})
    assert error.code == "no-push-access" and tools.calls_to("gh", "issue", "comment") == []


def test_github_enterprise_server_refuses_not_supported(tools, picture):
    gh_ready(tools, url="https://git.example.test/o/r")
    error = refused(github_issues.comment_put, {"key": "7", "repo": "o/r", "body": BODY, "pictures": [picture()], "receipt": RECEIPT})
    assert error.code == "not-supported" and tools.calls_to("gh", "issue", "comment") == []


def test_github_refuses_a_picture_over_10_mb(tools, picture):
    gh_ready(tools)
    big = picture("big.png", size=10 * 1024 * 1024 + 1)
    error = refused(github_issues.comment_put, {"key": "7", "repo": "o/r", "body": BODY, "pictures": [big], "receipt": RECEIPT})
    assert error.code == "too-large" and tools.calls_to("gh", "issue", "comment") == []


@pytest.mark.parametrize("name", ["a.png", "a.jpg", "a.jpeg", "a.gif", "a.webp", "a.svg", "a.mp4", "a.mov", "a.webm", "A.PNG"])
def test_github_attaches_pictures_and_video(tools, picture, name):
    gh_ready(tools)
    answer = github_issues.comment_put({"key": "7", "repo": "o/r", "body": BODY, "pictures": [picture(name)], "receipt": RECEIPT})
    assert answer["attached"] == [name]


@pytest.mark.parametrize("name", ["a.pdf", "a.log", "a.zip", "a"])
def test_github_refuses_a_file_that_is_not_a_picture_or_video(tools, picture, name):
    gh_ready(tools)
    error = refused(github_issues.comment_put, {"key": "7", "repo": "o/r", "body": BODY, "pictures": [picture(name)], "receipt": RECEIPT})
    assert error.code == "not-supported" and tools.calls_to("gh", "issue", "comment") == []


def test_github_refuses_a_path_with_a_hash_sign(tools, picture):
    gh_ready(tools)
    error = refused(github_issues.comment_put, {"key": "7", "repo": "o/r", "body": BODY, "pictures": [picture("a#1.png")], "receipt": RECEIPT})
    assert error.code == "bad-payload"
