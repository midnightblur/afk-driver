import json
import socket
import subprocess
import sys
import time
import urllib.request
from datetime import date
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import live_build  # noqa: E402
from afkv2_config import Refusal  # noqa: E402

TOOL = SCRIPTS / "live_build.py"
PY = f'"{sys.executable}"'

FAKE_SERVER = """
import os, sys
from http.server import BaseHTTPRequestHandler, HTTPServer
port, status, pid_file = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
open(pid_file, "w").write(str(os.getpid()))
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(status)
        self.end_headers()
        if self.path == "/quit":
            open(pid_file + ".quit", "w").write("quit")
            os._exit(0)
    def log_message(self, *args):
        pass
HTTPServer(("127.0.0.1", port), Handler).serve_forever()
"""


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def alive(pid):
    if sys.platform == "win32":
        import ctypes

        kernel = ctypes.windll.kernel32
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        code = ctypes.c_ulong()
        kernel.GetExitCodeProcess(handle, ctypes.byref(code))
        kernel.CloseHandle(handle)
        return code.value == 259
    try:
        import os

        os.kill(pid, 0)
    except OSError:
        return False
    return True


def answers(address):
    try:
        urllib.request.urlopen(address, timeout=1)
    except urllib.error.HTTPError:
        return True
    except OSError:
        return False
    return True


def git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True, stdin=subprocess.DEVNULL).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q")
    (root / "server.py").write_text(FAKE_SERVER, encoding="utf-8")
    write_config(root, None)
    git(root, "add", "-A")
    git(root, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "seed")
    return root


def write_config(root, live, **extra):
    config = {"spec_folder": "docs", "forge": "github", **extra}
    if live is not None:
        config["live"] = live
    (root / ".afkv2").mkdir(exist_ok=True)
    (root / ".afkv2" / "config.json").write_text(json.dumps(config), encoding="utf-8")


def read_raw(root):
    return json.loads((root / ".afkv2" / "config.json").read_text(encoding="utf-8"))


def server_block(root, port=None, status=200, **fields):
    port = port or free_port()
    pid_file = root.parent / "server.pid"
    block = {"start": f"{PY} server.py {port} {status} \"{pid_file}\"", "address": f"http://127.0.0.1:{port}/", "ready_seconds": 20}
    return {**block, **fields}


def server_pid(root):
    return int((root.parent / "server.pid").read_text())


def test_prove_starts_waits_stops_and_writes_the_block(repo):
    block = server_block(repo, needs=["API_TOKEN"])
    write_config(repo, block, tracker={"kind": "jira", "project": "ABC"})
    answer = live_build.prove(repo)
    assert answer["ok"] is True, answer
    raw = read_raw(repo)
    assert raw["tracker"] == {"kind": "jira", "project": "ABC"}
    assert raw["live"] == {**block, "stop": None, "proven_at": date.today().isoformat(), "proven_head": git(repo, "rev-parse", "HEAD")}
    assert answer["live"] == raw["live"]
    assert not alive(server_pid(repo))
    assert not answers(block["address"])


def test_prove_takes_a_proposed_block_and_writes_it(repo):
    block = server_block(repo)
    answer = live_build.prove(repo, live=block)
    assert answer["ok"] is True, answer
    assert read_raw(repo)["live"]["start"] == block["start"]


def test_any_http_answer_is_ready(repo):
    write_config(repo, server_block(repo, status=500))
    assert live_build.prove(repo)["ok"] is True


def test_check_runs_the_proof_and_writes_nothing(repo):
    write_config(repo, server_block(repo))
    before = (repo / ".afkv2" / "config.json").read_bytes()
    answer = live_build.check(repo)
    assert answer["ok"] is True, answer
    assert (repo / ".afkv2" / "config.json").read_bytes() == before
    assert not alive(server_pid(repo))


def test_check_of_a_proposed_block_writes_nothing(repo):
    before = (repo / ".afkv2" / "config.json").read_bytes()
    assert live_build.check(repo, live=server_block(repo))["ok"] is True
    assert (repo / ".afkv2" / "config.json").read_bytes() == before


@pytest.mark.parametrize("verb", ["prove", "check"])
def test_a_missing_block_refuses_live_undefined(repo, verb):
    answer = getattr(live_build, verb)(repo)
    assert answer["error"]["code"] == "live-undefined"


def test_a_start_that_exits_refuses_live_start_failed(repo):
    write_config(repo, {"start": f"{PY} -c \"print('boom'); raise SystemExit(3)\"", "address": f"http://127.0.0.1:{free_port()}/"})
    before = read_raw(repo)
    answer = live_build.prove(repo)
    assert answer["error"]["code"] == "live-start-failed"
    assert "boom" in answer["error"]["reason"]
    assert read_raw(repo) == before


