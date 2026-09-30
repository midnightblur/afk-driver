"""The user-scoped `tracker` server that setup registers must start, must answer
when Jira credentials are missing, and must never take another server with it.

Every test here spawns a real `server.py` (or the registered command) in a fake
HOME and speaks JSON-RPC to it: a mock would pass against the failures pinned.
"""
from __future__ import annotations

import importlib.util
import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "mcp-servers" / "tracker" / "server.py"
REGISTRATION = ROOT / "skills" / "afk" / "setup" / "scripts" / "tracker_registration.py"
ROOT_VARS = ("AFK_PLUGIN_ROOT", "CLAUDE_PLUGIN_ROOT", "PLUGIN_ROOT", "CLAUDE_PROJECT_DIR",
             "JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN", "AFK_CONFIG")


def registration():
    spec = importlib.util.spec_from_file_location("tracker_registration", REGISTRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def clean_env(home: Path) -> dict:
    env = {k: v for k, v in os.environ.items() if k not in ROOT_VARS}
    env["HOME"] = env["USERPROFILE"] = str(home)
    return env


class Rpc:
    """A spawned MCP stdio server and a line-per-message JSON-RPC client."""

    def __init__(self, command, args, cwd, env):
        self.proc = subprocess.Popen(
            [command, *args], cwd=str(cwd), env=env, text=True, bufsize=1,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.next_id = 0
        self.lines: queue.Queue = queue.Queue()
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self):
        for line in self.proc.stdout:
            self.lines.put(line)
        self.lines.put(None)

    def send(self, method, params=None, notify=False):
        message = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            message["params"] = params
        if not notify:
            self.next_id += 1
            message["id"] = self.next_id
        self.proc.stdin.write(json.dumps(message) + "\n")
        self.proc.stdin.flush()
        return None if notify else self.next_id

    def answer(self, request_id, timeout=30):
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                line = self.lines.get(timeout=max(0.1, deadline - time.time()))
            except queue.Empty:
                return None
            if line is None:
                return None
            reply = json.loads(line)
            if reply.get("id") == request_id:
                return reply
        return None

    def start(self):
        reply = self.answer(self.send("initialize", {
            "protocolVersion": "2024-11-05", "capabilities": {},
            "clientInfo": {"name": "test", "version": "0"}}))
        if reply is not None:
            self.send("notifications/initialized", notify=True)
        return reply

    def call(self, tool, arguments):
        return self.answer(self.send("tools/call", {"name": tool, "arguments": arguments}))

    def stderr_text(self) -> str:
        if self.alive():
            self.proc.kill()
        self.proc.wait()
        return self.proc.stderr.read()

    def alive(self) -> bool:
        return self.proc.poll() is None

    def close(self):
        if self.alive():
            self.proc.kill()
        self.proc.wait()
        for stream in (self.proc.stdin, self.proc.stdout, self.proc.stderr):
            stream.close()


@pytest.fixture
def home(tmp_path):
    h = tmp_path / "home"
    h.mkdir()
    return h


@pytest.fixture
def jira_repo(tmp_path):
    repo = tmp_path / "repo"
    (repo / ".afk").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / ".afk" / "config.yaml").write_text("schema: 1\ntracker: jira\n", encoding="utf-8")
    return repo


def text_of(reply) -> str:
    return json.dumps(reply)


# ---- G1: no credentials is an answer, not an exit ---------------------------

def test_a_call_without_jira_credentials_is_answered_and_the_server_lives(home, jira_repo):
    env = clean_env(home)
    env["AFK_PLUGIN_ROOT"] = str(ROOT)
    rpc = Rpc(sys.executable, [str(SERVER)], jira_repo, env)
    try:
        assert rpc.start() is not None
        reply = rpc.call("tracker_get", {"ticket_key": "ABC-1"})
        assert reply is not None, rpc.stderr_text()
        body = text_of(reply)
        assert "could not resolve Jira creds" in body
        assert '\\"error\\": true' in body or '"error": true' in body
        assert rpc.alive()
    finally:
        rpc.close()


def test_credentials_written_after_the_failed_call_apply_without_a_restart(home, jira_repo):
    env = clean_env(home)
    env["AFK_PLUGIN_ROOT"] = str(ROOT)
    rpc = Rpc(sys.executable, [str(SERVER)], jira_repo, env)
    try:
        assert rpc.start() is not None
        assert "could not resolve Jira creds" in text_of(rpc.call("tracker_get", {"ticket_key": "A-1"}))
        (home / ".claude.json").write_text(json.dumps({"mcpServers": {"tracker": {"env": {
            "JIRA_BASE_URL": "http://127.0.0.1:9", "JIRA_EMAIL": "dev@example.com",
            "JIRA_API_TOKEN": "t"}}}}), encoding="utf-8")
        later = rpc.call("tracker_get", {"ticket_key": "A-1"})
        assert later is not None and rpc.alive()
        assert "could not resolve Jira creds" not in text_of(later)
    finally:
        rpc.close()


