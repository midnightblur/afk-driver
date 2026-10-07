"""`runtime/uv.lock` must be exactly the lock of `runtime/pyproject.toml`.

Setup syncs the private environment frozen from the lock, so a dependency
added to the project but not re-locked would never be installed.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

tomllib = pytest.importorskip("tomllib")

RUNTIME = Path(__file__).resolve().parents[2] / "runtime"
PROJECT = tomllib.loads((RUNTIME / "pyproject.toml").read_text(encoding="utf-8"))
LOCK = tomllib.loads((RUNTIME / "uv.lock").read_text(encoding="utf-8"))


def norm(name: str) -> str:
    return name.lower().replace("_", "-").replace(".", "-")


def split(requirement: str) -> tuple[str, str]:
    name = requirement
    for i, ch in enumerate(requirement):
        if ch in "<>=!~;[ ":
            name = requirement[:i]
            break
    return norm(name), requirement[len(name):].replace(" ", "")


def own_package() -> dict:
    return next(p for p in LOCK["package"] if p["name"] == PROJECT["project"]["name"])


def test_the_lock_records_exactly_the_declared_requirements():
    declared = {split(r) for r in PROJECT["project"]["dependencies"]}
    for extra, reqs in PROJECT["project"].get("optional-dependencies", {}).items():
        declared |= {(n, f"{s};extra=='{extra}'") for n, s in map(split, reqs)}
    locked = {(norm(r["name"]), r.get("specifier", "") + (f";{r['marker']}".replace(" ", "")
                                                          if "marker" in r else ""))
              for r in own_package()["metadata"]["requires-dist"]}
    assert locked == declared


def test_the_lock_targets_the_pinned_python():
    assert LOCK["requires-python"] == PROJECT["project"]["requires-python"]
    assert PROJECT["project"]["requires-python"].startswith("==")


def test_every_locked_distribution_is_pinned_and_hashed():
    for package in LOCK["package"]:
        if package["name"] == PROJECT["project"]["name"]:
            continue
        assert package.get("version"), package["name"]
        files = package.get("wheels", []) + ([package["sdist"]] if "sdist" in package else [])
        assert files, f"{package['name']} has no artifact"
        for artifact in files:
            assert artifact.get("hash", "").startswith("sha256:"), package["name"]


def test_every_dependency_names_the_module_setup_probes():
    imports = PROJECT["tool"]["afk-runtime"]["imports"]
    test_imports = PROJECT["tool"]["afk-runtime"]["test-imports"]
    assert set(imports) == {split(r)[0] for r in PROJECT["project"]["dependencies"]}
    assert set(test_imports) == {split(r)[0] for r in PROJECT["project"]["optional-dependencies"]["test"]}


def test_uv_agrees_the_lock_is_current():
    uv = shutil.which("uv")
    if not uv:
        pytest.skip("uv is not on PATH")
    pinned = PROJECT["tool"]["uv"]["required-version"].lstrip("=")
    version = subprocess.run([uv, "--version"], capture_output=True, text=True).stdout.split()
    if version[1:2] != [pinned]:
        pytest.skip(f"uv {pinned} is the pin; found {' '.join(version)}")
    done = subprocess.run([uv, "lock", "--check", "--offline", "--project", str(RUNTIME)],
                          capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stderr
