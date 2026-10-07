#!/usr/bin/env python3
"""Install or check AFK's private Python runtime and its `afk-python` command.

    python_runtime.py plan    [--test]   print the install steps; change nothing
    python_runtime.py install [--test]   run them; idempotent
    python_runtime.py check   [--test]   probe the installed runtime; read-only

Pins and the dependency lock live in `runtime/` at the plugin root:
`pyproject.toml` (`requires-python`, `[tool.uv] required-version`, the import
names) and `uv.lock`. `--test` adds the `test` extra (pytest). Requested extras
persist in `AFK-RUNTIME.extras` beside the environment, written before any
change, so every later install keeps them, even after a failed one.

Layout, under `%LOCALAPPDATA%\\afk` on Windows or
`${XDG_DATA_HOME:-~/.local/share}/afk` elsewhere: `uv/` (the pinned uv),
`pythons/` (the managed CPython), `cache/`, and `python/` (the environment,
with its `AFK-RUNTIME` stamp). The command is the interpreter itself:
`python/afk-bin/afk-python` is a symlink to the managed CPython (a copy of the
environment's `python.exe` on Windows), and it finds `python/pyvenv.cfg` one
level up, so `sys.prefix` is the environment. `afk-bin` holds nothing else and
is the one directory added to the user PATH. `afk_python.pth` in the
environment sets `AFK_PYTHON` to `sys.executable`; `-S` skips it.

Packages install from wheels only (`--no-build`): a platform the lock has no
wheel for fails the sync with the package's name, never a source build. The
installer and uv run without the user's `UV_*` settings and installer download
overrides; proxy, TLS and uv's HTTP timeout, retry and concurrency variables
pass through.

`install` deletes the stamp before it changes anything and publishes a new one
only after every `check` probe passes, so a stamp always names a healthy
runtime. Its `command=` and `file=` lines are what the bash every hook runs in
(`hooks/run-hook.py` `find_bash` and `shell_env`) printed for `afk-python`
during that check; the SessionStart notice compares its own lookup with them.

`check` compares the installed packages with the lock (`uv sync --check
--offline`), then resolves `afk-python` through the PATH a new terminal would
get, never this process's own, from every shell the platform has. Setup's PATH
step uses the same PATH. It prints one `ok <probe>` or
`fail <probe>: <reason>` line per probe. Exit 0 when all pass, 1 otherwise,
2 on a usage or plugin-tree error.
"""
from __future__ import annotations

import argparse
import functools
import hashlib
import importlib.util
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable, Mapping

PLUGIN_ROOT = Path(__file__).resolve().parents[4]
RUNTIME = PLUGIN_ROOT / "runtime"
INSTALLER = "https://releases.astral.sh/github/uv/releases/download/{version}/uv-installer.{ext}"
STAMP = "AFK-RUNTIME"
COMMAND = "afk-python"
PTH = "afk_python.pth"
PTH_LINE = 'import os, sys; os.environ.setdefault("AFK_PYTHON", sys.executable)\n'
NO_WHEEL = "marked as `--no-build` but has no binary distribution"
# uv reads every UV_* variable as a setting (uv 0.12.23 crates/uv-static/src/env_vars.rs); keep only
# TLS and transport controls, which pick no package source or location.
UV_KEEP = ("UV_NATIVE_TLS", "UV_SYSTEM_CERTS", "UV_HTTP_TIMEOUT", "UV_HTTP_CONNECT_TIMEOUT",
           "UV_REQUEST_TIMEOUT", "UV_HTTP_RETRIES", "UV_CONCURRENT_DOWNLOADS")
# Non-UV_ download and location overrides in uv-installer.{sh,ps1} 0.12.23, and an active venv.
INSTALLER_OVERRIDES =("INSTALLER_DOWNLOAD_URL", "INSTALLER_NO_MODIFY_PATH",
                       "CARGO_DIST_FORCE_INSTALL_DIR", "CARGO_HOME", "VIRTUAL_ENV")

Runner = Callable[[object, Mapping[str, str]], "tuple[int, str]"]


def run(argv: object, env: Mapping[str, str]) -> tuple[int, str]:
    try:
        done = subprocess.run(argv, env=dict(env), capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=900)
    except (OSError, subprocess.SubprocessError) as exc:
        return 127, str(exc)
    return done.returncode, (done.stdout + done.stderr).strip()


