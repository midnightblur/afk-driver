"""The tracker MCP server resolves its tracker kind per call, from the project root.

Pinned: a server started below the repository root still finds the repository's
`.afk/config.yaml`; a config written or changed after start takes effect on the
next call; `CLAUDE_PROJECT_DIR` outranks the working directory; a kind that
becomes unknown mid-session is an answer, not an exit.
"""
from __future__ import annotations

import importlib.util
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
