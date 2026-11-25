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