# ---- pins ------------------------------------------------------------------

def broken_tree(problem: str) -> SystemExit:
    print(f"python_runtime: {problem}", file=sys.stderr)
    return SystemExit(2)


def pins(root: Path = RUNTIME) -> dict:
    try:
        text = (root / "pyproject.toml").read_text(encoding="utf-8")
        lock = (root / "uv.lock").read_bytes()
    except OSError as exc:
        raise broken_tree(str(exc))
    python = re.search(r'^requires-python\s*=\s*"==([0-9.]+)"', text, re.M)
    uv = re.search(r'^required-version\s*=\s*"==([0-9.]+)"', text, re.M)
    if not (python and uv):
        raise broken_tree(f"{root / 'pyproject.toml'}: exact Python and uv pins not found")

    def table(key: str) -> dict[str, str]:
        """Distribution name -> the module setup imports for it."""
        found = re.search(rf"^{key}\s*=\s*\{{(.*)\}}", text, re.M)
        return dict(re.findall(r'([A-Za-z0-9_.-]+)\s*=\s*"([A-Za-z0-9_.]+)"', found.group(1))) if found else {}

    # Line endings vary with the checkout (core.autocrlf), the lock's content does not.
    lock = lock.replace(b"\r\n", b"\n")
    return {"python": python.group(1), "uv": uv.group(1),
            "imports": list(table("imports").values()), "test_imports": list(table("test-imports").values()),
            "lock": hashlib.sha256(lock).hexdigest()}


# ---- layout ----------------------------------------------------------------

def layout(env: Mapping[str, str], windows: bool) -> dict:
    home_dir = env.get("HOME") or env.get("USERPROFILE") or str(Path.home())
    if windows:
        base = Path(env["LOCALAPPDATA"]) / "afk"
    else:
        base = Path(env.get("XDG_DATA_HOME") or Path(home_dir, ".local", "share")) / "afk"
    env_dir = base / "python"
    exe = ".exe" if windows else ""
    bin_dir = env_dir / "afk-bin"
    return {
        "base": base, "uv": base / "uv" / f"uv{exe}", "pythons": base / "pythons",
        "cache": base / "cache", "env": env_dir, "stamp": env_dir / STAMP,
        "intent": base / f"{STAMP}.extras",
        "interpreter": env_dir / ("Scripts" if windows else "bin") / f"python{exe}",
        "bin": bin_dir, "launcher": bin_dir / f"{COMMAND}{exe}",
    }


def site_packages(paths: dict, python: str, windows: bool) -> Path:
    if windows:
        return paths["env"] / "Lib" / "site-packages"
    return paths["env"] / "lib" / ("python" + ".".join(python.split(".")[:2])) / "site-packages"


def without_entry(env: Mapping[str, str], directory: Path, windows: bool) -> dict:
    """`env` with `directory` dropped from PATH, so only startup files can put it back."""
    out = dict(env)
    sep = ";" if windows else ":"
    out["PATH"] = sep.join(e for e in env.get("PATH", "").split(sep) if e and not on_path(directory, e, windows))
    return out


def uv_env(env: Mapping[str, str], paths: dict, windows: bool) -> dict:
    """The installer's and uv's environment: the user's, minus every source or location override."""
    out = {k: v for k, v in without_entry(env, paths["bin"], windows).items()
           if not (k.upper().startswith("UV_") and k.upper() not in UV_KEEP)
           and k.upper() not in INSTALLER_OVERRIDES}
    out.update(UV_PYTHON_INSTALL_DIR=str(paths["pythons"]), UV_CACHE_DIR=str(paths["cache"]),
               UV_PROJECT_ENVIRONMENT=str(paths["env"]), UV_TOOL_BIN_DIR=str(paths["bin"]),
               UV_NO_CONFIG="1")
    return out


def requested_extras(paths: dict) -> set[str]:
    """Extras any install asked for: the intent file, else a stamp written before it existed."""
    try:
        text = paths["intent"].read_text(encoding="utf-8")
    except FileNotFoundError:
        text = read_stamp(paths).get("extras", "")
    return {extra for extra in re.split(r"[,\s]+", text) if extra}


def write_atomically(path: Path, text: str) -> None:
    staged = path.with_name(path.name + ".new")
    with open(staged, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    os.replace(staged, path)


def read_stamp(paths: dict) -> dict:
    try:
        lines = paths["stamp"].read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}
    return dict(line.split("=", 1) for line in lines if "=" in line)


