"""Tests for prototype_files.py: start, check and settle (SDD §3), and the network check (SDD §6).

A throwaway git repository holds the config and the spec folder; each verb runs through its command line. No lavish
host, live app or browser runs here. Each failure message shows the input (the command and every change made to the
fixture), the expected value and the actual value. A settle that passes runs with the date pinned to 2026-03-14, so
the expected INDEX row is a literal.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
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

# Runs the script file as __main__, with date.today() pinned to 2026-03-14. Only the date changes: the argv, the
# answer and the exit code are those of the real command line.
PINNED_CLOCK = """
import datetime, runpy, sys
class PinnedDate(datetime.date):
    @classmethod
    def today(cls):
        return cls(2026, 3, 14)
datetime.date = PinnedDate
script = sys.argv[1]
sys.argv = sys.argv[1:]
runpy.run_path(script, run_name="__main__")
"""
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


def run(cwd, *args, pinned=False):
    head = [sys.executable, "-c", PINNED_CLOCK, str(SCRIPT)] if pinned else [sys.executable, str(SCRIPT)]
    done = subprocess.run([*head, *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                          stdin=subprocess.DEVNULL)
    given = f"prototype_files.py {' '.join(args)}" + (f" after: {'; '.join(CHANGES)}" if CHANGES else "")
    try:
        answer = json.loads(done.stdout)
    except ValueError:
        pytest.fail(f"\ninput: {given}\nexpected: 1 JSON answer\nactual: exit {done.returncode}, "
                    f"stdout {done.stdout!r}, stderr {done.stderr!r}")
    return Ran(done.returncode, answer, given)


def expect(actual, expected, given):
    assert actual == expected, f"\ninput: {given}\nexpected: {expected!r}\nactual: {actual!r}"


def expect_in(part, whole, given):
    assert part in whole, f"\ninput: {given}\nexpected to hold: {part!r}\nactual: {whole!r}"


def expect_problem(words, ran):
    problems = ran.answer.get("error", {}).get("problems", [])
    assert any(words in problem for problem in problems), \
        f"\ninput: {ran.given}\nexpected: a problem with {words!r}\nactual: {ran.answer!r}"


def expect_refusal(ran, exit_code, code):
    expect(ran.code, exit_code, f"{ran.given} (answer {ran.answer!r})")
    expect(ran.answer.get("error", {}).get("code"), code, f"{ran.given} (answer {ran.answer!r})")


def expect_ok(ran):
    expect(ran.code, 0, f"{ran.given} (answer {ran.answer!r})")
    expect(ran.answer.get("ok"), True, f"{ran.given} (answer {ran.answer!r})")


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
    ("<img srcset=https://cdn.example/a.png>", "scheme URL in an unquoted srcset"),
]
PASSED = [
    '<a href="#orders">Orders</a>',
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 4 4"><use href="#dot"/></svg>',
    '<img src="data:image/png;base64,iVBORw0KGgo=" alt="">',
    '<a href="mailto:someone@example.test">Mail</a>',
    '<link rel="stylesheet" href="local.css">',
    'const data = "status: open";',
    '<img srcset="a.png 1x, b.png 2x">',
    '<a href="javascript:void(0)">x</a>',
    '<img src="blob:abc">',
    '<a href="tel:123">call</a>',
    '<iframe src="about:blank"></iframe>',
]


@pytest.mark.parametrize("snippet, why", FLAGGED, ids=[why for _, why in FLAGGED])
def test_the_network_check_flags_a_call_or_a_scheme_url_with_its_line(snippet, why):
    text = f"<p>first line</p>\n{snippet}\n<p>last line</p>\n"
    found = prototype_files.find_network_calls(text)
    expect([finding["line"] for finding in found], [2], f"{why}: {text!r}")
    expect(found[0]["text"], snippet, f"{why}: {text!r}")


@pytest.mark.parametrize("snippet", PASSED)
def test_the_network_check_passes_an_id_link_and_inline_content(snippet):
    expect(prototype_files.find_network_calls(snippet), [], repr(snippet))


def test_the_network_check_gives_one_finding_per_line():
    text = "fetch('/a'); fetch('/b'); new WebSocket('wss://x.test');\n<a href=\"#x\">x</a>\n"
    found = prototype_files.find_network_calls(text)
    expect([finding["line"] for finding in found], [1], repr(text))
    expect(found[0]["found"], ["fetch", "WebSocket"], repr(text))


def test_the_network_check_flags_a_protocol_relative_address():
    text = '<img src="//cdn.example/a.png">'
    expect([finding["line"] for finding in prototype_files.find_network_calls(text)], [1], repr(text))


# --- check (VR-008, VR-009) ----------------------------------------------------------------------------------------

def test_check_refuses_network_call_naming_each_line_with_a_call(tmp_path):
    shutil.copyfile(FIXTURES / "network.html", tmp_path / "orders.html")
    note("orders.html is fixtures/prototype/network.html: a CDN script on line 6, a #orders link on line 9, a fetch on line 12")
    ran = run(tmp_path, "check", "--mockup", "orders.html")
    expect_refusal(ran, 1, "network-call")
    expect([finding["line"] for finding in ran.answer["error"]["lines"]], [6, 12], ran.given)
    expect_in("orders.html:6", ran.answer["error"]["reason"], ran.given)
    expect_in("orders.html:12", ran.answer["error"]["reason"], ran.given)


def clean_lf():
    """clean.html with LF line ends, 539 bytes on every checkout."""
    return (FIXTURES / "clean.html").read_bytes().replace(b"\r\n", b"\n")


def test_check_answers_ok_on_a_clean_mockup(tmp_path):
    (tmp_path / "orders.html").write_bytes(clean_lf())
    note("orders.html is fixtures/prototype/clean.html with LF line ends, 539 bytes")
    ran = run(tmp_path, "check", "--mockup", "orders.html")
    expect_ok(ran)
    expect(ran.answer["file"], "orders.html", ran.given)
    expect(ran.answer["bytes"], 539, ran.given)


def test_check_echoes_an_absolute_mockup_path(tmp_path):
    (tmp_path / "orders.html").write_bytes(clean_lf())
    note("orders.html is clean.html, given as an absolute path")
    ran = run(tmp_path, "check", "--mockup", str(tmp_path / "orders.html"))
    expect_ok(ran)
    expect(Path(ran.answer["file"]).is_absolute(), True, f"{ran.given} (answer {ran.answer!r})")
    expect(Path(ran.answer["file"]).name, "orders.html", ran.given)


def test_check_refuses_unreadable_for_a_missing_file(tmp_path):
    ran = run(tmp_path, "check", "--mockup", "none.html")
    expect_refusal(ran, 2, "unreadable")


def test_check_refuses_afkv2_runtime_on_the_tooltip_block(tmp_path):
    clean = clean_lf().decode("utf-8")
    (tmp_path / "orders.html").write_text(inject.inject(clean, {"mockup": "a made-up term"}), encoding="utf-8",
                                          newline="\n")
    expect_in(inject.MARK_START, (tmp_path / "orders.html").read_text(encoding="utf-8"), "inject.inject(clean.html)")
    note("orders.html is clean.html with the afkv2 tooltip block injected: start mark line 17, end mark line 434")
    ran = run(tmp_path, "check", "--mockup", "orders.html")
    expect_refusal(ran, 1, "afkv2-runtime")
    expect(ran.answer["error"]["file"], "orders.html", ran.given)
    expect(ran.answer["error"]["lines"], [17, 434], ran.given)


def test_check_refuses_a_tooltip_mark_that_shares_its_line(tmp_path):
    (tmp_path / "orders.html").write_text(f"<p>x</p>\n<p>y</p>{inject.MARK_START}<style></style>\n", encoding="utf-8")
    note("orders.html holds the tooltip start mark at the end of line 2")
    ran = run(tmp_path, "check", "--mockup", "orders.html")
    expect_refusal(ran, 1, "afkv2-runtime")
    expect(ran.answer["error"]["lines"], [2], ran.given)


# --- start (VR-007) ------------------------------------------------------------------------------------------------

TICKET = "PROJ-7"


def git(repo, *args):
    done = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    assert done.returncode == 0, f"\ninput: git {' '.join(args)}\nexpected: exit 0\nactual: {done.stderr}"
    return done.stdout.strip()


def set_config(repo, **values):
    config = {"spec_folder": "docs", **values}
    (repo / ".afkv2" / "config.json").write_text(json.dumps(config), encoding="utf-8")
    note(f"config {json.dumps(config)}")


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
    CHANGES.clear()
    note("spec folder docs/PROJ-7 is fixtures/prototype/spec; config frontends [web]")
    return root


def relative(path, repo):
    """The answered path from the repository root; the raw path when it is not under it, so expect shows it."""
    try:
        return Path(path).relative_to(repo).as_posix()
    except ValueError:
        return path


def test_start_with_no_frontend_refuses_naming_the_add_frontend_command(repo):
    set_config(repo)
    ran = run(repo, "start", "--ticket", TICKET)
    expect_refusal(ran, 1, "no-frontend")
    expect_in("catalog_files.py add-frontend", ran.answer["error"]["reason"], ran.given)


def test_start_with_2_frontends_and_no_choice_refuses_pick_frontend_listing_both(repo):
    set_config(repo, frontends=[WEB, ADMIN])
    ran = run(repo, "start", "--ticket", TICKET)
    expect_refusal(ran, 1, "pick-frontend")
    expect(ran.answer["error"]["names"], ["web", "admin"], ran.given)
    expect_in("web", ran.answer["error"]["reason"], ran.given)
    expect_in("admin", ran.answer["error"]["reason"], ran.given)


def test_start_with_an_unknown_frontend_refuses_no_frontend_naming_it(repo):
    ran = run(repo, "start", "--ticket", TICKET, "--frontend", "shop")
    expect_refusal(ran, 1, "no-frontend")
    expect_in("shop", ran.answer["error"]["reason"], ran.given)
    expect_in("catalog_files.py add-frontend", ran.answer["error"]["reason"], ran.given)


def test_start_with_no_prd_refuses_missing_input_naming_to_prd(repo):
    (repo / "docs" / TICKET / "PRD.md").unlink()
    note("PRD.md deleted")
    ran = run(repo, "start", "--ticket", TICKET)
    expect_refusal(ran, 1, "missing-input")
    expect(ran.answer["error"]["writer"], "/afkv2:to-prd", ran.given)


def test_start_answers_the_paths_and_the_source_anchor(repo):
    (repo / "docs" / TICKET / "PROTOTYPE.md").unlink()
    note("PROTOTYPE.md deleted")
    ran = run(repo, "start", "--ticket", TICKET)
    expect(ran.code, 0, f"{ran.given} (answer {ran.answer!r})")
    paths = {key: relative(ran.answer[key], repo) for key in ("spec_dir", "prd", "index", "prototype_md", "mockup_dir")}
    expect([key for key in paths if "\\" in ran.answer[key]], [], f"{ran.given} (answer {ran.answer!r})")
    expect(paths, {"spec_dir": "docs/PROJ-7", "prd": "docs/PROJ-7/PRD.md", "index": "docs/PROJ-7/INDEX.md",
                   "prototype_md": "docs/PROJ-7/PROTOTYPE.md", "mockup_dir": "docs/PROJ-7/prototype"}, ran.given)
    expect(ran.answer["frontend"], {"name": "web", "source": "frontend/web", "catalog": "design/web"}, ran.given)
    expect(ran.answer["catalog_exists"], False, ran.given)
    expect(ran.answer["live"], None, ran.given)
    expect(ran.answer["anchor"], "source", ran.given)
    expect(ran.answer["resume"], False, ran.given)


def test_start_picks_the_named_frontend_and_answers_the_catalog_and_live_anchors(repo):
    set_config(repo, frontends=[WEB, ADMIN], live=LIVE)
    ran = run(repo, "start", "--ticket", TICKET, "--frontend", "admin")
    expect(ran.code, 0, f"{ran.given} (answer {ran.answer!r})")
    expect(ran.answer["frontend"], {"name": "admin", "source": "frontend/admin", "catalog": "design/admin"}, ran.given)
    expect(ran.answer["anchor"], "live", ran.given)
    expect(ran.answer["live"]["address"], "http://127.0.0.1:4999", ran.given)
    (repo / "design" / "admin").mkdir(parents=True)
    (repo / "design" / "admin" / "README.md").write_text("# Catalog\n", encoding="utf-8")
    note("design/admin/README.md written")
    ran = run(repo, "start", "--ticket", TICKET, "--frontend", "admin")
    expect(ran.answer["catalog_exists"], True, ran.given)
    expect(ran.answer["anchor"], "catalog", ran.given)
    expect(ran.answer["resume"], True, ran.given)


# --- settle (VR-011, VR-002, VR-012) -------------------------------------------------------------------------------

PINNED_ROW = "| Prototype | PROTOTYPE.md | chosen 2026-03-14 |"
FIXTURE_ROW = "| Prototype | PROTOTYPE.md | — |"


def spec(repo):
    return repo / "docs" / TICKET


def prototype_row(repo):
    lines = (spec(repo) / "INDEX.md").read_text(encoding="utf-8").splitlines()
    return next(line for line in lines if line.startswith("| Prototype |"))


def edit(path, old, new):
    text = path.read_text(encoding="utf-8")
    assert old in text, f"\ninput: {path.name}\nexpected to hold: {old!r}\nactual: {text!r}"
    path.write_text(text.replace(old, new), encoding="utf-8")
    note(f"{path.name}: {old!r} -> {new!r}")


def test_settle_refuses_bad_prototype_for_a_story_with_no_coverage_row_then_sets_the_index_row(repo):
    edit(spec(repo) / "PRD.md", "so that I find an open order.\n",
         "so that I find an open order.\n3. As a buyer, I want to cancel an order, so that I stop a mistake.\n")
    edit(spec(repo) / "PROTOTYPE.md", "| 2 | nav Orders → status filter → Open | reachable |",
         "| 3 | nav Orders → order → Cancel | gap |")
    before = (spec(repo) / "INDEX.md").read_bytes()
    ran = run(repo, "settle", "--ticket", TICKET, pinned=True)
    expect_refusal(ran, 1, "bad-prototype")
    expect_problem("no coverage row for story 2", ran)
    expect(prototype_row(repo), FIXTURE_ROW, ran.given)
    expect((spec(repo) / "INDEX.md").read_bytes() == before, True, f"{ran.given}: INDEX.md bytes unchanged")
    edit(spec(repo) / "PROTOTYPE.md", "| 3 | nav Orders → order → Cancel | gap |",
         "| 2 | nav Orders → status filter → Open | reachable |\n| 3 | nav Orders → order → Cancel | gap |")
    ran = run(repo, "settle", "--ticket", TICKET, pinned=True)
    expect_ok(ran)
    expect(ran.answer["index_state"], "chosen 2026-03-14", ran.given)
    expect(prototype_row(repo), PINNED_ROW, ran.given)
    expect(sorted(ran.answer["scanned"]), ["PROTOTYPE.md", "prototype/orders.html"], ran.given)


def test_settle_refuses_a_coverage_row_for_a_story_the_prd_does_not_hold(repo):
    edit(spec(repo) / "PROTOTYPE.md", "| 2 | nav Orders → status filter → Open | reachable |",
         "| 2 | nav Orders → status filter → Open | reachable |\n| 9 | nowhere | gap |")
    ran = run(repo, "settle", "--ticket", TICKET)
    expect_refusal(ran, 1, "bad-prototype")
    expect_problem("story 9", ran)


@pytest.mark.parametrize("old, new, words", [
    ("## Decisions", "## Choices", "Decisions"),
    ("> Frontend: web", "> Frontend: shop", "shop"),
    ("prototype/orders.html |", "prototype/list.html |", "prototype/list.html"),
    ("| 1 | nav Orders → the order list | reachable |", "| 1 | nav Orders → the order list | done |", "done"),
    ("| 1 | nav Orders → the order list | reachable |",
     "| 1 | nav Orders → the order list | reachable |\n| 1 | nav Orders | reachable |", "2 coverage rows"),
    ("> Date: 2026-11-25\n", "", "Date"),
    ("> Date: 2026-11-25", "> Date: soon", "Date"),
    ("> Fidelity: source-only", "> Fidelity: guessed", "Fidelity"),
    ("| Orders | prototype/orders.html | the Orders link of the nav bar | 1, 2 |\n", "", "Screens table has no row"),
    ("## Screens", "## PRD gaps\n\nnone\n\n## Screens", "order"),
])
def test_settle_names_each_problem_of_the_format(repo, old, new, words):
    edit(spec(repo) / "PROTOTYPE.md", old, new)
    ran = run(repo, "settle", "--ticket", TICKET)
    expect_refusal(ran, 1, "bad-prototype")
    expect_problem(words, ran)


def test_the_format_file_names_each_section_settle_reads():
    text = (SKILL_DIR / "PROTOTYPE-FORMAT.md").read_text(encoding="utf-8")
    for section in ("Screens", "Coverage", "Fidelity", "Decisions", "PRD gaps"):
        expect_in(f"| `{section}` |", text, "PROTOTYPE-FORMAT.md")
    for state in ("reachable", "gap", "retired"):
        expect_in(f"`{state}`", text, "PROTOTYPE-FORMAT.md")
    expect(prototype_files.SECTIONS, ("Screens", "Coverage", "Fidelity", "Decisions", "PRD gaps"), "SECTIONS")
    expect(prototype_files.STATES, ("reachable", "gap", "retired"), "STATES")


def test_settle_takes_live_verified_with_named_screenshots_and_refuses_it_without(repo):
    set_config(repo, frontends=[WEB], live=LIVE)
    edit(spec(repo) / "PROTOTYPE.md", "> Fidelity: source-only",
         "> Fidelity: live-verified · screenshots: shell.png, orders.png")
    ran = run(repo, "settle", "--ticket", TICKET, pinned=True)
    expect_ok(ran)
    expect(prototype_row(repo), PINNED_ROW, ran.given)
    edit(spec(repo) / "PROTOTYPE.md", " · screenshots: shell.png, orders.png", "")
    ran = run(repo, "settle", "--ticket", TICKET, pinned=True)
    expect_refusal(ran, 1, "bad-prototype")
    expect_problem("screenshot", ran)


def test_settle_takes_source_only_with_no_live_block(repo):
    ran = run(repo, "settle", "--ticket", TICKET, pinned=True)
    expect_ok(ran)
    expect(prototype_row(repo), PINNED_ROW, ran.given)


# Built at run time, so no committed file holds a key shape.
MADE_UP_KEY = "gh" + "p_" + "Made0Up" * 5


def test_settle_refuses_secrets_in_prototype_md_itself(repo):
    edit(spec(repo) / "PROTOTYPE.md", "Differences left: none.", f"Differences left: none. {MADE_UP_KEY}")
    ran = run(repo, "settle", "--ticket", TICKET)
    expect_refusal(ran, 1, "secrets")
    expect(ran.answer["error"]["hits"], [{"file": "PROTOTYPE.md", "line": 22, "shape": "github-token"}], ran.given)


def test_settle_with_no_index_refuses_missing_input_naming_to_prd(repo):
    (spec(repo) / "INDEX.md").unlink()
    note("INDEX.md deleted")
    ran = run(repo, "settle", "--ticket", TICKET)
    expect_refusal(ran, 1, "missing-input")
    expect(ran.answer["error"]["writer"], "/afkv2:to-prd", ran.given)


def test_settle_refuses_secrets_with_the_file_and_line_and_keeps_the_index(repo):
    edit(spec(repo) / "prototype" / "orders.html", "<td>Made-up Buyer</td>", f"<td>{MADE_UP_KEY}</td>")
    before = (spec(repo) / "INDEX.md").read_bytes()
    ran = run(repo, "settle", "--ticket", TICKET)
    expect_refusal(ran, 1, "secrets")
    expect(ran.answer["error"]["hits"], [{"file": "prototype/orders.html", "line": 14, "shape": "github-token"}],
           ran.given)
    expect_in("prototype/orders.html:14", ran.answer["error"]["reason"], ran.given)
    expect(MADE_UP_KEY in json.dumps(ran.answer), False, f"{ran.given} (answer {ran.answer!r})")
    expect(prototype_row(repo), FIXTURE_ROW, ran.given)
    expect((spec(repo) / "INDEX.md").read_bytes() == before, True, f"{ran.given}: INDEX.md bytes unchanged")


@pytest.mark.parametrize("old, new, code_name", [
    ("<nav id=\"nav\">", "<script src=\"https://cdn.example/a.js\"></script>\n<nav id=\"nav\">", "network-call"),
    ("</body>", f"{inject.MARK_START}\n{inject.MARK_END}\n</body>", "afkv2-runtime"),
])
def test_settle_runs_the_mockup_checks_on_every_mockup_and_keeps_the_index(repo, old, new, code_name):
    edit(spec(repo) / "prototype" / "orders.html", old, new)
    before = (spec(repo) / "INDEX.md").read_bytes()
    ran = run(repo, "settle", "--ticket", TICKET)
    expect_refusal(ran, 1, code_name)
    expect(ran.answer["error"]["file"], "prototype/orders.html", ran.given)
    expect(prototype_row(repo), FIXTURE_ROW, ran.given)
    expect((spec(repo) / "INDEX.md").read_bytes() == before, True, f"{ran.given}: INDEX.md bytes unchanged")


def test_settle_checks_every_file_of_the_mockup_folder(repo):
    (spec(repo) / "prototype" / "app.js").write_text("fetch('/api/orders');\n", encoding="utf-8")
    note("prototype/app.js holds fetch('/api/orders')")
    ran = run(repo, "settle", "--ticket", TICKET)
    expect_refusal(ran, 1, "network-call")
    expect(ran.answer["error"]["file"], "prototype/app.js", ran.given)


def test_settle_refuses_a_mockup_outside_the_mockup_folder(repo):
    (spec(repo) / "other").mkdir()
    shutil.copyfile(FIXTURES / "clean.html", spec(repo) / "other" / "orders.html")
    note("other/orders.html is clean.html")
    edit(spec(repo) / "PROTOTYPE.md", "| prototype/orders.html |", "| other/orders.html |")
    ran = run(repo, "settle", "--ticket", TICKET)
    expect_refusal(ran, 1, "bad-prototype")
    expect_problem("prototype/", ran)


def test_settle_keeps_a_retired_row_of_a_story_the_prd_dropped(repo):
    edit(spec(repo) / "PROTOTYPE.md", "| 2 | nav Orders → status filter → Open | reachable |",
         "| 2 | nav Orders → status filter → Open | reachable |\n| 3 | nav Orders → order → Cancel | retired |")
    ran = run(repo, "settle", "--ticket", TICKET, pinned=True)
    expect_ok(ran)
    expect(prototype_row(repo), PINNED_ROW, ran.given)
    expect_in("| 3 | nav Orders → order → Cancel | retired |",
              (spec(repo) / "PROTOTYPE.md").read_text(encoding="utf-8"), ran.given)


def test_settle_counts_only_top_level_stories(repo):
    edit(spec(repo) / "PRD.md", "so that I know what I bought.\n",
         "so that I know what I bought.\n   1. a note under story 1\n   7. another note\n")
    ran = run(repo, "settle", "--ticket", TICKET)
    expect_ok(ran)


def test_settle_refuses_a_file_too_large_to_scan(repo):
    (spec(repo) / "prototype" / "big.svg").write_text("<svg>" + "x" * (2 * 1024 * 1024) + "</svg>\n", encoding="utf-8")
    note("prototype/big.svg is 2 MiB")
    ran = run(repo, "settle", "--ticket", TICKET)
    expect_refusal(ran, 1, "bad-prototype")
    expect_problem("prototype/big.svg", ran)


# --- round 2 of the review -----------------------------------------------------------------------------------------

def test_settle_numbers_bullet_stories_by_their_position(repo):
    edit(spec(repo) / "PRD.md", "1. As a buyer, I want to see", "- As a buyer, I want to see")
    edit(spec(repo) / "PRD.md", "2. As a buyer, I want to filter", "* As a buyer, I want to filter")
    ran = run(repo, "settle", "--ticket", TICKET)
    expect_ok(ran)
    edit(spec(repo) / "PROTOTYPE.md", "| 2 | nav Orders → status filter → Open | reachable |\n", "")
    ran = run(repo, "settle", "--ticket", TICKET)
    expect_refusal(ran, 1, "bad-prototype")
    expect_in("no coverage row for story 2", ran.answer["error"]["problems"], ran.given)


def test_settle_refuses_a_prd_with_no_story(repo):
    edit(spec(repo) / "PRD.md", "1. As a buyer, I want to see", "As a buyer, I want to see")
    edit(spec(repo) / "PRD.md", "2. As a buyer, I want to filter", "As a buyer, I want to filter")
    ran = run(repo, "settle", "--ticket", TICKET)
    expect_refusal(ran, 1, "bad-prototype")
    expect_problem("no story", ran)


def test_settle_refuses_retired_for_a_story_the_prd_holds(repo):
    edit(spec(repo) / "PROTOTYPE.md", "| 2 | nav Orders → status filter → Open | reachable |", "| 2 | — | retired |")
    ran = run(repo, "settle", "--ticket", TICKET)
    expect_refusal(ran, 1, "bad-prototype")
    expect_problem("story 2 is in the PRD, so it is not retired", ran)


def test_settle_lets_prototype_md_describe_the_calls_of_the_live_app(repo):
    edit(spec(repo) / "PROTOTYPE.md", "- The status filter sits above the list",
         "- The live app loads the rows with fetch() from the orders API; the mockup inlines them.\n"
         "- The status filter sits above the list")
    ran = run(repo, "settle", "--ticket", TICKET)
    expect_ok(ran)


def test_settle_refuses_a_mockup_path_that_climbs_out_of_the_mockup_folder(repo):
    (spec(repo) / "other").mkdir()
    shutil.copyfile(FIXTURES / "clean.html", spec(repo) / "other" / "orders.html")
    note("other/orders.html is clean.html")
    edit(spec(repo) / "PROTOTYPE.md", "| prototype/orders.html |", "| prototype/../other/orders.html |")
    ran = run(repo, "settle", "--ticket", TICKET)
    expect_refusal(ran, 1, "bad-prototype")
    expect_problem("mockup prototype/../other/orders.html is not a file in prototype/", ran)


def test_settle_with_no_prototype_md_refuses_bad_prototype(repo):
    (spec(repo) / "PROTOTYPE.md").unlink()
    note("PROTOTYPE.md deleted")
    ran = run(repo, "settle", "--ticket", TICKET)
    expect_refusal(ran, 1, "bad-prototype")
    expect(ran.answer["error"]["problems"], ["no PROTOTYPE.md"], ran.given)
