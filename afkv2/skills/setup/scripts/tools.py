"""Machine tools setup checks or installs: Python 3, rg, the lavish host, herdr, the diagram renderer,
the browser driver and the gh floor.

Every outside command goes through a `Runner`, so a test replaces it with an
in-process fake.
"""

from __future__ import annotations

import base64
import contextlib
import http.server
import json
import os
import queue
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
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
# Chrome DevTools MCP (requirement ADR-0004). The pin is the newest release at least 30 days old on 2026-11-11.
DRIVER_PACKAGE = "chrome-devtools-mcp"
DRIVER_VERSION = "1.10.1"
DRIVER_ENTRY = "chrome-devtools"
ATTACH_ENTRY = "chrome-devtools-attach"
DRIVER_FLAGS = ("--no-usage-statistics",)
NOT_ON_DISK = (".exe", ".dll", ".node")
BROWSERS = {"chrome": ("Google", "Chrome", "chrome.exe"), "edge": ("Microsoft", "Edge", "msedge.exe")}
INSPECT_PAGES = {"chrome": "chrome://inspect/#remote-debugging", "edge": "edge://inspect/#remote-debugging"}
ATTACH_FALLBACKS = ("watch the developer run the steps", "reproduce the steps on a local app")
PROOF_MESSAGE = "afkv2-proof-clicked"
PROOF_PAGE = ("<!doctype html><title>afkv2 proof</title><button onclick=\"console.log('" + PROOF_MESSAGE
              + "');this.textContent='clicked'\">Prove</button>").encode("utf-8")
