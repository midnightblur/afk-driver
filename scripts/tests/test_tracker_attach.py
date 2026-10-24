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
    assert answer["ok"] is True and answer["attached"] == [{"file": png}, {"file": mp4}]
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
    assert answer["refused"] is True and "gone.png" in answer["reason"]
    assert gh.comments() == []


# ---------------------------------------------------------------------------
# GitHub Issues: field truth
def test_github_transition_to_an_unknown_state_makes_no_gh_call(github, monkeypatch):
    api, gh = github
    monkeypatch.setattr(api, "state_labels", lambda: {"in-review": "status:in-review"})
    answer = api.call("tracker_transition", {"ticket_key": "7", "transition_id": "in-reveiw"})
    assert answer["refused"] is True and "in-reveiw" in answer["reason"]
    assert gh.calls == []


def test_github_create_with_an_unknown_state_makes_no_gh_call(github, monkeypatch):
    api, gh = github
    monkeypatch.setattr(api, "state_labels", lambda: {"in-review": "status:in-review"})
    answer = api.call("tracker_create", {"summary": "s", "issue_type": "bug", "status": "nonesuch"})
    assert answer["refused"] is True and "nonesuch" in answer["reason"]
    assert gh.calls == []


def test_github_create_with_a_known_state_labels_it(github, monkeypatch):
    api, gh = github
    monkeypatch.setattr(api, "state_labels", lambda: {"in-review": "status:in-review"})
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


UUID = "0123abcd-4567-89ab-cdef-0123456789ab"


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
    para, image, video, group = comment["body"]["content"]
    media = {"type": "file", "id": UUID, "collection": ""}
    assert para["type"] == "paragraph"
    assert image["type"] == video["type"] == "mediaSingle"
    assert image["content"] == [{"type": "media", "attrs": media}]
    assert video["content"] == [{"type": "media", "attrs": media}]
    assert group == {"type": "mediaGroup", "content": [{"type": "media", "attrs": media}]}
    assert answer["ok"] is True and answer["mismatches"] == [] and answer["comment"] == "c9"
    assert [a["file"] for a in answer["attached"]] == [png, txt, mp4]


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
    assert mismatch["reason"] == "stored differently" and answer["read_back"] is True
    [comment] = fake.json_of("POST", "/rest/api/3/issue/P-1/comment")
    assert "b (1).txt" in json.dumps(comment) and "application/octet-stream" in json.dumps(comment)


def test_jira_attach_refuses_a_missing_file_before_any_write(jira, tmp_path):
    api, fake = jira
    answer = api.call("tracker_attach", {"ticket_key": "P-1", "files": [str(tmp_path / "gone.png")]})
    assert answer["refused"] is True and "gone.png" in answer["reason"]
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


def test_jira_transition_to_an_unknown_key_is_refused_with_no_write(jira, monkeypatch):
    api, fake = jira
    monkeypatch.setattr(api, "transitions_config", lambda: {"in-review": "Code Review"})
    fake.on("GET", "/rest/api/3/issue/P-1/transitions", TRANSITIONS)
    answer = api.call("tracker_transition", {"ticket_key": "P-1", "transition_id": "in-review"})
    assert answer["refused"] is True and "Code Review" in answer["reason"]
    assert fake.writes() == []


def test_jira_create_with_an_unknown_fix_version_is_refused_with_no_write(jira):
    api, fake = jira
    fake.on("GET", "/rest/api/3/project/P/versions", [{"id": "10", "name": "1.0"}])
    answer = api.call("tracker_create", {"project": "P", "issue_type": "Bug", "summary": "s",
                                         "fix_version": "9.9"})
    assert answer["refused"] is True and "9.9" in answer["reason"] and "1.0" in answer["reason"]
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
    assert answer["refused"] is True and "2.0" in answer["reason"]
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


