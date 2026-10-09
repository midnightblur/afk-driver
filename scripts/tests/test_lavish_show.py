"""`scripts/lavish_show.py`: the grammar it runs, the operations it refuses, and what reaches the upstream."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SHOW = ROOT / "scripts" / "lavish_show.py"
sys.path.insert(0, str(ROOT / "scripts"))

import lavish_show  # noqa: E402
from lavish import inject  # noqa: E402

URL = "http://127.0.0.1:43217/session/abc?token=x&y=2"
FAKE = """\
import json, os, sys
page = next((a for a in sys.argv[1:] if a.endswith(".html")), None)
runtime = bool(page and os.path.isfile(page) and "afk-lavish-tips:start" in open(page, encoding="utf-8").read())
open(os.environ["FAKE_LOG"], "a", encoding="utf-8").write(json.dumps(sys.argv[1:]) + "\\n")
print(json.dumps({"argv": sys.argv[1:], "runtime": runtime}))
print(%r)
sys.stderr.write("upstream note\\n")
sys.exit(int(os.environ.get("FAKE_RC", "0")))
""" % URL
PAGE = "<html><head><title>t</title></head><body><p>x</p></body></html>\n"


@pytest.fixture
def fake(tmp_path, monkeypatch):
    script = tmp_path / "fake_axi.py"
    script.write_text(FAKE, encoding="utf-8")
    log = tmp_path / "calls.log"
    monkeypatch.setenv("FAKE_LOG", str(log))
    monkeypatch.delenv("LAVISH_AXI_HOST", raising=False)
    monkeypatch.setattr(lavish_show, "upstream", lambda args: [sys.executable, str(script), *args])
    monkeypatch.chdir(tmp_path)
    (tmp_path / "page.html").write_text(PAGE, encoding="utf-8")
    return log


def calls(log: Path) -> list:
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()] if log.exists() else []


def out_json(text: str) -> dict:
    return json.loads(text.splitlines()[0])


@pytest.mark.parametrize("argv", [
    ["page.html"], ["page.html", "--no-open"], ["page.html", "--reopen"],
    ["poll", "page.html"], ["poll", "page.html", "--agent-reply", "done; see \"R2\" & next | 100%"],
])
def test_show_and_poll_inject_first_then_pass_argv_exactly(fake, capfd, argv):
    assert lavish_show.main(argv) == 0
    out, err = capfd.readouterr()
    assert out_json(out) == {"argv": argv, "runtime": True}
    assert calls(fake) == [argv]
    assert "upstream note" in err


@pytest.mark.parametrize("argv", [["stop"], ["playbook"], ["playbook", "diagram"], ["end", "page.html"]])
def test_non_render_operations_run_without_injection(fake, capfd, argv):
    before = Path("page.html").read_bytes()
    assert lavish_show.main(argv) == 0
    assert out_json(capfd.readouterr()[0])["argv"] == argv
    assert Path("page.html").read_bytes() == before


def test_upstream_exit_status_propagates(fake, monkeypatch):
    monkeypatch.setenv("FAKE_RC", "3")
    assert lavish_show.main(["poll", "page.html"]) == 3


def test_the_session_url_reaches_stdout_unchanged(fake, capfd):
    lavish_show.main(["page.html", "--no-open"])
    assert URL in capfd.readouterr()[0].splitlines()


@pytest.mark.parametrize("argv", [
    ["share", "page.html"], ["setup", "hooks"], ["update"], [], ["--version"], ["open", "page.html"],
    ["missing.html"], ["notes.md"], ["page.html", "--no-open", "--reopen"], ["page.html", "--port", "1"],
    ["poll"], ["poll", "page.html", "--agent-reply"], ["poll", "page.html", "extra"],
    ["end"], ["end", "notes.md"], ["stop", "now"], ["playbook", "a", "b"], ["playbook", "--all"],
])
def test_refusals_run_nothing(fake, capfd, argv):
    assert lavish_show.main(argv) == 64
    assert "refused" in capfd.readouterr()[1]
    assert calls(fake) == []


def test_lavish_axi_host_in_the_environment_is_refused(fake, monkeypatch, capfd):
    monkeypatch.setenv("LAVISH_AXI_HOST", "127.0.0.1")
    assert lavish_show.main(["page.html"]) == 64
    assert "LAVISH_AXI_HOST" in capfd.readouterr()[1] and calls(fake) == []


def test_a_page_that_cannot_be_injected_is_not_shown(fake):
    Path("bad.html").write_bytes(b"\xff\xfe<html>")
    assert lavish_show.main(["bad.html"]) == 65
    assert calls(fake) == []


def test_a_failed_publication_keeps_the_page_and_runs_nothing(fake, monkeypatch, capfd):
    before = Path("page.html").read_bytes()

    def refuse(*_args):
        raise PermissionError(13, "locked")

    monkeypatch.setattr(inject.os, "replace", refuse)
    assert lavish_show.main(["poll", "page.html"]) == 65
    assert Path("page.html").read_bytes() == before and calls(fake) == []
    assert not [p for p in Path(".").iterdir() if p.name.startswith(".afk-lavish-")]


def test_a_missing_upstream_says_how_to_install(fake, monkeypatch, capfd):
    monkeypatch.setattr(lavish_show, "upstream", lambda args: None)
    assert lavish_show.main(["stop"]) == 127
    assert "/afk:setup" in capfd.readouterr()[1]


def test_unchanged_poll_keeps_the_file_untouched(fake):
    lavish_show.main(["page.html", "--no-open"])
    path = Path("page.html")
    past = path.stat().st_mtime_ns - 5_000_000_000
    os.utime(path, ns=(past, past))
    before = path.read_bytes()
    lavish_show.main(["poll", "page.html"])
    assert path.read_bytes() == before and path.stat().st_mtime_ns == past


def install_fake_upstream(folder: Path) -> None:
    """A global-install layout on PATH: npm's .cmd shim plus package on Windows, an executable elsewhere."""
    folder.mkdir()
    if os.name == "nt":
        (folder / "lavish-axi.cmd").write_text("@echo off\r\nexit /b 99\r\n", encoding="utf-8")
        package = folder / "node_modules" / "lavish-axi"
        package.mkdir(parents=True)
        (package / "package.json").write_text(json.dumps({"bin": {"lavish-axi": "cli.mjs"}}), encoding="utf-8")
        (package / "cli.mjs").write_text(
            "console.log(JSON.stringify(process.argv.slice(2))); process.exit(4);\n", encoding="utf-8")
    else:
        shim = folder / "lavish-axi"
        shim.write_text(f"#!/bin/sh\nexec \"{sys.executable}\" -c 'import json,sys; print(json.dumps(sys.argv[1:])); "
                        "sys.exit(4)' \"$@\"\n", encoding="utf-8")
        shim.chmod(0o755)


