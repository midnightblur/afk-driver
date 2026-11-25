"""Tests for mockup_show.py: show, wait, reply and end over the launcher (SDD §3, §9b; ADR-0003 of ticket 207).

A `.py` stub of lavish-axi stands behind the real launcher: a package at the pinned version, found through
`shutil.which`, so the pin and host checks run as they do on a developer machine. mockup_show runs through its command
line in this process, because a separate process cannot point the launcher at a `.py` stub (decision D-5);
prototype_files runs as a separate process. No real lavish host, browser or live app runs here. Each failure message
shows the input (the command and every change made to the fixture), the expected value and the actual value.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
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

CHANGES = []


@pytest.fixture(autouse=True)
def _fresh_changes():
    CHANGES.clear()


def note(change):
    """Record a change to the fixture, so that a failure message names it as input."""
    CHANGES.append(change)


@dataclass
class Ran:
    code: int
    answer: dict
    given: str


def _given(command, args):
    return f"{command} {' '.join(str(arg) for arg in args)}" + (f" after: {'; '.join(CHANGES)}" if CHANGES else "")


def expect(actual, expected, given):
    assert actual == expected, f"\ninput: {given}\nexpected: {expected!r}\nactual: {actual!r}"


def expect_in(part, whole, given):
    assert part in whole, f"\ninput: {given}\nexpected to hold: {part!r}\nactual: {whole!r}"


def expect_not_in(part, whole, given):
    assert part not in whole, f"\ninput: {given}\nexpected not to hold: {part!r}\nactual: {whole!r}"


def expect_prefix(prefix, whole, given):
    assert str(whole).startswith(prefix), f"\ninput: {given}\nexpected to start with: {prefix!r}\nactual: {whole!r}"


def expect_ok(ran):
    expect(ran.code, 0, f"{ran.given} (answer {ran.answer!r})")
    expect(ran.answer.get("ok"), True, f"{ran.given} (answer {ran.answer!r})")


def expect_refusal(ran, code):
    expect(ran.code, 1, f"{ran.given} (answer {ran.answer!r})")
    expect(ran.answer.get("error", {}).get("code"), code, f"{ran.given} (answer {ran.answer!r})")


def expect_field(ran, field, expected):
    expect(ran.answer.get(field), expected, f"{ran.given} (field {field!r} of answer {ran.answer!r})")


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
    note(f"lavish-axi {launcher.PIN} stub on PATH")
    return package


def host_output(package, op, fixture, code=None):
    """Make the stub answer `op` with the recorded `fixture` output and, when given, that exit code."""
    shutil.copyfile(fixture, package / f"{op}.txt")
    if code is not None:
        (package / f"{op}.code").write_text(str(code), "utf-8")
    note(f"lavish {op} answers {fixture.name}" + (f" with exit {code}" if code is not None else ""))


def no_lavish_on_path(monkeypatch):
    monkeypatch.setattr(launcher.shutil, "which", lambda name: None)
    note("lavish-axi not on PATH")


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
    args = [str(arg) for arg in args]
    code = mockup_show.main(args)
    return Ran(code, json.loads(capsys.readouterr().out), _given("mockup_show.py", args))


# --- wait on recorded poll output (VR-013) -------------------------------------------------------------------------

def test_wait_on_recorded_poll_output_writes_each_note_with_uid_prompt_selector_tag_and_text(lavish, mockup, tmp_path,
                                                                                            capsys):
    host_output(lavish, "poll", HOST_FIXTURES / "host-poll-two-prompts.txt")
    notes = tmp_path / "local" / "afkv2" / "notes" / "run-1.json"
    ran = show_cli(capsys, "wait", "--mockup", mockup, "--notes-file", notes)
    expect_ok(ran)
    expect_field(ran, "count", 2)
    expect_field(ran, "ended", True)
    expect(json.loads(notes.read_text("utf-8")), [
        {"uid": "1", "prompt": "first, with a comma", "selector": "p", "tag": "note", "text": "x"},
        {"uid": "2", "prompt": "- second\nline", "selector": None, "tag": "choice", "text": "y"},
    ], f"{ran.given} (the notes file)")
    expect(calls(lavish), [["poll", str(mockup)]], f"{ran.given} (the lavish calls)")


# --- the start, show and wait chain on a scratch frontend (VR-001) -------------------------------------------------

PROTOTYPE_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "prototype"
TICKET = "PROJ-7"
WEB = {"name": "web", "source": "frontend/web", "catalog": "design/web"}
LIVE = {"start": "python -m http.server 4999", "address": "http://127.0.0.1:4999"}


def git(repo, *args):
    done = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    expect(done.returncode, 0, f"git {' '.join(args)} in {repo} (stderr {done.stderr!r})")
    return done.stdout.strip()


def prototype_files(repo, *args):
    done = subprocess.run([sys.executable, str(SCRIPTS / "prototype_files.py"), *args], cwd=repo, capture_output=True,
                          text=True, encoding="utf-8", stdin=subprocess.DEVNULL)
    return Ran(done.returncode, json.loads(done.stdout), _given("prototype_files.py", args))


@pytest.fixture
def frontend_repo(tmp_path):
    """A scratch git repository: 1 frontend in the config, its source folder, a spec folder with 2 screen stories."""
    def make(**config):
        root = tmp_path / "repo"
        (root / ".afkv2").mkdir(parents=True)
        git(root, "init", "-q", "-b", "main")
        settings = {"spec_folder": "docs", "frontends": [WEB], **config}
        (root / ".afkv2" / "config.json").write_text(json.dumps(settings), "utf-8")
        (root / "frontend" / "web").mkdir(parents=True)
        shutil.copytree(PROTOTYPE_FIXTURES / "spec", root / "docs" / TICKET)
        note(f"config {settings!r}; spec folder docs/{TICKET} with 2 screen stories")
        return root
    return make


def test_start_show_and_wait_show_the_mockup_itself_and_bring_back_the_note_with_its_element(frontend_repo, lavish,
                                                                                               capsys):
    repo = frontend_repo(live=LIVE)
    catalog = repo / "design" / "web"
    catalog.mkdir(parents=True)
    (catalog / "README.md").write_text("# Catalog\n", "utf-8")
    (catalog / "tokens.css").write_text(":root { --accent: #36c; }\n", "utf-8")
    note("catalog design/web with README.md and tokens.css")
    start = prototype_files(repo, "start", "--ticket", TICKET)
    expect(start.code, 0, f"{start.given} (answer {start.answer!r})")
    expect_field(start, "frontend", {"name": "web", "source": "frontend/web", "catalog": "design/web"})
    expect((start.answer.get("live") or {}).get("address"), "http://127.0.0.1:4999",
           f"{start.given} (field 'live' of answer {start.answer!r})")
    expect_field(start, "anchor", "catalog")
    mockup = Path(start.answer["mockup_dir"]) / "orders.html"
    shutil.copyfile(FIXTURES / "orders.html", mockup)
    note("orders.html copied into mockup_dir")
    before = mockup.read_bytes()

    shown = show_cli(capsys, "show", "--mockup", mockup)
    expect(shown.code, 0, f"{shown.given} (answer {shown.answer!r})")
    expect_prefix("http://127.0.0.1:", shown.answer.get("url"), f"{shown.given} (field 'url' of {shown.answer!r})")
    expect_field(shown, "page", str(mockup))
    expect(mockup.read_bytes(), before, f"{shown.given} (the mockup bytes)")
    expect(calls(lavish), [[str(mockup)]], f"{shown.given} (the lavish calls)")

    host_output(lavish, "poll", FIXTURES / "poll-one-note.txt")
    notes = repo.parent / "local" / "afkv2" / "notes" / "run-1.json"
    waited = show_cli(capsys, "wait", "--mockup", mockup, "--notes-file", notes)
    expect(waited.code, 0, f"{waited.given} (answer {waited.answer!r})")
    expect_field(waited, "count", 1)
    expect_field(waited, "ended", False)
    expect(json.loads(notes.read_text("utf-8")), [{"uid": "1", "prompt": "Put Open first in the filter bar",
                                                   "selector": "#filters > button:nth-of-type(2)", "tag": "button",
                                                   "text": "Open"}], f"{waited.given} (the notes file)")
    expect(mockup.read_bytes(), before, f"{waited.given} (the mockup bytes)")


# --- no host: lavish missing, at the wrong pin, or LAVISH_AXI_HOST set (VR-010) ------------------------------------

def no_lavish(monkeypatch, package):
    no_lavish_on_path(monkeypatch)


def old_pin(monkeypatch, package):
    (package / "package.json").write_text(json.dumps({"name": "lavish-axi", "version": "0.1.85",
                                                      "bin": {"lavish-axi": "stub.py"}}), "utf-8")
    note("lavish-axi package.json version 0.1.85")


def unsafe_host(monkeypatch, package):
    monkeypatch.setenv("LAVISH_AXI_HOST", "0.0.0.0")
    note("LAVISH_AXI_HOST=0.0.0.0")


@pytest.mark.parametrize("cause, words", [(no_lavish, "not on PATH"), (old_pin, "0.1.85"),
                                          (unsafe_host, "LAVISH_AXI_HOST")], ids=["missing", "pin", "host"])
def test_show_with_no_usable_host_refuses_no_host_naming_the_cause_and_writes_nothing(lavish, mockup, capsys,
                                                                                         monkeypatch, cause, words):
    cause(monkeypatch, lavish)
    before = mockup.read_bytes()
    listing = sorted(path.name for path in mockup.parent.iterdir())
    ran = show_cli(capsys, "show", "--mockup", mockup)
    expect_refusal(ran, "no-host")
    reason = ran.answer["error"].get("reason", "")
    expect_in(words, reason, f"{ran.given} (the reason)")
    expect_not_in("..", reason, f"{ran.given} (the reason)")
    expect(mockup.read_bytes(), before, f"{ran.given} (the mockup bytes)")
    expect(sorted(path.name for path in mockup.parent.iterdir()), listing, f"{ran.given} (the mockup folder)")
    expect(calls(lavish), [], f"{ran.given} (the lavish calls)")


# --- the source-only chain: no live block, no lavish (VR-003) ------------------------------------------------------

def test_start_show_and_settle_with_no_live_block_and_no_lavish_give_the_file_path_and_settle_source_only(
        frontend_repo, data_home, monkeypatch, capsys):
    repo = frontend_repo()
    no_lavish_on_path(monkeypatch)
    start = prototype_files(repo, "start", "--ticket", TICKET)
    expect(start.code, 0, f"{start.given} (answer {start.answer!r})")
    expect_field(start, "live", None)
    expect_field(start, "anchor", "source")
    mockup = Path(start.answer["mockup_dir"]) / "orders.html"
    shown = show_cli(capsys, "show", "--mockup", mockup)
    expect_refusal(shown, "no-host")
    expect_in(mockup.resolve().as_uri(), shown.answer["error"].get("reason", ""), f"{shown.given} (the reason)")
    expect_in("> Fidelity: source-only", Path(start.answer["prototype_md"]).read_text("utf-8"),
              f"{start.given} (PROTOTYPE.md)")
    settled = prototype_files(repo, "settle", "--ticket", TICKET)
    expect_ok(settled)


# --- the Codex waiting record, the other poll statuses, reply and end (VR-001) -------------------------------------

def test_show_on_codex_writes_the_waiting_record_with_no_document_and_wait_clears_it(lavish, mockup, data_home,
                                                                                    monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("CODEX_THREAD_ID", "thread-1")
    note("CODEX_THREAD_ID=thread-1")
    shown = show_cli(capsys, "show", "--mockup", mockup)
    expect(shown.code, 0, f"{shown.given} (answer {shown.answer!r})")
    record = launcher.read_waiting_record(data_home / "afkv2", "thread-1") or {}
    expect(record.get("document"), None, f"{shown.given} (field 'document' of waiting record {record!r})")
    expect(record.get("page"), str(mockup), f"{shown.given} (field 'page' of waiting record {record!r})")
    expect_field(shown, "waiting_record", str(launcher._waiting_path(data_home / "afkv2", "thread-1")))
    host_output(lavish, "poll", FIXTURES / "poll-one-note.txt")
    waited = show_cli(capsys, "wait", "--mockup", mockup, "--notes-file", tmp_path / "notes.json")
    expect(waited.code, 0, f"{waited.given} (answer {waited.answer!r})")
    expect(launcher.read_waiting_record(data_home / "afkv2", "thread-1"), None, f"{waited.given} (the waiting record)")


def test_a_refused_show_on_codex_writes_no_waiting_record(lavish, mockup, data_home, monkeypatch, capsys):
    monkeypatch.setenv("CODEX_THREAD_ID", "thread-1")
    note("CODEX_THREAD_ID=thread-1")
    no_lavish_on_path(monkeypatch)
    shown = show_cli(capsys, "show", "--mockup", mockup)
    expect(shown.code, 1, f"{shown.given} (answer {shown.answer!r})")
    expect(launcher.read_waiting_record(data_home / "afkv2", "thread-1"), None, f"{shown.given} (the waiting record)")


@pytest.mark.parametrize("fixture", ["host-poll-ended.txt", "host-poll-disconnected.txt"])
def test_wait_status_after_the_browser_closed_answers_ended_with_no_notes(lavish, mockup, tmp_path, capsys, fixture):
    host_output(lavish, "poll", HOST_FIXTURES / fixture)
    notes = tmp_path / "notes.json"
    ran = show_cli(capsys, "wait", "--mockup", mockup, "--notes-file", notes)
    expect(ran.code, 0, f"{ran.given} (answer {ran.answer!r})")
    expect_field(ran, "ended", True)
    expect_field(ran, "count", 0)
    expect(json.loads(notes.read_text("utf-8")), [], f"{ran.given} (the notes file)")


def test_wait_status_with_no_session_refuses_no_session(lavish, mockup, tmp_path, capsys):
    host_output(lavish, "poll", HOST_FIXTURES / "host-error-missing.txt", code=1)
    ran = show_cli(capsys, "wait", "--mockup", mockup, "--notes-file", tmp_path / "notes.json")
    expect_refusal(ran, "no-session")
    expect((tmp_path / "notes.json").exists(), False, f"{ran.given} (the notes file exists)")


def test_wait_status_with_no_host_refuses_no_host_with_the_file_path(lavish, mockup, tmp_path, capsys, monkeypatch):
    no_lavish_on_path(monkeypatch)
    ran = show_cli(capsys, "wait", "--mockup", mockup, "--notes-file", tmp_path / "notes.json")
    expect_refusal(ran, "no-host")
    expect_in(mockup.resolve().as_uri(), ran.answer["error"].get("reason", ""), f"{ran.given} (the reason)")


def test_reply_end_shows_the_reply_file_and_end_closes_the_session(lavish, mockup, tmp_path, capsys, data_home,
                                                                    monkeypatch):
    monkeypatch.setenv("CODEX_THREAD_ID", "thread-1")
    note("CODEX_THREAD_ID=thread-1")
    reply = tmp_path / "reply.md"
    reply.write_text("Moved Open first.\n", "utf-8")
    note("reply.md holds 'Moved Open first.'")
    shown = show_cli(capsys, "show", "--mockup", mockup)
    expect(shown.code, 0, f"{shown.given} (answer {shown.answer!r})")
    replied = show_cli(capsys, "reply", "--mockup", mockup, "--reply-file", reply)
    expect_ok(replied)
    ended = show_cli(capsys, "end", "--mockup", mockup)
    expect_ok(ended)
    expect(calls(lavish)[1:], [["reply", str(mockup), "--agent-reply-file", str(reply)], ["end", str(mockup)]],
           f"{ended.given} (the lavish calls after show)")
    expect(launcher.read_waiting_record(data_home / "afkv2", "thread-1"), None, f"{ended.given} (the waiting record)")


def test_reply_end_reply_with_no_session_refuses_no_session(lavish, mockup, tmp_path, capsys):
    reply = tmp_path / "reply.md"
    reply.write_text("Moved Open first.\n", "utf-8")
    note("reply.md holds 'Moved Open first.'")
    host_output(lavish, "reply", HOST_FIXTURES / "host-error-missing.txt", code=1)
    ran = show_cli(capsys, "reply", "--mockup", mockup, "--reply-file", reply)
    expect_refusal(ran, "no-session")


def test_reply_end_end_never_refuses_on_the_host(lavish, mockup, capsys, monkeypatch):
    host_output(lavish, "end", HOST_FIXTURES / "host-error-missing.txt", code=1)
    ran = show_cli(capsys, "end", "--mockup", mockup)
    expect_ok(ran)
    expect_in("No active", ran.answer.get("host", ""), f"{ran.given} (field 'host' of answer {ran.answer!r})")
    no_lavish_on_path(monkeypatch)
    ran = show_cli(capsys, "end", "--mockup", mockup)
    expect_ok(ran)
    expect_in("not on PATH", ran.answer.get("host", ""), f"{ran.given} (field 'host' of answer {ran.answer!r})")