# ---------------------------------------------------------------------------
# GitHub Issues: attach boundaries
@pytest.mark.parametrize("version, attached", [("2.98.9", False), ("2.99.0", True), ("2.100.0", True)])
def test_github_attach_floor_is_2_99_0(github, tmp_path, version, attached):
    api, gh = github
    gh.version = version
    png = proof(tmp_path, "a.png")
    api.call("tracker_attach", {"ticket_key": "7", "files": [png]})
    [comment] = gh.comments()
    assert attach_values(comment["argv"]) == ([png] if attached else [])


@pytest.mark.parametrize("permission", ["READ", "TRIAGE", "NONE"])
def test_github_attach_needs_write_access(github, tmp_path, permission):
    api, gh = github
    gh.permission = permission
    answer = api.call("tracker_attach", {"ticket_key": "7", "files": [proof(tmp_path, "a.png")]})
    assert answer["attached"] == [] and "write access" in answer["unsupported_files"][0]["reason"]


def test_github_attach_names_a_hash_path_takes_an_upper_case_type_and_drops_repeats(github, tmp_path):
    api, gh = github
    hashed, upper = proof(tmp_path, "x#1.png"), proof(tmp_path, "A.PNG")
    answer = api.call("tracker_attach", {"ticket_key": "7", "files": [hashed, upper, upper]})
    [comment] = gh.comments()
    assert attach_values(comment["argv"]) == [upper]
    assert [u["file"] for u in answer["unsupported_files"]] == [hashed]
    assert "alt text" in answer["unsupported_files"][0]["reason"] and "x#1.png" in comment["input"]


def test_github_attach_reports_a_failed_comment(github, monkeypatch, tmp_path):
    api, gh = github

    def failing(argv, **kwargs):
        if argv[1:3] == ["issue", "comment"]:
            gh.calls.append({"argv": list(argv), "input": kwargs.get("input")})
            return subprocess.CompletedProcess(argv, 1, stdout="", stderr="HTTP 422")
        return gh(argv, **kwargs)
    monkeypatch.setattr(api.subprocess, "run", failing)
    answer = api.call("tracker_attach", {"ticket_key": "7", "files": [proof(tmp_path, "a.png")]})
    assert answer["error"] is True and answer["operation"] == "tracker_attach"
    assert len(gh.comments()) == 1


# ---------------------------------------------------------------------------
# Jira: attach failure paths
def attach_routes(fake, uploaded, stored):
    fake.on("POST", "/rest/api/3/issue/P-1/attachments", uploaded)
    fake.on("GET", "/rest/api/3/issue/P-1?", {"fields": {"attachment": stored}})
    fake.on("GET", "/rest/api/3/attachment/content/",
            location=f"https://api.media.atlassian.com/file/{UUID}/binary")


def test_jira_attach_upload_error_posts_no_comment(jira, tmp_path):
    api, fake = jira
    answer = api.call("tracker_attach", {"ticket_key": "P-1", "files": [proof(tmp_path, "a.png")]})
    assert answer["error"] is True and answer["status"] == 404
    assert fake.json_of("POST", "/rest/api/3/issue/P-1/comment") == []


def test_jira_attach_reports_files_stored_when_the_comment_fails(jira, tmp_path):
    api, fake = jira
    png = proof(tmp_path, "a.png")
    attach_routes(fake, [{"id": "1"}], [{"id": "1", "filename": "a.png", "mimeType": "image/png"}])
    answer = api.call("tracker_attach", {"ticket_key": "P-1", "files": [png]})
    assert answer["error"] is True and answer["comment_error"]["error"] is True
    assert [a["file"] for a in answer["attached"]] == [png]


def test_jira_attach_names_a_file_it_could_not_embed(jira, tmp_path, monkeypatch):
    api, fake = jira
    attach_routes(fake, [{"id": "1"}], [{"id": "1", "filename": "a.png", "mimeType": "image/png"}])
    fake.on("POST", "/rest/api/3/issue/P-1/comment", {"id": "c9"})

    def no_uuid(self, att_id):
        raise RuntimeError("no redirect")
    monkeypatch.setattr(api.Jira, "resolve_media_uuid", no_uuid)
    api.call("tracker_attach", {"ticket_key": "P-1", "files": [proof(tmp_path, "a.png")]})
    [comment] = fake.json_of("POST", "/rest/api/3/issue/P-1/comment")
    assert "attached but not embedded" in json.dumps(comment)
    assert not [n for n in comment["body"]["content"] if n["type"] in ("mediaSingle", "mediaGroup")]


