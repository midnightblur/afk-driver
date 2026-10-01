#!/usr/bin/env python3
"""Is one branch protected on the forge? The forge family's shared read.

    python branch_protection.py github|gitlab --branch <name> [--repo <slug>] [--timeout <s>]
      -> {"protected": bool, "via": "branch"|"ruleset"|"none"}
       | {"error": true, "verb": "branch-protection", "reason": "..."}

`scripts/protected-lookup.py` calls `protection` in-process; no adapter verb fronts it.
A failing read is an error, never "not protected". The time cap is wall-clock: a
child still running at the cap is killed with its process tree.

GitHub: the branch flag (`branches/<b>`; a 404 there only means "not classically
protected") or a ruleset rule of type pull_request, update, non_fast_forward,
deletion or required_*. Both reads run at once, so it costs one round trip; the
rules read is the only source for a branch not yet pushed. GitLab: an exact or
wildcard entry (`*` spans `/`) among the paginated protected branches.

Credentials: with `api` given and `GH_TOKEN`/`GITHUB_TOKEN` (GitLab: `GITLAB_TOKEN`)
set, the reads go straight over HTTPS (plain http only to loopback; otherwise the CLI path). GitHub without one, and only for the public API
(`https://api.github.com`), asks `gh auth token` once (glab has no such command) and does the same; if that fails, both reads go through `gh api` / `glab api`.
The token lives in memory only: nothing is written to disk.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

PUBLIC_GITHUB_API = "https://api.github.com"
NOT_FOUND = re.compile(r"HTTP 404|\"status\":\s*\"?404|Not Found")
RULE_TYPES = {"pull_request", "update", "non_fast_forward", "deletion"}


def _error(reason: str) -> dict:
    return {"error": True, "verb": "branch-protection", "reason": reason}


def _kill_tree(process: subprocess.Popen) -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(process.pid)],
                       capture_output=True, timeout=10)
    else:
        try:
            os.killpg(process.pid, 9)
        except OSError:
            process.kill()


def _run(argv: list[str], cwd: str, deadline: float) -> tuple[int, str, str] | None:
    """`(exit code, stdout, stderr)`, or None when the deadline passed or the CLI is missing."""
    exe = shutil.which(argv[0])
    if exe is None:
        return None
    try:
        process = subprocess.Popen([exe, *argv[1:]], cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   stdin=subprocess.DEVNULL, start_new_session=(os.name != "nt"))
    except OSError:
        return None
    try:
        out, err = process.communicate(timeout=max(deadline - time.monotonic(), 0.05))
    except subprocess.TimeoutExpired:
        _kill_tree(process)
        try:
            process.communicate(timeout=0.2)  # a grandchild that outlives the kill must not hold the cap
        except subprocess.TimeoutExpired:
            pass
        return None
    return process.returncode, out.decode("utf-8", "replace"), err.decode("utf-8", "replace")


def _cli_get(argv: list[str], cwd: str, deadline: float):
    """`(status, body)`: 200, 404, or 0 for any other failure; None when unanswered."""
    done = _run(argv, cwd, deadline)
    if done is None:
        return None
    code, out, err = done
    if code == 0:
        return 200, out
    return (404, "") if NOT_FOUND.search(err + out) else (0, "")


def _https_get(url: str, headers: dict, deadline: float):
    """`(status, body, response headers)` over HTTPS; None when unanswered."""
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=max(deadline - time.monotonic(), 0.05)) as reply:
            return reply.status, reply.read().decode("utf-8", "replace"), dict(reply.headers)
    except urllib.error.HTTPError as problem:
        return problem.code, "", {}
    except (OSError, ValueError):
        return None


def _together(reads: dict, deadline: float) -> dict:
    """Run named zero-argument reads at once; a read still running at the deadline stays unanswered."""
    answers: dict = {}

    def one(key, read):
        try:
            answers[key] = read()
        except Exception:
            answers[key] = None

    threads = [threading.Thread(target=one, args=item, daemon=True) for item in reads.items()]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(max(deadline - time.monotonic(), 0) + 0.2)
    return dict(answers)


def _may_send_token(api: str) -> bool:
    """A token travels over HTTPS, or over plain http only to this machine; anything else takes the CLI."""
    parts = urllib.parse.urlsplit(api or "")
    return parts.scheme == "https" or (parts.scheme == "http" and parts.hostname in ("127.0.0.1", "localhost", "::1"))


PUBLIC_HOSTS = {"github": "github.com", "gitlab": "gitlab.com"}


def _config_hosts(forge: str) -> set[str]:
    """The hosts the CLI is logged in to, read from its own config file (no process)."""
    home, xdg, appdata = Path.home(), os.environ.get("XDG_CONFIG_HOME"), os.environ.get("APPDATA")
    if forge == "github":
        name, dirs = "hosts.yml", [os.environ.get("GH_CONFIG_DIR"), xdg and f"{xdg}/gh",
                                   appdata and f"{appdata}/GitHub CLI", home / ".config" / "gh"]
    else:  # glab's directory list is from its docs, not measured on every platform
        name, dirs = "config.yml", [os.environ.get("GLAB_CONFIG_DIR"), xdg and f"{xdg}/glab-cli",
                                    appdata and f"{appdata}/glab-cli", home / ".config" / "glab-cli"]
    for folder in filter(None, dirs):
        try:
            text = (Path(folder) / name).read_text(encoding="utf-8")
        except OSError:
            continue
        if forge == "gitlab":
            found = re.search(r"^hosts:", text, re.M)
            text = text[found.end():] if found else ""
            return set(re.findall(r"^  ([A-Za-z0-9][A-Za-z0-9.-]*):\s*$", text, re.M))
        return set(re.findall(r"^([A-Za-z0-9][A-Za-z0-9.-]*):\s*$", text, re.M))
    return set()


def _ssh_host(alias: str, cwd: str, deadline: float) -> str:
    """The real host an SSH alias names, from `ssh -G`'s hostname line; "" when it cannot tell."""
    done = _run(["ssh", "-G", alias], cwd, deadline)
    found = re.search(r"^hostname (\S+)", done[1], re.M) if done is not None and done[0] == 0 else None
    return found.group(1).lower() if found else ""


