"""The installed `afk-python` is the pinned CPython running in AFK's private environment.

Runs against this machine's runtime, at the layout setup installs to; skips when
setup has not installed it.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "skills" / "afk" / "setup" / "scripts" / "python_runtime.py"
spec = importlib.util.spec_from_file_location("python_runtime", SCRIPT)
pr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pr)
PINS = pr.pins()
PATHS = pr.layout(os.environ, os.name == "nt")

pytestmark = pytest.mark.skipif(not PATHS["launcher"].exists(), reason="afk-python is not installed here")

REPORT = ("import json, os, sys; print(json.dumps({'prefix': sys.prefix, 'executable': sys.executable, "
          "'version': sys.version.split()[0], 'afk_python': os.environ.get('AFK_PYTHON'), "
          "'argv': sys.argv, 'path0': sys.path[0]}))")


def afk_python(*args: str) -> dict:
    env = {k: v for k, v in os.environ.items() if k not in ("AFK_PYTHON", "PYTHONPATH", "PYTHONHOME")}
    done = subprocess.run([str(PATHS["launcher"]), *args], env=env, capture_output=True, text=True,
                          timeout=60)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def same(a: str, b: Path) -> bool:
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def test_the_entry_is_the_pinned_python_in_the_private_environment():
    seen = afk_python("-c", REPORT, "one")
    assert seen["version"] == PINS["python"]
    assert same(seen["prefix"], PATHS["env"])
    assert same(seen["executable"], PATHS["launcher"])
    # Plain CPython argument handling: nothing between the command and the interpreter.
    assert seen["argv"] == ["-c", "one"] and seen["path0"] == ""


def test_afk_python_names_the_entry_for_children():
    seen = afk_python("-c", REPORT)
    assert seen["afk_python"] == seen["executable"]
    child = afk_python("-c", "import os, subprocess, sys; print(subprocess.run([os.environ['AFK_PYTHON'], "
                             f"'-c', {REPORT!r}], capture_output=True, text=True).stdout)")
    assert same(child["executable"], PATHS["launcher"]) and same(child["prefix"], PATHS["env"])


def test_minus_s_skips_the_afk_python_line_but_keeps_the_environment():
    seen = afk_python("-S", "-c", REPORT)
    assert seen["afk_python"] is None and same(seen["prefix"], PATHS["env"])


def test_every_required_module_imports():
    modules = PINS["imports"] + (PINS["test_imports"] if "test" in pr.read_stamp(PATHS).get("extras", "") else [])
    afk_python("-c", "".join(f"import {m}; " for m in modules) + "print('{}')")


def test_the_path_directory_resolves_only_afk_python():
    assert same(shutil.which(pr.COMMAND, path=str(PATHS["bin"])), PATHS["launcher"])
    assert all(entry.name.startswith(pr.COMMAND) for entry in PATHS["bin"].iterdir())
