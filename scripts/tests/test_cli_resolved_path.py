"""A forge CLI runs from the path `shutil.which` found, so a script stub on PATH is the CLI run.

On Windows a bare `subprocess.run(["gh", ...])` starts only `gh.exe`: a `gh.cmd`
stub passes the `which` check and is then skipped for whatever `gh.exe` follows.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[2]


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def stub(tmp_path: Path, monkeypatch, tool: str, answer: str) -> None:
    """Put a script stub named `tool` first on PATH; it prints `answer`."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    if os.name == "nt":
        (bin_dir / f"{tool}.cmd").write_text(f"@echo {answer}\r\n", encoding="utf-8")
    else:
        script = bin_dir / tool
        script.write_text(f"#!/bin/sh\necho '{answer}'\n", encoding="utf-8")
        script.chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ["PATH"])


def test_github_issues_adapter_runs_the_stub_on_path(tmp_path, monkeypatch):
    stub(tmp_path, monkeypatch, "gh", '{"stub": true}')
    api = load(PLUGIN_ROOT / "adapters" / "tracker" / "github-issues" / "api.py", "afk_gh_resolved_api")
    assert api._gh("api", "user") == {"stub": True}


def test_forge_user_runs_the_stub_on_path(tmp_path, monkeypatch):
    stub(tmp_path, monkeypatch, "gh", "stub-login")
    values = load(PLUGIN_ROOT / "skills" / "afk" / "setup" / "scripts" / "developer_values.py",
                  "afk_gh_resolved_values")
    assert values.forge_user("github") == "stub-login"