def _hostname(forge: str, host: str, cwd: str, deadline: float) -> list[str] | None:
    """`--hostname <h>` for a host the CLI is logged in to; [] for the public host; None otherwise.

    An SSH alias is resolved with `ssh -G` and re-checked. None means the CLI has no login for
    the host: asking its default host instead would answer for another repository.
    """
    public = PUBLIC_HOSTS.get(forge)
    if not host or host == public:
        return []
    known = _config_hosts(forge)
    if host not in known:
        host = _ssh_host(host, cwd, deadline)
    if host == public:
        return []
    return ["--hostname", host] if host in known else None


def _login_token(cwd: str, deadline: float) -> str:
    """The CLI's own login token for the public API, asked once; "" falls back to the CLI reads.

    Only the public API is ever given it: an override host gets the CLI path, which resolves
    that host's own credentials, so a github.com login never travels to another address.
    """
    done = _run(["gh", "auth", "token", "--hostname", "github.com"], cwd, deadline)
    return done[1].strip() if done is not None and done[0] == 0 else ""


def _github(branch: str, repo: str, cwd: str, deadline: float, api: str, host: str = "") -> dict:
    enc = urllib.parse.quote(branch, safe="/")
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
    if api == PUBLIC_GITHUB_API and repo and not token and deadline - time.monotonic() > 0.3:
        token = _login_token(cwd, deadline)  # with the budget nearly spent a spawn cannot pay for itself
    answers = None
    if _may_send_token(api) and token and repo:
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                   "User-Agent": "afk-protected-lookup"}

        def by_token(path: str):
            done = _https_get(f"{api}/repos/{repo}/{path}/{enc}", headers, deadline)
            return None if done is None else (done[0] if done[0] in (200, 404, 401, 403) else 0, done[1])

        answers = _together({"branch": lambda: by_token("branches"), "rules": lambda: by_token("rules/branches")},
                            deadline)
        if any(a and a[0] in (401, 403) for a in answers.values()):
            answers = None  # this token is not good for this host: the CLI may hold a login that is
    if answers is None:
        base = f"repos/{repo}" if repo else "repos/{owner}/{repo}"
        target = _hostname("github", host, cwd, deadline)
        if target is None:
            return _error(f"the CLI is not logged in to {host}")

        def by_cli(path: str):
            return _cli_get(["gh", "api", *target, f"{base}/{path}/{enc}"], cwd, deadline)

        answers = _together({"branch": lambda: by_cli("branches"), "rules": lambda: by_cli("rules/branches")},
                            deadline)
    flag = answers.get("branch")
    if flag is None:
        return _error("the branch read did not answer (missing CLI, network or timeout)")
    if flag[0] == 200:
        try:
            if json.loads(flag[1]).get("protected") is True:
                return {"protected": True, "via": "branch"}
        except (ValueError, AttributeError):
            return _error("the branch answer is unreadable")
    elif flag[0] != 404:
        return _error("the branch read failed")

    rules = answers.get("rules")
    if rules is None or rules[0] != 200:
        return _error("the rules read failed")
    try:
        body = json.loads(rules[1])
    except ValueError:
        return _error("the rules answer is unreadable")
    if not isinstance(body, list):
        return _error("the rules answer is not a list")
    kinds = [item.get("type", "") for item in body if isinstance(item, dict)]
    hit = [kind for kind in kinds if kind in RULE_TYPES or kind.startswith("required_")]
    return {"protected": bool(hit), "via": "ruleset" if hit else "none"}