def test_jira_attach_names_a_file_the_upload_answer_leaves_out(jira, tmp_path):
    api, fake = jira
    png, txt = proof(tmp_path, "a.png"), proof(tmp_path, "b.txt")
    attach_routes(fake, [{"id": "1"}], [{"id": "1", "filename": "a.png", "mimeType": "image/png"}])
    fake.on("POST", "/rest/api/3/issue/P-1/comment", {"id": "c9"})
    answer = api.call("tracker_attach", {"ticket_key": "P-1", "files": [png, txt]})
    [missing] = answer["mismatches"]
    assert missing["file"] == txt and missing["stored"] is None
    assert missing["reason"] == "not in the upload answer"
    [comment] = fake.json_of("POST", "/rest/api/3/issue/P-1/comment")
    assert "b.txt" in json.dumps(comment)


# ---------------------------------------------------------------------------
# Jira: the opening state, the real config read, unreadable versions
def test_jira_create_moves_to_a_known_status(jira):
    api, fake = jira
    fake.on("POST", "/rest/api/3/issue", {"key": "P-4", "id": "4"})
    fake.on("GET", "/rest/api/3/issue/P-4/transitions", TRANSITIONS)
    fake.on("POST", "/rest/api/3/issue/P-4/transitions", b"")
    moved = api.call("tracker_create", {"project": "P", "issue_type": "Bug", "summary": "s",
                                        "status": "in-review"})
    assert moved["transitioned_to"] == "in-review"
    assert fake.json_of("POST", "/rest/api/3/issue/P-4/transitions") == [{"transition": {"id": "31"}}]


def test_jira_create_with_an_unknown_status_says_the_issue_was_created(jira):
    api, fake = jira
    fake.on("POST", "/rest/api/3/issue", {"key": "P-4", "id": "4"})
    fake.on("GET", "/rest/api/3/issue/P-4/transitions", TRANSITIONS)
    kept = api.call("tracker_create", {"project": "P", "issue_type": "Bug", "summary": "s",
                                       "status": "Nope"})
    assert kept["key"] == "P-4" and "was created" in kept["status_warning"]
    assert "nothing was written" not in kept["status_warning"]
    assert fake.json_of("POST", "/rest/api/3/issue/P-4/transitions") == []


def test_jira_create_names_the_cause_when_transitions_cannot_be_read(jira):
    api, fake = jira
    fake.on("POST", "/rest/api/3/issue", {"key": "P-4", "id": "4"})
    kept = api.call("tracker_create", {"project": "P", "issue_type": "Bug", "summary": "s",
                                       "status": "in-review"})
    assert "was created" in kept["status_warning"] and "HTTP 404" in kept["status_warning"]


def test_jira_transition_reports_a_failed_transitions_read_and_writes_nothing(jira):
    api, fake = jira
    answer = api.call("tracker_transition", {"ticket_key": "P-1", "transition_id": "in-review"})
    assert answer["error"] is True and answer["operation"] == "tracker_transition"
    assert "refused" not in answer and fake.writes() == []


def config_repo(tmp_path, monkeypatch, text):
    repo = tmp_path / "repo"
    (repo / ".afk").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / ".afk" / "config.yaml").write_text(text, encoding="utf-8")
    for name in ("HOME", "USERPROFILE"):
        monkeypatch.setenv(name, str(tmp_path))
    monkeypatch.delenv("AFK_CONFIG", raising=False)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(repo))


