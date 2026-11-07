"""Machine tools setup checks or installs: Python 3, rg, the lavish host, herdr and the diagram renderer.

Every outside command goes through a `Runner`, so a test replaces it with an
in-process fake.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import Callable, Mapping, Sequence

from places import Places, has_backup, write_atomic

LAVISH_PACKAGE = "lavish-axi"
LAVISH_PIN = "0.1.80"
RG_WINGET_ID = "BurntSushi.ripgrep.MSVC"
MERMAID_PACKAGE = "@mermaid-js/mermaid-cli"
# The renderer pin: the engine keys its diagram cache by this version (`engine/diagrams.py`).
MERMAID_VERSION = "12.0.0"
# https://pptr.dev/api/puppeteer.configuration: this variable overrides `skipDownload`.
NO_BROWSER_DOWNLOAD = {"PUPPETEER_SKIP_DOWNLOAD": "true"}
EDGE_ROOTS = ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA")
HERDR_INSTALL_PS1 = "https://herdr.dev/install.ps1"
HERDR_INSTALL_SH = "https://herdr.dev/install.sh"
HERDR_INSTALL_TIMEOUT = 300


@dataclass
class Result:
    code: int
    out: str = ""
    err: str = ""


class Runner:
    """Runs a command by name; resolves `.cmd`/`.exe` through PATH first."""

    def which(self, name: str, env: Mapping[str, str] | None = None) -> str | None:
        return shutil.which(name, path=(env or os.environ).get("PATH"))

    def __call__(self, argv: Sequence[str], env: Mapping[str, str] | None = None,
                 timeout: float = 300) -> Result:
        exe = self.which(argv[0], env)
        if not exe:
            return Result(127, "", f"{argv[0]} not found on PATH")
        try:
            done = subprocess.run([exe, *argv[1:]], capture_output=True, text=True,
                                  env=dict(env) if env else None, timeout=timeout)
        except (OSError, subprocess.SubprocessError) as exc:
            return Result(126, "", str(exc))
        return Result(done.returncode, done.stdout, done.stderr)


# ---------------------------------------------------------- the backup folder

def lock_to_current_user(folder: Path, run: Runner, windows: bool = os.name == "nt",
                         env: Mapping[str, str] = os.environ) -> None:
    """Only the current user can open `folder` and what it holds. OSError if this fails."""
    folder.mkdir(parents=True, exist_ok=True)
    if not windows:
        os.chmod(folder, 0o700)
        return
    user = env.get("USERNAME")
    if not user:
        raise OSError(f"cannot limit {folder} to the current user: USERNAME is not set")
    # The domain stops a local account with the same name from matching first.
    name = f"{env['USERDOMAIN']}\\{user}" if env.get("USERDOMAIN") else user
    got = run(["icacls", str(folder), "/inheritance:r", "/grant:r", f"{name}:(OI)(CI)F"],
              env=env, timeout=60)
    if got.code != 0:
        raise OSError(f"cannot limit {folder} to the current user: {(got.err or got.out).strip()}")


# ----------------------------------------------------------------- Python 3

def find_python(run: Runner, env: Mapping[str, str]) -> dict:
    for name in ("python3", "python", "py"):
        argv = [name, "-3", "--version"] if name == "py" else [name, "--version"]
        got = run(argv, env=env, timeout=30)
        text = (got.out + got.err).strip()
        match = re.fullmatch(r"Python (3\.\d+(?:\.\d+)?)\S*", text)
        if got.code == 0 and match:
            where = run.which(name, env) or name
            return {"ok": True, "command": name, "path": where, "version": match.group(1)}
    return {"ok": False, "error": {"code": "no-python",
                                   "reason": "no Python 3 on the path (python3, python, py -3)"}}


# ----------------------------------------------------------------------- rg

def shell_probes(windows: bool, which: Callable[[str], str | None]) -> list[tuple[str, list[str]]]:
    """One rg probe per shell the agent uses. `which` resolves in the agent's
    own environment, so `bash` is the agent's Git Bash, never the WSL launcher."""
    probes: list[tuple[str, list[str]]] = []
    if windows:
        for name in ("powershell", "pwsh"):
            if where := which(name):
                probes.append((name, [where, "-NoProfile", "-Command",
                                      "(Get-Command rg -ErrorAction Stop).Source"]))
        probes.append(("cmd", [which("cmd") or "cmd", "/d", "/c", "where rg"]))
    for name in ("bash",) if windows else ("bash", "sh"):
        where = which(name)
        if where and not (windows and PureWindowsPath(where).parent.name.lower() == "system32"):
            probes.append((name, [where, "-lc", "command -v rg"]))
    return probes


