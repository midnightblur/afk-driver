"""Fixtures for the port tests: in-process fakes for gh and glab, a fake Jira, a preview file."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
from port_fakes import PORTS, http_error

sys.path.insert(0, str(PORTS))

from tracker import jira, shell  # noqa: E402

FAKE_PROCESS = Path(__file__).resolve().parent / "fake_forge_process.py"


class FakeJira(jira.Jira):
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
def fake_jira(monkeypatch):
    def install(routes=None):
        client = FakeJira(routes)
        monkeypatch.setattr(jira, "client", lambda: client)
        return client
    return install


class FakeTools:
    """Stands in for `shell.run_tool`. A rule is (tool, argument prefix) -> stdout, (rc, stdout, stderr) or a callable."""

    def __init__(self, real_run):
        self.rules = []
        self.calls = []
        self.real_run = real_run
        self.written = None

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
                self._keep_body(tool, args, stdin_text)
                answer = self._with_kept_body(tool, args, answer)
                return shell.Done(0, answer if isinstance(answer, str) else json.dumps(answer), "")
        if tool == "git":
            return self.real_run(tool, args, stdin_text=stdin_text, timeout=timeout)
        if self.written is not None and self._is_view(tool, args):
            return shell.Done(0, json.dumps(self._with_kept_body(tool, args, {})), "")
        return shell.Done(1, "", f"no fake answer for {tool} {' '.join(args)}")

    def _keep_body(self, tool, args, stdin_text):
        if tool == "gh" and args[:2] in (["pr", "edit"], ["pr", "create"]):
            self.written = stdin_text
        elif tool == "glab" and args[:2] == ["api", "-X"] and "description" in (stdin_text or ""):
            self.written = json.loads(stdin_text).get("description", self.written)

    @staticmethod
    def _is_view(tool, args):
        return (tool == "gh" and args[:2] == ["pr", "view"]) or (tool == "glab" and args[:2] == ["mr", "view"])

    def _with_kept_body(self, tool, args, answer):
        """A view after a body write shows that body, unless the rule names another."""
        if self.written is None or not self._is_view(tool, args) or not isinstance(answer, dict):
            return answer
        return {"gh": {"body": self.written}, "glab": {"description": self.written}}[tool] | answer

    def calls_to(self, tool, *prefix):
        return [call for call in self.calls
                if call[0] == tool and tuple(call[1][:len(prefix)]) == prefix]


@pytest.fixture
def tools(monkeypatch):
    fake = FakeTools(shell.run_tool)
    monkeypatch.setattr(shell, "run_tool", fake)
    return fake


class PipedTools:
    """gh and glab as real processes, so the real pipes and the real argument limit apply."""

    def __init__(self, folder):
        self.rules = []
        self.rules_file, self.record_file = folder / "rules.json", folder / "record.jsonl"
        self.record_file.write_bytes(b"")

    def on(self, tool, *prefix, answer=""):
        raw = answer if isinstance(answer, bytes) else (answer if isinstance(answer, str) else json.dumps(answer)).encode("utf-8")
        self.rules.insert(0, (tool, list(prefix), raw.hex()))
        self.rules_file.write_text(json.dumps(self.rules), encoding="utf-8")
        return self

    @property
    def calls(self):
        return [json.loads(line) for line in self.record_file.read_text(encoding="utf-8").splitlines()]

    def sent(self, *prefix):
        """The stdin bytes of each call whose arguments start with `prefix`."""
        return [bytes.fromhex(call["stdin"]) for call in self.calls if tuple(call["args"][:len(prefix)]) == prefix]


@pytest.fixture
def piped(monkeypatch, tmp_path):
    folder = tmp_path / "piped"
    folder.mkdir()
    fake = PipedTools(folder)
    real_run = subprocess.run

    def run(argv, **kwargs):
        return real_run([sys.executable, str(FAKE_PROCESS), str(fake.rules_file), str(fake.record_file), *argv], **kwargs)

    monkeypatch.setattr(shell.shutil, "which", lambda tool: tool)
    monkeypatch.setattr(shell.subprocess, "run", run)
    return fake


@pytest.fixture
def preview(tmp_path):
    """A preview file with its pictures; returns (path, receipt, picture paths)."""
    def build(key="PROJ-1", description_hash="h" * 64, pictures=(b"\x89PNG one",), text=""):
        hashes = [hashlib.sha256(data).hexdigest() for data in pictures]
        receipt = hashlib.sha256((key + text + "".join(hashes)).encode("utf-8")).hexdigest()
        folder = tmp_path / "preview"
        folder.mkdir(exist_ok=True)
        paths = []
        for n, data in enumerate(pictures, start=1):
            tag = receipt[:8]
            path = folder / f"afkv2-fig-{tag}-{n}.png"
            path.write_bytes(data)
            paths.append(path)
        file = folder / "preview.json"
        file.write_text(json.dumps({
            "ticket_key": key, "receipt": receipt, "description_hash": description_hash,
            "picture_hashes": hashes,
        }), encoding="utf-8")
        return str(file), receipt, paths
    return build
