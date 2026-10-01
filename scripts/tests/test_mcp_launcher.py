"""The `.mcp.json` launcher picks the right installed copy when it must find one.

With no root argument or variable, the launcher searches the user's home. These
tests run the launcher text exactly as a harness would, under a fake home, and
read which copy answered. Both registrations carry the same launcher, so each
case runs against both files.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CLAUDE, CODEX = ".mcp.json", ".mcp.codex.json"
ROOT_ENV = ("AFK_PLUGIN_ROOT", "CLAUDE_PLUGIN_ROOT", "PLUGIN_ROOT")


def launcher(registration: str) -> str:
    data = json.loads((ROOT / registration).read_text(encoding="utf-8"))
    return data["mcpServers"]["tracker"]["args"][1]


def install(home: Path, harness: str, version: str, orphaned: bool = False) -> Path:
    base = home / harness / "plugins" / "cache" / "afk-toolkit" / "afk" / version
    server = base / "mcp-servers" / "tracker" / "server.py"
    server.parent.mkdir(parents=True)
    server.write_text(f'print("RAN {harness}/{version}")\n', encoding="utf-8")
    if orphaned:
        (base / ".orphaned_at").write_text("1", encoding="utf-8")
    return base


def ran(registration: str, home: Path, *pinned: Path) -> str:
    env = {k: v for k, v in os.environ.items() if k not in ROOT_ENV}
    env.update(HOME=str(home), USERPROFILE=str(home))
    done = subprocess.run([sys.executable, "-c", launcher(registration), *map(str, pinned)], cwd=home,
                          env=env, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


@pytest.fixture
def home(tmp_path):
    return tmp_path / "home"


@pytest.mark.parametrize("registration,own", [(CLAUDE, ".claude"), (CODEX, ".codex")])
def test_a_version_compares_as_numbers_not_text(home, registration, own):
    install(home, own, "1.9.0")
    install(home, own, "1.10.0")
    assert ran(registration, home) == f"RAN {own}/1.10.0"


@pytest.mark.parametrize("registration,own", [(CLAUDE, ".claude"), (CODEX, ".codex")])
def test_an_orphaned_copy_is_never_chosen(home, registration, own):
    install(home, own, "1.10.0", orphaned=True)
    install(home, own, "1.9.0")
    assert ran(registration, home) == f"RAN {own}/1.9.0"


def test_the_claude_registration_prefers_the_claude_cache(home):
    install(home, ".claude", "1.9.0")
    install(home, ".codex", "2.0.0")
    assert ran(CLAUDE, home) == "RAN .claude/1.9.0"


def test_the_codex_registration_prefers_the_codex_cache(home):
    install(home, ".claude", "9.0.0")
    install(home, ".codex", "1.0.0")
    assert ran(CODEX, home) == "RAN .codex/1.0.0"


@pytest.mark.parametrize("registration,other", [(CLAUDE, ".codex"), (CODEX, ".claude")])
def test_the_other_harness_is_still_a_fallback(home, registration, other):
    install(home, other, "1.0.0")
    assert ran(registration, home) == f"RAN {other}/1.0.0"


def test_the_two_registrations_differ_only_by_their_harness():
    claude, codex = launcher(CLAUDE), launcher(CODEX)
    assert claude.replace('own = ".claude"', 'own = "<OWN>"') == \
        codex.replace('own = ".codex"', 'own = "<OWN>"')


@pytest.mark.parametrize("registration,own", [(CLAUDE, ".claude"), (CODEX, ".codex")])
def test_a_pinned_orphaned_root_yields_to_a_live_install(home, registration, own):
    old = install(home, own, "1.9.0", orphaned=True)
    install(home, own, "1.10.0")
    assert ran(registration, home, old) == f"RAN {own}/1.10.0"


@pytest.mark.parametrize("registration,own", [(CLAUDE, ".claude"), (CODEX, ".codex")])
def test_a_pinned_orphaned_root_still_runs_when_nothing_else_exists(home, registration, own):
    old = install(home, own, "1.9.0", orphaned=True)
    assert ran(registration, home, old) == f"RAN {own}/1.9.0"


@pytest.mark.parametrize("registration,own", [(CLAUDE, ".claude"), (CODEX, ".codex")])
def test_a_pinned_live_root_stays_first(home, registration, own):
    pinned = install(home, own, "1.9.0")
    install(home, own, "1.10.0")
    assert ran(registration, home, pinned) == f"RAN {own}/1.9.0"
