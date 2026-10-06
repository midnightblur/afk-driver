"""Setup's afk-python transaction, run against a stubbed command runner."""
from __future__ import annotations

import importlib.util
import io
import os
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = PLUGIN_ROOT / "skills" / "afk" / "setup" / "scripts" / "python_runtime.py"
spec = importlib.util.spec_from_file_location("python_runtime", SCRIPT)
pr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pr)
PINS = pr.pins()
FIND_BASH = pr.find_bash


class Machine:
    """Answers each command the way a healthy uv and launcher would, and records it."""

    def __init__(self, paths: dict, *, uv_version: str | None = None, fail: str | None = None,
                 reported: str | None = None):
        self.paths, self.calls = paths, []
        self.uv_version, self.fail = uv_version, fail
        self.reported = reported or f"{PINS['python']} {paths['launcher']}"

    def __call__(self, argv, env):
        self.calls.append((argv, dict(env)))
        line = argv if isinstance(argv, str) else " ".join(map(str, argv))
        if self.fail and self.fail in line:
            return 1, "error: simulated failure"
        if line.endswith("--version") and str(self.paths["uv"]) in line:
            return (0, f"uv {self.uv_version} (abc)") if self.uv_version else (127, "not found")
        if " sync " in line:
            self.paths["script"].parent.mkdir(parents=True, exist_ok=True)
            self.paths["script"].write_text("launcher", encoding="utf-8")
        if "afk-python -c" in line:
            return 0, self.reported
        return 0, ""

    def lines(self) -> list[str]:
        return [a if isinstance(a, str) else " ".join(map(str, a)) for a, _ in self.calls]


@pytest.fixture(autouse=True)
def windows_shells_anywhere(monkeypatch):
    # Windows-layout cases run on any host: no registry read, no Git Bash lookup.
    monkeypatch.setattr(pr, "fresh_path", lambda env, windows: env.get("PATH", ""))
    monkeypatch.setattr(pr, "find_bash", lambda: None)


def machine_env(tmp_path: Path) -> dict:
    return {"HOME": str(tmp_path / "home"), "LOCALAPPDATA": str(tmp_path / "local"),
            "PATH": os.environ.get("PATH", ""), "SHELL": "/bin/bash"}


def test_plan_names_the_pinned_steps_and_changes_nothing(tmp_path):
    env = dict(os.environ, LOCALAPPDATA=str(tmp_path / "local"), HOME=str(tmp_path / "home"),
               XDG_DATA_HOME=str(tmp_path / "data"), XDG_BIN_HOME=str(tmp_path / "bin"))
    done = subprocess.run([sys.executable, str(SCRIPT), "plan"], env=env, capture_output=True,
                          text=True, timeout=60)
    assert done.returncode == 0, done.stderr
    assert f"/download/{PINS['uv']}/uv-installer." in done.stdout
    assert f"python install {PINS['python']} --no-bin" in done.stdout
    assert "sync --project" in done.stdout and "--frozen --no-editable --compile-bytecode" in done.stdout
    assert "--extra test" not in done.stdout
    assert list(tmp_path.iterdir()) == []
    with_test = subprocess.run([sys.executable, str(SCRIPT), "plan", "--test"], env=env,
                               capture_output=True, text=True, timeout=60)
    assert "--extra test" in with_test.stdout


@pytest.mark.parametrize("windows", [True, False])
def test_layout_keeps_everything_under_one_private_home(tmp_path, windows):
    env = machine_env(tmp_path)
    paths = pr.layout(env, windows)
    if windows:
        assert paths["env"] == tmp_path / "local" / "afk" / "python"
        assert paths["launcher"] == tmp_path / "local" / "afk" / "bin" / "afk-python.exe"
        assert paths["script"] == paths["env"] / "Scripts" / "afk-python.exe"
    else:
        assert paths["env"] == tmp_path / "home" / ".local" / "share" / "afk" / "python"
        assert paths["launcher"] == tmp_path / "home" / ".local" / "bin" / "afk-python"
        xdg = pr.layout(dict(env, XDG_DATA_HOME=str(tmp_path / "d"), XDG_BIN_HOME=str(tmp_path / "b")), False)
        assert xdg["env"] == tmp_path / "d" / "afk" / "python" and xdg["bin"] == tmp_path / "b"


