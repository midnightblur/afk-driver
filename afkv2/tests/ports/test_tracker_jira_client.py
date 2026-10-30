"""Ported from the v1 Jira tests: credentials, the REST client, PNG sizes. No network."""

from __future__ import annotations

import base64
import json
import http.server
import struct
import threading
import urllib.request
from pathlib import Path

import pytest

from port_fakes import FakeResp, http_error
from tracker import envelope, jira

KEYS = ("JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN")
FILE_VALUES = {"JIRA_BASE_URL": "https://file.atlassian.net", "JIRA_EMAIL": "file@x.test", "JIRA_API_TOKEN": "file-tok"}


@pytest.fixture
def home(tmp_path, monkeypatch):
    for key in KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(jira.Path, "home", lambda: tmp_path)
    return tmp_path


def write_claude_json(home: Path, values=FILE_VALUES, server="tracker"):
    (home / ".claude.json").write_text(json.dumps({"mcpServers": {server: {"env": values}}}), encoding="utf-8")


def test_env_wins_and_base_trailing_slash_stripped(home, monkeypatch):
    write_claude_json(home)
    monkeypatch.setenv("JIRA_BASE_URL", "https://n.atlassian.net/")
    monkeypatch.setenv("JIRA_EMAIL", "me@x.test")
    monkeypatch.setenv("JIRA_API_TOKEN", "tok123")
    assert jira.load_creds() == ("https://n.atlassian.net", "me@x.test", "tok123")


def test_walk_for_jira_env():
    assert jira._walk_for_jira_env({"mcpServers": {"tracker": {"env": {"A": "1"}}}}) == {"A": "1"}
    assert jira._walk_for_jira_env({"other": {"x": 1}}) is None


def test_falls_back_to_claude_json(home):
    write_claude_json(home)
    assert jira.load_creds() == ("https://file.atlassian.net", "file@x.test", "file-tok")


def test_resolve_creds_env_never_exits(home):
    assert jira.resolve_creds_env() == {}
    write_claude_json(home)
    assert set(jira.resolve_creds_env()) == set(KEYS)


def test_creds_merge_per_field(home, monkeypatch):
    write_claude_json(home)
    monkeypatch.setenv("JIRA_BASE_URL", "https://env.atlassian.net")
    assert jira.load_creds() == ("https://env.atlassian.net", "file@x.test", "file-tok")


def test_codex_config_is_the_last_source(home):
    codex = home / ".codex"
    codex.mkdir()
    (codex / "config.toml").write_text(
        '[mcp_servers.tracker.env]\nJIRA_BASE_URL = "https://codex.test"\nJIRA_EMAIL = "c@x.test"\nJIRA_API_TOKEN = "c-tok"\n',
        encoding="utf-8")
    assert jira.load_creds() == ("https://codex.test", "c@x.test", "c-tok")
    write_claude_json(home)
    assert jira.load_creds()[0] == "https://file.atlassian.net"


def test_a_broken_claude_json_does_not_stop_the_lookup(home, monkeypatch):
    (home / ".claude.json").write_text("{not json", encoding="utf-8")
    assert jira.resolve_creds_env() == {}
    (home / ".codex").mkdir(exist_ok=True)
    (home / ".codex" / "config.toml").write_text(
        '[mcp_servers.tracker.env]\nJIRA_BASE_URL = "https://codex.test"\nJIRA_EMAIL = "c@x.test"\nJIRA_API_TOKEN = "c-tok"\n',
        encoding="utf-8")
    assert jira.load_creds()[0] == "https://codex.test"


def test_a_jira_named_server_is_not_a_credential_source(home):
    write_claude_json(home, server="jira")
    assert jira.resolve_creds_env() == {}


def test_a_jira_named_server_does_not_hide_a_project_tracker(home):
    (home / ".claude.json").write_text(json.dumps({
        "mcpServers": {"jira": {"env": {"JIRA_BASE_URL": "https://foreign.test"}}},
        "projects": {"/work/p": {"mcpServers": {"tracker": {"env": FILE_VALUES}}}},
    }), encoding="utf-8")
    assert jira.resolve_creds_env() == FILE_VALUES


def test_missing_credentials_are_a_named_refusal_without_values(home, monkeypatch):
    monkeypatch.setenv("JIRA_API_TOKEN", "tok-secret")
    with pytest.raises(envelope.Refusal) as caught:
        jira.load_creds()
    assert caught.value.code == "no-credentials"
    assert "JIRA_BASE_URL" in caught.value.reason and "tok-secret" not in caught.value.reason


def make():
    return jira.Jira("https://n.atlassian.net", "me@x.test", "tok")


