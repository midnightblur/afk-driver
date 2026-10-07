"""The zero-Python setup bootstrap: bootstrap.sh against stub uv/curl, bootstrap.ps1 against stub uv/installer."""
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
# Without `sh` on PATH, the hooks' own bash: never the Windows WSL stub that `bash` can resolve to.
SHELL = shutil.which("sh") or pr.find_bash()

STUB_UV = """#!/bin/sh
printf '%s\\n' "$*" >> "$LOG"
env | grep -E '^(UV_|INSTALLER_|CARGO_HOME=)' | sort >> "$LOG.env"
case "$1" in --version) echo "uv {version} (stub)" ;; run) exit "${{RUN_RC:-0}}" ;; esac
exit 0
"""
STUB_CURL = """#!/bin/sh
printf 'curl %s\\n' "$*" >> "$LOG"
[ -z "${CURL_RC:-}" ] || exit "$CURL_RC"
while [ "$#" -gt 0 ]; do [ "$1" = -o ] && out=$2; shift; done
cat > "$out" <<'EOF'
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
               STUB_BIN=posix(bin_dir))
    return tmp_path, data / "afk", env, stub


def run(env, *args):
    # Git's bin\bash.exe puts its own tool dirs first, real curl included: the stubs go first inside.
    return subprocess.run([SHELL, "-c", 'PATH="$STUB_BIN:$PATH" exec sh "$0" "$@"', posix(SH), *args],
                          env=env, capture_output=True, text=True, timeout=60)


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
    assert log[0].startswith(f"curl --proto =https --tlsv1.2 -LsSf {url} -o ")
    assert log[1] == f"installer {posix(base / 'uv')}"
    assert log[-1].startswith("run --no-project") and log[-1].endswith("python_runtime.py plan")


def test_a_failed_download_stops_before_any_uv_runs(machine):
    tmp_path, base, env, _stub = machine
    # A stale uv a failed download would otherwise leave in charge.
    (base / "uv").mkdir(parents=True)
    (base / "uv" / "uv").write_text("#!/bin/sh\necho 'uv 0.0.1'\necho \"$*\" >> \"$LOG\"\n", encoding="utf-8",
                                    newline="\n")
    (base / "uv" / "uv").chmod(0o755)
    done = run(dict(env, CURL_RC="22"), "install")
    assert done.returncode == 1 and "cannot download" in done.stderr
    assert [line for line in calls(tmp_path) if not line.startswith("curl")] == ["--version"]


def test_an_installer_that_leaves_another_uv_version_stops_the_bootstrap(machine):
    tmp_path, base, env, _stub = machine
    old = tmp_path / "old-uv"
    old.write_text(STUB_UV.format(version="0.0.1"), encoding="utf-8", newline="\n")
    old.chmod(0o755)
    done = run(dict(env, STUB_UV_SOURCE=posix(old)), "install")
    assert done.returncode == 1 and f"is not uv {PINS['uv']}" in done.stderr
    assert not any(line.startswith(("python install", "run ")) for line in calls(tmp_path))


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


# ---- bootstrap.ps1 against a stub uv.exe and a stub installer --------------------------------------

STUB_UV_CS = r"""
using System; using System.Collections; using System.IO; using System.Text;
class Uv {
    static int Main(string[] argv) {
        string line = string.Join(" ", argv);
        var env = new StringBuilder();
        foreach (DictionaryEntry e in Environment.GetEnvironmentVariables()) env.Append(e.Key + "=" + e.Value + "\u0001");
        File.AppendAllText(Environment.GetEnvironmentVariable("STUB_LOG"), "uv " + line + "\t" + env + "\n");
        if (line == "--version") {
            Console.WriteLine("uv " + File.ReadAllText(Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "uv.version")).Trim());
            return 0;
        }
        Console.Error.WriteLine("uv progress goes to stderr");
        string fail = Environment.GetEnvironmentVariable("STUB_UV_FAIL");
        return !string.IsNullOrEmpty(fail) && line.Contains(fail) ? 3 : 0;
    }
}
"""
STUB_INSTALLER_CMD = "\r\n".join([
    "@echo off",
    '>>"%STUB_LOG%" echo installer %UV_UNMANAGED_INSTALL%',
    'if defined STUB_INSTALLER_RC exit /b %STUB_INSTALLER_RC%',
    'if not exist "%UV_UNMANAGED_INSTALL%" mkdir "%UV_UNMANAGED_INSTALL%"',
    'copy /y "%STUB_UV_SOURCE%" "%UV_UNMANAGED_INSTALL%\\uv.exe" >nul',
    '>"%UV_UNMANAGED_INSTALL%\\uv.version" echo %STUB_INSTALL_VERSION%',
    "exit /b 0", ""])
POWERSHELLS = [name for name in ("powershell", "pwsh") if os.name == "nt" and shutil.which(name)]


@pytest.fixture(scope="module")
def uv_exe(tmp_path_factory):
    if not POWERSHELLS or not shutil.which("powershell"):
        pytest.skip("bootstrap.ps1 is the Windows bootstrap; needs Windows PowerShell")
    where = tmp_path_factory.mktemp("uv-stub")
    (where / "uv.cs").write_text(STUB_UV_CS, encoding="utf-8")
    done = subprocess.run(["powershell", "-NoProfile", "-Command",
                           f"Add-Type -Path '{where / 'uv.cs'}' -OutputAssembly '{where / 'uv.exe'}' "
                           "-OutputType ConsoleApplication"], capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stdout + done.stderr
    return where / "uv.exe"


@pytest.fixture(params=POWERSHELLS or ["powershell"])
def windows_machine(request, tmp_path, uv_exe):
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    (stubs / "powershell.cmd").write_text(STUB_INSTALLER_CMD, encoding="utf-8", newline="")
    system = os.environ.get("SystemRoot", r"C:\Windows")
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("UV_")}
    env.update(LOCALAPPDATA=str(tmp_path / "local"), STUB_LOG=str(tmp_path / "log"), STUB_UV_SOURCE=str(uv_exe),
               STUB_INSTALL_VERSION=PINS["uv"], PATH=os.pathsep.join([str(stubs), rf"{system}\System32"]))
    shell = shutil.which(request.param)
    return tmp_path, tmp_path / "local" / "afk", env, shell


def run_ps1(shell, env, *args):
    return subprocess.run([shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(PS1), *args],
                          env=env, capture_output=True, text=True, timeout=120)


def ps1_calls(tmp_path) -> list[tuple[str, dict]]:
    found = []
    for line in (tmp_path / "log").read_text(encoding="utf-8", errors="replace").splitlines():
        command, _, env = line.partition("\t")
        found.append((command.strip(), dict(e.split("=", 1) for e in env.split("\x01") if "=" in e)))
    return found


def place_uv(base: Path, uv_exe: Path, version: str) -> None:
    (base / "uv").mkdir(parents=True)
    shutil.copy(uv_exe, base / "uv" / "uv.exe")
    (base / "uv" / "uv.version").write_text(version, encoding="utf-8")


def test_ps1_missing_uv_installs_the_pin_then_runs_the_runtime(windows_machine):
    tmp_path, base, env, shell = windows_machine
    done = run_ps1(shell, env, "install", "--test")
    assert done.returncode == 0, done.stdout + done.stderr
    commands = [c for c, _ in ps1_calls(tmp_path)]
    assert commands[0] == f"installer {base / 'uv'}"
    assert commands[-2] == f"uv python install {PINS['python']} --no-bin --no-registry"
    assert commands[-1] == (f"uv run --no-project --managed-python --no-python-downloads --python {PINS['python']} "
                            f"{SCRIPTS / 'python_runtime.py'} install --test")


@pytest.mark.parametrize("installed", [None, "0.0.1"])
def test_ps1_present_or_wrong_uv(windows_machine, uv_exe, installed):
    tmp_path, base, env, shell = windows_machine
    place_uv(base, uv_exe, installed or PINS["uv"])
    assert run_ps1(shell, env, "check").returncode == 0
    commands = [c for c, _ in ps1_calls(tmp_path)]
    assert any(c.startswith("installer") for c in commands) == (installed is not None)


def test_ps1_scrubs_the_settings_python_runtime_drops(windows_machine, uv_exe):
    tmp_path, base, env, shell = windows_machine
    place_uv(base, uv_exe, PINS["uv"])
    env.update(UV_INDEX_URL="https://elsewhere.invalid", UV_PYTHON_INSTALL_DIR=r"C:\elsewhere",
               UV_HTTP_TIMEOUT="90", INSTALLER_DOWNLOAD_URL="https://elsewhere.invalid", CARGO_HOME=r"C:\x",
               VIRTUAL_ENV=r"C:\venv")
    assert run_ps1(shell, env, "plan").returncode == 0
    seen = next(e for c, e in ps1_calls(tmp_path) if c.startswith("uv python install"))
    upper = {k.upper(): v for k, v in seen.items()}
    assert upper["UV_HTTP_TIMEOUT"] == "90" and upper["UV_NO_CONFIG"] == "1"
    assert upper["UV_PYTHON_INSTALL_DIR"] == str(base / "pythons") and upper["UV_CACHE_DIR"] == str(base / "cache")
    assert not {"UV_INDEX_URL", "INSTALLER_DOWNLOAD_URL", "CARGO_HOME", "VIRTUAL_ENV", "UV_UNMANAGED_INSTALL"} & set(upper)


@pytest.mark.parametrize("local", [None, "", r"relative\dir"])
def test_ps1_without_an_absolute_localappdata_changes_nothing(windows_machine, local):
    tmp_path, _base, env, shell = windows_machine
    env.pop("LOCALAPPDATA")
    if local is not None:
        env["LOCALAPPDATA"] = local
    done = run_ps1(shell, env, "install")
    assert done.returncode == 2 and "LOCALAPPDATA" in done.stderr
    assert not (tmp_path / "log").exists()


@pytest.mark.parametrize("change, code, message", [
    ({"STUB_INSTALLER_RC": "5"}, 5, ""),
    ({"STUB_INSTALL_VERSION": "0.0.1"}, 1, "is not uv"),
    ({"STUB_UV_FAIL": "python install"}, 3, ""),
    ({"STUB_UV_FAIL": "run --no-project"}, 3, ""),
])
def test_ps1_a_failed_step_stops_with_its_exit_code(windows_machine, change, code, message):
    tmp_path, _base, env, shell = windows_machine
    done = run_ps1(shell, dict(env, **change), "install")
    assert done.returncode == code, done.stdout + done.stderr
    assert message in done.stderr
    commands = [c for c, _ in ps1_calls(tmp_path)]
    after = {"STUB_INSTALLER_RC": "uv python", "STUB_INSTALL_VERSION": "uv python",
             "STUB_UV_FAIL": None}[next(iter(change))]
    if after:
        assert not any(c.startswith(after) for c in commands)
    elif "python install" in change["STUB_UV_FAIL"]:
        assert not any(c.startswith("uv run") for c in commands)


def test_ps1_an_installer_that_cannot_start_fails_the_bootstrap(windows_machine):
    tmp_path, _base, env, shell = windows_machine
    (tmp_path / "stubs" / "powershell.cmd").unlink()
    env["PATH"] = str(tmp_path / "stubs")
    done = run_ps1(shell, env, "install")
    assert done.returncode == 1 and "could not start" in done.stderr, done.stdout + done.stderr


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