def _documents(text: str) -> list:
    decoder, index, found = json.JSONDecoder(), 0, []
    while True:
        while index < len(text) and text[index].isspace():
            index += 1
        if index >= len(text):
            return found
        value, index = decoder.raw_decode(text, index)
        found.append(value)


def _wildcard(pattern: str, branch: str) -> bool:
    return re.fullmatch(".*".join(re.escape(part) for part in pattern.split("*")),
                        branch, re.DOTALL) is not None


def _gitlab(branch: str, repo: str, cwd: str, deadline: float, api: str, host: str = "") -> dict:
    project = urllib.parse.quote(repo, safe="") if repo else ":id"
    token = os.environ.get("GITLAB_TOKEN") or ""
    texts: list[str] = []
    refused = False
    if _may_send_token(api) and token and repo:
        page = "1"
        while page:
            done = _https_get(f"{api}/projects/{project}/protected_branches?per_page=100&page={page}",
                              {"PRIVATE-TOKEN": token}, deadline)
            if done is not None and done[0] in (401, 403):
                refused, texts = True, []  # this token is not good for this host: try the CLI
                break
            if done is None or done[0] != 200:
                return _error("the protected-branch read failed")
            texts.append(done[1])
            page = {k.lower(): v for k, v in done[2].items()}.get("x-next-page", "").strip()
    if refused or not (_may_send_token(api) and token and repo):
        target = _hostname("gitlab", host, cwd, deadline)
        if target is None:
            return _error(f"the CLI is not logged in to {host}")
        done = _run(["glab", "api", *target, "--paginate", f"projects/{project}/protected_branches?per_page=100"],
                    cwd, deadline)
        if done is None or done[0] != 0:
            return _error("the protected-branch read failed")
        texts.append(done[1])
    try:
        names = []
        for text in texts:
            for document in _documents(text):
                names.extend(entry["name"] for entry in (document if isinstance(document, list) else [document]))
    except (ValueError, KeyError, TypeError):
        return _error("the protected-branch answer is unreadable")
    return {"protected": any(_wildcard(name, branch) for name in names), "via": "branch"}


def protection(forge: str, branch: str, repo: str = "", cwd: str = ".", limit: float = 30.0,
               api: str = "", host: str = "") -> dict:
    """`api` is the forge's HTTPS API root: with a token in the environment it replaces the CLI.

    `host` is the remote's host name; a CLI read names it only when the CLI is logged in to it.
    """
    if not branch:
        return _error("branch is required")
    deadline = time.monotonic() + limit
    if forge == "github":
        return _github(branch, repo, cwd, deadline, api, host)
    if forge == "gitlab":
        return _gitlab(branch, repo, cwd, deadline, api, host)
    return _error(f"forge {forge!r} has no branch-protection read")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("forge", choices=("github", "gitlab"))
    parser.add_argument("--branch", default="")
    parser.add_argument("--repo", default="")
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args(argv)
    print(json.dumps(protection(args.forge, args.branch, args.repo, ".", args.timeout)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
