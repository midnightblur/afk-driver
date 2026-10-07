"""The zero-Python setup bootstrap: bootstrap.sh against stub uv/curl, bootstrap.ps1 in plan mode."""
from __future__ import annotations

import importlib.util
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = PLUGIN_ROOT / "skills" / "afk" / "setup" / "scripts"
SH, PS1 = SCRIPTS / "bootstrap.sh", SCRIPTS / "bootstrap.ps1"
spec = importlib.util.spec_from_file_location("python_runtime", SCRIPTS / "python_runtime.py")
pr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pr)
PINS = pr.pins()
SHELL = shutil.which("sh") or shutil.which("bash")

STUB_UV = """#!/bin/sh
printf '%s\\n' "$*" >> "$LOG"
env | grep -E '^(UV_|INSTALLER_|CARGO_HOME=)' | sort >> "$LOG.env"
case "$1" in --version) echo "uv {version} (stub)" ;; run) exit "${{RUN_RC:-0}}" ;; esac
exit 0
"""
STUB_CURL = """#!/bin/sh
printf 'curl %s\\n' "$*" >> "$LOG"
cat <<'EOF'
mkdir -p "$UV_UNMANAGED_INSTALL"
echo "installer $UV_UNMANAGED_INSTALL" >> "$LOG"
cp "$STUB_UV_SOURCE" "$UV_UNMANAGED_INSTALL/uv"
chmod +x "$UV_UNMANAGED_INSTALL/uv"
EOF
"""


def posix(path: Path) -> str:
    """A path the stub shell reads: `C:\\x` becomes `/c/x` under Git Bash."""
    text = path.as_posix()
    return f"/{text[0].lower()}{text[2:]}" if os.name == "nt" and re.match(r"^[A-Za-z]:", text) else text


@pytest.fixture
def machine(tmp_path):
    if SHELL is None:
        pytest.skip("no POSIX shell")
    data, bin_dir = tmp_path / "data", tmp_path / "bin"
    bin_dir.mkdir()
    stub = tmp_path / "uv-stub"
    stub.write_text(STUB_UV.format(version=PINS["uv"]), encoding="utf-8", newline="\n")
    (bin_dir / "curl").write_text(STUB_CURL, encoding="utf-8", newline="\n")
    for script in (stub, bin_dir / "curl"):
        script.chmod(0o755)
    env = {k: v for k, v in os.environ.items() if not k.startswith("UV_")}
    env.update(XDG_DATA_HOME=posix(data), LOG=posix(tmp_path / "log"), STUB_UV_SOURCE=posix(stub),
               PATH=str(bin_dir) + os.pathsep + env.get("PATH", ""))
    return tmp_path, data / "afk", env, stub


def run(env, *args):
    return subprocess.run([SHELL, posix(SH), *args], env=env, capture_output=True, text=True, timeout=60)


def calls(tmp_path):
    return (tmp_path / "log").read_text(encoding="utf-8").splitlines()


def test_present_uv_installs_the_pinned_python_then_runs_the_installer_under_it(machine):
    tmp_path, base, env, stub = machine
    (base / "uv").mkdir(parents=True)
    shutil.copy(stub, base / "uv" / "uv")
    done = run(env, "install", "--test")
    assert done.returncode == 0, done.stderr
    log = calls(tmp_path)
    assert not any(line.startswith("curl") for line in log)
    assert log[1] == f"python install {PINS['python']} --no-bin"
    assert log[2] == (f"run --no-project --managed-python --no-python-downloads --python {PINS['python']} "
                      f"{posix(SCRIPTS)}/python_runtime.py install --test")


def test_missing_uv_fetches_the_pinned_installer_into_the_private_dir(machine):
    tmp_path, base, env, _stub = machine
    done = run(env, "plan")
    assert done.returncode == 0, done.stderr
    log = calls(tmp_path)
    url = pr.INSTALLER.format(version=PINS["uv"], ext="sh")
    assert log[0] == f"curl --proto =https --tlsv1.2 -LsSf {url}"
    assert log[1] == f"installer {posix(base / 'uv')}"
    assert log[-1].startswith("run --no-project") and log[-1].endswith("python_runtime.py plan")


