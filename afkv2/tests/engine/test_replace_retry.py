"""A file write survives a short hold on its target: Windows refuses a replace while another process has the file
open, as a scanner briefly does with a new file. Both atomic writers retry the replace."""

import os
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "engine"))
sys.path.insert(0, str(ROOT / "skills" / "use-lavish" / "scripts"))
from grill_common import write_text  # noqa: E402
from shell import inject  # noqa: E402

pytestmark = pytest.mark.skipif(os.name != "nt", reason="only Windows refuses a replace of an open file")


def _hold(target, seconds):
    handle = open(target, "rb")
    threading.Timer(seconds, handle.close).start()


def test_write_text_waits_for_a_reader_to_let_go(tmp_path):
    target = tmp_path / "GRILL-LOG.md"
    target.write_text("old\n", "utf-8")
    _hold(target, 0.2)
    write_text(target, "new\n")
    assert target.read_text("utf-8") == "new\n"
    assert not (tmp_path / "GRILL-LOG.md.tmp").exists()


def test_write_if_changed_waits_for_a_reader_to_let_go(tmp_path):
    target = tmp_path / "page.html"
    target.write_bytes(b"old\n")
    _hold(target, 0.2)
    assert inject.write_if_changed(target, b"new\n") is True
    assert target.read_bytes() == b"new\n"
    assert not list(tmp_path.glob(".page-*.tmp"))