def test_install_runs_the_transaction_in_order_writes_the_stamp_and_probes(tmp_path):
    env = machine_env(tmp_path)
    paths = pr.layout(env, True)
    machine, out = Machine(paths), io.StringIO()
    code = pr.install(env, True, False, machine, out)
    assert code == 0, out.getvalue()
    lines = machine.lines()
    order = [next(i for i, l in enumerate(lines) if marker in l) for marker in
             ("uv-installer.ps1", "python install", " sync ", "tool update-shell", "afk-python -c")]
    assert order == sorted(order)
    installer_env = next(e for a, e in machine.calls if "uv-installer" in str(a))
    assert installer_env["UV_UNMANAGED_INSTALL"] == str(paths["uv"].parent)
    sync_env = next(e for a, e in machine.calls if "sync" in str(a))
    assert sync_env["UV_PROJECT_ENVIRONMENT"] == str(paths["env"])
    assert sync_env["UV_PYTHON_INSTALL_DIR"] == str(paths["pythons"])
    assert sync_env["UV_TOOL_BIN_DIR"] == str(paths["bin"])
    assert "VIRTUAL_ENV" not in sync_env
    assert paths["launcher"].read_text(encoding="utf-8") == "launcher"
    stamp = pr.read_stamp(paths)
    assert stamp == {"python": PINS["python"], "uv": PINS["uv"], "lock": PINS["lock"],
                     "extras": "", "launcher": str(paths["launcher"])}
    assert "Restart the harness" in out.getvalue()


def test_install_skips_the_uv_installer_when_the_pinned_uv_is_present(tmp_path):
    env = machine_env(tmp_path)
    machine = Machine(pr.layout(env, True), uv_version=PINS["uv"])
    assert pr.install(env, True, False, machine, io.StringIO()) == 0
    assert not any("uv-installer" in l for l in machine.lines())


@pytest.mark.parametrize("windows", [True, False])
def test_a_bin_directory_already_on_the_new_terminal_path_is_not_added_again(tmp_path, windows):
    if not windows and os.name == "nt":
        pytest.skip("the POSIX layout symlinks the launcher, which needs privileges here")
    env = machine_env(tmp_path)
    paths = pr.layout(env, windows)
    # Spelled the way PATH entries drift: case on Windows, a trailing separator anywhere.
    entry = str(paths["bin"]).upper() + "\\" if windows else str(paths["bin"]) + "/"
    env["PATH"] = (";" if windows else ":").join([entry, env["PATH"]])
    machine, out = Machine(paths), io.StringIO()
    assert pr.install(env, windows, False, machine, out) == 0, out.getvalue()
    assert "ok path already set" in out.getvalue()
    assert not any("update-shell" in l for l in machine.lines())


def test_a_failing_step_stops_the_transaction_without_a_stamp(tmp_path):
    env = machine_env(tmp_path)
    paths = pr.layout(env, True)
    machine, out = Machine(paths, fail=" sync "), io.StringIO()
    assert pr.install(env, True, False, machine, out) == 1
    assert "fail environment: error: simulated failure" in out.getvalue()
    assert not any("update-shell" in l for l in machine.lines())
    assert not paths["stamp"].exists()


def test_a_runtime_that_has_the_test_extra_keeps_it(tmp_path):
    env = machine_env(tmp_path)
    paths = pr.layout(env, True)
    paths["env"].mkdir(parents=True)
    paths["stamp"].write_text("extras=test\n", encoding="utf-8")
    machine = Machine(paths)
    assert pr.install(env, True, False, machine, io.StringIO()) == 0
    assert any(" sync " in l and l.endswith("--extra test") for l in machine.lines())
    assert any("import pytest" in l for l in machine.lines())