MCP_PROTOCOL = "2025-06-18"
MCP_SECONDS = 90
STOP_SECONDS = 15
GH_FLOOR = (2, 99, 0)
# The judge model setup names when the developer names none: a higher tier of that provider (PRD AC-019).
JUDGE_MODELS = {"claude": "fable"}


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
            done = subprocess.run([exe, *argv[1:]], capture_output=True, text=True, stdin=subprocess.DEVNULL,
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

    Where each one stages the program file (read 2026-11-07): install.ps1 downloads into
    `Join-Path ([System.IO.Path]::GetTempPath()) "herdr-install-<guid>"`, which reads TMP, then TEMP;
    install.sh runs `TMP="$(mktemp -d)"` and `curl ... -o "${TMP}/${BIN}"`, which reads TMPDIR; brew
    builds in HOMEBREW_TEMP (https://docs.brew.sh/Manpage, ENVIRONMENT; default /private/tmp or /var/tmp).
    With `download_dir`, TMP, TEMP, TMPDIR and HOMEBREW_TEMP name that folder for the installer process
    only, so no program file lands in a temporary folder (AC-029, decision D-11); the folder is removed
    after the run."""
    command = herdr_installer(run, windows, env)
    run_env = env
    if download_dir is not None:
        download_dir.mkdir(parents=True, exist_ok=True)
        folder = str(download_dir)
        run_env = {**(env if env is not None else os.environ), "TMP": folder, "TEMP": folder, "TMPDIR": folder,
                   "HOMEBREW_TEMP": folder}
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


# ------------------------------------------------------------ browser driver

class DriverError(Exception):
    """The driver server did not start, exited, or gave no answer in time."""


def find_browsers(env: Mapping[str, str]) -> dict[str, Path]:
    """Chrome and Edge at their known install paths. No lookup on the path, and no download."""
    found = {}
    for name, (vendor, product, exe) in BROWSERS.items():
        for root in EDGE_ROOTS:
            path = Path(env[root], vendor, product, "Application", exe) if env.get(root) else None
            if path and path.is_file():
                found[name] = path
                break
    return found


def _install_failed(reason: str) -> dict:
    return {"ok": False, "error": {"code": "driver-install-failed", "reason": reason[:300]}}


def ensure_browser_driver(run: Runner, env: Mapping[str, str]) -> dict:
    """The driver package at the pin, in the npm global folder, with the browser download off.

    Answers `node` and `script`, which each harness entry starts. The package is JavaScript only: a file
    with a suffix of NOT_ON_DISK in it refuses, so no program file lands anywhere (PRD AC-044)."""
    node = run.which("node", env)
    if not node:
        return _install_failed("node is not on the path: install Node.js, then run this step again")
    try:
        prior = global_version(run, env, DRIVER_PACKAGE)
        if prior != DRIVER_VERSION:
            got = run(["npm", "install", "-g", f"{DRIVER_PACKAGE}@{DRIVER_VERSION}"],
                      env={**env, **NO_BROWSER_DOWNLOAD}, timeout=600)
            now = global_version(run, env, DRIVER_PACKAGE)
            if got.code != 0 or now != DRIVER_VERSION:
                return _install_failed((got.err or got.out).strip() or f"npm installed {now}, not {DRIVER_VERSION}")
    except ValueError as exc:
        return _install_failed(str(exc))
    root = run(["npm", "root", "-g"], env=env, timeout=120).out.strip()
    if "***" in root:
        # npm masks a path part it reads as a secret, such as a UUID-shaped folder name.
        return _install_failed(f"npm hid part of its global folder: {root}; use a global folder without such a part")
    folder = Path(root, DRIVER_PACKAGE)
    try:
        script = Path(folder, json.loads((folder / "package.json").read_text(encoding="utf-8"))["bin"][DRIVER_PACKAGE])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return _install_failed(f"cannot read the start script of the driver in {folder}: {exc}")
    programs = sorted(p.name for p in folder.rglob("*") if p.suffix.lower() in NOT_ON_DISK)
    if programs:
        return _install_failed(f"the driver package holds program files: {', '.join(programs[:5])}")
    if not script.is_file():
        return _install_failed(f"the start script {script} of the driver is missing")
    return {"ok": True, "action": "present" if prior == DRIVER_VERSION else "installed", "version": DRIVER_VERSION,
            "node": node, "script": str(script)}


def driver_command(install: Mapping[str, str]) -> dict:
    """The server command with usage statistics off; an entry or a proof adds the browser flags."""
    return {"command": install["node"], "args": [install["script"], *DRIVER_FLAGS]}


def launch_entry(command: Mapping, browser: Path) -> dict:
    """The entry that starts its own browser, with a fresh profile per session."""
    return {"command": command["command"], "args": [*command["args"], "--isolated", "--executablePath", str(browser)]}


def attach_entry(command: Mapping, user_data: Path) -> dict:
    """The entry that attaches to the running browser of the developer's profile."""
    return {"command": command["command"], "args": [*command["args"], "--autoConnect", "--userDataDir", str(user_data)]}


class McpSession:
    """1 MCP server over stdio: newline-delimited JSON-RPC (modelcontextprotocol.io, Transports, stdio)."""

    def __init__(self, argv: Sequence[str], seconds: float = MCP_SECONDS):
        self._seconds, self._next = seconds, 0
        self._err = tempfile.TemporaryFile()
        try:
            self._process = subprocess.Popen(list(argv), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self._err,
                                             text=True, encoding="utf-8", **_process_group())
        except OSError as exc:
            self._err.close()
            raise DriverError(f"the server did not start: {exc}") from None
        self._lines: queue.Queue = queue.Queue()
        threading.Thread(target=self._read, daemon=True).start()
        try:
            self._request("initialize", {"protocolVersion": MCP_PROTOCOL, "capabilities": {},
                                         "clientInfo": {"name": "afkv2-setup", "version": "1"}})
            self._send({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
        except DriverError:
            self.close()
            raise

    def _read(self) -> None:
        for line in self._process.stdout:
            self._lines.put(line)
        self._lines.put(None)

    def _send(self, message: dict) -> None:
        try:
            self._process.stdin.write(json.dumps(message) + "\n")
            self._process.stdin.flush()
        except OSError:
            raise DriverError(f"the server exited: {self._stderr()}") from None

    def _stderr(self) -> str:
        self._err.seek(0)
        return self._err.read().decode("utf-8", "replace").strip()[-300:]

    def _request(self, method: str, params: dict) -> dict:
        self._next += 1
        self._send({"jsonrpc": "2.0", "id": self._next, "method": method, "params": params})
        while True:
            try:
                line = self._lines.get(timeout=self._seconds)
            except queue.Empty:
                raise DriverError(f"no answer to {method} in {self._seconds:.0f} s") from None
            if line is None:
                with contextlib.suppress(subprocess.TimeoutExpired):
                    self._process.wait(STOP_SECONDS)
                raise DriverError(f"the server exited: {self._stderr()}")
            try:
                message = json.loads(line)
            except ValueError:
                continue
            if isinstance(message, dict) and message.get("id") == self._next:
                if "error" in message:
                    raise DriverError(f"{method}: {(message['error'] or {}).get('message')}")
                return message.get("result") or {}

    def call(self, tool: str, arguments: dict) -> tuple[bool, list]:
        """(is_error, the content list) of 1 tool call."""
        result = self._request("tools/call", {"name": tool, "arguments": arguments})
        return bool(result.get("isError")), result.get("content") or []

    def close(self) -> None:
        """Closing stdin stops the server, and the server closes the browser it started."""
        with contextlib.suppress(OSError):
            self._process.stdin.close()
        try:
            self._process.wait(STOP_SECONDS)
        except subprocess.TimeoutExpired:
            _stop_tree(self._process)
        self._err.close()


def _process_group() -> dict:
    if sys.platform == "win32":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def _stop_tree(process) -> None:
    with contextlib.suppress(OSError, subprocess.SubprocessError):
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(process.pid)], capture_output=True, timeout=STOP_SECONDS)
        else:
            os.killpg(process.pid, 9)
    with contextlib.suppress(subprocess.SubprocessError):
        process.wait(STOP_SECONDS)


def _text(content) -> str:
    if isinstance(content, str):
        return content
    return "\n".join(str(part.get("text", "")) for part in content if isinstance(part, dict) and part.get("type") == "text")


def _png(content) -> bool:
    for part in content if isinstance(content, list) else []:
        if isinstance(part, dict) and part.get("type") == "image":
            with contextlib.suppress(ValueError, TypeError):
                return base64.b64decode(part.get("data", ""), validate=True).startswith(b"\x89PNG")
    return False


@contextlib.contextmanager
def proof_page():
    """The test page on 127.0.0.1 for the length of the block: a button that logs PROOF_MESSAGE."""
    class Page(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(PROOF_PAGE)

        def log_message(self, *_args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Page)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/"
    finally:
        server.shutdown()
        server.server_close()


def prove_driver(command: Mapping, browser: Path, headless: bool, session=McpSession, url: str | None = None) -> dict:
    """The live proof in 1 browser: open the test page, click its button, take a screenshot, read the console.

    Answers each step green, or `failed` with the step (`start`, `open`, `click`, `screenshot`, `console`) and
    the answer of the server. `session` starts the server from an argv list; a test passes a fake."""
    if url is None:
        with proof_page() as page:
            return prove_driver(command, browser, headless, session, page)
    argv = [command["command"], *launch_entry(command, browser)["args"], *(["--headless"] if headless else [])]
    steps: dict[str, str] = {}
    step = "start"
    try:
        server = session(argv)
    except DriverError as exc:
        return {"ok": False, "steps": steps, "failed": step, "reason": str(exc)[:300]}
    try:
        step = "open"
        broken, content = server.call("new_page", {"url": url})
        found = re.search(r"(\d+): [^\n]*\[selected\]", _text(content))
        if broken or url not in _text(content) or not found:
            raise DriverError(_text(content) or "the page did not open")
        page = {"pageId": int(found.group(1))}
        steps[step] = "green"
        step = "click"
        broken, content = server.call("take_snapshot", page)
        button = re.search(r'uid=(\S+) button "Prove"', _text(content))
        if broken or not button:
            raise DriverError(_text(content) or "the snapshot shows no button")
        broken, content = server.call("click", {**page, "uid": button.group(1)})
        if broken:
            raise DriverError(_text(content))
        steps[step] = "green"
        step = "screenshot"
        broken, content = server.call("take_screenshot", page)
        if broken or not _png(content):
            raise DriverError(_text(content) or "the answer holds no PNG picture")
        steps[step] = "green"
        step = "console"
        broken, content = server.call("list_console_messages", page)
        if broken or PROOF_MESSAGE not in _text(content):
            raise DriverError(_text(content) or "the console holds no message of the click")
        steps[step] = "green"
    except DriverError as exc:
        return {"ok": False, "steps": steps, "failed": step, "reason": str(exc)[:300]}
    finally:
        server.close()
    return {"ok": True, "steps": steps}


def browser_profile(name: str, env: Mapping[str, str]) -> Path | None:
    """The default user data folder of the developer's Chrome or Edge on Windows."""
    vendor, product, _exe = BROWSERS[name]
    return Path(env["LOCALAPPDATA"], vendor, product, "User Data") if env.get("LOCALAPPDATA") else None


def _debug_port_open(port_file: Path) -> bool:
    """The browser writes its debug port to this file and keeps the file after the port closes."""
    try:
        port = int(port_file.read_text(encoding="utf-8").split()[0])
        with socket.create_connection(("127.0.0.1", port), timeout=2):
            return True
    except (OSError, ValueError, IndexError):
        return False


def prove_attach(command: Mapping, name: str, env: Mapping[str, str], session=McpSession) -> dict:
    """Attach to the running, signed-in browser of the developer and list its pages.

    A failure says why and offers ATTACH_FALLBACKS (PRD AC-043)."""
    profile = browser_profile(name, env)
    failed = {"ok": False, "browser": name, "offer": list(ATTACH_FALLBACKS)}
    if profile is None or not _debug_port_open(profile / "DevToolsActivePort"):
        return {**failed, "why": f"remote debugging is off in {name}: open {INSPECT_PAGES[name]} in it, allow "
                                 "remote debugging, keep the browser open, then run this step again"}
    entry = attach_entry(command, profile)
    try:
        server = session([entry["command"], *entry["args"]])
    except DriverError as exc:
        return {**failed, "why": str(exc)[:300]}
    try:
        broken, content = server.call("list_pages", {})
    except DriverError as exc:
        return {**failed, "why": str(exc)[:300]}
    finally:
        server.close()
    if broken:
        return {**failed, "why": _text(content)[:300]}
    return {"ok": True, "browser": name, "entry": entry, "pages": _text(content)[:300]}


# ------------------------------------------------------------------- gh floor

def check_gh(run: Runner, env: Mapping[str, str], windows: bool = os.name == "nt") -> dict:
    """gh at GH_FLOOR or later: the proof comment of the tracker port runs `gh issue comment --attach`."""
    got = run(["gh", "--version"], env=env, timeout=60)
    found = re.search(r"gh version (\d+)\.(\d+)\.(\d+)", got.out) if got.code == 0 else None
    version = tuple(int(part) for part in found.groups()) if found else None
    answer = {"needed": True, "version": ".".join(map(str, version)) if version else None,
              "ok": bool(version) and version >= GH_FLOOR}
    if not answer["ok"]:
        how = "run `winget upgrade --id GitHub.cli -e`" if windows else "upgrade gh with the system package manager"
        answer["fix"] = f"the proof comment needs gh {'.'.join(map(str, GH_FLOOR))} or later: {how}, then open a new terminal"
    return answer