def test_no_answer_in_time_refuses_live_no_answer_and_leaves_no_process(repo):
    pid_file = repo.parent / "sleeper.pid"
    sleeper = f"import os, time; open(r'{pid_file}', 'w').write(str(os.getpid())); time.sleep(120)"
    write_config(repo, {"start": f"{PY} -c \"{sleeper}\"", "address": f"http://127.0.0.1:{free_port()}/", "ready_seconds": 2})
    before = read_raw(repo)
    started = time.monotonic()
    answer = live_build.prove(repo)
    assert answer["error"]["code"] == "live-no-answer"
    assert time.monotonic() - started < 30
    assert not alive(int(pid_file.read_text()))
    assert read_raw(repo) == before


def test_a_stop_command_stops_the_build(repo):
    block = server_block(repo)
    block["stop"] = f"{PY} -c \"import urllib.request as u; u.urlopen('{block['address']}quit', timeout=5)\""
    write_config(repo, block)
    answer = live_build.prove(repo)
    assert answer["ok"] is True, answer
    assert read_raw(repo)["live"]["stop"] == block["stop"]
    assert (repo.parent / "server.pid.quit").exists()
    assert not alive(server_pid(repo))


def test_a_failed_stop_refuses_live_stop_failed_and_leaves_no_process(repo):
    write_config(repo, server_block(repo, stop=f"{PY} -c \"raise SystemExit(4)\""))
    before = read_raw(repo)
    answer = live_build.prove(repo)
    assert answer["error"]["code"] == "live-stop-failed"
    assert read_raw(repo) == before
    assert not alive(server_pid(repo))


def test_needs_values_are_never_written(repo, monkeypatch):
    monkeypatch.setenv("API_TOKEN", "s3cret-value")
    write_config(repo, server_block(repo, needs=["API_TOKEN"]))
    assert live_build.prove(repo)["ok"] is True
    text = (repo / ".afkv2" / "config.json").read_text(encoding="utf-8")
    assert "s3cret-value" not in text
    assert read_raw(repo)["live"]["needs"] == ["API_TOKEN"]


def test_a_bad_proposed_block_is_refused(repo):
    answer = live_build.prove(repo, live={"start": "x", "address": "http://x", "needs": ["A=b"]})
    assert answer["error"]["code"] == "bad-value"


def test_start_live_and_stop_live(repo):
    block = server_block(repo)
    write_config(repo, block)
    handle = live_build.start_live(repo)
    try:
        assert answers(block["address"])
    finally:
        live_build.stop_live(handle)
    assert not answers(block["address"])
    assert not alive(server_pid(repo))


def test_start_live_refuses_without_a_block(repo):
    with pytest.raises(Refusal) as refused:
        live_build.start_live(repo)
    assert refused.value.code == "live-undefined"


def run_tool(*args, cwd):
    done = subprocess.run([sys.executable, str(TOOL), *args], cwd=cwd, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=120)
    return done.returncode, json.loads(done.stdout)


def test_command_prove_and_check(repo):
    write_config(repo, server_block(repo))
    code, answer = run_tool("check", cwd=repo)
    assert (code, answer["ok"]) == (0, True)
    assert "proven_head" not in read_raw(repo)["live"]
    code, answer = run_tool("prove", "--start", str(repo), cwd=repo.parent)
    assert (code, answer["ok"]) == (0, True)
    assert read_raw(repo)["live"]["proven_head"] == git(repo, "rev-parse", "HEAD")


def test_command_takes_a_proposed_block(repo):
    code, answer = run_tool("check", "--live", json.dumps(server_block(repo)), cwd=repo)
    assert (code, answer["ok"]) == (0, True)


def test_command_refusal_exits_1_and_usage_exits_2(repo):
    code, answer = run_tool("prove", cwd=repo)
    assert (code, answer["error"]["code"]) == (1, "live-undefined")
    code, answer = run_tool("check", "--live", "{not json", cwd=repo)
    assert (code, answer["error"]["code"]) == (2, "usage")
    code, answer = run_tool("launch", cwd=repo)
    assert (code, answer["error"]["code"]) == (2, "usage")


NOT_HTTP = r"""
import os, socket, sys
port, pid_file = int(sys.argv[1]), sys.argv[2]
open(pid_file, "w").write(str(os.getpid()))
server = socket.socket()
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(("127.0.0.1", port))
server.listen(5)
while True:
    conn, _ = server.accept()
    try:
        conn.recv(1024)
        conn.sendall(b"SSH-2.0-garbage\r\n\r\n")
    finally:
        conn.close()
"""


def test_a_reply_that_is_not_http_is_no_answer_and_leaves_no_process(repo):
    (repo / "nothttp.py").write_text(NOT_HTTP, encoding="utf-8")
    pid_file = repo.parent / "nothttp.pid"
    port = free_port()
    write_config(repo, {"start": f"{PY} nothttp.py {port} \"{pid_file}\"", "address": f"http://127.0.0.1:{port}/", "ready_seconds": 3})
    answer = live_build.check(repo)
    assert answer["ok"] is False
    assert answer["error"]["code"] == "live-no-answer"
    assert not alive(int(pid_file.read_text()))


