"""provider.sh finds its own folder, and so its adapters, however its path is spelled."""
from __future__ import annotations

import importlib.util
import os
import subprocess
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
LIBRARY = PLUGIN_ROOT / "hooks" / "lib" / "provider.sh"
_spec = importlib.util.spec_from_file_location("afk_run_hook", PLUGIN_ROOT / "hooks" / "run-hook.py")
_launcher = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_launcher)
BASH = _launcher.hook_bash()

pytestmark = pytest.mark.skipif(BASH is None, reason="no POSIX shell")


def sourced(spelling: str, cwd: Path) -> list[str]:
    done = subprocess.run([str(BASH), "-c", '. "$1" && printf "%s\\n" "$AFK_PROVIDER_NAMES"', "_", spelling],
                          capture_output=True, text=True, cwd=cwd, env=_launcher.shell_env(BASH), timeout=60)
    assert done.returncode == 0, done.stderr
    return done.stdout.split()


EXPECTED = sorted(p.stem for p in (LIBRARY.parent / "providers").glob("*.sh"))


@pytest.mark.parametrize("form", ["posix", "relative", "bare"])
def test_every_spelling_finds_the_adapters(form):
    spelling, cwd = {
        "posix": (LIBRARY.as_posix(), PLUGIN_ROOT),
        "relative": ("hooks/lib/provider.sh", PLUGIN_ROOT),
        "bare": ("./provider.sh", LIBRARY.parent),
    }[form]
    assert sorted(sourced(spelling, cwd)) == EXPECTED


@pytest.mark.skipif(os.name != "nt", reason="a backslash is a separator only on Windows")
def test_an_all_backslash_windows_path_finds_the_adapters():
    assert "/" not in str(LIBRARY)
    assert sorted(sourced(str(LIBRARY), PLUGIN_ROOT)) == EXPECTED
