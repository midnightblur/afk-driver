#!/usr/bin/env python3
"""Install or check AFK's private Python runtime and its `afk-python` command.

    python_runtime.py plan    [--test]   print the install steps; change nothing
    python_runtime.py install [--test]   run them; idempotent
    python_runtime.py check   [--test]   probe the installed runtime; read-only

Pins and the dependency lock live in `runtime/` at the plugin root:
`pyproject.toml` (`requires-python`, `[tool.uv] required-version`, the import
names) and `uv.lock`. `--test` adds the `test` extra (pytest); a runtime that
already has it keeps it.

Layout, under `%LOCALAPPDATA%\\afk` on Windows or
`${XDG_DATA_HOME:-~/.local/share}/afk` elsewhere: `uv/` (the pinned uv),
`pythons/` (the managed CPython), `cache/`, and `python/` (the environment,
with its `AFK-RUNTIME` stamp). The command goes in `%LOCALAPPDATA%\\afk\\bin`
on Windows or `${XDG_BIN_HOME:-~/.local/bin}` elsewhere, and that directory is
added to the user PATH.

`check` resolves `afk-python` through the PATH a new terminal would get, from
every shell the platform has, and prints one `ok <probe>` or
`fail <probe>: <reason>` line per probe. Exit 0 when all pass, 1 otherwise,
2 on a usage or plugin-tree error.
"""
from __future__ import annotations

import argparse
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

    def table(key: str) -> list[str]:
        found = re.search(rf"^{key}\s*=\s*\{{(.*)\}}", text, re.M)
        return re.findall(r'=\s*"([A-Za-z0-9_.]+)"', found.group(1)) if found else []

    # Line endings vary with the checkout (core.autocrlf), the lock's content does not.
    lock = lock.replace(b"\r\n", b"\n")
    return {"python": python.group(1), "uv": uv.group(1),
            "imports": table("imports"), "test_imports": table("test-imports"),
            "lock": hashlib.sha256(lock).hexdigest()}


# ---- layout ----------------------------------------------------------------

def layout(env: Mapping[str, str], windows: bool) -> dict:
    home_dir = env.get("HOME") or env.get("USERPROFILE") or str(Path.home())
    if windows:
        base = Path(env["LOCALAPPDATA"]) / "afk"
        bin_dir = base / "bin"
    else:
        base = Path(env.get("XDG_DATA_HOME") or Path(home_dir, ".local", "share")) / "afk"
        bin_dir = Path(env.get("XDG_BIN_HOME") or Path(home_dir, ".local", "bin"))
    env_dir = base / "python"
    exe = ".exe" if windows else ""
    return {
        "base": base, "uv": base / "uv" / f"uv{exe}", "pythons": base / "pythons",
        "cache": base / "cache", "env": env_dir, "stamp": env_dir / STAMP,
        "script": env_dir / ("Scripts" if windows else "bin") / f"{COMMAND}{exe}",
        "bin": bin_dir, "launcher": bin_dir / f"{COMMAND}{exe}",
    }


def uv_env(env: Mapping[str, str], paths: dict) -> dict:
    out = dict(env)
    out.update(UV_PYTHON_INSTALL_DIR=str(paths["pythons"]), UV_CACHE_DIR=str(paths["cache"]),
               UV_PROJECT_ENVIRONMENT=str(paths["env"]), UV_TOOL_BIN_DIR=str(paths["bin"]),
               UV_NO_CONFIG="1")
    out.pop("VIRTUAL_ENV", None)
    return out


def read_stamp(paths: dict) -> dict:
    try:
        lines = paths["stamp"].read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}
    return dict(line.split("=", 1) for line in lines if "=" in line)


# ---- the transaction -------------------------------------------------------

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
    sync = [uv, "sync", "--project", str(RUNTIME), "--frozen", "--no-editable", "--compile-bytecode",
            "--managed-python", "--python", p["python"]] + (["--extra", "test"] if test else [])
    return [
        ("uv", get_uv),
        ("python", py_install),
        ("environment", sync),
        ("launcher", ["<copy>", str(paths["script"]), str(paths["launcher"])]),
        ("path", [uv, "tool", "update-shell"]),
    ]


def place_launcher(source: Path, target: Path, windows: bool) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if windows:
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
    target.symlink_to(source)


def install(env: Mapping[str, str], windows: bool, test: bool, runner: Runner = run,
            out=sys.stdout) -> int:
    p, paths = pins(), layout(env, windows)
    test = test or "test" in read_stamp(paths).get("extras", "").split(",")
    child_env = uv_env(env, paths)
    for name, argv in steps(p, paths, windows, test):
        if name == "uv":
            code, said = runner([str(paths["uv"]), "--version"], child_env)
            if code == 0 and said.split()[1:2] == [p["uv"]]:
                print(f"ok uv {p['uv']} already installed", file=out)
                continue
            child_env_uv = dict(child_env, UV_UNMANAGED_INSTALL=str(paths["uv"].parent))
            code, said = runner(argv, child_env_uv)
        elif name == "path" and on_path(paths["bin"], fresh_path(env, windows), windows):
            # uv refuses a second update-shell while the running PATH lags the startup files.
            print("ok path already set", file=out)
            continue
        elif name == "launcher":
            try:
                place_launcher(paths["script"], paths["launcher"], windows)
                code, said = 0, ""
            except OSError as exc:
                code, said = 1, str(exc)
        else:
            code, said = runner(argv, child_env)
        if code != 0:
            print(f"fail {name}: {said.splitlines()[-1] if said else f'exit {code}'}", file=out)
            return 1
        print(f"ok {name}", file=out)
    with open(paths["stamp"], "w", encoding="utf-8", newline="\n") as stamp:
        stamp.write(f"python={p['python']}\nuv={p['uv']}\nlock={p['lock']}\n"
                    f"extras={'test' if test else ''}\nlauncher={paths['launcher']}\n")
    print("ok stamp", file=out)
    print("Restart the harness and any open terminal: a running process keeps its old PATH.",
          file=out)
    return check(env, windows, test, runner, out)


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


def find_bash() -> str | None:
    spec = importlib.util.spec_from_file_location("afk_run_hook", PLUGIN_ROOT / "hooks" / "run-hook.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    found = module.find_bash()
    return str(found) if found else None


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
    # Single quotes only: every shell above passes them through a double-quoted line.
    return ("import os, platform; "
            + "".join(f"import {m}; " for m in modules)
            + "print(platform.python_version(), os.environ.get('AFK_PYTHON', '-'))")


def check(env: Mapping[str, str], windows: bool, test: bool, runner: Runner = run,
          out=sys.stdout) -> int:
    p, paths = pins(), layout(env, windows)
    stamp = read_stamp(paths)
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
    probe_env = dict(env, PATH=fresh_path(env, windows))
    probe_env.pop("AFK_PYTHON", None)
    quoted = '"' + probe_code(p["imports"] + (p["test_imports"] if test else [])) + '"'
    for name, build in shells(env, windows):
        status, said = runner(build(f"{COMMAND} -c {quoted}"), probe_env)
        seen = said.split() if status == 0 else []
        if len(seen) < 2:
            verdict(name, said.splitlines()[-1] if said else f"exit {status}")
        elif seen[0] != p["python"]:
            verdict(name, f"afk-python runs Python {seen[0]}, want {p['python']}")
        elif seen[1] == "-":
            verdict(name, "afk-python did not export AFK_PYTHON")
        else:
            verdict(name, None)
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