def test_auth_header_is_basic_base64():
    assert make().auth == "Basic " + base64.b64encode(b"me@x.test:tok").decode()


def test_upload_attachment_multipart_body(tmp_path):
    client = make()
    captured = {}

    def fake_req(method, path, data=None, headers=None, follow=True):
        captured.update(method=method, path=path, data=data, headers=headers)
        return FakeResp(body=b'[{"id":"9001"}]')

    client._req = fake_req
    png = tmp_path / "afkv2-fig-00000000-1.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\nDATA")
    assert client.upload_attachment("PROJ-1", str(png)) == "9001"
    assert captured["method"] == "POST" and captured["path"].endswith("/issue/PROJ-1/attachments")
    assert captured["headers"]["X-Atlassian-Token"] == "no-check"
    assert "multipart/form-data; boundary=" in captured["headers"]["Content-Type"]
    body = captured["data"]
    picture = png.name.encode()
    assert b'Content-Disposition: form-data; name="file"; filename="' + picture + b'"' in body
    assert b"Content-Type: image/png" in body and b"DATA" in body


def test_resolve_media_uuid_from_location():
    client = make()
    uuid = "0123abcd-4567-89ab-cdef-0123456789ab"

    def fake_req(method, path, data=None, headers=None, follow=True):
        assert follow is False
        return FakeResp(location=f"https://api.media.atlassian.com/file/{uuid}/binary?token=x")

    client._req = fake_req
    assert client.resolve_media_uuid("9001") == uuid


def test_resolve_media_uuid_reads_the_location_of_a_303():
    client = make()
    uuid = "0123abcd-4567-89ab-cdef-0123456789ab"

    def fake_req(method, path, data=None, headers=None, follow=True):
        raise http_error(303, location=f"https://api.media.atlassian.com/file/{uuid}/binary")

    client._req = fake_req
    assert client.resolve_media_uuid("9001") == uuid


def test_every_rest_call_makes_one_attempt_with_a_60_second_timeout(monkeypatch):
    seen = []

    def fake_urlopen(request, timeout=None):
        seen.append(timeout)
        raise http_error(503, b"down")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(jira, "client", make)
    with pytest.raises(envelope.Refusal) as caught:
        jira.issue_get({"key": "PROJ-1"})
    assert caught.value.code == "server-error"
    assert seen == [60]


def test_a_network_failure_is_a_named_refusal(monkeypatch):
    def fake_urlopen(request, timeout=None):
        raise TimeoutError("timed out")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(jira, "client", make)
    with pytest.raises(envelope.Refusal) as caught:
        jira.issue_get({"key": "PROJ-1"})
    assert caught.value.code == "network"


def test_an_answer_that_is_not_json_is_a_named_refusal(fake_jira):
    fake_jira({("GET", "/rest/api/3/issue/PROJ-1"): FakeResp(b"<html>")})
    with pytest.raises(envelope.Refusal) as caught:
        jira.issue_get({"key": "PROJ-1"})
    assert caught.value.code == "bad-answer"


def test_the_no_redirect_path_also_has_a_60_second_timeout(monkeypatch):
    seen = []

    class Opener:
        def open(self, request, timeout=None):
            seen.append(timeout)
            return FakeResp(location="x")

    monkeypatch.setattr(urllib.request, "build_opener", lambda *_: Opener())
    make()._req("GET", "/x", follow=False)
    assert seen == [60]


def test_png_size(tmp_path):
    png = tmp_path / "a.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", 32, 16) + b"\x00" * 16)
    assert jira.png_size(png) == (32, 16)


def test_truncated_png_returns_none(tmp_path):
    png = tmp_path / "a.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00")
    assert jira.png_size(png) is None


def test_non_png_returns_none(tmp_path):
    other = tmp_path / "a.bin"
    other.write_bytes(b"not a png at all here")
    assert jira.png_size(other) is None


def test_the_media_id_comes_from_a_real_303_and_the_redirect_is_not_followed(monkeypatch):
    media = "6e8f6c52-3b1a-4a55-9f10-2a1e6f0c7d11"
    paths = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            paths.append(self.path)
            self.send_response(303)
            self.send_header("Location", f"/file/{media}/binary")
            self.end_headers()

        def log_message(self, *_):
            pass

    monkeypatch.setenv("NO_PROXY", "*")
    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        client = jira.Jira(f"http://127.0.0.1:{server.server_port}", "me@x.test", "tok-secret")
        assert client.resolve_media_uuid("9001") == media
    finally:
        server.shutdown()
        thread.join()
        server.server_close()
    assert paths == ["/rest/api/3/attachment/content/9001"]
