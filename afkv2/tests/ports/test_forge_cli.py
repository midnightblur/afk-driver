"""The forge command: the kind it resolves, one object, exit 0/1/2."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from port_fakes import PORTS
from forge import cli
from tracker import settings, shell

CLI = PORTS / "forge" / "cli.py"


def run(*argv, stdin="", cwd=None):
    return subprocess.run([sys.executable, str(CLI), *argv], input=stdin, capture_output=True,
                          text=True, encoding="utf-8", timeout=120, cwd=cwd)


def call(capsys, *argv):
    code = cli.forge_main(list(argv))
    return code, json.loads(capsys.readouterr().out)


def test_an_unknown_verb_exits_2_as_a_real_command(tmp_path):
    done = run("no-such-verb", "{}", cwd=tmp_path)
    assert done.returncode == 2 and json.loads(done.stdout)["error"]["code"] == "unknown-verb"


@pytest.mark.parametrize("payload", ["{bad", "[1, 2]"])
def test_a_payload_that_is_not_one_object_exits_2(payload, tmp_path):
    done = run("change-view", payload, cwd=tmp_path)
    assert done.returncode == 2 and json.loads(done.stdout)["error"]["code"] == "bad-payload"


def test_payload_can_arrive_on_stdin(capsys, tools, monkeypatch):
    import io
    tools.on("gh", "pr", "view", answer={"number": 7})
    monkeypatch.setattr(sys, "stdin", io.StringIO('{"id":"7","forge":"github"}'))
    code, answer = call(capsys, "change-view")
    assert code == 0 and answer["id"] == "7"


def test_the_payload_kind_wins(capsys, tools, monkeypatch):
    monkeypatch.setattr(settings, "read_config", lambda: {"forge": "gitlab"})
    tools.on("gh", "pr", "view", answer={"number": 7})
    assert call(capsys, "change-view", '{"id":"7","forge":"github"}')[1]["id"] == "7"


def test_the_config_kind_beats_the_remote(capsys, tools, monkeypatch):
    monkeypatch.setattr(settings, "read_config", lambda: {"forge": "gitlab"})
    tools.on("git", "remote", "get-url", answer="https://github.com/o/r.git\n")
    tools.on("glab", "mr", "view", answer={"iid": 7})
    assert call(capsys, "change-view", '{"id":"7"}')[1]["id"] == "7"


@pytest.mark.parametrize("url,tool,view", [
    ("https://github.com/o/r.git\n", "gh", {"number": 7}),
    ("git@gitlab.example.com:o/r.git\n", "glab", {"iid": 7}),
])
def test_the_origin_host_names_the_kind(capsys, tools, monkeypatch, url, tool, view):
    monkeypatch.setattr(settings, "read_config", lambda: {})
    tools.on("git", "remote", "get-url", answer=url)
    tools.on(tool, "pr" if tool == "gh" else "mr", "view", answer=view)
    assert call(capsys, "change-view", '{"id":"7"}')[1]["id"] == "7"


@pytest.mark.parametrize("url,tool,view", [
    ("git@gitlab.example.com:infra/github-mirror.git\n", "glab", {"iid": 7}),
    ("https://gitlab.example.com/github-tools/r.git\n", "glab", {"iid": 7}),
    ("ssh://git@github.com/team/gitlab-sync.git\n", "gh", {"number": 7}),
])
def test_only_the_host_names_the_kind(capsys, tools, monkeypatch, url, tool, view):
    monkeypatch.setattr(settings, "read_config", lambda: {})
    tools.on("git", "remote", "get-url", answer=url)
    tools.on(tool, "pr" if tool == "gh" else "mr", "view", answer=view)
    assert call(capsys, "change-view", '{"id":"7"}')[1]["id"] == "7"


def test_a_dash_ends_a_part_of_the_host(capsys, tools, monkeypatch):
    monkeypatch.setattr(settings, "read_config", lambda: {})
    tools.on("git", "remote", "get-url", answer="git@gitlab-ee.corp.example:o/r.git\n")
    tools.on("glab", "mr", "view", answer={"iid": 7})
    assert call(capsys, "change-view", '{"id":"7"}')[1]["id"] == "7"


@pytest.mark.parametrize("url", [
    "https://example.test/github-archive/r.git\n", "https://notgithub.example/o/r.git\n", "https://github-proxy.gitlab.example/o/r.git\n"])
def test_a_host_that_names_no_forge_is_refused(capsys, tools, monkeypatch, url):
    monkeypatch.setattr(settings, "read_config", lambda: {})
    tools.on("git", "remote", "get-url", answer=url)
    code, answer = call(capsys, "change-view", '{"id":"7"}')
    assert code == 1 and answer["error"]["code"] == "no-forge"


def test_a_forge_kind_that_is_no_word_is_bad_payload(capsys, tools):
    code, answer = call(capsys, "change-view", '{"id":"7","forge":["github"]}')
    assert code == 2 and answer["error"]["code"] == "bad-payload"


@pytest.mark.parametrize("remote", ["https://example.test/o/r.git\n", (1, "", "no such remote")])
def test_no_kind_is_a_named_refusal(capsys, tools, monkeypatch, remote):
    monkeypatch.setattr(settings, "read_config", lambda: {})
    tools.on("git", "remote", "get-url", answer=remote)
    code, answer = call(capsys, "change-view", '{"id":"7"}')
    assert code == 1 and answer["error"]["code"] == "no-forge"


def test_a_missing_command_is_unavailable(capsys, monkeypatch):
    monkeypatch.setattr(shell.shutil, "which", lambda _: None)
    code, answer = call(capsys, "change-view", '{"id":"7","forge":"gitlab"}')
    assert code == 1 and answer["error"]["code"] == "unavailable"


def test_the_time_limit_is_a_named_refusal(capsys, monkeypatch):
    def too_slow(*args, **kwargs):
        raise subprocess.TimeoutExpired("gh", 60)

    monkeypatch.setattr(shell.shutil, "which", lambda tool: tool)
    monkeypatch.setattr(shell.subprocess, "run", too_slow)
    code, answer = call(capsys, "change-view", '{"id":"7","forge":"github"}')
    assert code == 1 and answer["error"]["code"] == "timeout"


def test_the_time_limit_comes_from_the_environment(monkeypatch):
    seen = {}

    def record(argv, **kwargs):
        seen.update(kwargs)
        return subprocess.CompletedProcess(argv, 0, b"{}", b"")

    monkeypatch.setattr(shell.shutil, "which", lambda tool: tool)
    monkeypatch.setattr(shell.subprocess, "run", record)
    shell.run_tool("gh", ["x"])
    assert seen["timeout"] == 60 and seen["stdin"] == subprocess.DEVNULL
    monkeypatch.setenv("AFKV2_FORGE_TIMEOUT", "5")
    shell.run_tool("gh", ["x"])
    assert seen["timeout"] == 5


def test_the_tool_text_is_decoded_as_utf8_with_no_line_end_change(monkeypatch):
    monkeypatch.setattr(shell.shutil, "which", lambda tool: tool)
    monkeypatch.setattr(shell.subprocess, "run", lambda argv, **kwargs: subprocess.CompletedProcess(
        argv, 0, "é\r\nline".encode("utf-8"), b""))
    assert shell.run_tool("gh", ["x"]).stdout == "é\r\nline"


def test_stdin_text_is_sent_as_utf8(monkeypatch):
    seen = {}

    def record(argv, **kwargs):
        seen.update(kwargs)
        return subprocess.CompletedProcess(argv, 0, b"", b"")

    monkeypatch.setattr(shell.shutil, "which", lambda tool: tool)
    monkeypatch.setattr(shell.subprocess, "run", record)
    shell.run_tool("gh", ["x"], stdin_text="é")
    assert seen["input"] == "é".encode("utf-8") and "stdin" not in seen
