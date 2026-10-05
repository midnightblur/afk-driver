"""The user-scoped `tracker` server that setup registers must start, must answer
when Jira credentials are missing, and must never take another server with it.

Every test here spawns a real `server.py` (or the registered command) in a fake
HOME and speaks JSON-RPC to it: a mock would pass against the failures pinned.
"""
from __future__ import annotations

import http.server
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
        write_creds(home, "http://127.0.0.1:9")
        later = rpc.call("tracker_get", {"ticket_key": "A-1"})
        assert later is not None and rpc.alive()
        assert "could not resolve Jira creds" not in text_of(later)
    finally:
        rpc.close()


def write_creds(home: Path, base: str) -> None:
    (home / ".claude.json").write_text(json.dumps({"mcpServers": {"tracker": {"env": {
        "JIRA_BASE_URL": base, "JIRA_EMAIL": "dev@example.com",
        "JIRA_API_TOKEN": "t"}}}}), encoding="utf-8")


class FakeJira(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({"key": "A-1", "fields": {"summary": "reached the fake host"}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def test_corrected_credentials_reach_the_new_host_without_a_restart(home, jira_repo):
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FakeJira)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    env = clean_env(home)
    env["AFK_PLUGIN_ROOT"] = str(ROOT)
    rpc = Rpc(sys.executable, [str(SERVER)], jira_repo, env)
    try:
        assert rpc.start() is not None
        write_creds(home, "http://127.0.0.1:9")                      # a wrong host
        first = rpc.call("tracker_get", {"ticket_key": "A-1"})
        assert "reached the fake host" not in text_of(first)
        write_creds(home, f"http://127.0.0.1:{server.server_address[1]}")   # the right one
        second = rpc.call("tracker_get", {"ticket_key": "A-1"})
        assert "reached the fake host" in text_of(second)
    finally:
        rpc.close()
        server.shutdown()


def test_a_server_started_with_credentials_in_its_env_keeps_them_until_restarted(home, jira_repo):
    """The premise of the H2 wording: the user-scoped entry carries `env`, and
    process env outranks `~/.claude.json`, so a corrected file does not reach it."""
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FakeJira)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    env = clean_env(home)
    env.update(AFK_PLUGIN_ROOT=str(ROOT), JIRA_BASE_URL="http://127.0.0.1:9",
               JIRA_EMAIL="dev@example.com", JIRA_API_TOKEN="t")
    rpc = Rpc(sys.executable, [str(SERVER)], jira_repo, env)
    try:
        assert rpc.start() is not None
        write_creds(home, f"http://127.0.0.1:{server.server_address[1]}")
        stale = rpc.call("tracker_get", {"ticket_key": "A-1"})
        assert stale is not None and rpc.alive()
        assert "URLError" in text_of(stale)              # it still called the old, dead host
        assert "reached the fake host" not in text_of(stale)
    finally:
        rpc.close()
        server.shutdown()


# ---- G7: the registered entry starts ---------------------------------------

def copy_plugin(dest: Path) -> Path:
    """The parts of the plugin the server loads, at `dest`."""
    for part in ("mcp-servers", "adapters", "scripts/afk-config.py",
                 "skills/afk/setup/scripts/tracker_registration.py"):
        src, target = ROOT / part, dest / part
        target.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, target, ignore=shutil.ignore_patterns("__pycache__"))
        else:
            shutil.copy2(src, target)
    shutil.copy2(ROOT / ".mcp.json", dest / ".mcp.json")
    return dest


def cache_dir(base: Path, version: str = "9.9.9") -> Path:
    return base / "plugins" / "cache" / "afk-toolkit" / "afk" / version


def assert_registered_entry_starts(installed: Path, home: Path, repo: Path):
    entry = registration().entry({}, installed, sys.executable)
    assert entry["args"][-1] == str(installed)      # the root is always passed
    rpc = Rpc(entry["command"], entry["args"], repo, clean_env(home))
    try:
        reply = rpc.start()
        assert reply is not None, rpc.stderr_text()
        assert reply["result"]["serverInfo"]["name"] == "tracker"
    finally:
        rpc.close()


def test_the_entry_starts_from_a_cache_install_with_no_root_in_the_environment(home, jira_repo):
    assert_registered_entry_starts(copy_plugin(cache_dir(home / ".claude")), home, jira_repo)


