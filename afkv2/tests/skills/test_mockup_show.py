"""Tests for mockup_show.py: show, wait, reply and end over the launcher (SDD §3, §9b; ADR-0003 of ticket 207).

A `.py` stub of lavish-axi stands behind the real launcher: a package at the pinned version, found through
`shutil.which`, so the pin and host checks run as they do on a developer machine. mockup_show runs through its command
line in this process, because a separate process cannot point the launcher at a `.py` stub (decision D-5);
prototype_files runs as a separate process. No real lavish host, browser or live app runs here.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[2]
SCRIPTS = PLUGIN / "skills" / "prototype" / "scripts"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "mockup_show"
HOST_FIXTURES = PLUGIN / "tests" / "engine" / "fixtures"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(PLUGIN / "engine"))

import launcher  # noqa: E402
import mockup_show  # noqa: E402


@pytest.fixture
def data_home(tmp_path, monkeypatch):
    home = tmp_path / "local"
    home.mkdir()
    monkeypatch.setenv("LOCALAPPDATA", str(home))
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    monkeypatch.delenv("LAVISH_AXI_HOST", raising=False)
    return home


@pytest.fixture
def lavish(tmp_path, monkeypatch, data_home):
    """The stub package folder: `<op>.txt` beside the stub is the output of that operation."""
    bin_folder = tmp_path / "bin"
    package = bin_folder / "node_modules" / "lavish-axi"
    package.mkdir(parents=True)
    shutil.copyfile(FIXTURES / "lavish_stub.py", package / "stub.py")
    manifest = {"name": "lavish-axi", "version": launcher.PIN, "bin": {"lavish-axi": "stub.py"}}
    (package / "package.json").write_text(json.dumps(manifest), "utf-8")
    if os.name == "nt":
        shim = bin_folder / "lavish-axi.cmd"
        shim.write_text("@exit /b 1\r\n", "utf-8")
        found = {"lavish-axi": str(shim), "node": sys.executable}
    else:
        shim = bin_folder / "lavish-axi"
        shim.write_text(f"#!{sys.executable}\nimport runpy, sys\nsys.argv[0] = {str(package / 'stub.py')!r}\n"
                        f"runpy.run_path(sys.argv[0], run_name='__main__')\n", "utf-8")
        shim.chmod(0o755)
        found = {"lavish-axi": str(shim)}
    monkeypatch.setattr(launcher.shutil, "which", lambda name: found.get(name) or shutil.which(name))
    shutil.copyfile(HOST_FIXTURES / "host-open.txt", package / "open.txt")
    return package


def calls(package):
    log = package / "calls.jsonl"
    return [json.loads(line) for line in log.read_text("utf-8").splitlines()] if log.is_file() else []


@pytest.fixture
def mockup(tmp_path):
    page = tmp_path / "spec" / "prototype" / "orders.html"
    page.parent.mkdir(parents=True)
    shutil.copyfile(FIXTURES / "orders.html", page)
    return page


def show_cli(capsys, *args):
    code = mockup_show.main([str(arg) for arg in args])
    return code, json.loads(capsys.readouterr().out)


# --- wait on recorded poll output (VR-013) -------------------------------------------------------------------------

def test_wait_on_recorded_poll_output_writes_each_note_with_uid_prompt_selector_tag_and_text(lavish, mockup, tmp_path,
                                                                                            capsys):
    shutil.copyfile(HOST_FIXTURES / "host-poll-two-prompts.txt", lavish / "poll.txt")
    notes = tmp_path / "local" / "afkv2" / "notes" / "run-1.json"
    code, answer = show_cli(capsys, "wait", "--mockup", mockup, "--notes-file", notes)
    assert code == 0 and answer["ok"] is True, answer
    assert answer["count"] == 2 and answer["ended"] is True
    assert json.loads(notes.read_text("utf-8")) == [
        {"uid": "1", "prompt": "first, with a comma", "selector": "p", "tag": "note", "text": "x"},
        {"uid": "2", "prompt": "- second\nline", "selector": None, "tag": "choice", "text": "y"},
    ]
    assert calls(lavish) == [["poll", str(mockup)]]