def stamped(tmp_path: Path, **override) -> tuple[dict, dict]:
    env = machine_env(tmp_path)
    paths = pr.layout(env, False)
    paths["env"].mkdir(parents=True)
    paths["launcher"].parent.mkdir(parents=True)
    paths["launcher"].write_text("", encoding="utf-8")
    values = {"python": PINS["python"], "uv": PINS["uv"], "lock": PINS["lock"], "extras": ""}
    values.update(override)
    paths["stamp"].write_text("".join(f"{k}={v}\n" for k, v in values.items()), encoding="utf-8")
    return env, paths


def test_check_passes_a_healthy_runtime_from_every_shell(tmp_path):
    env, paths = stamped(tmp_path)
    machine, out = Machine(paths), io.StringIO()
    assert pr.check(env, False, False, machine, out) == 0, out.getvalue()
    probes = [l for l in machine.lines() if "afk-python -c" in l]
    assert len(probes) == 2
    for module in PINS["imports"]:
        assert all(f"import {module};" in l for l in probes)
    assert all(e.get("AFK_PYTHON") is None for a, e in machine.calls)


@pytest.mark.parametrize("override, reported, expected", [
    ({"lock": "0" * 64}, None, "fail lock"),
    ({"python": "3.13.0"}, None, "fail stamp: want Python"),
    ({}, "3.12.1 /x/afk-python", "runs Python 3.12.1"),
    ({}, f"{PINS['python']} -", "did not export AFK_PYTHON"),
])
def test_check_names_each_kind_of_drift(tmp_path, override, reported, expected):
    env, paths = stamped(tmp_path, **override)
    machine, out = Machine(paths, reported=reported), io.StringIO()
    assert pr.check(env, False, False, machine, out) == 1
    assert expected in out.getvalue()


def test_check_fails_when_the_command_does_not_resolve(tmp_path):
    env, paths = stamped(tmp_path)
    paths["launcher"].unlink()

    def missing(argv, env):
        return 127, "sh: afk-python: not found"

    out = io.StringIO()
    assert pr.check(env, False, False, missing, out) == 1
    assert "fail launcher" in out.getvalue() and "afk-python: not found" in out.getvalue()


NOTICE = "AFK will switch to afk-python in the next release; run /afk:setup"


def session_notice(tmp_path: Path, *, command: bool, stamp: str | None) -> str:
    bash = FIND_BASH()
    if not bash:
        pytest.skip("no POSIX shell")
    root = tmp_path / "plugin"
    (root / "runtime").mkdir(parents=True)
    (root / "runtime" / "pyproject.toml").write_bytes((PLUGIN_ROOT / "runtime" / "pyproject.toml").read_bytes())
    data = tmp_path / "data"
    if stamp is not None:
        (data / "afk" / "python").mkdir(parents=True)
        # A CRLF stamp: the notice must read either line ending.
        (data / "afk" / "python" / "AFK-RUNTIME").write_bytes(f"python={stamp}\r\n".encode())
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    if command:
        launcher = bin_dir / "afk-python"
        launcher.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        launcher.chmod(0o755)
    shell_path = subprocess.run([bash, "-c", 'cygpath -u "$1" 2>/dev/null || printf %s "$1"', "_", str(bin_dir)],
                                capture_output=True, text=True).stdout.strip()
    env = dict(os.environ, AFK_PLUGIN_ROOT=str(root), LOCALAPPDATA=str(data), XDG_DATA_HOME=str(data))
    script = PLUGIN_ROOT / "hooks" / "update-notice.sh"
    done = subprocess.run([bash, "-c", f'PATH="{shell_path}:/usr/bin:/bin"; . "$0"', str(script)],
                          env=env, capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr
    return done.stdout


@pytest.mark.parametrize("command, stamp, shown", [
    (False, None, True),
    (True, None, True),
    (True, "3.13.1", True),
    (True, PINS["python"], False),
])
def test_the_session_notice_shows_until_the_pinned_runtime_resolves(tmp_path, command, stamp, shown):
    out = session_notice(tmp_path, command=command, stamp=stamp)
    assert (NOTICE in out) is shown
