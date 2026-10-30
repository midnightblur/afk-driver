"""Fixtures for the port tests: in-process fakes for gh and glab, a recorded Jira, a preview file."""

from __future__ import annotations

import hashlib
import io
import json
import sys
import urllib.error
from pathlib import Path

import pytest

PORTS = Path(__file__).resolve().parents[2] / "ports"
sys.path.insert(0, str(PORTS))

from tracker import jira, shell  # noqa: E402


class FakeResp:
    def __init__(self, body=b"", location=None):
        self._body = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.headers = {"Location": location} if location is not None else {}

    def read(self):
        return self._body


def http_error(status, body=b"", location=None):
    headers = {"Location": location} if location else {}
    return urllib.error.HTTPError("https://n.test/x", status, "status", headers, io.BytesIO(body))


class RecordedJira(jira.Jira):
    """The real client over a route table: (method, path prefix) -> response or error."""

    def __init__(self, routes=None):
        super().__init__("https://n.test", "me@x.test", "tok-secret")
        self.routes = dict(routes or {})
        self.calls = []

    def _req(self, method, path, data=None, headers=None, follow=True):
        self.calls.append((method, path, data))
        for (route_method, prefix), answer in self.routes.items():
            if route_method == method and path.startswith(prefix):
                if isinstance(answer, Exception):
                    raise answer
                return answer
        raise http_error(404, b"no route " + path.encode())

    def writes(self):
        return [call for call in self.calls if call[0] != "GET"]


@pytest.fixture
def recorded_jira(monkeypatch):
    def install(routes=None):
        client = RecordedJira(routes)
        monkeypatch.setattr(jira, "client", lambda: client)
        return client
    return install


class FakeTools:
    """Stands in for `shell.run_tool`. A rule is (tool, argument prefix) -> stdout, (rc, stdout, stderr) or a callable."""

    def __init__(self, real_run):
        self.rules = []
        self.calls = []
        self.real_run = real_run

    def on(self, tool, *prefix, answer=""):
        self.rules.insert(0, (tool, prefix, answer))
        return self

    def __call__(self, tool, args, *, stdin_text=None, timeout=None):
        self.calls.append((tool, list(args), stdin_text))
        for rule_tool, prefix, answer in self.rules:
            if rule_tool == tool and tuple(args[:len(prefix)]) == prefix:
                if callable(answer):
                    answer = answer(list(args), stdin_text)
                if isinstance(answer, tuple):
                    return shell.Done(*answer)
                return shell.Done(0, answer if isinstance(answer, str) else json.dumps(answer), "")
        if tool == "git":
            return self.real_run(tool, args, stdin_text=stdin_text, timeout=timeout)
        return shell.Done(1, "", f"no fake answer for {tool} {' '.join(args)}")

    def calls_to(self, tool, *prefix):
        return [call for call in self.calls
                if call[0] == tool and tuple(call[1][:len(prefix)]) == prefix]


@pytest.fixture
def tools(monkeypatch):
    fake = FakeTools(shell.run_tool)
    monkeypatch.setattr(shell, "run_tool", fake)
    return fake


@pytest.fixture
def preview(tmp_path):
    """A preview file with its pictures; returns (path, receipt, picture paths)."""
    def build(key="PROJ-1", description_hash="h" * 64, pictures=(b"\x89PNG one",)):
        receipt = hashlib.sha256(f"{key}{description_hash}".encode()).hexdigest()
        folder = tmp_path / "preview"
        folder.mkdir(exist_ok=True)
        paths = []
        for n, data in enumerate(pictures, start=1):
            path = folder / f"afkv2-fig-{receipt[:8]}-{n}.png"
            path.write_bytes(data)
            paths.append(path)
        file = folder / "preview.json"
        file.write_text(json.dumps({
            "ticket_key": key, "receipt": receipt, "description_hash": description_hash,
            "picture_hashes": [hashlib.sha256(data).hexdigest() for data in pictures],
        }), encoding="utf-8")
        return str(file), receipt, paths
    return build
