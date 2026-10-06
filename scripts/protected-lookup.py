#!/usr/bin/env python3
"""Is a branch protected? Asked live from the forge, with a local fallback.

    python protected-lookup.py --branch <name> [--checkout <dir>]
      -> {"protected": bool, "source": "github"|"gitlab"|"fallback"[, "reason": "..."]}

The forge is the repository's `forge:` (`CONFIG.md`) when it names one, else the
one the branch's remote host implies. `adapters/forge/branch_protection.py` reads
the one branch (`ADAPTERS.md`); it runs in this process, and no shell starts.
Nothing is cached: every call asks again.

Fallback (`source: fallback`, with a `reason`): no forge, no login, no network, a
timeout (`AFK_PROTECTED_TIMEOUT`, default 5 s, wall-clock; `AFK_GITHUB_API_URL` / `AFK_GITLAB_API_URL` replace the
forge's public API root for the token path), or an unreadable
answer. Then exactly the remote's default branch, `main` and `master` are
protected. The remote is the branch's own, else `origin`.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(os.environ.get("AFK_PLUGIN_ROOT") or Path(__file__).resolve().parents[1])
TIMEOUT = 5.0
end = [0.0]  # monotonic time by which one lookup, git reads included, must finish
PUBLIC_API = {"github": ("github.com", "https://api.github.com"),
              "gitlab": ("gitlab.com", "https://gitlab.com/api/v4")}


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _left() -> float:
    if end[0]:
        return max(end[0] - time.monotonic(), 0.05)
    return float(os.environ.get("AFK_PROTECTED_TIMEOUT") or TIMEOUT)


def _git(checkout: Path, *args: str) -> str:
    try:
        done = subprocess.run(["git", "-C", str(checkout), *args], capture_output=True,
                              encoding="utf-8", errors="replace", timeout=_left())
    except (OSError, ValueError, subprocess.SubprocessError):
        return ""
    return done.stdout.strip() if done.returncode == 0 else ""


def _common_dir(checkout: Path) -> Path | None:
    found = _git(checkout, "rev-parse", "--path-format=absolute", "--git-common-dir")
    return Path(found) if found else None


def read_config(common: Path) -> dict[str, dict[str, str]]:
    """The repository's own config file as `{"remote origin": {"url": ...}, ...}`."""
    try:
        text = (common / "config").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    sections: dict[str, dict[str, str]] = {}
    current: dict[str, str] | None = None
    for line in text.splitlines():
        head = re.match(r'^\s*\[\s*([A-Za-z0-9.-]+)(?:\s+"((?:[^"\\]|\\.)*)")?\s*\]', line)
        if head:
            name = f"{head.group(1).lower()} {head.group(2)}" if head.group(2) is not None else head.group(1).lower()
            current = sections.setdefault(name, {})
            continue
        pair = re.match(r"^\s*([A-Za-z][A-Za-z0-9-]*)\s*=\s*(.*?)\s*$", line)
        if pair and current is not None:
            current[pair.group(1).lower()] = re.sub(r"\s+[;#].*$", "", pair.group(2)).strip('"')
    return sections


def _remote_of(config: dict, branch: str) -> str:
    own = config.get(f"branch {branch}", {}).get("remote", "")
    if own and f"remote {own}" in config:
        return own
    if "remote origin" in config:
        return "origin"
    names = [key.split(" ", 1)[1] for key in config if key.startswith("remote ")]
    return names[0] if names else ""