# ---- the transaction -------------------------------------------------------

def sync_command(p: dict, paths: dict, test: bool) -> list[str]:
    return ([str(paths["uv"]), "sync", "--project", str(RUNTIME), "--frozen", "--no-build",
             "--managed-python", "--python", p["python"]] + (["--extra", "test"] if test else []))


def steps(p: dict, paths: dict, windows: bool, test: bool) -> list[tuple[str, list]]:
    uv = str(paths["uv"])
    if windows:
        url = INSTALLER.format(version=p["uv"], ext="ps1")
        get_uv = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
                  f"irm {url} | iex"]
    else:
        url = INSTALLER.format(version=p["uv"], ext="sh")
        get_uv = ["sh", "-c", 'curl --proto =https --tlsv1.2 -LsSf "$1" | sh', "sh", url]
    py_install = [uv, "python", "install", p["python"], "--no-bin"] + (["--no-registry"] if windows else [])
    return [
        ("uv", get_uv),
        ("python", py_install),
        ("environment", sync_command(p, paths, test) + ["--compile-bytecode"]),
        ("launcher", ["<entry>", str(paths["interpreter"]), str(paths["launcher"]), PTH]),
        ("path", [uv, "tool", "update-shell"]),
    ]


def place_entry(paths: dict, python: str, windows: bool) -> None:
    """Put `afk-python` in afk-bin and the AFK_PYTHON line in site-packages; a sync may rebuild both."""
    (site_packages(paths, python, windows) / PTH).write_text(PTH_LINE, encoding="utf-8", newline="\n")
    target = paths["launcher"]
    target.parent.mkdir(parents=True, exist_ok=True)
    if windows:
        # The venv's python.exe is a launcher that reads pyvenv.cfg beside it or one level up.
        source = paths["interpreter"]
        # A running .exe cannot be overwritten, but it can be renamed away.
        staged = target.with_name(target.name + ".new")
        shutil.copy2(source, staged)
        try:
            os.replace(staged, target)
        except PermissionError:
            old = target.with_name(target.name + ".old")
            if old.exists():
                old.unlink()
            os.replace(target, old)
            os.replace(staged, target)
        return
    if target.is_symlink() or target.exists():
        target.unlink()
    # The base interpreter itself: CPython finds pyvenv.cfg from the unresolved link's location.
    target.symlink_to(os.path.realpath(paths["interpreter"]))


def install(env: Mapping[str, str], windows: bool, test: bool, runner: Runner = run,
            out=sys.stdout) -> int:
    p, paths = pins(), layout(env, windows)
    try:
        extras = requested_extras(paths) | ({"test"} if test else set())
    except OSError as exc:
        # An intent file that exists but cannot be read is not an empty request: change nothing.
        print(f"fail extras: cannot read {paths['intent']}: {exc}", file=out)
        return 1
    test = "test" in extras
    child_env = uv_env(env, paths, windows)
    # The request outlives a failed run; the stamp must not vouch for a half-repaired runtime.
    try:
        paths["intent"].parent.mkdir(parents=True, exist_ok=True)
        write_atomically(paths["intent"], ",".join(sorted(extras)) + "\n")
        paths["stamp"].unlink(missing_ok=True)
    except OSError as exc:
        print(f"fail stamp: {exc}", file=out)
        return 1
    for name, argv in steps(p, paths, windows, test):
        if name == "uv":
            code, said = runner([str(paths["uv"]), "--version"], child_env)
            if code == 0 and said.split()[1:2] == [p["uv"]]:
                print(f"ok uv {p['uv']} already installed", file=out)
                continue
            child_env_uv = dict(child_env, UV_UNMANAGED_INSTALL=str(paths["uv"].parent))
            code, said = runner(argv, child_env_uv)
        elif name == "path" and on_path(paths["bin"], fresh_path(child_env, windows), windows):
            # uv refuses a second update-shell while the running PATH lags the startup files.
            print("ok path already set", file=out)
            continue
        elif name == "launcher":
            try:
                place_entry(paths, p["python"], windows)
                code, said = 0, ""
            except OSError as exc:
                code, said = 1, str(exc)
        else:
            code, said = runner(argv, child_env)
        if code != 0:
            print(f"fail {name}: {said.splitlines()[-1] if said else f'exit {code}'}", file=out)
            if NO_WHEEL in said:
                print("This platform has no prebuilt wheel for that package, and setup does not "
                      "build from source. afk-python is not supported here yet.", file=out)
            return 1
        print(f"ok {name}", file=out)
    stamp = {"python": p["python"], "uv": p["uv"], "lock": p["lock"], "extras": "test" if test else "",
             "launcher": str(paths["launcher"])}
    spelling: dict = {}
    if check(env, windows, test, runner, out, stamp, spelling) != 0:
        return 1
    stamp.update(spelling)
    try:
        write_atomically(paths["stamp"], "".join(f"{key}={value}\n" for key, value in stamp.items()))
    except OSError as exc:
        print(f"fail stamp: {exc}", file=out)
        return 1
    print("ok stamp published", file=out)
    print("Restart the harness and any open terminal: a running process keeps its old PATH.",
          file=out)
    return 0