def probe_shells(run: Runner, probes, env: Mapping[str, str]) -> dict[str, bool]:
    return {name: run(argv, env=env, timeout=60).code == 0 for name, argv in probes}


def ensure_rg(run: Runner, fresh_env: Callable[[], Mapping[str, str]], probes,
              add_to_user_path: Callable[[Path], bool], windows: bool) -> dict:
    """rg on the path of every shell in `probes`; install it if no shell has it.

    `fresh_env` answers the environment a newly started shell gets, so an
    install or a PATH change shows on the next call.
    """
    before = probe_shells(run, probes, fresh_env())
    if before and all(before.values()):
        return {"ok": True, "action": "present", "shells": before}
    found = run.which("rg", fresh_env())
    installed = False
    if not found:
        if not windows:
            return {"ok": False, "shells": before, "error": {
                "code": "no-rg", "reason": "install ripgrep with the system package manager"}}
        got = run(["winget", "install", "--id", RG_WINGET_ID, "-e",
                   "--accept-source-agreements", "--accept-package-agreements"], env=fresh_env())
        if got.code != 0:
            return {"ok": False, "shells": before, "error": {
                "code": "rg-install-failed", "reason": (got.err or got.out).strip()[:300]}}
        installed = True
        found = run.which("rg", fresh_env())
    path_added = bool(found) and add_to_user_path(Path(found).parent)
    after = probe_shells(run, probes, fresh_env())
    ok = bool(after) and all(after.values())
    answer = {"ok": ok, "action": "installed" if installed else "path",
              "rg": found, "path_added": path_added, "shells": after}
    if not ok:
        answer["error"] = {"code": "rg-not-on-every-shell",
                           "reason": "start a new terminal and the harness, then re-run"}
    return answer


def windows_user_path_adder(folder: Path) -> bool:
    """Add `folder` to the user PATH in the registry; True when it was added."""
    import winreg  # Windows only

    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0,
                         winreg.KEY_READ | winreg.KEY_WRITE)
    try:
        try:
            current, kind = winreg.QueryValueEx(key, "Path")
        except FileNotFoundError:
            current, kind = "", winreg.REG_EXPAND_SZ
        parts = [p for p in current.split(";") if p]
        wanted = os.path.normcase(str(folder)).rstrip("\\")
        if any(os.path.normcase(os.path.expandvars(p)).rstrip("\\") == wanted for p in parts):
            return False
        winreg.SetValueEx(key, "Path", 0, kind, ";".join([*parts, str(folder)]))
    finally:
        winreg.CloseKey(key)
    broadcast_environment_change()
    return True


def broadcast_environment_change() -> None:
    try:
        import ctypes

        ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x001A, 0, "Environment", 2, 5000, None)
    except Exception:
        pass