def test_a_hanging_stop_command_refuses_in_time_and_leaves_no_process(repo, monkeypatch):
    monkeypatch.setattr(live_build, "STOP_SECONDS", 2)
    pid_file = repo.parent / "stopper.pid"
    stopper = f"import os, time; open(r'{pid_file}', 'w').write(str(os.getpid())); time.sleep(120)"
    write_config(repo, server_block(repo, stop=f"{PY} -c \"{stopper}\""))
    started = time.monotonic()
    answer = live_build.check(repo)
    assert answer["error"]["code"] == "live-stop-failed"
    assert time.monotonic() - started < 40
    assert not alive(int(pid_file.read_text()))
    assert not alive(server_pid(repo))


def test_a_proposed_block_replaces_a_bad_stored_block(repo):
    write_config(repo, {"start": "serve", "address": "http://x", "ready_seconds": 0})
    block = server_block(repo)
    answer = live_build.prove(repo, live=block)
    assert answer["ok"] is True, answer
    assert read_raw(repo)["live"]["start"] == block["start"]


def test_an_address_that_answers_before_the_start_refuses(repo):
    port = free_port()
    other = subprocess.Popen([sys.executable, str(repo / "server.py"), str(port), "200", str(repo.parent / "other.pid")],
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = time.monotonic() + 20
        while not answers(f"http://127.0.0.1:{port}/") and time.monotonic() < deadline:
            time.sleep(0.2)
        write_config(repo, {"start": f"{PY} -c \"import time; time.sleep(60)\"", "address": f"http://127.0.0.1:{port}/"})
        answer = live_build.check(repo)
        assert answer["error"]["code"] == "live-start-failed"
        assert "already answers" in answer["error"]["reason"]
    finally:
        other.kill()
        other.wait()


def test_a_failed_config_write_refuses_and_leaves_no_temporary_file(repo, monkeypatch):
    write_config(repo, server_block(repo))
    before = read_raw(repo)

    def refuse(*args):
        raise PermissionError("locked")

    monkeypatch.setattr(live_build.os, "replace", refuse)
    answer = live_build.prove(repo)
    assert answer["error"]["code"] == "config-write-failed"
    assert read_raw(repo) == before
    assert not (repo / ".afkv2" / "config.tmp").exists()


def test_the_write_keeps_non_ascii_text(repo):
    write_config(repo, server_block(repo), note="caf\u00e9")
    assert live_build.prove(repo)["ok"] is True
    assert "caf\u00e9" in (repo / ".afkv2" / "config.json").read_text(encoding="utf-8")


@pytest.mark.skipif(sys.platform != "win32", reason="cmd start /b detaches a process on Windows")
def test_a_detached_server_is_stopped_with_the_build(repo):
    port = free_port()
    pid_file = repo.parent / "detached.pid"
    write_config(repo, {"start": f"start \"\" /b {PY} server.py {port} 200 \"{pid_file}\" & {PY} -c \"import time; time.sleep(60)\"",
                        "address": f"http://127.0.0.1:{port}/", "ready_seconds": 20})
    answer = live_build.check(repo)
    assert answer["ok"] is True, answer
    assert not alive(int(pid_file.read_text()))
    assert not answers(f"http://127.0.0.1:{port}/")


@pytest.mark.skipif(sys.platform != "win32", reason="cmd start /b detaches a process on Windows")
def test_a_start_that_detaches_and_exits_leaves_no_process(repo):
    port = free_port()
    pid_file = repo.parent / "orphan.pid"
    sleeper = f"import os, time; open(r'{pid_file}', 'w').write(str(os.getpid())); time.sleep(60)"
    write_config(repo, {"start": f"start \"\" /b {PY} -c \"{sleeper}\"", "address": f"http://127.0.0.1:{port}/", "ready_seconds": 5})
    answer = live_build.check(repo)
    assert answer["ok"] is False
    deadline = time.monotonic() + 5
    while not pid_file.exists() and time.monotonic() < deadline:
        time.sleep(0.2)
    if pid_file.exists():
        assert not alive(int(pid_file.read_text()))


REDIRECT = r"""
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(302)
        self.send_header("Location", "http://127.0.0.1:1/login")
        self.end_headers()
    def log_message(self, *args):
        pass
HTTPServer(("127.0.0.1", int(sys.argv[1])), Handler).serve_forever()
"""


def test_a_redirect_is_an_answer(repo):
    (repo / "redirect.py").write_text(REDIRECT, encoding="utf-8")
    port = free_port()
    write_config(repo, {"start": f"{PY} redirect.py {port}", "address": f"http://127.0.0.1:{port}/", "ready_seconds": 20})
    answer = live_build.check(repo)
    assert answer["ok"] is True, answer


def test_prove_outside_git_refuses_and_writes_nothing(tmp_path):
    root = tmp_path / "plain"
    root.mkdir()
    (root / "server.py").write_text(FAKE_SERVER, encoding="utf-8")
    write_config(root, server_block(root))
    (root / ".git").write_text("gitdir: nowhere", encoding="utf-8")
    before = (root / ".afkv2" / "config.json").read_bytes()
    answer = live_build.prove(root)
    assert answer["error"]["code"] == "git-failed"
    assert (root / ".afkv2" / "config.json").read_bytes() == before