# ---- the probe -------------------------------------------------------------

def fresh_path(env: Mapping[str, str], windows: bool) -> str:
    """The PATH a newly opened terminal gets, not the one this process inherited."""
    if not windows:
        # A new terminal's PATH comes from the login shell's startup files.
        login = env.get("SHELL") or "/bin/sh"
        code, said = run([login, "-l", "-c", 'printf %s "$PATH"'], env)
        return said if code == 0 and said else env.get("PATH", "")
    import winreg

    parts = []
    for hive, key in ((winreg.HKEY_LOCAL_MACHINE,
                       r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
                      (winreg.HKEY_CURRENT_USER, "Environment")):
        try:
            with winreg.OpenKey(hive, key) as handle:
                parts.append(os.path.expandvars(winreg.QueryValueEx(handle, "Path")[0]))
        except OSError:
            continue
    return ";".join(parts)


def on_path(directory: Path, path: str, windows: bool) -> bool:
    def same(entry: str) -> str:
        entry = os.path.normpath(entry.strip().rstrip("\\/")) if entry.strip() else ""
        return entry.lower() if windows else entry

    return same(str(directory)) in {same(e) for e in path.split(";" if windows else ":")}


@functools.lru_cache(maxsize=None)
def hook_launcher():
    spec = importlib.util.spec_from_file_location("afk_run_hook", PLUGIN_ROOT / "hooks" / "run-hook.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def find_bash() -> str | None:
    """The bash every hook runs in."""
    found = hook_launcher().find_bash()
    return str(found) if found else None


def hook_env(bash: str, env: Mapping[str, str]) -> dict:
    return hook_launcher().shell_env(Path(bash), env)


# How the hooks' bash spells the command, and the file it runs: Git Bash drops `.exe` from the
# spelling, and `-ef` tells the .exe from an extensionless file beside or instead of it.
RESOLVE = ('p=$(command -v afk-python) && f=$p && { [ "$p" -ef "$p.exe" ] && f=$p.exe; :; } '
           '&& printf "afk-command\\t%s\\t%s\\n" "$p" "$f"')


def resolved(said: str) -> dict:
    for line in said.splitlines():
        if line.startswith("afk-command\t") and line.count("\t") == 2:
            _, command, entry = line.split("\t")
            return {"command": command, "file": entry}
    return {}


def shells(env: Mapping[str, str], windows: bool) -> list[tuple[str, Callable[[str], object]]]:
    """Each shell a hook or a human may resolve the command from, and how to hand it a line."""
    if windows:
        # cmd keeps the inner quotes only when /s strips one outer pair.
        found = [("powershell", lambda line: ["powershell", "-NoProfile", "-Command", line]),
                 ("cmd", lambda line: f'cmd /d /s /c "{line}"')]
        bash = find_bash()
        if bash:
            found.append(("git-bash", lambda line: [bash, "-c", line]))
        return found
    login = env.get("SHELL") or "/bin/sh"
    return [("sh", lambda line: ["/bin/sh", "-c", line]),
            (Path(login).name + " login", lambda line: [login, "-l", "-c", line])]


def probe_code(modules: list[str]) -> str:
    # Single quotes, no shell metacharacters: every shell above gets it inside a double-quoted line.
    return ("import os, platform, sys; "
            + "".join(f"import {m}; " for m in modules)
            + "print(platform.python_version(), os.environ.get('AFK_PYTHON', '-'), sys.prefix, sep=chr(9))")


def same_dir(a: str, b: Path) -> bool:
    return os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))