def test_jira_transition_reads_the_in_review_key_from_the_config_file(jira, tmp_path, monkeypatch):
    api, fake = jira
    config_repo(tmp_path, monkeypatch, "tracker: jira\njira:\n  transitions:\n    in-review: Ready for Review\n")
    monkeypatch.setattr(api, "transitions_config", load("jira").transitions_config)
    fake.on("GET", "/rest/api/3/issue/P-1/transitions", TRANSITIONS)
    fake.on("POST", "/rest/api/3/issue/P-1/transitions", b"")
    api.call("tracker_transition", {"ticket_key": "P-1", "transition_id": "in-review"})
    assert fake.json_of("POST", "/rest/api/3/issue/P-1/transitions") == [{"transition": {"id": "31"}}]


def test_jira_transition_with_an_unreadable_config_still_matches_by_id(jira, monkeypatch):
    api, fake = jira

    def unreadable():
        raise ValueError("bad config")
    monkeypatch.setattr(api, "transitions_config", unreadable)
    fake.on("GET", "/rest/api/3/issue/P-1/transitions", TRANSITIONS)
    fake.on("POST", "/rest/api/3/issue/P-1/transitions", b"")
    api.call("tracker_transition", {"ticket_key": "P-1", "transition_id": "41"})
    assert fake.json_of("POST", "/rest/api/3/issue/P-1/transitions") == [{"transition": {"id": "41"}}]
    refused = api.call("tracker_transition", {"ticket_key": "P-1", "transition_id": "in-review"})
    assert refused["refused"] is True and "unreadable" in refused["reason"]


def test_jira_edit_writes_with_a_warning_when_versions_cannot_be_read(jira):
    api, fake = jira
    fake.on("GET", "/rest/api/3/issue/P-1?", {"fields": {"project": {"key": "P"}}})
    fake.on("PUT", "/rest/api/3/issue/P-1", b"")
    answer = api.call("tracker_edit", {"ticket_key": "P-1", "fields": {"fixVersions": [{"name": "1.0"}]}})
    assert "versions of project P unreadable" in answer["fix_version_warning"]
    assert fake.json_of("PUT", "/rest/api/3/issue/P-1") == [{"fields": {"fixVersions": [{"name": "1.0"}]}}]


def test_jira_edit_writes_with_a_warning_when_the_project_cannot_be_read(jira):
    api, fake = jira
    fake.on("PUT", "/rest/api/3/issue/P-1", b"")
    answer = api.call("tracker_edit", {"ticket_key": "P-1", "fields": {"fixVersions": [{"name": "1.0"}]}})
    assert "project of P-1 unreadable" in answer["fix_version_warning"]
    assert fake.json_of("PUT", "/rest/api/3/issue/P-1") == [{"fields": {"fixVersions": [{"name": "1.0"}]}}]


def test_jira_attach_without_a_read_back_checks_nothing(jira, tmp_path):
    api, fake = jira
    fake.on("POST", "/rest/api/3/issue/P-1/attachments", [{"id": "1"}])
    fake.on("GET", "/rest/api/3/attachment/content/",
            location=f"https://api.media.atlassian.com/file/{UUID}/binary")
    fake.on("POST", "/rest/api/3/issue/P-1/comment", {"id": "c9"})
    answer = api.call("tracker_attach", {"ticket_key": "P-1", "files": [proof(tmp_path, "a.png")]})
    assert answer["ok"] is True and answer["read_back"] is False and answer["mismatches"] == []
    [comment] = fake.json_of("POST", "/rest/api/3/issue/P-1/comment")
    assert "could not be read back" in json.dumps(comment) and "None" not in json.dumps(comment)


def test_jira_create_writes_with_a_warning_when_versions_cannot_be_read(jira):
    api, fake = jira
    fake.on("POST", "/rest/api/3/issue", {"key": "P-5", "id": "5"})
    answer = api.call("tracker_create", {"project": "P", "issue_type": "Bug", "summary": "s",
                                         "fix_version": "1.0"})
    assert answer["key"] == "P-5" and "not checked" in answer["fix_version_warning"]
    [body] = fake.json_of("POST", "/rest/api/3/issue")
    assert body["fields"]["fixVersions"] == [{"name": "1.0"}]
