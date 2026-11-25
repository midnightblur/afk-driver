"""Tests for prototype_files.py: start, check and settle (SDD §3), and the network check (SDD §6).

A throwaway git repository holds the config and the spec folder; each verb runs through its command line. No lavish
host, live app or browser runs here.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import date
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
    ('import "https://cdn.example/side.js";', "side-effect import from an address"),
    ("import { chart } from 'https://cdn.example/chart.js';", "import from an address"),
    ('<img srcset="a.png 1x, https://cdn.example/b.png 2x">', "scheme URL in a later srcset candidate"),
    ("@import 'https://cdn.example/a.css';", "CSS import"),
    ("navigator.sendBeacon('/beacon', data);", "sendBeacon"),
    ('<video poster="https://cdn.example/p.png"></video>', "scheme URL in poster"),
    ('<object data="https://cdn.example/o.svg"></object>', "scheme URL in object data"),
]
PASSED = [
    '<a href="#orders">Orders</a>',
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 4 4"><use href="#dot"/></svg>',
    '<img src="data:image/png;base64,iVBORw0KGgo=" alt="">',
    '<a href="mailto:someone@example.test">Mail</a>',
    '<link rel="stylesheet" href="local.css">',
    'const data = "status: open";',
    '<img srcset="a.png 1x, b.png 2x">',
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
    assert found[0]["found"] == ["fetch", "WebSocket"]


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


# --- start (VR-007) ------------------------------------------------------------------------------------------------

TICKET = "PROJ-7"


def git(repo, *args):
    done = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


def set_config(repo, **values):
    config = {"spec_folder": "docs", **values}
    (repo / ".afkv2" / "config.json").write_text(json.dumps(config), encoding="utf-8")


WEB = {"name": "web", "source": "frontend/web", "catalog": "design/web"}
ADMIN = {"name": "admin", "source": "frontend/admin", "catalog": "design/admin"}
LIVE = {"start": "python -m http.server 4999", "address": "http://127.0.0.1:4999"}


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    (root / ".afkv2").mkdir(parents=True)
    git(root, "init", "-q", "-b", "main")
    set_config(root, frontends=[WEB])
    (root / "frontend" / "web").mkdir(parents=True)
    shutil.copytree(FIXTURES / "spec", root / "docs" / TICKET)
    return root


def test_start_with_no_frontend_refuses_naming_the_add_frontend_command(repo):
    set_config(repo)
    code, answer = run(repo, "start", "--ticket", TICKET)
    assert code == 1 and answer["error"]["code"] == "no-frontend"
    assert "catalog_files.py add-frontend" in answer["error"]["reason"]


def test_start_with_2_frontends_and_no_choice_refuses_pick_frontend_listing_both(repo):
    set_config(repo, frontends=[WEB, ADMIN])
    code, answer = run(repo, "start", "--ticket", TICKET)
    assert code == 1 and answer["error"]["code"] == "pick-frontend"
    assert answer["error"]["names"] == ["web", "admin"]
    assert "web" in answer["error"]["reason"] and "admin" in answer["error"]["reason"]


def test_start_with_an_unknown_frontend_refuses_no_frontend_naming_it(repo):
    code, answer = run(repo, "start", "--ticket", TICKET, "--frontend", "shop")
    assert code == 1 and answer["error"]["code"] == "no-frontend"
    assert "shop" in answer["error"]["reason"] and "catalog_files.py add-frontend" in answer["error"]["reason"]


def test_start_with_no_prd_refuses_missing_input_naming_to_prd(repo):
    (repo / "docs" / TICKET / "PRD.md").unlink()
    code, answer = run(repo, "start", "--ticket", TICKET)
    assert code == 1 and answer["error"]["code"] == "missing-input" and answer["error"]["writer"] == "/afkv2:to-prd"


def test_start_answers_the_paths_and_the_source_anchor(repo):
    (repo / "docs" / TICKET / "PROTOTYPE.md").unlink()
    code, answer = run(repo, "start", "--ticket", TICKET)
    assert code == 0, answer
    spec = (repo / "docs" / TICKET).as_posix()
    assert answer["spec_dir"] == spec and answer["prd"] == f"{spec}/PRD.md" and answer["index"] == f"{spec}/INDEX.md"
    assert answer["prototype_md"] == f"{spec}/PROTOTYPE.md" and answer["mockup_dir"] == f"{spec}/prototype"
    assert answer["frontend"] == WEB and answer["catalog_exists"] is False
    assert answer["live"] is None and answer["anchor"] == "source" and answer["resume"] is False


def test_start_picks_the_named_frontend_and_answers_the_catalog_and_live_anchors(repo):
    set_config(repo, frontends=[WEB, ADMIN], live=LIVE)
    code, answer = run(repo, "start", "--ticket", TICKET, "--frontend", "admin")
    assert code == 0 and answer["frontend"] == ADMIN and answer["anchor"] == "live"
    assert answer["live"]["address"] == LIVE["address"]
    (repo / "design" / "admin").mkdir(parents=True)
    (repo / "design" / "admin" / "README.md").write_text("# Catalog\n", encoding="utf-8")
    code, answer = run(repo, "start", "--ticket", TICKET, "--frontend", "admin")
    assert answer["catalog_exists"] is True and answer["anchor"] == "catalog" and answer["resume"] is True


# --- settle (VR-011, VR-002, VR-012) -------------------------------------------------------------------------------

def spec(repo):
    return repo / "docs" / TICKET


def prototype_row(repo):
    lines = (spec(repo) / "INDEX.md").read_text(encoding="utf-8").splitlines()
    return next(line for line in lines if line.startswith("| Prototype |"))


def edit(path, old, new):
    text = path.read_text(encoding="utf-8")
    assert old in text, old
    path.write_text(text.replace(old, new), encoding="utf-8")


def test_settle_refuses_bad_prototype_for_a_story_with_no_coverage_row_then_sets_the_index_row(repo):
    edit(spec(repo) / "PRD.md", "so that I find an open order.\n",
         "so that I find an open order.\n3. As a buyer, I want to cancel an order, so that I stop a mistake.\n")
    edit(spec(repo) / "PROTOTYPE.md", "| 2 | nav Orders → status filter → Open | reachable |",
         "| 3 | nav Orders → order → Cancel | gap |")
    before = (spec(repo) / "INDEX.md").read_bytes()
    code, answer = run(repo, "settle", "--ticket", TICKET)
    assert code == 1 and answer["error"]["code"] == "bad-prototype"
    assert any("story 2" in problem for problem in answer["error"]["problems"]), answer
    assert (spec(repo) / "INDEX.md").read_bytes() == before
    edit(spec(repo) / "PROTOTYPE.md", "| 3 | nav Orders → order → Cancel | gap |",
         "| 2 | nav Orders → status filter → Open | reachable |\n| 3 | nav Orders → order → Cancel | gap |")
    code, answer = run(repo, "settle", "--ticket", TICKET)
    assert code == 0, answer
    today = date.today().isoformat()
    assert answer["index_state"] == f"chosen {today}"
    assert prototype_row(repo) == f"| Prototype | PROTOTYPE.md | chosen {today} |"
    assert sorted(answer["scanned"]) == ["PROTOTYPE.md", "prototype/orders.html"]


def test_settle_refuses_a_coverage_row_for_a_story_the_prd_does_not_hold(repo):
    edit(spec(repo) / "PROTOTYPE.md", "| 2 | nav Orders → status filter → Open | reachable |",
         "| 2 | nav Orders → status filter → Open | reachable |\n| 9 | nowhere | gap |")
    code, answer = run(repo, "settle", "--ticket", TICKET)
    assert code == 1 and any("story 9" in problem for problem in answer["error"]["problems"])


@pytest.mark.parametrize("old, new, words", [
    ("## Decisions", "## Choices", "Decisions"),
    ("> Frontend: web", "> Frontend: shop", "shop"),
    ("prototype/orders.html |", "prototype/list.html |", "prototype/list.html"),
    ("| 1 | nav Orders → the order list | reachable |", "| 1 | nav Orders → the order list | done |", "done"),
])
def test_settle_names_each_problem_of_the_format(repo, old, new, words):
    edit(spec(repo) / "PROTOTYPE.md", old, new)
    code, answer = run(repo, "settle", "--ticket", TICKET)
    assert code == 1 and answer["error"]["code"] == "bad-prototype"
    assert any(words in problem for problem in answer["error"]["problems"]), answer


def test_the_format_file_names_each_section_settle_reads():
    text = (SKILL_DIR / "PROTOTYPE-FORMAT.md").read_text(encoding="utf-8")
    for section in prototype_files.SECTIONS:
        assert f"| `{section}` |" in text
    for state in prototype_files.STATES:
        assert f"`{state}`" in text


def test_settle_takes_live_verified_with_named_screenshots_and_refuses_it_without(repo):
    set_config(repo, frontends=[WEB], live=LIVE)
    edit(spec(repo) / "PROTOTYPE.md", "> Fidelity: source-only", "> Fidelity: live-verified · screenshots: shell.png, orders.png")
    code, answer = run(repo, "settle", "--ticket", TICKET)
    assert code == 0, answer
    assert prototype_row(repo) == f"| Prototype | PROTOTYPE.md | chosen {date.today().isoformat()} |"
    edit(spec(repo) / "PROTOTYPE.md", " · screenshots: shell.png, orders.png", "")
    code, answer = run(repo, "settle", "--ticket", TICKET)
    assert code == 1 and answer["error"]["code"] == "bad-prototype"
    assert any("screenshot" in problem for problem in answer["error"]["problems"]), answer


def test_settle_takes_source_only_with_no_live_block(repo):
    code, answer = run(repo, "settle", "--ticket", TICKET)
    assert code == 0 and answer["ok"] is True


# Built at run time, so no committed file holds a key shape.
MADE_UP_KEY = "gh" + "p_" + "Made0Up" * 5


def test_settle_refuses_secrets_with_the_file_and_line_and_keeps_the_index(repo):
    edit(spec(repo) / "prototype" / "orders.html", "<td>Made-up Buyer</td>", f"<td>{MADE_UP_KEY}</td>")
    before = (spec(repo) / "INDEX.md").read_bytes()
    code, answer = run(repo, "settle", "--ticket", TICKET)
    assert code == 1 and answer["error"]["code"] == "secrets"
    assert answer["error"]["hits"] == [{"file": "prototype/orders.html", "line": 14, "shape": "github-token"}]
    assert "prototype/orders.html:14" in answer["error"]["reason"] and MADE_UP_KEY not in json.dumps(answer)
    assert (spec(repo) / "INDEX.md").read_bytes() == before


@pytest.mark.parametrize("old, new, code_name", [
    ("<nav id=\"nav\">", "<script src=\"https://cdn.example/a.js\"></script>\n<nav id=\"nav\">", "network-call"),
    ("</body>", f"{inject.MARK_START}\n{inject.MARK_END}\n</body>", "afkv2-runtime"),
])
def test_settle_runs_the_mockup_checks_on_every_mockup_and_keeps_the_index(repo, old, new, code_name):
    edit(spec(repo) / "prototype" / "orders.html", old, new)
    before = (spec(repo) / "INDEX.md").read_bytes()
    code, answer = run(repo, "settle", "--ticket", TICKET)
    assert code == 1 and answer["error"]["code"] == code_name and answer["error"]["file"] == "prototype/orders.html"
    assert (spec(repo) / "INDEX.md").read_bytes() == before