def same_file(a: str, b: Path) -> bool:
    # Not realpath: on POSIX the entry is a symlink, and its own path is what PATH found.
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def check(env: Mapping[str, str], windows: bool, test: bool, runner: Runner = run,
          out=sys.stdout, stamp: dict | None = None, spelling: dict | None = None) -> int:
    """Probe the runtime; `stamp` stands in for the stamp file while install has not published it.

    `spelling` receives the hooks' bash's `command` and `file` for the stamp.
    """
    p, paths = pins(), layout(env, windows)
    stamp = read_stamp(paths) if stamp is None else stamp
    test = test or "test" in stamp.get("extras", "").split(",")
    failures = 0

    def verdict(probe: str, problem: str | None) -> None:
        nonlocal failures
        failures += problem is not None
        print(f"ok {probe}" if problem is None else f"fail {probe}: {problem}", file=out)

    verdict("launcher", None if paths["launcher"].exists() else f"{paths['launcher']} missing")
    verdict("stamp", None if stamp.get("python") == p["python"]
            else f"want Python {p['python']}, have {stamp.get('python') or 'none'}")
    verdict("lock", None if stamp.get("lock") == p["lock"]
            else "the environment was not built from this plugin's runtime/uv.lock")
    # Read-only and offline: the installed distributions against the lock, exactly.
    status, said = runner(sync_command(p, paths, test) + ["--check", "--offline"], uv_env(env, paths, windows))
    drift = [line.strip() for line in said.splitlines() if line.startswith((" - ", " + "))]
    verdict("packages", None if status == 0 else
            ("differ from runtime/uv.lock: " + ", ".join(drift)) if drift
            else (said.splitlines()[-1] if said else f"uv exit {status}"))
    probe_env = without_entry(env, paths["bin"], windows)
    probe_env["PATH"] = fresh_path(probe_env, windows)
    probe_env.pop("AFK_PYTHON", None)
    quoted = '"' + probe_code(p["imports"] + (p["test_imports"] if test else [])) + '"'
    for name, build in shells(env, windows):
        status, said = runner(build(f"{COMMAND} -c {quoted}"), probe_env)
        seen = said.splitlines()[-1].split("\t") if status == 0 and said else []
        if len(seen) != 3:
            verdict(name, said.splitlines()[-1] if said else f"exit {status}")
        elif seen[0] != p["python"]:
            verdict(name, f"afk-python runs Python {seen[0]}, want {p['python']}")
        elif not same_dir(seen[2], paths["env"]):
            verdict(name, f"afk-python runs in {seen[2]}, want the environment {paths['env']}")
        elif seen[1] == "-":
            verdict(name, f"AFK_PYTHON is not set: {PTH} is missing from the environment")
        elif not same_file(seen[1], paths["launcher"]):
            verdict(name, f"afk-python resolves to {seen[1]}, want {paths['launcher']}")
        else:
            verdict(name, None)
    bash = find_bash()
    if bash:
        # The identity probe: the bash and environment run-hook.py gives every hook, never a login shell.
        status, said = runner([bash, "-c", RESOLVE], hook_env(bash, probe_env))
        spelled = resolved(said) if status == 0 else {}
        if not spelled:
            verdict("hook bash", f"{bash} finds no afk-python" + (f": {said.splitlines()[-1]}" if said else ""))
        elif "command" in stamp and spelled != {k: stamp.get(k) for k in spelled}:
            verdict("hook bash", f"the stamp names {stamp.get('file')}, the hooks' bash finds {spelled['file']}")
        else:
            verdict("hook bash", None)
            if spelling is not None:
                spelling.update(spelled)
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("action", choices=("plan", "install", "check"))
    parser.add_argument("--test", action="store_true", help="include the test extra (pytest)")
    args = parser.parse_args(argv)
    windows = os.name == "nt"
    env = os.environ
    if args.action == "plan":
        paths = layout(env, windows)
        for name, command in steps(pins(), paths, windows, args.test):
            where = f"UV_UNMANAGED_INSTALL={paths['uv'].parent} " if name == "uv" else ""
            print(f"{name}: {where}{' '.join(command)}")
        print(f"stamp: {paths['stamp']}")
        return 0
    if args.action == "install":
        return install(env, windows, args.test)
    return check(env, windows, args.test)


if __name__ == "__main__":
    sys.exit(main())