def fresh_windows_env(env: Mapping[str, str]) -> dict[str, str]:
    """`env` with PATH rebuilt from the machine and user registry values."""
    import winreg

    def read(root, sub):
        try:
            with winreg.OpenKey(root, sub) as key:
                return os.path.expandvars(winreg.QueryValueEx(key, "Path")[0])
        except OSError:
            return ""

    machine = read(winreg.HKEY_LOCAL_MACHINE,
                   r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment")
    user = read(winreg.HKEY_CURRENT_USER, "Environment")
    fresh = dict(env)
    fresh["PATH"] = ";".join(p for p in (machine, user, env.get("PATH", "")) if p)
    return fresh


# ------------------------------------------------------------- lavish host

def global_version(run: Runner, env: Mapping[str, str], package: str) -> str | None:
    """The globally installed version, or None when npm says it is absent.

    ValueError when npm gives no answer, because then nothing is known.
    """
    got = run(["npm", "ls", "-g", package, "--json", "--depth=0"], env=env, timeout=120)
    try:
        deps = json.loads(got.out).get("dependencies") or {}
    except ValueError:
        raise ValueError(f"npm ls gave no answer: {(got.err or got.out).strip()[:200]}") from None
    return (deps.get(package) or {}).get("version")


def lavish_version(run: Runner, env: Mapping[str, str]) -> str | None:
    return global_version(run, env, LAVISH_PACKAGE)


def _npm_unavailable(exc: ValueError) -> dict:
    return {"ok": False, "error": {"code": "npm-unavailable", "reason": str(exc)}}


def lavish_record(places: Places) -> Path:
    return places.backup / "lavish-host.txt"


def install_lavish_pin(places: Places, run: Runner, env: Mapping[str, str]) -> dict:
    """Record the installed host version once, then install the pin."""
    try:
        prior = lavish_version(run, env)
    except ValueError as exc:
        return _npm_unavailable(exc)
    record = lavish_record(places)
    if not has_backup(record):
        record.parent.mkdir(parents=True, exist_ok=True)
        record.write_text((prior or "none") + "\n", encoding="utf-8")
    if prior == LAVISH_PIN:
        return {"ok": True, "action": "present", "version": prior}
    got = run(["npm", "install", "-g", f"{LAVISH_PACKAGE}@{LAVISH_PIN}"], env=env, timeout=600)
    try:
        now = lavish_version(run, env)
    except ValueError as exc:
        return _npm_unavailable(exc)
    if got.code != 0 or now != LAVISH_PIN:
        return {"ok": False, "prior": prior, "error": {
            "code": "lavish-install-failed", "reason": (got.err or got.out).strip()[:300]}}
    return {"ok": True, "action": "installed", "prior": prior, "version": now}


def restore_lavish(places: Places, run: Runner, env: Mapping[str, str]) -> dict:
    record = lavish_record(places)
    if not record.exists():
        return {"ok": True, "action": "no-backup"}
    prior = record.read_text(encoding="utf-8").strip()
    try:
        now = lavish_version(run, env)
    except ValueError as exc:
        return _npm_unavailable(exc)
    if prior == "none":
        got = run(["npm", "uninstall", "-g", LAVISH_PACKAGE], env=env, timeout=600) \
            if now else Result(0)
    elif now != prior:
        got = run(["npm", "install", "-g", f"{LAVISH_PACKAGE}@{prior}"], env=env, timeout=600)
    else:
        got = Result(0)
    if got.code != 0:
        return {"ok": False, "error": {"code": "lavish-restore-failed",
                                       "reason": (got.err or got.out).strip()[:300]}}
    record.unlink()
    return {"ok": True, "action": "restored", "version": prior}


# -------------------------------------------------------------------- herdr

def herdr_status(run: Runner, record: Mapping[str, str], env: Mapping[str, str] | None = None) -> str:
    """`present` on the path, else the recorded answer (`declined` or `installed`), else `ask`. Read-only.
    `installed` off the path means a new terminal has not read the installer's path change yet."""
    if run.which("herdr", env):
        return "present"
    return record.get("herdr") if record.get("herdr") in ("declined", "installed") else "ask"


def herdr_installer(run: Runner, windows: bool, env: Mapping[str, str] | None = None) -> list[str]:
    """The official install command (https://herdr.dev/tui/docs/install/). Each one streams
    the installer into a shell or uses a package manager, and saves no program file first (AC-029)."""
    if windows:
        return ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
                f"irm {HERDR_INSTALL_PS1} | iex"]
    if run.which("brew", env):
        return ["brew", "install", "herdr"]
    return ["sh", "-c", f"curl -fsSL {HERDR_INSTALL_SH} | sh"]


