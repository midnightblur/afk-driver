"""`scripts/lavish_show.py`: the grammar it runs, the operations it refuses, and what reaches the upstream."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
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