@pytest.mark.skipif(os.name == "nt" and not shutil.which("node"), reason="the Windows npm layout needs node")
def test_end_to_end_through_path_keeps_hostile_arguments_intact(tmp_path):
    install_fake_upstream(tmp_path / "bin")
    (tmp_path / "page.html").write_text(PAGE, encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k != "LAVISH_AXI_HOST"}
    env["PATH"] = str(tmp_path / "bin") + os.pathsep + env.get("PATH", "")
    reply = 'a & b | "c" %PATH% ^ <d> !e!'
    done = subprocess.run([sys.executable, str(SHOW), "poll", "page.html", "--agent-reply", reply],
                          cwd=tmp_path, env=env, capture_output=True, text=True, timeout=60)
    assert done.returncode == 4, done.stderr
    assert json.loads(done.stdout.splitlines()[0]) == ["poll", "page.html", "--agent-reply", reply]
    assert inject.MARK_START in (tmp_path / "page.html").read_text(encoding="utf-8")


@pytest.mark.skipif(os.name != "nt", reason="batch shims exist only on Windows")
def test_a_batch_shim_without_its_package_takes_only_plain_arguments(tmp_path, monkeypatch):
    folder = tmp_path / "bin"
    folder.mkdir()
    (folder / "lavish-axi.cmd").write_text("@echo off\r\n", encoding="utf-8")
    monkeypatch.setenv("PATH", str(folder) + os.pathsep + os.environ.get("PATH", ""))
    assert lavish_show.upstream(["stop"])[0].lower().endswith("lavish-axi.cmd")
    with pytest.raises(lavish_show.Refused):
        lavish_show.upstream(["poll", "p.html", "--agent-reply", "a & b"])


