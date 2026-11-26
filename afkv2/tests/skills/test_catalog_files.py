"""Tests for catalog_files.py: start, add-frontend and check (SDD §3, §4; ticket 207 VR-018 to VR-021; decision D-8).

A throwaway git repository holds the config and the catalog folder; each verb runs through its command line. No
live app or browser runs here. Each failure message shows the input (the command and every change made to the
fixture), the expected value and the actual value.
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
SCRIPT = PLUGIN / "skills" / "design-system" / "scripts" / "catalog_files.py"
CONFIG_READER = PLUGIN / "scripts" / "afkv2_config.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "catalog"

CHANGES = []


@pytest.fixture(autouse=True)
def _fresh_changes():
    CHANGES.clear()


def note(change):
    """Record a change to the fixture, so that a failure message names it as input."""
    CHANGES.append(change)


def given(command):
    return command + (f" after: {'; '.join(CHANGES)}" if CHANGES else "")


@dataclass
class Ran:
    code: int
    answer: dict
    given: str

    def about(self, part):
        return f"{self.given} ({part} of answer {self.answer!r})"


def expect(actual, expected, input_):
    assert actual == expected, f"\ninput: {input_}\nexpected: {expected!r}\nactual: {actual!r}"


def expect_in(part, whole, input_):
    assert part in whole, f"\ninput: {input_}\nexpected to hold: {part!r}\nactual: {whole!r}"


def expect_not_in(part, whole, input_):
    assert part not in whole, f"\ninput: {input_}\nexpected not to hold: {part!r}\nactual: {whole!r}"


def expect_ok(ran):
    expect(ran.code, 0, ran.about("exit code"))
    expect_field(ran, "ok", True)


def expect_refusal(ran, code):
    expect(ran.code, 1, ran.about("exit code"))
    expect(ran.answer.get("error", {}).get("code"), code, ran.about("error code"))


def expect_field(ran, field, expected):
    expect(ran.answer.get(field), expected, ran.about(f"field {field!r}"))
    if isinstance(expected, bool):
        expect(type(ran.answer.get(field)), bool, ran.about(f"type of field {field!r}"))


def expect_error_field(ran, field, expected):
    expect(ran.answer.get("error", {}).get(field), expected, ran.about(f"error field {field!r}"))


def expect_error_reason_holds(ran, part):
    expect_in(part, ran.answer.get("error", {}).get("reason", ""), ran.about("error reason"))


def expect_any_problem(ran, words):
    problems = ran.answer.get("error", {}).get("problems", [])
    assert any(words in problem for problem in problems), (
        f"\ninput: {ran.given}\nexpected a problem holding: {words!r}\nactual problems: {problems!r}")


def run(cwd, *args):
    command = "catalog_files.py " + " ".join(str(arg) for arg in args)
    done = subprocess.run([sys.executable, str(SCRIPT), *args], cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", stdin=subprocess.DEVNULL)
    try:
        answer = json.loads(done.stdout)
    except json.JSONDecodeError:
        pytest.fail(f"\ninput: {given(command)}\nexpected: one JSON object on stdout\n"
                    f"actual stdout: {done.stdout!r}\nactual stderr: {done.stderr!r}")
    return Ran(done.returncode, answer, given(command))


def read_config(cwd):
    done = subprocess.run([sys.executable, str(CONFIG_READER), "read"], cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", stdin=subprocess.DEVNULL)
    try:
        answer = json.loads(done.stdout)
    except json.JSONDecodeError:
        answer = None
    if done.returncode != 0 or not isinstance(answer, dict):
        pytest.fail(f"\ninput: {given('afkv2_config.py read')}\nexpected: exit 0 and one JSON object on stdout\n"
                    f"actual exit: {done.returncode}\nactual stdout: {done.stdout!r}\nactual stderr: {done.stderr!r}")
    return answer


def config_bytes(repo):
    return (repo / ".afkv2" / "config.json").read_bytes()


def git(repo, *args):
    done = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    assert done.returncode == 0, f"\ninput: git {' '.join(args)}\nexpected: exit 0\nactual: {done.stderr!r}"
    return done.stdout.strip()


def set_config(repo, **values):
    config = {"spec_folder": "docs", **values}
    (repo / ".afkv2" / "config.json").write_text(json.dumps(config), encoding="utf-8")
    note(f"config.json is {json.dumps(config)}")


WEB = {"name": "web", "source": "frontend/web", "catalog": "design/web"}


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    (root / ".afkv2").mkdir(parents=True)
    git(root, "init", "-q", "-b", "main")
    set_config(root)
    (root / "frontend" / "web").mkdir(parents=True)
    note("folder frontend/web exists")
    return root


def expect_config_frontends(repo, ran, expected):
    config = read_config(repo)
    expect(config.get("frontends"), expected, f"{ran.given}, then afkv2_config.py read (answer {config!r})")


def expect_config_unchanged(repo, ran, before):
    expect(config_bytes(repo), before, f"{ran.given} (config.json bytes after the refusal)")


# --- add-frontend (VR-020) -----------------------------------------------------------------------------------------

def test_add_frontend_writes_the_entry_and_the_config_read_answers_it(repo):
    ran = run(repo, "add-frontend", "--name", "web", "--source", "frontend/web", "--catalog", "design/web")
    expect_ok(ran)
    expect_field(ran, "entry", WEB)
    expect_config_frontends(repo, ran, [WEB])
    stored = json.loads(config_bytes(repo).decode("utf-8"))
    expect(stored.get("spec_folder"), "docs", f"{ran.given} (config.json after: {stored!r})")


@pytest.mark.parametrize("name, source, catalog, words", [
    ("web", "frontend/web", "design/other", "already the name"),
    ("shop", "frontend/web", "design/web", "already the catalog"),
    ("shop", "../outside", "design/shop", "inside the repository"),
    ("shop", "frontend/web", "../outside", "inside the repository"),
    ("shop", "frontend/none", "design/shop", "no folder"),
    ("Shop", "frontend/web", "design/shop", "lower case"),
    ("shop", "frontend/web", ".", "not the repository root"),
    ("shop", "frontend/web", "./", "not the repository root"),
])
def test_add_frontend_refuses_bad_value_and_leaves_the_config_unchanged(repo, name, source, catalog, words):
    expect_ok(run(repo, "add-frontend", "--name", "web", "--source", "frontend/web", "--catalog", "design/web"))
    note("add-frontend --name web --source frontend/web --catalog design/web answered ok")
    before = config_bytes(repo)
    ran = run(repo, "add-frontend", "--name", name, "--source", source, "--catalog", catalog)
    expect_refusal(ran, "bad-value")
    expect_error_reason_holds(ran, words)
    expect_config_unchanged(repo, ran, before)


def test_add_frontend_refuses_an_absolute_source_outside_the_repository(repo, tmp_path):
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    note(f"folder {outside.as_posix()} exists outside the repository")
    before = config_bytes(repo)
    ran = run(repo, "add-frontend", "--name", "web", "--source", str(outside), "--catalog", "design/web")
    expect_refusal(ran, "bad-value")
    expect_error_reason_holds(ran, "must stay inside the repository root")
    expect_config_unchanged(repo, ran, before)


def test_add_frontend_stores_posix_paths_relative_to_the_repository(repo):
    ran = run(repo, "add-frontend", "--name", "web", "--source", "frontend/web/", "--catalog", "./design/web")
    expect_ok(ran)
    expect_config_frontends(repo, ran, [WEB])


# --- start and check on a whole catalog (VR-018) ----------------------------------------------------------------

ADMIN = {"name": "admin", "source": "frontend/admin", "catalog": "design/admin"}
LIVE = {"start": "python -m http.server 4999", "address": "http://127.0.0.1:4999"}


@pytest.fixture
def catalog(repo):
    """The repository with the frontend web and its catalog of tokens.css and 3 checked cards."""
    set_config(repo, frontends=[WEB])
    shutil.copytree(FIXTURES, repo / "design" / "web")
    note("design/web is a copy of fixtures/catalog (README.md, tokens.css, 3 checked cards)")
    return repo / "design" / "web"


def test_start_answers_the_frontend_its_catalog_folder_and_the_cards(repo, catalog):
    ran = run(repo, "start", "--frontend", "web")
    expect_ok(ran)
    expect_field(ran, "frontend", WEB)
    expect_field(ran, "catalog_dir", catalog.resolve().as_posix())
    expect_field(ran, "catalog_exists", True)
    expect_field(ran, "live", None)
    cards = ran.answer.get("cards") or [{}]
    expect([card.get("file") for card in cards], ["cards/shell.html", "cards/button.html", "cards/list-page.html"],
           ran.about("card files"))
    expect(cards[0], {"file": "cards/shell.html", "kind": "shell", "state": "checked", "screenshot": "shell.png"},
           ran.about("first card"))


def test_start_with_no_catalog_answers_no_cards_and_the_live_block(repo):
    set_config(repo, frontends=[WEB], live=LIVE)
    ran = run(repo, "start")
    expect_ok(ran)
    expect_field(ran, "catalog_exists", False)
    expect_field(ran, "cards", [])
    expect((ran.answer.get("live") or {}).get("address"), LIVE["address"], ran.about("live address"))


def test_start_refuses_no_frontend_and_pick_frontend(repo):
    ran = run(repo, "start")
    expect_refusal(ran, "no-frontend")
    expect_error_reason_holds(ran, "catalog_files.py add-frontend")
    set_config(repo, frontends=[WEB, ADMIN])
    ran = run(repo, "start")
    expect_refusal(ran, "pick-frontend")
    expect_error_field(ran, "names", ["web", "admin"])


def test_check_answers_ok_with_3_checked_cards(repo, catalog):
    ran = run(repo, "check", "--frontend", "web")
    expect_ok(ran)
    expect_field(ran, "cards", 3)
    expect_field(ran, "checked", 3)
    expect_field(ran, "unchecked", 0)


# --- check refuses bad-catalog (VR-019) ---------------------------------------------------------------------------

def edit(path, old, new):
    text = path.read_text(encoding="utf-8")
    expect_in(old, text, given(f"edit {path.name}"))
    path.write_text(text.replace(old, new), encoding="utf-8")
    note(f"{path.name}: {old!r} replaced by {new!r}")


def test_check_refuses_bad_catalog_for_a_missing_card_file_then_counts_the_unchecked_cards(repo, catalog):
    readme = catalog / "README.md"
    edit(readme, "| cards/button.html | component | checked | orders-list.png |",
         "| cards/button.html | component | unchecked | — |")
    edit(readme, "| cards/list-page.html | page | checked | orders-list.png |",
         "| cards/detail-page.html | page | unchecked | — |")
    ran = run(repo, "check", "--frontend", "web")
    expect_refusal(ran, "bad-catalog")
    expect_error_field(ran, "problems", ["card cards/detail-page.html: no such file in the catalog folder"])
    expect_error_reason_holds(ran, "cards/detail-page.html")
    shutil.copyfile(catalog / "cards" / "list-page.html", catalog / "cards" / "detail-page.html")
    note("cards/detail-page.html added as a copy of cards/list-page.html")
    ran = run(repo, "check", "--frontend", "web")
    expect_ok(ran)
    expect_field(ran, "cards", 3)
    expect_field(ran, "checked", 1)
    expect_field(ran, "unchecked", 2)


@pytest.mark.parametrize("old, new, words", [
    ("| cards/shell.html | shell | checked | shell.png |", "| cards/shell.html | widget | checked | shell.png |",
     "kind `widget`"),
    ("| cards/shell.html | shell | checked | shell.png |", "| cards/shell.html | shell | done | shell.png |",
     "state `done`"),
    ("| cards/shell.html | shell | checked | shell.png |", "| cards/shell.html | shell | checked | — |",
     "names no screenshot"),
    ("| cards/shell.html | shell | checked | shell.png |", "| ../shell.html | shell | checked | shell.png |",
     "not a file in the catalog folder"),
    ("| cards/button.html | component | checked | orders-list.png |",
     "| cards/shell.html | component | checked | orders-list.png |", "2 rows"),
    ("## Refresh", "## Later", "no section `## Refresh`"),
    ("## Scope", "## Range", "no section `## Scope`"),
])
def test_check_names_each_problem_of_the_format(repo, catalog, old, new, words):
    edit(catalog / "README.md", old, new)
    ran = run(repo, "check", "--frontend", "web")
    expect_refusal(ran, "bad-catalog")
    expect_any_problem(ran, words)


def test_check_refuses_bad_catalog_with_no_readme_no_tokens_or_no_card(repo, catalog):
    (catalog / "tokens.css").unlink()
    note("tokens.css removed")
    ran = run(repo, "check", "--frontend", "web")
    expect_refusal(ran, "bad-catalog")
    expect_error_field(ran, "problems", ["no tokens.css in the catalog folder"])
    (catalog / "README.md").unlink()
    note("README.md removed")
    ran = run(repo, "check", "--frontend", "web")
    expect_refusal(ran, "bad-catalog")
    expect_in("no README.md in the catalog folder", ran.answer["error"].get("problems", []), ran.about("problems"))


def test_check_refuses_a_cards_table_with_no_row(repo, catalog):
    readme = catalog / "README.md"
    text = readme.read_text(encoding="utf-8")
    kept = [line for line in text.splitlines() if not line.startswith("| cards/")]
    readme.write_text("\n".join(kept) + "\n", encoding="utf-8")
    note("README.md: every `| cards/` row removed")
    ran = run(repo, "check", "--frontend", "web")
    expect_refusal(ran, "bad-catalog")
    expect_error_field(ran, "problems", ["the Cards table has no row"])


# --- check refuses secrets and network-call (VR-021) ----------------------------------------------------------------

# Built at run time, so no committed file holds a key shape.
MADE_UP_KEY = "gh" + "p_" + "Made0Up" * 5


def put_made_up_key(path):
    """Replace the placeholder MADE_UP_KEY in `path` by the key; the note leaves the value out of the messages."""
    path.write_text(path.read_text(encoding="utf-8").replace("MADE_UP_KEY", MADE_UP_KEY), encoding="utf-8")
    note(f"{path.name}: MADE_UP_KEY replaced by a made-up github-token-shaped value")


def call_places(ran):
    return [(call.get("file"), call.get("line")) for call in ran.answer.get("error", {}).get("calls", [])]


def test_check_refuses_secrets_with_the_file_and_line(repo, catalog):
    edit(catalog / "cards" / "list-page.html", "<td>Made-up Buyer</td>", "<td>MADE_UP_KEY</td>")
    put_made_up_key(catalog / "cards" / "list-page.html")
    ran = run(repo, "check", "--frontend", "web")
    expect_refusal(ran, "secrets")
    expect_error_field(ran, "hits", [{"file": "cards/list-page.html", "line": 4, "shape": "github-token"}])
    expect_error_reason_holds(ran, "cards/list-page.html:4")
    expect_not_in(MADE_UP_KEY, json.dumps(ran.answer), f"{ran.given} (the whole answer)")


def test_check_refuses_network_call_with_the_file_and_line(repo, catalog):
    edit(catalog / "tokens.css", "  --font-body: system-ui, sans-serif;",
         "  --font-body: system-ui, sans-serif;\n  src: url('https://fonts.example/body.woff2');")
    ran = run(repo, "check", "--frontend", "web")
    expect_refusal(ran, "network-call")
    expect(call_places(ran), [("tokens.css", 9)], ran.about("(file, line) of each call"))
    expect_error_reason_holds(ran, "tokens.css:9")


def test_check_scans_the_readme_for_secrets_but_lets_it_name_the_calls_of_the_app(repo, catalog):
    edit(catalog / "README.md", "- App address: http://127.0.0.1:4999",
         "- App address: http://127.0.0.1:4999, which loads its rows with `fetch('/api/orders')`")
    expect_ok(run(repo, "check", "--frontend", "web"))
    edit(catalog / "README.md", "## Refresh", "## Refresh\n\nMADE_UP_KEY")
    put_made_up_key(catalog / "README.md")
    ran = run(repo, "check", "--frontend", "web")
    expect_refusal(ran, "secrets")
    hits = ran.answer.get("error", {}).get("hits") or [{}]
    expect(hits[0].get("file"), "README.md", ran.about("file of the first hit"))


def test_check_refuses_a_file_too_large_to_scan(repo, catalog):
    sys.path.insert(0, str(PLUGIN / "engine"))
    import notices
    (catalog / "cards" / "big.html").write_bytes(b"a" * (notices.MAX_SCAN_BYTES + 1))
    note(f"cards/big.html added with {notices.MAX_SCAN_BYTES + 1} bytes")
    ran = run(repo, "check", "--frontend", "web")
    expect_refusal(ran, "bad-catalog")
    expect_any_problem(ran, "cards/big.html")


def test_check_refuses_a_card_path_that_climbs_out_by_backslashes(repo, catalog):
    (catalog.parent / "out.html").write_text("<p>outside</p>\n", encoding="utf-8")
    note("design/out.html added outside the catalog folder")
    edit(catalog / "README.md", "| cards/shell.html | shell |", "| cards\\..\\..\\out.html | shell |")
    ran = run(repo, "check", "--frontend", "web")
    expect_refusal(ran, "bad-catalog")
    expect_any_problem(ran, "not a file in the catalog folder")


def test_check_refuses_network_call_in_a_card(repo, catalog):
    edit(catalog / "cards" / "shell.html", "<main id=\"main\"",
         "<img src=\"https://cdn.example/a.png\">\n  <main id=\"main\"")
    ran = run(repo, "check", "--frontend", "web")
    expect_refusal(ran, "network-call")
    expect(call_places(ran), [("cards/shell.html", 4)], ran.about("(file, line) of each call"))
