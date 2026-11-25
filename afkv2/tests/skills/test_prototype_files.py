"""Tests for prototype_files.py: start, check and settle (SDD §3), and the network check (SDD §6).

A throwaway git repository holds the config and the spec folder; each verb runs through its command line. No lavish
host, live app or browser runs here.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[2]
SKILL_DIR = PLUGIN / "skills" / "prototype"
SCRIPT = SKILL_DIR / "scripts" / "prototype_files.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "prototype"
sys.path.insert(0, str(SKILL_DIR / "scripts"))
sys.path.insert(0, str(PLUGIN / "engine"))

import prototype_files  # noqa: E402
from shell import inject  # noqa: E402


# --- the network check (VR-017) ------------------------------------------------------------------------------------

FLAGGED = [
    ('<script src="https://cdn.example/app.js"></script>', "scheme URL in src"),
    ('<a href="http://example.test/orders">Orders</a>', "scheme URL in href"),
    ('<form action="https://example.test/save">', "scheme URL in action"),
    ("body { background: url('https://cdn.example/bg.png'); }", "scheme URL in a CSS url()"),
    ("fetch('/api/orders').then(show);", "fetch call"),
    ("const request = new XMLHttpRequest();", "XMLHttpRequest"),
    ("const socket = new WebSocket('/live');", "WebSocket"),
    ("const events = new EventSource('/stream');", "EventSource"),
    ("import('./chart.js').then(draw);", "dynamic import"),
]
PASSED = [
    '<a href="#orders">Orders</a>',
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 4 4"><use href="#dot"/></svg>',
    '<img src="data:image/png;base64,iVBORw0KGgo=" alt="">',
    '<a href="mailto:someone@example.test">Mail</a>',
    '<link rel="stylesheet" href="local.css">',
]


@pytest.mark.parametrize("snippet, why", FLAGGED, ids=[why for _, why in FLAGGED])
def test_the_network_check_flags_a_call_or_a_scheme_url_with_its_line(snippet, why):
    text = f"<p>first line</p>\n{snippet}\n<p>last line</p>\n"
    found = prototype_files.find_network_calls(text)
    assert [finding["line"] for finding in found] == [2], why
    assert found[0]["text"] == snippet


@pytest.mark.parametrize("snippet", PASSED)
def test_the_network_check_passes_an_id_link_and_inline_content(snippet):
    assert prototype_files.find_network_calls(snippet) == []


def test_the_network_check_gives_one_finding_per_line():
    text = "fetch('/a'); fetch('/b'); new WebSocket('wss://x.test');\n<a href=\"#x\">x</a>\n"
    found = prototype_files.find_network_calls(text)
    assert [finding["line"] for finding in found] == [1]


def test_the_network_check_flags_a_protocol_relative_address():
    assert [f["line"] for f in prototype_files.find_network_calls('<img src="//cdn.example/a.png">')] == [1]


# --- check (VR-008, VR-009) ----------------------------------------------------------------------------------------

def run(cwd, *args):
    done = subprocess.run([sys.executable, str(SCRIPT), *args], cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", stdin=subprocess.DEVNULL)
    return done.returncode, json.loads(done.stdout)


def test_check_refuses_network_call_naming_each_line_with_a_call(tmp_path):
    mockup = tmp_path / "orders.html"
    shutil.copyfile(FIXTURES / "network.html", mockup)
    code, answer = run(tmp_path, "check", "--mockup", str(mockup))
    assert code == 1 and answer["error"]["code"] == "network-call"
    assert [finding["line"] for finding in answer["error"]["lines"]] == [6, 12]
    assert "6" in answer["error"]["reason"] and "12" in answer["error"]["reason"]


def test_check_answers_ok_on_a_clean_mockup(tmp_path):
    mockup = tmp_path / "orders.html"
    shutil.copyfile(FIXTURES / "clean.html", mockup)
    code, answer = run(tmp_path, "check", "--mockup", str(mockup))
    assert code == 0 and answer["ok"] is True
    assert answer["file"] == str(mockup) and answer["bytes"] == mockup.stat().st_size


def test_check_refuses_unreadable_for_a_missing_file(tmp_path):
    code, answer = run(tmp_path, "check", "--mockup", str(tmp_path / "none.html"))
    assert code == 2 and answer["error"]["code"] == "unreadable"


def test_check_refuses_afkv2_runtime_on_the_tooltip_block(tmp_path):
    mockup = tmp_path / "orders.html"
    clean = (FIXTURES / "clean.html").read_text(encoding="utf-8")
    mockup.write_text(inject.inject(clean, {"mockup": "a made-up term"}), encoding="utf-8")
    assert inject.MARK_START in mockup.read_text(encoding="utf-8")
    code, answer = run(tmp_path, "check", "--mockup", str(mockup))
    assert code == 1 and answer["error"]["code"] == "afkv2-runtime"
    assert answer["error"]["file"] == str(mockup) and answer["error"]["lines"]