SERVER_JS = """\
import { spawn } from "node:child_process";
const op = process.argv[2];
let server = null;
if (op !== "poll" || process.env.FAKE_SPAWN) {
  const child = spawn(process.execPath, ["-e", "setTimeout(() => {}, 120000)"], { detached: true, stdio: "ignore" });
  child.unref();
  server = child.pid;
}
console.log(JSON.stringify({ pid: process.pid, server }));
if (process.env.FAKE_BLOCK) setTimeout(() => {}, 120000);
"""
SERVER_PY = """\
import json, os, subprocess, sys, time
server = None
if sys.argv[1] != "poll" or os.environ.get("FAKE_SPAWN"):
    server = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"], stdin=subprocess.DEVNULL,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True).pid
print(json.dumps({"pid": os.getpid(), "server": server}), flush=True)
if os.environ.get("FAKE_BLOCK"):
    time.sleep(120)
"""


def install_server_upstream(folder: Path, layout: str = "package") -> None:
    """An upstream that, like lavish-axi, starts a detached server on render and blocks on `FAKE_BLOCK`.

    Layout `batch` is the Windows fallback: a `.cmd` shim with no readable npm package;
    `batch-helper` runs a 2.2 s helper process before the real one."""
    folder.mkdir()
    if layout.startswith("batch"):
        (folder / "fake.py").write_text(SERVER_PY, encoding="utf-8")
        helper = f"@\"{sys.executable}\" -c \"import time; time.sleep(2.2)\"\r\n" if layout == "batch-helper" else ""
        (folder / "lavish-axi.cmd").write_text(
            helper + f"@\"{sys.executable}\" \"{folder / 'fake.py'}\" %*\r\n", encoding="utf-8")
    elif os.name == "nt":
        (folder / "lavish-axi.cmd").write_text("@echo off\r\nexit /b 99\r\n", encoding="utf-8")
        package = folder / "node_modules" / "lavish-axi"
        package.mkdir(parents=True)
        (package / "package.json").write_text(json.dumps({"bin": "cli.mjs"}), encoding="utf-8")
        (package / "cli.mjs").write_text(SERVER_JS, encoding="utf-8")
    else:
        (folder / "fake.py").write_text(SERVER_PY, encoding="utf-8")
        shim = folder / "lavish-axi"
        shim.write_text(f"#!/bin/sh\nexec \"{sys.executable}\" \"{folder / 'fake.py'}\" \"$@\"\n", encoding="utf-8")
        shim.chmod(0o755)


def alive(pid: int) -> bool:
    if os.name == "nt":
        import ctypes
        kernel = ctypes.WinDLL("kernel32")
        handle = kernel.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        code = ctypes.c_ulong()
        kernel.GetExitCodeProcess(handle, ctypes.byref(code))
        kernel.CloseHandle(handle)
        return code.value == 259  # STILL_ACTIVE
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def gone(pid: int, seconds: float = 10.0) -> bool:
    deadline = time.monotonic() + seconds
    while alive(pid) and time.monotonic() < deadline:
        time.sleep(0.1)
    return not alive(pid)


def kill(pid: int | None) -> None:
    if pid and alive(pid):
        os.kill(pid, 9)


LAYOUTS = [pytest.param("package", marks=pytest.mark.skipif(os.name == "nt" and not shutil.which("node"),
                                                           reason="the Windows npm layout needs node")),
           *(pytest.param(name, marks=pytest.mark.skipif(os.name != "nt", reason="batch shims exist only on Windows"))
             for name in ("batch", "batch-helper"))]