def _host_of(url: str) -> str:
    rest = re.sub(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", "", url.strip())
    rest = re.sub(r"^[^@/]+@", "", rest)
    return re.split(r"[/:]", rest, maxsplit=1)[0].lower()


def _configured(checkout: Path, common: Path) -> dict:
    """The repository configuration, read only when a configuration file exists."""
    files = [Path.home() / ".afk" / "config.yaml", checkout / ".afk" / "config.yaml",
             common / "afk" / "config.yaml", checkout / ".afk" / "config.local.yaml"]
    if not (os.environ.get("AFK_CONFIG") or any(path.is_file() for path in files)):
        return {}
    try:
        return _load("afk_config_for_lookup", ROOT / "scripts" / "afk-config.py").load(checkout)
    except Exception:
        return {}


def facts(checkout: Path, common: Path, branch: str) -> dict:
    """`forge`, `repo` (owner/name or ""), `host` and `remote` of the branch's remote."""
    config = read_config(common)
    settings = _configured(checkout, common)
    forge = settings.get("forge") or "none"
    remote = _remote_of(config, branch)
    if forge in ("github", "gitlab"):
        pinned = (settings.get(forge) or {}).get("remote") or ""
        remote = pinned if f"remote {pinned}" in config else remote
    url = config.get(f"remote {remote}", {}).get("url", "") if remote else ""
    host = _host_of(url) if url else ""
    aliased = any(key.startswith(("url ", "include")) for key in config)
    if remote and (aliased or (url and "." not in host)):
        url = _git(checkout, "remote", "get-url", remote) or url  # git resolves insteadOf and includes
        host = _host_of(url) if url else ""
    elif not remote and any(key.startswith("include") for key in config):
        remote = (_git(checkout, "remote").splitlines() or [""])[0]
        url = _git(checkout, "remote", "get-url", remote) if remote else ""
        host = _host_of(url) if url else ""
    if forge not in ("github", "gitlab"):
        forge = "gitlab" if "gitlab" in host else "github" if "github" in host else "none"
    repo = _load("afk_project_for_lookup", ROOT / "adapters" / "forge" / "project_from_remote.py").project(url) if url else ""
    return {"forge": forge, "repo": repo, "host": host, "remote": remote}


def default_branch(common: Path, remote: str) -> str:
    """The remote's default branch, from its symbolic HEAD ref; "" when unset."""
    try:
        text = (common / "refs" / "remotes" / (remote or "origin") / "HEAD").read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    prefix = f"ref: refs/remotes/{remote or 'origin'}/"
    return text[len(prefix):] if text.startswith(prefix) else ""


def fallback(branch: str, common: Path, remote: str, reason: str) -> dict:
    names = {"main", "master", default_branch(common, remote)} - {""}
    return {"protected": branch in names, "source": "fallback", "reason": reason}


def lookup(branch: str, checkout: Path, common: Path | None = None) -> dict:
    try:
        cap = float(os.environ.get("AFK_PROTECTED_TIMEOUT") or TIMEOUT)
    except ValueError:
        cap = TIMEOUT
    end[0] = time.monotonic() + cap
    common = common or _common_dir(checkout)
    if common is None:
        return {"protected": branch in ("main", "master"), "source": "fallback",
                "reason": "the repository's git directory could not be found"}
    found = facts(checkout, common, branch)
    forge = found["forge"]
    if forge not in ("github", "gitlab"):
        return fallback(branch, common, found["remote"], "the forge is not GitHub or GitLab")
    limit = _left()
    public_host, api = PUBLIC_API[forge]
    override = os.environ.get("AFK_GITHUB_API_URL" if forge == "github" else "AFK_GITLAB_API_URL")
    api = override or (api if found["host"] == public_host else "")
    answer = _load("afk_branch_protection", ROOT / "adapters" / "forge" / "branch_protection.py").protection(
        forge, branch, found["repo"], str(checkout), limit, api, found["host"])
    if answer.get("error") or not isinstance(answer.get("protected"), bool):
        return fallback(branch, common, found["remote"], answer.get("reason") or f"the {forge} forge did not answer")
    return {"protected": answer["protected"], "source": forge}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--branch", required=True)
    parser.add_argument("--checkout", default=".")
    args = parser.parse_args(argv)
    print(json.dumps(lookup(args.branch, Path(args.checkout))))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
