"""Seam tests for `tracker_attach`, Jira rich text and the field-truth refusals.

Every assertion reads the real outgoing call: the argv `subprocess.run` gets
for `gh`, and the `urllib` request Jira would receive (its multipart part
types, its JSON body). No network, no `gh`.
"""
from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
ADAPTERS = PLUGIN_ROOT / "adapters" / "tracker"
SERVER = PLUGIN_ROOT / "mcp-servers" / "tracker" / "server.py"
KINDS = ("jira", "github-issues", "none")


def load(kind: str):
    spec = importlib.util.spec_from_file_location(
        f"afk_tracker_attach_{kind.replace('-', '_')}", ADAPTERS / kind / "api.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def proof(tmp_path: Path, name: str, data: bytes = b"proof") -> str:
    path = tmp_path / name
    path.write_bytes(data)
    return str(path)


# ---------------------------------------------------------------------------
# the verb set: ten, the same on every home
def server_tools() -> set[str]:
    text = SERVER.read_text(encoding="utf-8")
    return set(re.findall(r"@mcp\.tool\(\)\ndef (tracker_\w+)\(", text))


@pytest.mark.parametrize("kind", KINDS)
def test_every_kind_lists_the_same_ten_verbs_as_the_server(kind):
    tools = server_tools()
    assert len(tools) == 10 and "tracker_attach" in tools
    assert set(load(kind).OPERATIONS) == tools
    manifest = json.loads((ADAPTERS / kind / "adapter.json").read_text(encoding="utf-8"))
    assert set(manifest["operations"]) == tools
    contract = (ADAPTERS / kind / "CONTRACT.md").read_text(encoding="utf-8")
    assert set(re.findall(r"^- `(tracker_\w+)`$", contract, re.M)) == tools


def test_adapters_md_names_ten_verbs():
    text = (PLUGIN_ROOT / "ADAPTERS.md").read_text(encoding="utf-8")
    section = text.split("## tracker", 1)[1].split("\n## ", 1)[0]
    assert "Ten operations" in section
    assert set(re.findall(r"`(tracker_\w+)`", section)) >= server_tools()


# ---------------------------------------------------------------------------
# GitHub Issues: one comment, one --attach per supported file
class FakeGh:
    """Stands in for `subprocess.run`; records every gh argv and its stdin."""

    def __init__(self, version="2.99.0", permission="WRITE"):
        self.version = version
        self.permission = permission
        self.calls = []

    def __call__(self, argv, **kwargs):
        self.calls.append({"argv": list(argv), "input": kwargs.get("input")})
        if argv[1:] == ["--version"]:
            return subprocess.CompletedProcess(argv, 0, stdout=f"gh version {self.version} (2026-09-01)\n", stderr="")
        if argv[1:3] == ["repo", "view"]:
            return subprocess.CompletedProcess(argv, 0, stdout=json.dumps({"viewerPermission": self.permission}), stderr="")
        return subprocess.CompletedProcess(argv, 0, stdout="https://github.com/o/r/issues/7#issuecomment-1\n", stderr="")

    def comments(self):
        return [c for c in self.calls if c["argv"][1:3] == ["issue", "comment"]]


@pytest.fixture
def github(monkeypatch):
    api = load("github-issues")
    gh = FakeGh()
    monkeypatch.delenv("GH_HOST", raising=False)
    monkeypatch.setattr(api.shutil, "which", lambda name: "/usr/bin/gh")
    monkeypatch.setattr(api.subprocess, "run", gh)
    monkeypatch.setattr(api, "repo", lambda: "o/r")
    return api, gh


def attach_values(argv):
    return [argv[i + 1] for i, a in enumerate(argv) if a == "--attach"]


def test_github_attach_passes_one_attach_per_image_or_video_and_none_for_others(github, tmp_path):
    api, gh = github
    png, mp4, log = proof(tmp_path, "a.png"), proof(tmp_path, "b.mp4"), proof(tmp_path, "c.log")
    answer = api.call("tracker_attach", {"ticket_key": "7", "files": [png, mp4, log], "text": "Proof"})
    [comment] = gh.comments()
    assert attach_values(comment["argv"]) == [png, mp4]
    assert comment["argv"][:6] == ["gh", "issue", "comment", "7", "--repo", "o/r"]
    assert "Proof" in comment["input"] and "c.log" in comment["input"]
    assert answer["ok"] is True and answer["attached"] == [png, mp4]
    assert [u["file"] for u in answer["unsupported_files"]] == [log]


def test_github_attach_on_older_gh_attaches_nothing_and_names_every_file(github, tmp_path):
    api, gh = github
    gh.version = "2.92.0"
    png = proof(tmp_path, "a.png")
    answer = api.call("tracker_attach", {"ticket_key": "7", "files": [png]})
    [comment] = gh.comments()
    assert "--attach" not in comment["argv"]
    assert "a.png" in comment["input"] and "2.99.0" in comment["input"]
    assert answer["attached"] == [] and answer["unsupported_files"][0]["file"] == png


def test_github_attach_on_enterprise_server_attaches_nothing(github, monkeypatch, tmp_path):
    api, gh = github
    monkeypatch.setenv("GH_HOST", "github.example.com")
    png = proof(tmp_path, "a.png")
    answer = api.call("tracker_attach", {"ticket_key": "7", "files": [png]})
    [comment] = gh.comments()
    assert "--attach" not in comment["argv"] and "a.png" in comment["input"]
    assert "Enterprise Server" in answer["unsupported_files"][0]["reason"]


def test_github_attach_without_write_access_attaches_nothing(github, tmp_path):
    api, gh = github
    gh.permission = "READ"
    png = proof(tmp_path, "a.png")
    answer = api.call("tracker_attach", {"ticket_key": "7", "files": [png]})
    [comment] = gh.comments()
    assert "--attach" not in comment["argv"] and "a.png" in comment["input"]
    assert "write access" in answer["unsupported_files"][0]["reason"]


def test_github_attach_refuses_a_missing_file_before_any_write(github, tmp_path):
    api, gh = github
    answer = api.call("tracker_attach", {"ticket_key": "7", "files": [str(tmp_path / "gone.png")]})
    assert answer["error"] is True and "gone.png" in answer["reason"]
    assert gh.comments() == []


# ---------------------------------------------------------------------------
# GitHub Issues: field truth
def test_github_transition_to_an_unknown_state_makes_no_gh_call(github):
    api, gh = github
    api.state_labels = lambda: {"in-review": "status:in-review"}
    answer = api.call("tracker_transition", {"ticket_key": "7", "transition_id": "in-reveiw"})
    assert answer["error"] is True and "in-reveiw" in answer["reason"]
    assert gh.calls == []


def test_github_create_with_an_unknown_state_makes_no_gh_call(github):
    api, gh = github
    api.state_labels = lambda: {"in-review": "status:in-review"}
    answer = api.call("tracker_create", {"summary": "s", "issue_type": "bug", "status": "nonesuch"})
    assert answer["error"] is True and "nonesuch" in answer["reason"]
    assert gh.calls == []


def test_github_create_with_a_known_state_labels_it(github):
    api, gh = github
    api.state_labels = lambda: {"in-review": "status:in-review"}
    api.call("tracker_create", {"summary": "s", "issue_type": "bug", "status": "in-review"})
    [create] = [c for c in gh.calls if c["argv"][1:3] == ["issue", "create"]]
    assert "status:in-review" in create["argv"]


# ---------------------------------------------------------------------------
# none: unsupported, every file named
def test_none_attach_is_unsupported_and_names_each_file():
    answer = load("none").call("tracker_attach", {"ticket_key": "1", "files": ["a.png", "b.log"]})
    assert answer["unsupported"] is True
    assert [u["file"] for u in answer["unsupported_files"]] == ["a.png", "b.log"]


# ---------------------------------------------------------------------------
# Jira: a stub HTTP endpoint behind urllib
class Resp:
    def __init__(self, body=b"", location=None):
        self._body = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.headers = {"Location": location} if location else {}

    def read(self):
        return self._body


class FakeJira:
    """Records every urllib request; answers from a (method, path-prefix) table."""

    def __init__(self):
        self.requests = []
        self.routes = []

    def on(self, method, path, body=None, location=None):
        self.routes.insert(0, (method, path, body, location))

    def __call__(self, req, timeout=None):
        path = req.full_url.split("atlassian.net", 1)[1]
        headers = {k.lower(): v for k, v in req.header_items()}
        self.requests.append({"method": req.get_method(), "path": path,
                              "headers": headers, "data": req.data})
        for method, prefix, body, location in self.routes:
            if method == req.get_method() and path.startswith(prefix):
                return Resp(body if body is not None else b"", location)
        raise urllib.error.HTTPError(req.full_url, 404, "no route", {}, None)

    def writes(self):
        return [r for r in self.requests if r["method"] in ("POST", "PUT", "DELETE")]

    def json_of(self, method, prefix):
        return [json.loads(r["data"]) for r in self.requests
                if r["method"] == method and r["path"].startswith(prefix)]


@pytest.fixture
def jira(monkeypatch):
    api = load("jira")
    fake = FakeJira()
    for name, value in (("JIRA_BASE_URL", "https://n.atlassian.net"),
                        ("JIRA_EMAIL", "me@x.test"), ("JIRA_API_TOKEN", "tok")):
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(urllib.request, "urlopen", fake)
    monkeypatch.setattr(urllib.request, "build_opener", lambda *a: type("O", (), {"open": staticmethod(fake)})())
    monkeypatch.setattr(api, "transitions_config", lambda: {"in-review": "Ready for Review"})
    return api, fake


def multipart_parts(data: bytes):
    """(filename, content type) per part of a multipart body."""
    return re.findall(rb'filename="([^"]+)"\r\nContent-Type: ([^\r]+)\r\n', data)


def test_jira_attach_uploads_each_file_with_its_real_type_in_one_request(jira, tmp_path):
    api, fake = jira
    png, txt, mp4 = proof(tmp_path, "a.png"), proof(tmp_path, "b.txt"), proof(tmp_path, "c.mp4")
    fake.on("POST", "/rest/api/3/issue/P-1/attachments", [
        {"id": "1", "filename": "a.png"}, {"id": "2", "filename": "b.txt"}, {"id": "3", "filename": "c.mp4"}])
    fake.on("GET", "/rest/api/3/issue/P-1?", {"fields": {"attachment": [
        {"id": "1", "filename": "a.png", "mimeType": "image/png"},
        {"id": "2", "filename": "b.txt", "mimeType": "text/plain"},
        {"id": "3", "filename": "c.mp4", "mimeType": "video/mp4"}]}})
    fake.on("GET", "/rest/api/3/attachment/content/", location="https://api.media.atlassian.com/file/"
            "0123abcd-4567-89ab-cdef-0123456789ab/binary")
    fake.on("POST", "/rest/api/3/issue/P-1/comment", {"id": "c9"})
    answer = api.call("tracker_attach", {"ticket_key": "P-1", "files": [png, txt, mp4], "text": "Proof"})
    [upload] = [r for r in fake.requests if r["path"].endswith("/attachments")]
    assert upload["headers"]["content-type"].startswith("multipart/form-data; boundary=")
    assert multipart_parts(upload["data"]) == [
        (b"a.png", b"image/png"), (b"b.txt", b"text/plain"), (b"c.mp4", b"video/mp4")]
    [comment] = fake.json_of("POST", "/rest/api/3/issue/P-1/comment")
    kinds = [n["type"] for n in comment["body"]["content"]]
    assert kinds[0] == "paragraph" and "mediaSingle" in kinds and "mediaGroup" in kinds
    assert answer["ok"] is True and answer["mismatches"] == [] and answer["comment"] == "c9"


def test_jira_attach_reads_back_each_file_and_names_a_mismatch(jira, tmp_path):
    api, fake = jira
    txt = proof(tmp_path, "b.txt")
    fake.on("POST", "/rest/api/3/issue/P-1/attachments", [{"id": "2", "filename": "b.txt"}])
    fake.on("GET", "/rest/api/3/issue/P-1?", {"fields": {"attachment": [
        {"id": "2", "filename": "b (1).txt", "mimeType": "application/octet-stream"}]}})
    fake.on("GET", "/rest/api/3/attachment/content/", location="https://api.media.atlassian.com/file/"
            "0123abcd-4567-89ab-cdef-0123456789ab/binary")
    fake.on("POST", "/rest/api/3/issue/P-1/comment", {"id": "c9"})
    answer = api.call("tracker_attach", {"ticket_key": "P-1", "files": [txt]})
    [mismatch] = answer["mismatches"]
    assert mismatch["file"] == txt and mismatch["stored"] == {
        "filename": "b (1).txt", "mimeType": "application/octet-stream"}
    assert mismatch["sent"] == {"filename": "b.txt", "mimeType": "text/plain"}
    [comment] = fake.json_of("POST", "/rest/api/3/issue/P-1/comment")
    assert "b (1).txt" in json.dumps(comment) and "application/octet-stream" in json.dumps(comment)


def test_jira_attach_refuses_a_missing_file_before_any_write(jira, tmp_path):
    api, fake = jira
    answer = api.call("tracker_attach", {"ticket_key": "P-1", "files": [str(tmp_path / "gone.png")]})
    assert answer["error"] is True and "gone.png" in answer["reason"]
    assert fake.requests == []


def test_the_single_file_upload_still_sends_png_for_a_png(jira, tmp_path):
    api, fake = jira
    fake.on("POST", "/rest/api/3/issue/P-1/attachments", [{"id": "9001"}])
    assert api.client().upload_attachment("P-1", proof(tmp_path, "fig.png")) == "9001"
    assert multipart_parts(fake.requests[0]["data"]) == [(b"fig.png", b"image/png")]


# ---------------------------------------------------------------------------
# Jira: markdown -> Atlassian Document Format on create and comment
MARKDOWN = "# Title\n\n- one\n- two\n\n```python\nx = 1\n```\n\nSee [docs](https://x.test/d)."


def assert_rich(doc):
    assert doc["type"] == "doc" and doc["version"] == 1
    heading, bullets, code, para = doc["content"]
    assert heading == {"type": "heading", "attrs": {"level": 1},
                       "content": [{"type": "text", "text": "Title"}]}
    assert bullets["type"] == "bulletList" and len(bullets["content"]) == 2
    assert code == {"type": "codeBlock", "attrs": {"language": "python"},
                    "content": [{"type": "text", "text": "x = 1"}]}
    link = next(n for n in para["content"] if n.get("marks"))
    assert link == {"type": "text", "text": "docs",
                    "marks": [{"type": "link", "attrs": {"href": "https://x.test/d"}}]}


def test_jira_comment_sends_markdown_as_adf_nodes(jira):
    api, fake = jira
    fake.on("POST", "/rest/api/3/issue/P-1/comment", {"id": "c1"})
    api.call("tracker_comment", {"ticket_key": "P-1", "text": MARKDOWN})
    [body] = fake.json_of("POST", "/rest/api/3/issue/P-1/comment")
    assert_rich(body["body"])


def test_jira_create_sends_the_description_as_adf_nodes(jira):
    api, fake = jira
    fake.on("POST", "/rest/api/3/issue", {"key": "P-2", "id": "2"})
    api.call("tracker_create", {"project": "P", "issue_type": "Bug", "summary": "s",
                                "description": MARKDOWN})
    [body] = fake.json_of("POST", "/rest/api/3/issue")
    assert_rich(body["fields"]["description"])


# ---------------------------------------------------------------------------
# Jira: field truth — refused before any write
TRANSITIONS = {"transitions": [{"id": "31", "name": "Ready for Review"}, {"id": "41", "name": "Done"}]}


def test_jira_transition_by_the_in_review_key_moves_to_the_configured_transition(jira):
    api, fake = jira
    fake.on("GET", "/rest/api/3/issue/P-1/transitions", TRANSITIONS)
    fake.on("POST", "/rest/api/3/issue/P-1/transitions", b"")
    api.call("tracker_transition", {"ticket_key": "P-1", "transition_id": "in-review"})
    assert fake.json_of("POST", "/rest/api/3/issue/P-1/transitions") == [{"transition": {"id": "31"}}]


@pytest.mark.parametrize("given", ["31", "ready for review"])
def test_jira_transition_matches_by_id_or_name(jira, given):
    api, fake = jira
    fake.on("GET", "/rest/api/3/issue/P-1/transitions", TRANSITIONS)
    fake.on("POST", "/rest/api/3/issue/P-1/transitions", b"")
    api.call("tracker_transition", {"ticket_key": "P-1", "transition_id": given})
    assert fake.json_of("POST", "/rest/api/3/issue/P-1/transitions") == [{"transition": {"id": "31"}}]


def test_jira_transition_to_an_unknown_key_is_refused_with_no_write(jira):
    api, fake = jira
    api.transitions_config = lambda: {"in-review": "Code Review"}
    fake.on("GET", "/rest/api/3/issue/P-1/transitions", TRANSITIONS)
    answer = api.call("tracker_transition", {"ticket_key": "P-1", "transition_id": "in-review"})
    assert answer["error"] is True and "Code Review" in answer["reason"]
    assert fake.writes() == []


def test_jira_create_with_an_unknown_fix_version_is_refused_with_no_write(jira):
    api, fake = jira
    fake.on("GET", "/rest/api/3/project/P/versions", [{"id": "10", "name": "1.0"}])
    answer = api.call("tracker_create", {"project": "P", "issue_type": "Bug", "summary": "s",
                                         "fix_version": "9.9"})
    assert answer["error"] is True and "9.9" in answer["reason"] and "1.0" in answer["reason"]
    assert fake.writes() == []


def test_jira_create_with_a_known_fix_version_sends_it(jira):
    api, fake = jira
    fake.on("GET", "/rest/api/3/project/P/versions", [{"id": "10", "name": "1.0"}])
    fake.on("POST", "/rest/api/3/issue", {"key": "P-3", "id": "3"})
    api.call("tracker_create", {"project": "P", "issue_type": "Bug", "summary": "s", "fix_version": "1.0"})
    [body] = fake.json_of("POST", "/rest/api/3/issue")
    assert body["fields"]["fixVersions"] == [{"name": "1.0"}]


def test_jira_edit_with_an_unknown_fix_version_is_refused_with_no_write(jira):
    api, fake = jira
    fake.on("GET", "/rest/api/3/issue/P-1?", {"fields": {"project": {"key": "P"}}})
    fake.on("GET", "/rest/api/3/project/P/versions", [{"id": "10", "name": "1.0"}])
    answer = api.call("tracker_edit", {"ticket_key": "P-1", "fields": {"fixVersions": [{"name": "2.0"}]}})
    assert answer["error"] is True and "2.0" in answer["reason"]
    assert fake.writes() == []


def test_jira_edit_with_a_known_fix_version_by_id_writes_it(jira):
    api, fake = jira
    fake.on("GET", "/rest/api/3/issue/P-1?", {"fields": {"project": {"key": "P"}}})
    fake.on("GET", "/rest/api/3/project/P/versions", [{"id": "10", "name": "1.0"}])
    fake.on("PUT", "/rest/api/3/issue/P-1", b"")
    api.call("tracker_edit", {"ticket_key": "P-1", "fields": {"fixVersions": [{"id": "10"}]}})
    assert fake.json_of("PUT", "/rest/api/3/issue/P-1") == [{"fields": {"fixVersions": [{"id": "10"}]}}]


# ---------------------------------------------------------------------------
# the config scaffold: one in-review key on both trackers
def test_the_scaffold_uses_one_in_review_key_on_both_trackers(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.delenv("AFK_CONFIG", raising=False)
    spec = importlib.util.spec_from_file_location("afk_config_scaffold", PLUGIN_ROOT / "scripts" / "afk-config.py")
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)
    texts = []
    for name, remote in (("plain", None), ("hub", "https://github.com/acme/widget.git")):
        repo = tmp_path / name
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        if remote:
            subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", remote], check=True)
        texts.append(config.scaffold(repo))
    jira_block, github_block = texts
    assert re.search(r"^#\s+in-review: ", jira_block, re.M) and "ready-for-review" not in jira_block
    assert re.search(r"^\s+in-review: ", github_block, re.M)
