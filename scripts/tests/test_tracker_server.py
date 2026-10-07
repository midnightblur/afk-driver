"""The tracker MCP server resolves its tracker kind per call, from the project root.

Pinned: a server started below the repository root still finds the repository's
`.afk/config.yaml`; a config written or changed after start takes effect on the
next call; `CLAUDE_PROJECT_DIR` outranks the working directory; a kind that
becomes unknown mid-session is an answer, not an exit.
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
import types
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
SERVER = PLUGIN_ROOT / "mcp-servers" / "tracker" / "server.py"


class _FastMCP:
    def __init__(self, name):
        self.name = name

    def tool(self):
        return lambda fn: fn

    def run(self):
        pass


@pytest.fixture
def load_server(monkeypatch, tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    for name in ("HOME", "USERPROFILE"):
        monkeypatch.setenv(name, str(home))
    monkeypatch.delenv("AFK_CONFIG", raising=False)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.setenv("AFK_PLUGIN_ROOT", str(PLUGIN_ROOT))
    monkeypatch.setattr(sys, "argv", ["server.py"])
    for name, attrs in (("mcp", {}), ("mcp.server", {}),
                        ("mcp.server.fastmcp", {"FastMCP": _FastMCP})):
        module = types.ModuleType(name)
        module.__dict__.update(attrs)
        monkeypatch.setitem(sys.modules, name, module)

    def load():
        spec = importlib.util.spec_from_file_location("tracker_server_under_test", SERVER)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    return load


def repo(path: Path, tracker: str | None = None) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    if tracker:
        write_config(path, tracker)
    return path


def write_config(root: Path, tracker: str) -> None:
    (root / ".afk").mkdir(exist_ok=True)
    (root / ".afk" / "config.yaml").write_text(f"schema: 1\ntracker: {tracker}\n", encoding="utf-8")


def test_a_server_started_below_the_repo_root_reads_the_repo_config(load_server, monkeypatch, tmp_path):
    root = repo(tmp_path / "repo", "github-issues")
    sub = root / "sub"
    sub.mkdir()
    monkeypatch.chdir(sub)
    kind, _ = load_server()._api()
    assert kind == "github-issues"


def test_a_config_written_after_start_applies_to_the_next_call(load_server, monkeypatch, tmp_path):
    root = repo(tmp_path / "repo")
    monkeypatch.chdir(root)
    server = load_server()
    assert server._api()[0] == "none"
    assert server._call("tracker_get", ticket_key="1")["unsupported"] is True
    write_config(root, "github-issues")
    assert server._api()[0] == "github-issues"


def test_claude_project_dir_outranks_the_working_directory(load_server, monkeypatch, tmp_path):
    a = repo(tmp_path / "a", "github-issues")
    b = repo(tmp_path / "b", "none")
    monkeypatch.chdir(b)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(a))
    assert load_server()._api()[0] == "github-issues"


def test_a_kind_that_turns_unknown_mid_session_is_an_answer(load_server, monkeypatch, tmp_path):
    root = repo(tmp_path / "repo", "github-issues")
    monkeypatch.chdir(root)
    server = load_server()
    write_config(root, "nonesuch")
    answer = server._call("tracker_get", ticket_key="1")
    assert answer["error"] is True and answer["operation"] == "tracker_get"
    assert "nonesuch" in answer["reason"]


def test_an_unknown_kind_at_start_still_exits(load_server, monkeypatch, tmp_path):
    root = repo(tmp_path / "repo", "nonesuch")
    monkeypatch.chdir(root)
    with pytest.raises(SystemExit):
        load_server()


def test_claude_project_dir_below_the_git_root_still_finds_the_repo_config(load_server, monkeypatch, tmp_path):
    root = repo(tmp_path / "repo", "github-issues")
    sub = root / "sub"
    sub.mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(sub))
    assert load_server()._api()[0] == "github-issues"


def _github_adapter():
    spec = importlib.util.spec_from_file_location(
        "afk_tracker_github_under_test", PLUGIN_ROOT / "adapters" / "tracker" / "github-issues" / "api.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _github_config(root: Path, repo_name: str) -> None:
    (root / ".afk").mkdir(exist_ok=True)
    (root / ".afk" / "config.yaml").write_text(
        f"schema: 1\ntracker: github-issues\ngithub-issues:\n  repo: {repo_name}\n", encoding="utf-8")


def test_the_github_adapter_reads_its_block_from_the_repo_root(load_server, monkeypatch, tmp_path):
    monkeypatch.delenv("GH_REPO", raising=False)
    root = repo(tmp_path / "repo")
    _github_config(root, "acme/one")
    sub = root / "sub"
    sub.mkdir()
    monkeypatch.chdir(sub)
    assert _github_adapter().repo() == "acme/one"


def test_the_github_adapter_sees_a_config_edit_without_a_restart(load_server, monkeypatch, tmp_path):
    monkeypatch.delenv("GH_REPO", raising=False)
    root = repo(tmp_path / "repo")
    _github_config(root, "acme/one")
    monkeypatch.chdir(root)
    adapter = _github_adapter()
    assert adapter.repo() == "acme/one"
    _github_config(root, "acme/two")
    assert adapter.repo() == "acme/two"


# ---------------------------------------- the real server over piped stdio

def _rpc_session(env, cwd):
    """Spawn server.py with piped stdio, as a harness does, and return an `ask`."""
    import json
    import queue
    import threading

    proc = subprocess.Popen([sys.executable, str(SERVER), str(PLUGIN_ROOT)], cwd=cwd, env=env,
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, text=True)
    lines: queue.Queue = queue.Queue()
    threading.Thread(target=lambda: [lines.put(l) for l in proc.stdout], daemon=True).start()

    def send(message):
        proc.stdin.write(json.dumps(message) + "\n")
        proc.stdin.flush()

    def ask(ident, method, params, timeout=20):
        send({"jsonrpc": "2.0", "id": ident, "method": method, "params": params})
        while True:
            reply = json.loads(lines.get(timeout=timeout))
            if reply.get("id") == ident:
                return reply

    ask(1, "initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                          "clientInfo": {"name": "t", "version": "0"}})
    send({"jsonrpc": "2.0", "method": "notifications/initialized"})
    return proc, ask


def _tool_answer(reply):
    import json
    return json.loads(reply["result"]["content"][0]["text"])


def test_a_call_over_piped_stdio_from_a_subdirectory_answers_fast(tmp_path, monkeypatch):
    pytest.importorskip("mcp")
    import time
    root = repo(tmp_path / "repo", "github-issues")
    sub = root / "sub"
    sub.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PROJECT_DIR"}
    git = shutil.which("git")
    git_dir = str(Path(git).parent)  # git yes, gh no
    if os.name != "nt":  # git's folder may hold gh too (/usr/bin): link git alone into a folder of its own
        (tmp_path / "bin").mkdir()
        os.symlink(git, tmp_path / "bin" / "git")
        git_dir = str(tmp_path / "bin")
    env.update(HOME=str(home), USERPROFILE=str(home), PATH=git_dir + os.pathsep + str(Path(sys.executable).parent))
    proc, ask = _rpc_session(env, sub)
    try:
        started = time.monotonic()
        answer = _tool_answer(ask(2, "tools/call", {"name": "tracker_get",
                                                    "arguments": {"ticket_key": "1"}}))
        elapsed = time.monotonic() - started
    finally:
        proc.kill()
    assert answer.get("unavailable") is True and "github-issues" in answer["reason"], answer
    assert elapsed < 10, f"a git spawn inherited the server's stdin pipe and hung ({elapsed:.0f}s)"


def test_gh_never_inherits_the_servers_stdin(monkeypatch):
    adapter = _github_adapter()
    seen = []

    def fake_run(argv, **kwargs):
        seen.append(kwargs)
        return subprocess.CompletedProcess(argv, 0, stdout="{}", stderr="")

    monkeypatch.setattr(adapter.shutil, "which", lambda name: "/usr/bin/gh")
    monkeypatch.setattr(adapter.subprocess, "run", fake_run)
    adapter._gh("issue", "view", "1")
    adapter._gh("issue", "comment", "1", "--body-file", "-", stdin="text")
    assert seen[0]["stdin"] is subprocess.DEVNULL and "input" not in seen[0]
    assert seen[1]["input"] == "text" and "stdin" not in seen[1]


def test_a_refusal_names_the_checkout_the_server_read(tmp_path):
    """H2 decides from the server's answer: CPD = A, the prober stands in B."""
    pytest.importorskip("mcp")
    a = repo(tmp_path / "a", "none")
    b = repo(tmp_path / "b", "jira")
    home = tmp_path / "home"
    home.mkdir()
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PROJECT_DIR"}
    env.update(HOME=str(home), USERPROFILE=str(home), CLAUDE_PROJECT_DIR=str(a))
    proc, ask = _rpc_session(env, b)
    try:
        answer = _tool_answer(ask(2, "tools/call", {"name": "tracker_get",
                                                    "arguments": {"ticket_key": "1"}}))
    finally:
        proc.kill()
    assert answer.get("unsupported") is True and "tracker: none" in answer["reason"]
    assert Path(answer["config_root"]).resolve() == a.resolve()


def test_an_error_answer_names_the_checkout_too(load_server, monkeypatch, tmp_path):
    root = repo(tmp_path / "repo", "jira")
    monkeypatch.chdir(root)
    server = load_server()
    write_config(root, "no-such-kind")
    answer = server.tracker_get("1")
    assert answer["error"] is True
    assert Path(answer["config_root"]).resolve() == root.resolve()
