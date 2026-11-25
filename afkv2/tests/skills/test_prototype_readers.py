"""The 2 readers of PROTOTYPE.md: propose-solution and propose-verification (SDD §14; ADR-0004 design; ticket 207
VR-023, VR-024, VR-025, VR-026).

The start tests run each script through its command line in a scratch git repository. PROTOTYPE.md is an optional
input: a spec folder without it runs as today, with no refusal.
"""

import json
import subprocess
import sys
from pathlib import Path

from test_propose_solution import World
from test_propose_verification import SCRIPT as VERIFICATION_FILES, TICKET, git, repo  # noqa: F401

PROTOTYPE = "# Prototype — sample\n\n> Frontend: web\n> Fidelity: source-only\n> Date: 2026-11-25\n"


def _git_init(root):
    git(root, "init", "-q", "-b", "main")


# --- VR-023 (PRD AC-027, AC-029): design_files.py start answers prototype and prototype_exists

def test_design_start_answers_the_prototype_path_with_and_without_the_file(tmp_path):
    world = World(tmp_path)
    _git_init(world.repo)
    without = world.run("start", ticket_key="PROJ-1")
    assert without["ok"] is True and without["prototype_exists"] is False
    assert Path(world.repo / without["prototype"]).resolve() == (world.spec / "PROTOTYPE.md").resolve()
    (world.spec / "PROTOTYPE.md").write_text(PROTOTYPE, "utf-8")
    present = world.run("start", ticket_key="PROJ-1")
    assert present["ok"] is True and present["prototype_exists"] is True
    assert present["prototype"] == without["prototype"]


# --- VR-024 (PRD AC-028, AC-029): verification_files.py start answers prototype and prototype_exists

def _verification_start(root):
    done = subprocess.run([sys.executable, str(VERIFICATION_FILES), "start", "--ticket", TICKET], cwd=root,
                          capture_output=True, text=True, encoding="utf-8", stdin=subprocess.DEVNULL, timeout=120)
    return done.returncode, json.loads(done.stdout)


def test_verification_start_answers_the_prototype_path_with_and_without_the_file(repo):
    spec = (repo / "docs" / TICKET).resolve()
    code, without = _verification_start(repo)
    assert code == 0 and without["ok"] is True, without
    assert without["prototype_exists"] is False and "PROTOTYPE.md" not in json.dumps(without.get("missing", []))
    assert Path(repo / without["prototype"]).resolve() == spec / "PROTOTYPE.md"
    (spec / "PROTOTYPE.md").write_text(PROTOTYPE, "utf-8")
    code, present = _verification_start(repo)
    assert code == 0 and present["ok"] is True and present["prototype_exists"] is True
    assert present["prototype"] == without["prototype"]
