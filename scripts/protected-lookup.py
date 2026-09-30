#!/usr/bin/env python3
"""Is a branch protected? Asked live from the forge, with a local fallback.

    python protected-lookup.py --branch <name> [--checkout <dir>]
      -> {"protected": bool, "source": "github"|"gitlab"|"fallback"[, "reason": "..."]}

The forge is the repository's `forge:` (`CONFIG.md`) when it names one, else the
one the origin remote's host implies. The forge adapter's `protected-branches`
`branch-protection` verb answers for the one branch (`ADAPTERS.md`). Nothing is
cached: every call asks again.

Fallback (`source: fallback`, with a `reason`): no forge, no login, no network, a
timeout (`AFK_PROTECTED_TIMEOUT`, default 5 s), or an unreadable answer. Then
exactly the remote's default branch, `main` and `master` are protected. The remote
is the current branch's own, else `origin`.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(os.environ.get("AFK_PLUGIN_ROOT") or Path(__file__).resolve().parents[1])
TIMEOUT = 5.0


def _git(checkout: Path, *args: str) -> str:
    try:
        done = subprocess.run(["git", "-C", str(checkout), *args], capture_output=True,
                              text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return ""
    return done.stdout.strip() if done.returncode == 0 else ""


def _config_module():
    spec = importlib.util.spec_from_file_location("afk_config_for_lookup",
                                                  ROOT / "scripts" / "afk-config.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def forge_of(checkout: Path) -> str:
    """`github`, `gitlab` or `none`: the configuration first, the remote host second."""
    try:
        config = _config_module()
        configured = config.load(checkout).get("forge") or "none"
        if configured != "none":
            return configured
        return config.detect_forge(checkout)[0]
    except Exception:
        return "none"


def default_branch(checkout: Path) -> str:
    current = _git(checkout, "symbolic-ref", "--short", "HEAD")
    remote = (_git(checkout, "config", f"branch.{current}.remote") if current else "") or "origin"
    prefix = f"{remote}/"
    ref = _git(checkout, "symbolic-ref", "--short", f"refs/remotes/{remote}/HEAD")
    return ref[len(prefix):] if ref.startswith(prefix) else ""


def fallback(branch: str, checkout: Path, reason: str) -> dict:
    names = {"main", "master", default_branch(checkout)} - {""}
    return {"protected": branch in names, "source": "fallback", "reason": reason}


def _kill_tree(process: subprocess.Popen) -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(process.pid)],
                       capture_output=True, timeout=10)
    else:
        try:
            os.killpg(process.pid, 9)
        except OSError:
            process.kill()


def ask_forge(forge: str, branch: str, checkout: Path, limit: float) -> tuple[bool | None, str]:
    """The forge's verdict for one branch, or `(None, reason)`."""
    script = ROOT / "adapters" / "forge" / forge / "forge.sh"
    bash = _bash()
    if bash is None or not script.is_file():
        return None, f"no shell to run the {forge} adapter"
    environ = dict(os.environ, AFK_PLUGIN_ROOT=str(ROOT))
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as payload:
        payload.write(json.dumps({"branch": branch}).encode("utf-8"))
        payload.seek(0)
        try:
            process = subprocess.Popen(
                [bash, str(script), "branch-protection"], cwd=str(checkout),
                env=environ, stdout=out, stderr=subprocess.DEVNULL, stdin=payload,
                start_new_session=(os.name != "nt"))
        except OSError as problem:
            return None, f"the {forge} adapter did not start: {problem}"
        try:
            process.wait(timeout=limit)
        except subprocess.TimeoutExpired:
            _kill_tree(process)
            return None, f"the {forge} read timed out after {limit:g} s"
        out.seek(0)
        text = out.read().decode("utf-8", "replace")
    try:
        answer = json.loads(text)
    except ValueError:
        return None, f"the {forge} answer is unreadable"
    if not isinstance(answer, dict) or not isinstance(answer.get("protected"), bool):
        detail = answer.get("reason") if isinstance(answer, dict) else ""
        return None, detail or f"the {forge} forge did not answer"
    return answer["protected"], ""


def _bash() -> str | None:
    spec = importlib.util.spec_from_file_location("afk_run_hook_for_lookup",
                                                  ROOT / "hooks" / "run-hook.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    found = module.find_bash()
    return str(found) if found else None


def lookup(branch: str, checkout: Path) -> dict:
    forge = forge_of(checkout)
    if forge not in ("github", "gitlab"):
        return fallback(branch, checkout, "the forge is not GitHub or GitLab")
    try:
        limit = float(os.environ.get("AFK_PROTECTED_TIMEOUT") or TIMEOUT)
    except ValueError:
        limit = TIMEOUT
    verdict, reason = ask_forge(forge, branch, checkout, limit)
    if verdict is None:
        return fallback(branch, checkout, reason)
    return {"protected": verdict, "source": forge}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--branch", required=True)
    parser.add_argument("--checkout", default=".")
    args = parser.parse_args(argv)
    print(json.dumps(lookup(args.branch, Path(args.checkout))))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