@pytest.fixture(params=LAYOUTS)
def server_env(tmp_path, request):
    install_server_upstream(tmp_path / "bin", request.param)
    (tmp_path / "page.html").write_text(PAGE, encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k not in ("LAVISH_AXI_HOST", "FAKE_SPAWN", "FAKE_BLOCK")}
    env["PATH"] = str(tmp_path / "bin") + os.pathsep + env.get("PATH", "")
    return env


@pytest.mark.parametrize("argv,extra", [(["page.html", "--no-open"], {}), (["poll", "page.html"], {"FAKE_SPAWN": "1"})],
                         ids=["cold-render", "completed-poll"])
def test_a_completed_run_leaves_the_server_it_started_running(tmp_path, server_env, argv, extra):
    done = subprocess.run([sys.executable, str(SHOW), *argv], cwd=tmp_path, env={**server_env, **extra},
                          capture_output=True, text=True, timeout=60)
    server = json.loads(done.stdout.splitlines()[0])["server"]
    try:
        assert done.returncode == 0, done.stderr
        time.sleep(1.0)
        assert alive(server), "the server died with the wrapper"
    finally:
        kill(server)


def test_a_killed_poll_takes_its_upstream_down(tmp_path, server_env):
    wrapper = subprocess.Popen([sys.executable, str(SHOW), "poll", "page.html"], cwd=tmp_path,
                               env={**server_env, "FAKE_BLOCK": "1"}, stdout=subprocess.PIPE, text=True)
    first: list = []
    reader = threading.Thread(target=lambda: first.append(wrapper.stdout.readline()), daemon=True)
    reader.start()
    reader.join(30)
    upstream = json.loads(first[0])["pid"] if first and first[0] else None
    try:
        assert upstream and alive(upstream), "the upstream poll never started"
        wrapper.kill()
        wrapper.wait(30)
        assert gone(upstream), "the upstream poll outlived its killed wrapper"
    finally:
        kill(upstream)
        if wrapper.poll() is None:
            wrapper.kill()
        wrapper.stdout.close()


REAL_KERNEL32 = lavish_show.kernel32


class FailingKernel:
    """The real kernel32 with one call made to fail."""

    def __init__(self, failing: str):
        self.real, self.failing = REAL_KERNEL32(), failing

    def __getattr__(self, name):
        return (lambda *args: 0) if name == self.failing else getattr(self.real, name)


windows_only = pytest.mark.skipif(os.name != "nt", reason="job objects exist only on Windows")


@windows_only
def test_a_batch_shim_whose_jobs_cannot_be_set_up_starts_nothing_and_exits_69(monkeypatch, capsys):
    started = []
    monkeypatch.setattr(lavish_show, "kernel32", lambda: FailingKernel("CreateJobObjectW"))
    monkeypatch.setattr(lavish_show.subprocess, "Popen", lambda *a, **k: started.append(a))
    monkeypatch.setattr(lavish_show, "upstream", lambda args: ["C:/x/lavish-axi.cmd", *args])
    monkeypatch.setattr(sys, "argv", ["lavish_show.py", "stop"])
    assert lavish_show.main() == 69
    assert started == [] and "refused to run the batch shim: job setup failed" in capsys.readouterr().err


@windows_only
def test_a_shell_that_cannot_join_its_jobs_is_killed_before_it_runs(tmp_path, monkeypatch):
    marker = tmp_path / "ran.txt"
    shim = tmp_path / "shim.cmd"
    shim.write_text(f'@echo ran> "{marker}"\r\n', encoding="utf-8")
    monkeypatch.setattr(lavish_show, "kernel32", lambda: FailingKernel("AssignProcessToJobObject"))
    with pytest.raises(lavish_show.Unbound, match="could not join its jobs"):
        lavish_show.start_batch([str(shim)])
    time.sleep(0.5)
    assert not marker.exists()
