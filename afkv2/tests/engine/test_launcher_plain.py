"""`open --plain`: lavish opens the file as it is; the pin and host checks stay (ADR-0001 of ticket 207, VR-014)."""

import json
import os
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "engine"))
import launcher
from shell import inject

MOCKUP = '<!doctype html>\n<html><body><nav>Shell</nav><button title="Save">Save</button></body></html>\n'
STUB = "import json, sys\nfrom pathlib import Path\nPath(sys.argv[0]).with_name('argv.json').write_text(json.dumps(sys.argv[1:]))\nprint('opened')\n"


@pytest.fixture
def host(tmp_path, monkeypatch):
    """A `.py` stub of lavish-axi behind the real `upstream`: a package at the pinned version, found on PATH."""
    seed = tmp_path / "seed.json"
    seed.write_text("{}", "utf-8")
    monkeypatch.setattr(inject, "SEED", seed)
    monkeypatch.setattr(inject, "PLUGIN_GLOSSARY", tmp_path / "none.md")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.delenv("LAVISH_AXI_HOST", raising=False)
    bin_folder = tmp_path / "bin"
    package = bin_folder / "node_modules" / "lavish-axi"
    package.mkdir(parents=True)
    (package / "stub.py").write_text(STUB, "utf-8")
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
    (tmp_path / ".git").mkdir()
    (tmp_path / "GLOSSARY.md").write_text("**Shell**: The app frame around each page.\n", "utf-8")
    page = tmp_path / "docs" / "mockup.html"
    page.parent.mkdir()
    page.write_text(MOCKUP, "utf-8")
    return page, package


def test_plain_open_keeps_the_bytes_and_strips_the_flag(host):
    page, package = host
    before = page.read_bytes()
    code, out = launcher.run(["open", str(page), launcher.PLAIN_FLAG, "--no-open"])
    assert (code, out.strip()) == (0, "opened")
    assert page.read_bytes() == before
    assert inject.MARK_START.encode() not in page.read_bytes()
    assert json.loads((package / "argv.json").read_text("utf-8")) == [str(page), "--no-open"]


def test_open_without_the_flag_writes_the_tooltip_block(host):
    page, package = host
    assert launcher.run(["open", str(page)])[0] == 0
    assert inject.MARK_START.encode() in page.read_bytes()
    assert json.loads((package / "argv.json").read_text("utf-8")) == [str(page)]


def test_plain_open_keeps_the_pin_check(host):
    page, package = host
    (package / "package.json").write_text(json.dumps({"version": "0.0.1", "bin": "stub.py"}), "utf-8")
    code, out = launcher.run(["open", str(page), launcher.PLAIN_FLAG])
    assert code == 64 and launcher.PIN in out
    assert page.read_text("utf-8") == MOCKUP and not (package / "argv.json").exists()


def test_plain_open_keeps_the_host_check(host, monkeypatch):
    page, package = host
    monkeypatch.setenv("LAVISH_AXI_HOST", "0.0.0.0")
    assert launcher.run(["open", str(page), launcher.PLAIN_FLAG])[0] == 64
    assert page.read_text("utf-8") == MOCKUP and not (package / "argv.json").exists()


@pytest.mark.parametrize("argv", [["poll", "{page}", "--plain"], ["end", "{page}", "--plain"],
                                  ["open", "{page}", "--plain", "--plain"],
                                  ["open", "{page}", "--plain", "--no-open", "--reopen"]])
def test_plain_is_open_only_and_once(host, argv):
    page, package = host
    code, out = launcher.run([part.format(page=page) for part in argv])
    assert code == 64 and out.startswith("refused")
    assert page.read_text("utf-8") == MOCKUP and not (package / "argv.json").exists()