# ---- G7: the registered entry starts ---------------------------------------

def fake_cache_install(home: Path) -> Path:
    """The parts of the plugin the server loads, under a harness cache path."""
    root = home / ".claude" / "plugins" / "cache" / "afk-toolkit" / "afk" / "9.9.9"
    for part in ("mcp-servers", "adapters", "scripts/afk-config.py"):
        src, dst = ROOT / part, root / part
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__"))
        else:
            shutil.copy2(src, dst)
    shutil.copy2(ROOT / ".mcp.json", root / ".mcp.json")
    return root


def test_the_registered_entry_starts_with_no_plugin_root_in_the_environment(home, jira_repo):
    installed = fake_cache_install(home)
    entry = registration().entry({}, installed, sys.executable)
    rpc = Rpc(entry["command"], entry["args"], jira_repo, clean_env(home))
    try:
        reply = rpc.start()
        assert reply is not None, rpc.stderr_text()
        assert reply["result"]["serverInfo"]["name"] == "tracker"
    finally:
        rpc.close()


def test_a_cache_registration_carries_no_versioned_path(home):
    installed = fake_cache_install(home)
    entry = registration().entry({}, installed, sys.executable)
    assert all(str(installed) not in arg for arg in entry["args"])
    assert len(entry["args"]) == 2 and entry["args"][0] == "-c"    # launcher only, no root


def test_a_checkout_outside_any_cache_is_passed_as_the_root(home, jira_repo, tmp_path):
    checkout = tmp_path / "dev-clone"
    for part in ("mcp-servers", "adapters", "scripts/afk-config.py"):
        src, dst = ROOT / part, checkout / part
        dst.parent.mkdir(parents=True, exist_ok=True)
        (shutil.copytree if src.is_dir() else shutil.copy2)(src, dst)
    shutil.copy2(ROOT / ".mcp.json", checkout / ".mcp.json")
    entry = registration().entry({}, checkout, sys.executable)
    assert str(checkout) in entry["args"]
    rpc = Rpc(entry["command"], entry["args"], jira_repo, clean_env(home))
    try:
        assert rpc.start() is not None, rpc.stderr_text()
    finally:
        rpc.close()


# ---- G8: only afk's own legacy entry is legacy ------------------------------

UNRELATED = {"type": "stdio", "command": "node",
             "args": ["C:/work/core-services/mcp-servers/jira/server.js"],
             "env": {"JIRA_BASE_URL": "https://other.example.net", "JIRA_API_TOKEN": "theirs"}}


def test_an_unrelated_jira_server_survives_byte_identical():
    reg = registration()
    servers = {"jira": json.loads(json.dumps(UNRELATED)), "other": {"command": "x"}}
    before = json.dumps(servers["jira"], sort_keys=True)
    result = reg.register(servers, {"JIRA_BASE_URL": "https://mine.example.net"}, ROOT, sys.executable)
    assert json.dumps(result["jira"], sort_keys=True) == before
    assert result["other"] == {"command": "x"}
    assert result["tracker"]["env"] == {"JIRA_BASE_URL": "https://mine.example.net"}


def test_an_unrelated_jira_servers_env_is_not_prior_credentials():
    reg = registration()
    assert reg.prior_env({"jira": json.loads(json.dumps(UNRELATED))}) == {}


def test_afks_own_legacy_jira_entry_is_reused_and_replaced():
    reg = registration()
    legacy = {"type": "stdio", "command": "python",
              "args": ["C:/x/plugins/cache/m/afk/1.0.0/mcp-servers/jira/server.py"],
              "env": {"JIRA_BASE_URL": "https://mine.example.net"}}
    assert reg.prior_env({"jira": legacy}) == legacy["env"]
    result = reg.register({"jira": legacy}, dict(legacy["env"]), ROOT, sys.executable)
    assert "jira" not in result and "tracker" in result


def test_setup_secrets_places_the_entry_through_the_registration_module():
    source = (ROOT / "skills" / "afk" / "setup" / "scripts" / "setup_secrets.py").read_text(encoding="utf-8")
    assert "tracker_registration" in source
    assert 'servers.pop(LEGACY_MCP_KEY' not in source