def install_herdr(run: Runner, windows: bool = os.name == "nt",
                  env: Mapping[str, str] | None = None, download_dir: Path | None = None) -> dict:
    """Run the official installer. Only after the developer's yes in session.

    The official scripts download into GetTempPath() or `mktemp -d`. With `download_dir`, TMP,
    TEMP and TMPDIR name that folder for the installer process only, so no program file lands in
    a temporary folder (AC-029, decision D-11); the folder is removed after the run."""
    command = herdr_installer(run, windows, env)
    run_env = env
    if download_dir is not None:
        download_dir.mkdir(parents=True, exist_ok=True)
        folder = str(download_dir)
        run_env = {**(env if env is not None else os.environ), "TMP": folder, "TEMP": folder, "TMPDIR": folder}
    try:
        got = run(command, env=run_env, timeout=HERDR_INSTALL_TIMEOUT)
    finally:
        if download_dir is not None:
            shutil.rmtree(download_dir, ignore_errors=True)
    if got.code != 0:
        lines = [line.strip() for line in f"{got.out}\n{got.err}".splitlines() if line.strip()]
        return {"ok": False, "error": {"code": "install-failed",
                                       "reason": lines[-1][:300] if lines else f"exit {got.code}"}}
    return {"ok": True, "herdr": "installed", "path": run.which("herdr", env)}


# ---------------------------------------------------------- diagram renderer

def find_edge(env: Mapping[str, str]) -> Path | None:
    """The installed Edge at a known install path. No lookup on the path, and no download."""
    for root in EDGE_ROOTS:
        if env.get(root):
            edge = Path(env[root], "Microsoft", "Edge", "Application", "msedge.exe")
            if edge.is_file():
                return edge
    return None


def ensure_diagram_renderer(places: Places, run: Runner, env: Mapping[str, str]) -> dict:
    """The diagram command at the pin, with the browser download off, and a config that points it at Edge.
    Another installed version is replaced by the pin. With no Edge, nothing is installed."""
    edge = find_edge(env)
    if edge is None:
        return {"ok": False, "error": {"code": "no-edge", "reason": "no Microsoft Edge at its known install paths. "
                                       "Install Edge, then run this step again; setup downloads no browser"}}
    try:
        prior = global_version(run, env, MERMAID_PACKAGE)
        version = prior
        if prior != MERMAID_VERSION:
            got = run(["npm", "install", "-g", f"{MERMAID_PACKAGE}@{MERMAID_VERSION}"], env={**env, **NO_BROWSER_DOWNLOAD},
                      timeout=600)
            version = global_version(run, env, MERMAID_PACKAGE)
            if got.code != 0 or version != MERMAID_VERSION:
                return {"ok": False, "error": {"code": "renderer-install-failed", "reason": (got.err or got.out).strip()[:300]}}
    except ValueError as exc:
        return _npm_unavailable(exc)
    if run(["mmdc", "--version"], env=env, timeout=120).code != 0:
        return {"ok": False, "error": {"code": "mmdc-not-found", "reason": "the package is installed, but `mmdc` does not run: "
                                       "put the npm global folder on the path, then run this step again"}}
    write_atomic(places.puppeteer_config, json.dumps({"executablePath": str(edge)}, indent=2).encode("utf-8") + b"\n")
    return {"ok": True, "action": "present" if prior == MERMAID_VERSION else "installed", "version": version, "edge": str(edge),
            "config": str(places.puppeteer_config)}
