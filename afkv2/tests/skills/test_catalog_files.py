"""Tests for catalog_files.py: start, add-frontend and check (SDD §3, §4; ticket 207 VR-018 to VR-021; decision D-8).

A throwaway git repository holds the config and the catalog folder; each verb runs through its command line. No
live app or browser runs here.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[2]
SCRIPT = PLUGIN / "skills" / "design-system" / "scripts" / "catalog_files.py"
CONFIG_READER = PLUGIN / "scripts" / "afkv2_config.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "catalog"


def run(cwd, *args):
    done = subprocess.run([sys.executable, str(SCRIPT), *args], cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", stdin=subprocess.DEVNULL)
    return done.returncode, json.loads(done.stdout)


def read_config(cwd):
    done = subprocess.run([sys.executable, str(CONFIG_READER), "read"], cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", stdin=subprocess.DEVNULL)
    return json.loads(done.stdout)


def git(repo, *args):
    done = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


def set_config(repo, **values):
    config = {"spec_folder": "docs", **values}
    (repo / ".afkv2" / "config.json").write_text(json.dumps(config), encoding="utf-8")


WEB = {"name": "web", "source": "frontend/web", "catalog": "design/web"}


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    (root / ".afkv2").mkdir(parents=True)
    git(root, "init", "-q", "-b", "main")
    set_config(root)
    (root / "frontend" / "web").mkdir(parents=True)
    return root


# --- add-frontend (VR-020) -----------------------------------------------------------------------------------------

def test_add_frontend_writes_the_entry_and_the_config_read_answers_it(repo):
    code, answer = run(repo, "add-frontend", "--name", "web", "--source", "frontend/web", "--catalog", "design/web")
    assert code == 0, answer
    assert answer["entry"] == WEB
    assert read_config(repo)["frontends"] == [WEB]
    assert json.loads((repo / ".afkv2" / "config.json").read_text(encoding="utf-8"))["spec_folder"] == "docs"


@pytest.mark.parametrize("name, source, catalog, words", [
    ("web", "frontend/web", "design/other", "already the name"),
    ("shop", "frontend/web", "design/web", "already the catalog"),
    ("shop", "../outside", "design/shop", "inside the repository"),
    ("shop", "frontend/web", "../outside", "inside the repository"),
    ("shop", "frontend/none", "design/shop", "no folder"),
    ("Shop", "frontend/web", "design/shop", "lower case"),
])
def test_add_frontend_refuses_bad_value_and_leaves_the_config_unchanged(repo, name, source, catalog, words):
    assert run(repo, "add-frontend", "--name", "web", "--source", "frontend/web", "--catalog", "design/web")[0] == 0
    before = (repo / ".afkv2" / "config.json").read_bytes()
    code, answer = run(repo, "add-frontend", "--name", name, "--source", source, "--catalog", catalog)
    assert code == 1 and answer["error"]["code"] == "bad-value", answer
    assert words in answer["error"]["reason"]
    assert (repo / ".afkv2" / "config.json").read_bytes() == before


def test_add_frontend_refuses_an_absolute_source_outside_the_repository(repo, tmp_path):
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    before = (repo / ".afkv2" / "config.json").read_bytes()
    code, answer = run(repo, "add-frontend", "--name", "web", "--source", str(outside), "--catalog", "design/web")
    assert code == 1 and answer["error"]["code"] == "bad-value"
    assert (repo / ".afkv2" / "config.json").read_bytes() == before


def test_add_frontend_stores_posix_paths_relative_to_the_repository(repo):
    code, answer = run(repo, "add-frontend", "--name", "web", "--source", "frontend/web/", "--catalog", "./design/web")
    assert code == 0, answer
    assert read_config(repo)["frontends"] == [WEB]


# --- start and check on a whole catalog (VR-018) ----------------------------------------------------------------

ADMIN = {"name": "admin", "source": "frontend/admin", "catalog": "design/admin"}
LIVE = {"start": "python -m http.server 4999", "address": "http://127.0.0.1:4999"}


@pytest.fixture
def catalog(repo):
    """The repository with the frontend web and its catalog of tokens.css and 3 checked cards."""
    set_config(repo, frontends=[WEB])
    shutil.copytree(FIXTURES, repo / "design" / "web")
    return repo / "design" / "web"


def test_start_answers_the_frontend_its_catalog_folder_and_the_cards(repo, catalog):
    code, answer = run(repo, "start", "--frontend", "web")
    assert code == 0, answer
    assert answer["frontend"] == WEB and answer["catalog_dir"] == catalog.resolve().as_posix()
    assert answer["catalog_exists"] is True and answer["live"] is None
    assert [card["file"] for card in answer["cards"]] == ["cards/shell.html", "cards/button.html", "cards/list-page.html"]
    assert answer["cards"][0] == {"file": "cards/shell.html", "kind": "shell", "state": "checked",
                                  "screenshot": "shell.png"}


def test_start_with_no_catalog_answers_no_cards_and_the_live_block(repo):
    set_config(repo, frontends=[WEB], live=LIVE)
    code, answer = run(repo, "start")
    assert code == 0, answer
    assert answer["catalog_exists"] is False and answer["cards"] == []
    assert answer["live"]["address"] == LIVE["address"]


def test_start_refuses_no_frontend_and_pick_frontend(repo):
    code, answer = run(repo, "start")
    assert code == 1 and answer["error"]["code"] == "no-frontend"
    assert "catalog_files.py add-frontend" in answer["error"]["reason"]
    set_config(repo, frontends=[WEB, ADMIN])
    code, answer = run(repo, "start")
    assert code == 1 and answer["error"]["code"] == "pick-frontend" and answer["error"]["names"] == ["web", "admin"]


def test_check_answers_ok_with_3_checked_cards(repo, catalog):
    code, answer = run(repo, "check", "--frontend", "web")
    assert code == 0, answer
    assert answer["cards"] == 3 and answer["checked"] == 3 and answer["unchecked"] == 0


# --- check refuses bad-catalog (VR-019) ---------------------------------------------------------------------------

def edit(path, old, new):
    text = path.read_text(encoding="utf-8")
    assert old in text, old
    path.write_text(text.replace(old, new), encoding="utf-8")


def test_check_refuses_bad_catalog_for_a_missing_card_file_then_counts_the_unchecked_cards(repo, catalog):
    readme = catalog / "README.md"
    edit(readme, "| cards/button.html | component | checked | orders-list.png |",
         "| cards/button.html | component | unchecked | — |")
    edit(readme, "| cards/list-page.html | page | checked | orders-list.png |",
         "| cards/detail-page.html | page | unchecked | — |")
    code, answer = run(repo, "check", "--frontend", "web")
    assert code == 1 and answer["error"]["code"] == "bad-catalog", answer
    assert answer["error"]["problems"] == ["card cards/detail-page.html: no such file in the catalog folder"]
    assert "cards/detail-page.html" in answer["error"]["reason"]
    shutil.copyfile(catalog / "cards" / "list-page.html", catalog / "cards" / "detail-page.html")
    code, answer = run(repo, "check", "--frontend", "web")
    assert code == 0, answer
    assert answer["cards"] == 3 and answer["checked"] == 1 and answer["unchecked"] == 2


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
    code, answer = run(repo, "check", "--frontend", "web")
    assert code == 1 and answer["error"]["code"] == "bad-catalog", answer
    assert any(words in problem for problem in answer["error"]["problems"]), answer["error"]["problems"]


def test_check_refuses_bad_catalog_with_no_readme_no_tokens_or_no_card(repo, catalog):
    (catalog / "tokens.css").unlink()
    code, answer = run(repo, "check", "--frontend", "web")
    assert code == 1 and answer["error"]["problems"] == ["no tokens.css in the catalog folder"]
    (catalog / "README.md").unlink()
    code, answer = run(repo, "check", "--frontend", "web")
    assert code == 1 and answer["error"]["code"] == "bad-catalog"
    assert "no README.md in the catalog folder" in answer["error"]["problems"]


def test_check_refuses_a_cards_table_with_no_row(repo, catalog):
    readme = catalog / "README.md"
    text = readme.read_text(encoding="utf-8")
    kept = [line for line in text.splitlines() if not line.startswith("| cards/")]
    readme.write_text("\n".join(kept) + "\n", encoding="utf-8")
    code, answer = run(repo, "check", "--frontend", "web")
    assert code == 1 and answer["error"]["problems"] == ["the Cards table has no row"]


# --- check refuses secrets and network-call (VR-021) ----------------------------------------------------------------

# Built at run time, so no committed file holds a key shape.
MADE_UP_KEY = "gh" + "p_" + "Made0Up" * 5


def test_check_refuses_secrets_with_the_file_and_line(repo, catalog):
    edit(catalog / "cards" / "list-page.html", "<td>Made-up Buyer</td>", f"<td>{MADE_UP_KEY}</td>")
    code, answer = run(repo, "check", "--frontend", "web")
    assert code == 1 and answer["error"]["code"] == "secrets", answer
    assert answer["error"]["hits"] == [{"file": "cards/list-page.html", "line": 4, "shape": "github-token"}]
    assert "cards/list-page.html:4" in answer["error"]["reason"] and MADE_UP_KEY not in json.dumps(answer)


def test_check_refuses_network_call_with_the_file_and_line(repo, catalog):
    edit(catalog / "tokens.css", "  --font-body: system-ui, sans-serif;",
         "  --font-body: system-ui, sans-serif;\n  src: url('https://fonts.example/body.woff2');")
    code, answer = run(repo, "check", "--frontend", "web")
    assert code == 1 and answer["error"]["code"] == "network-call", answer
    assert [(call["file"], call["line"]) for call in answer["error"]["calls"]] == [("tokens.css", 9)]
    assert "tokens.css:9" in answer["error"]["reason"]


def test_check_scans_the_readme_for_secrets_but_lets_it_name_the_calls_of_the_app(repo, catalog):
    edit(catalog / "README.md", "- App address: http://127.0.0.1:4999",
         "- App address: http://127.0.0.1:4999, which loads its rows with `fetch('/api/orders')`")
    assert run(repo, "check", "--frontend", "web")[0] == 0
    edit(catalog / "README.md", "## Refresh", f"## Refresh\n\n{MADE_UP_KEY}")
    code, answer = run(repo, "check", "--frontend", "web")
    assert code == 1 and answer["error"]["code"] == "secrets"
    assert answer["error"]["hits"][0]["file"] == "README.md"


def test_check_refuses_a_file_too_large_to_scan(repo, catalog):
    sys.path.insert(0, str(PLUGIN / "engine"))
    import notices
    (catalog / "cards" / "big.html").write_bytes(b"a" * (notices.MAX_SCAN_BYTES + 1))
    code, answer = run(repo, "check", "--frontend", "web")
    assert code == 1 and answer["error"]["code"] == "bad-catalog"
    assert any("cards/big.html" in problem for problem in answer["error"]["problems"])