def test_a_wrong_uv_version_is_replaced(machine):
    tmp_path, base, env, stub = machine
    (base / "uv").mkdir(parents=True)
    (base / "uv" / "uv").write_text("#!/bin/sh\necho 'uv 0.0.1'\n", encoding="utf-8", newline="\n")
    (base / "uv" / "uv").chmod(0o755)
    assert run(env, "check").returncode == 0
    assert calls(tmp_path)[0].startswith("curl ")


def test_settings_that_move_a_download_are_dropped_and_transport_kept(machine):
    tmp_path, base, env, stub = machine
    (base / "uv").mkdir(parents=True)
    shutil.copy(stub, base / "uv" / "uv")
    env.update(UV_INDEX_URL="https://elsewhere.invalid", UV_PYTHON_INSTALL_DIR="/elsewhere",
               UV_HTTP_TIMEOUT="90", INSTALLER_DOWNLOAD_URL="https://elsewhere.invalid", CARGO_HOME="/x")
    assert run(env, "plan").returncode == 0
    seen = set((tmp_path / "log.env").read_text(encoding="utf-8").splitlines())
    assert "UV_HTTP_TIMEOUT=90" in seen and "UV_NO_CONFIG=1" in seen
    assert f"UV_PYTHON_INSTALL_DIR={posix(base / 'pythons')}" in seen
    assert f"UV_CACHE_DIR={posix(base / 'cache')}" in seen
    assert not any(line.startswith(("UV_INDEX_URL", "INSTALLER_", "CARGO_HOME")) for line in seen)


def test_the_installer_exit_code_is_the_bootstrap_exit_code(machine):
    tmp_path, base, env, stub = machine
    (base / "uv").mkdir(parents=True)
    shutil.copy(stub, base / "uv" / "uv")
    env["RUN_RC"] = "3"
    assert run(env, "install").returncode == 3


def test_missing_pins_stop_with_a_tree_error(tmp_path):
    if SHELL is None:
        pytest.skip("no POSIX shell")
    copy = tmp_path / "skills" / "afk" / "setup" / "scripts"
    copy.mkdir(parents=True)
    shutil.copy(SH, copy / "bootstrap.sh")
    (tmp_path / "runtime").mkdir()
    (tmp_path / "runtime" / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    done = subprocess.run([SHELL, posix(copy / "bootstrap.sh"), "plan"], capture_output=True, text=True)
    assert done.returncode == 2 and "pins not found" in done.stderr


@pytest.mark.parametrize("script", [SH, PS1], ids=["sh", "ps1"])
def test_both_bootstraps_drop_exactly_the_settings_python_runtime_drops(script):
    text = script.read_text(encoding="utf-8")
    assert set(pr.UV_KEEP) == set(re.findall(r"\bUV_[A-Z_]+\b", text)) - {
        "UV_PYTHON_INSTALL_DIR", "UV_CACHE_DIR", "UV_NO_CONFIG", "UV_UNMANAGED_INSTALL", "UV_KEEP"}
    for name in pr.INSTALLER_OVERRIDES:
        assert name in text
    assert pr.INSTALLER.split("{version}")[0] in text


@pytest.mark.skipif(os.name != "nt", reason="Windows bootstrap")
def test_ps1_plans_through_the_installed_uv_and_python():
    uv = Path(os.environ.get("LOCALAPPDATA", "")) / "afk" / "uv" / "uv.exe"
    pythons = Path(os.environ.get("LOCALAPPDATA", "")) / "afk" / "pythons"
    if not uv.is_file() or not any(pythons.glob(f"cpython-{PINS['python']}-*")):
        pytest.skip("needs the installed uv and pinned CPython (a real run, offline)")
    done = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(PS1), "plan"],
                          capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "launcher: <entry>" in done.stdout and "stamp:" in done.stdout