def test_the_entry_starts_from_a_dev_clone(home, jira_repo, tmp_path):
    assert_registered_entry_starts(copy_plugin(tmp_path / "dev-clone"), home, jira_repo)


def test_the_entry_starts_from_a_cache_outside_home(home, jira_repo, tmp_path):
    assert_registered_entry_starts(copy_plugin(cache_dir(tmp_path / "cfg")), home, jira_repo)


def test_a_newer_and_an_older_version_registers_the_one_setup_ran_from(home, jira_repo):
    older = copy_plugin(cache_dir(home / ".claude", "1.9.0"))
    newer = copy_plugin(cache_dir(home / ".claude", "1.10.0"))
    (older / "mcp-servers" / "tracker" / "server.py").write_text(
        'raise SystemExit("ran OLD 1.9.0")\n', encoding="utf-8")
    entry = registration().entry({}, newer, sys.executable)
    rpc = Rpc(entry["command"], entry["args"], jira_repo, clean_env(home))
    try:
        reply = rpc.start()
        assert reply is not None, rpc.stderr_text()
    finally:
        rpc.close()


# ---- G8: only afk's own legacy entry is legacy ------------------------------

# The shape another plugin's hand-registered Jira server has on a real machine.
UNRELATED = {"type": "stdio", "command": "python",
             "args": ["C:\\work\\core-services\\plugins\\workflow\\mcp-servers\\jira\\server.py"],
             "env": {"JIRA_BASE_URL": "https://other.example.net", "JIRA_API_TOKEN": "theirs"}}


def test_an_unrelated_jira_server_survives_byte_identical():
    reg = registration()
    servers = {"jira": json.loads(json.dumps(UNRELATED)), "other": {"command": "x"}}
    before = json.dumps(servers["jira"], sort_keys=True)
    result = reg.register(servers, {"JIRA_BASE_URL": "https://mine.example.net"}, ROOT, sys.executable)
    assert json.dumps(result["jira"], sort_keys=True) == before
    assert result["other"] == {"command": "x"}
    assert result["tracker"]["env"] == {"JIRA_BASE_URL": "https://mine.example.net"}
    assert reg.foreign_legacy(servers, ROOT) is True


def test_an_unrelated_jira_servers_env_is_not_prior_credentials():
    assert registration().prior_env({"jira": json.loads(json.dumps(UNRELATED))}, ROOT) == {}


@pytest.mark.parametrize("path", [
    "{root}/mcp-servers/jira/server.py",
    "C:/Users/x/.claude/plugins/cache/afk-toolkit/afk/1.9.0/mcp-servers/jira/server.py",
    "C:\\Users\\x\\.claude\\plugins\\cache\\afk-marketplace-dev\\afk-dev\\1.0.3\\mcp-servers\\jira\\server.py",
    "C:/Users/x/.claude/plugins/cache/afk-marketplace/afk-toolkit/1.0.8/mcp-servers/jira/server.py",
])
def test_afks_own_legacy_jira_entry_is_reused_and_replaced(path):
    reg = registration()
    legacy = {"type": "stdio", "command": "python", "args": [path.format(root=ROOT.as_posix())],
              "env": {"JIRA_BASE_URL": "https://mine.example.net"}}
    assert reg.prior_env({"jira": legacy}, ROOT) == legacy["env"]
    result = reg.register({"jira": legacy}, dict(legacy["env"]), ROOT, sys.executable)
    assert "jira" not in result and "tracker" in result
    assert reg.foreign_legacy({"jira": legacy}, ROOT) is False


def test_the_launcher_entry_under_either_key_is_afks_own():
    reg = registration()
    entry = reg.entry({"JIRA_BASE_URL": "https://mine.example.net"}, ROOT, sys.executable)
    assert reg.prior_env({"jira": entry}, ROOT) == entry["env"]


def test_setup_secrets_places_the_entry_through_the_registration_module():
    source = (ROOT / "skills" / "afk" / "setup" / "scripts" / "setup_secrets.py").read_text(encoding="utf-8")
    assert "tracker_registration" in source
    assert "foreign_legacy" in source
    assert 'servers.pop(LEGACY_MCP_KEY' not in source
