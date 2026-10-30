"""Machine tools setup checks or installs: Python 3, rg and the lavish host.

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
from pathlib import Path
from typing import Callable, Mapping, Sequence

from places import Places, has_backup

LAVISH_PACKAGE = "lavish-axi"
LAVISH_PIN = "0.1.80"
RG_WINGET_ID = "BurntSushi.ripgrep.MSVC"


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
        if where and not (windows and Path(where).parent.name.lower() == "system32"):
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
    _broadcast_environment_change()
    return True


def _broadcast_environment_change() -> None:
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

def lavish_version(run: Runner, env: Mapping[str, str]) -> str | None:
    got = run(["npm", "ls", "-g", LAVISH_PACKAGE, "--json", "--depth=0"], env=env, timeout=120)
    try:
        deps = json.loads(got.out or "{}").get("dependencies") or {}
    except json.JSONDecodeError:
        return None
    return (deps.get(LAVISH_PACKAGE) or {}).get("version")


def lavish_record(places: Places) -> Path:
    return places.backup / "lavish-host.txt"


def install_lavish_pin(places: Places, run: Runner, env: Mapping[str, str]) -> dict:
    """Record the installed host version once, then install the pin."""
    prior = lavish_version(run, env)
    record = lavish_record(places)
    if not has_backup(record):
        record.parent.mkdir(parents=True, exist_ok=True)
        record.write_text((prior or "none") + "\n", encoding="utf-8")
    if prior == LAVISH_PIN:
        return {"ok": True, "action": "present", "version": prior}
    got = run(["npm", "install", "-g", f"{LAVISH_PACKAGE}@{LAVISH_PIN}"], env=env, timeout=600)
    now = lavish_version(run, env)
    if got.code != 0 or now != LAVISH_PIN:
        return {"ok": False, "prior": prior, "error": {
            "code": "lavish-install-failed", "reason": (got.err or got.out).strip()[:300]}}
    return {"ok": True, "action": "installed", "prior": prior, "version": now}


def restore_lavish(places: Places, run: Runner, env: Mapping[str, str]) -> dict:
    record = lavish_record(places)
    if not record.exists():
        return {"ok": True, "action": "no-backup"}
    prior = record.read_text(encoding="utf-8").strip()
    now = lavish_version(run, env)
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
