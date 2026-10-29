#!/usr/bin/env afk-python
"""Check a forge account with the repository's forge host, and save it only when the host accepts it.

    afk-python forge_account_check.py --account NAME [--repo PATH]

Asks the host who the account is, one try within 20 s: gh runs `gh api user`
with that account's token (`gh auth token --hostname <host> --user <account>`);
glab runs `glab api --hostname <host> user` and refuses a login that differs
from the account, naming it. Accepted: `developer.forgeAccount` is written to
the repository file (`developer_values.save_forge_account`). Refused or
unreachable: nothing is saved and `cause` names why. `warnings` names a push
sign-in or a commit email that does not match the account. No token is printed,
logged or written.

Prints one JSON object. Exit 0 saved; 1 refused or unreachable; 2 usage, or the
repository or its settings cannot be read.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[4]
TIMEOUT = 20.0
TOKEN_VARIABLES = ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN")


def _module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ac = _module("afk_config_for_forge_account_check", PLUGIN_ROOT / "scripts" / "afk-config.py")
helper = _module("afk_forge_account_for_check", PLUGIN_ROOT / "scripts" / "forge_account.py")
dv = _module("afk_developer_values_for_check", Path(__file__).resolve().parent / "developer_values.py")


class Unreachable(Exception):
    """The host did not answer within the time limit."""


def _run(argv: list[str], timeout: float, env: dict | None = None, cwd: Path | None = None):
    """(exit code, stdout, stderr) of one forge CLI or git call; `Unreachable` on timeout."""
    try:
        done = subprocess.run(argv, capture_output=True, text=True, timeout=max(timeout, 0.1),
                              env=env, cwd=cwd, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired as late:
        raise Unreachable(str(late)) from late
    except OSError as problem:
        return 127, "", str(problem)
    return done.returncode, done.stdout or "", done.stderr or ""


def _clean_env() -> dict:
    return {k: v for k, v in os.environ.items() if k not in TOKEN_VARIABLES}


def _first_line(text: str) -> str:
    return next((line.strip() for line in text.splitlines() if line.strip()), "")[:300]


def _ask_github(host: str, account: str, deadline: float) -> tuple[dict | None, str]:
    """(the host's user record, "") when the host accepts the account; (None, cause) otherwise."""
    code, token, _ = _run(["gh", "auth", "token", "--hostname", host, "--user", account],
                          deadline - time.monotonic(), _clean_env())
    token = token.strip()
    if code != 0 or not token:
        return None, f"gh holds no sign-in for {account} on {host}; run `gh auth login --hostname {host}`"
    env = {**_clean_env(), "GH_HOST": host, helper.token_variable(host): token}
    code, out, err = _run(["gh", "api", "user"], deadline - time.monotonic(), env)
    if code != 0:
        return None, f"{host} refused {account}: {_first_line(err) or f'gh exited {code}'}"
    try:
        user = json.loads(out)
    except ValueError:
        return None, f"{host} answered something that is not a user record"
    login = str(user.get("login") or "") if isinstance(user, dict) else ""
    if login.lower() != account.lower():
        return None, f"the token gh holds for {account} on {host} signs in as {login or 'nobody'}"
    return user, ""


def _ask_gitlab(host: str, account: str, deadline: float) -> tuple[dict | None, str]:
    code, out, err = _run(["glab", "api", "--hostname", host, "user"], deadline - time.monotonic())
    if code != 0:
        return None, (f"glab has no sign-in that {host} accepts ({_first_line(err) or f'glab exited {code}'}); "
                      f"run `glab auth login --hostname {host}`")
    try:
        user = json.loads(out)
    except ValueError:
        return None, f"{host} answered something that is not a user record"
    login = str(user.get("username") or "") if isinstance(user, dict) else ""
    if login.lower() != account.lower():
        return None, (f"glab is signed in to {host} as {login or 'nobody'}, not {account}; "
                      f"glab holds one sign-in per host, so sign in as {account} first")
    return user, ""


def _git(root: Path, *args: str) -> str:
    try:
        code, out, _ = _run(["git", "-C", str(root), *args], 10.0)
    except Unreachable:
        return ""
    return out.strip() if code == 0 else ""


def _push_login(root: Path, forge: str, host: str) -> tuple[str, str]:
    """(the login a push to the forge remote signs in with, where it comes from); ("", "") when unknown."""
    remote = str(ac.get(ac.load(root), f"{forge}.remote") or "") or "origin"
    url = _git(root, "remote", "get-url", "--push", remote)
    named = re.match(r"^https?://([^@/:]+)(?::[^@/]*)?@", url)
    if named:
        return named.group(1), f"the push URL of {remote}"
    if not url.startswith(("http://", "https://")):
        return "", ""
    for key in (f"credential.https://{host}.username", "credential.username"):
        value = _git(root, "config", "--get", key)
        if value:
            return value, f"git config {key}"
    helpers = _git(root, "config", "--get-all", f"credential.https://{host}.helper")
    if forge == "github" and "gh auth git-credential" in helpers:
        try:
            code, out, _ = _run(["gh", "auth", "status", "--hostname", host, "--json", "hosts"], 10.0,
                                _clean_env())
        except Unreachable:
            return "", ""
        try:
            entries = json.loads(out).get("hosts", {}).get(host, []) if code == 0 else []
        except (ValueError, AttributeError):
            entries = []
        active = next((e.get("login") for e in entries if isinstance(e, dict) and e.get("active")), "")
        if active:
            return str(active), "gh's active sign-in, which git's credential helper uses"
    return "", ""


def _account_emails(forge: str, host: str, user: dict) -> set[str]:
    """The emails a commit by `user` may carry: the ones the host shows plus its no-reply forms."""
    login = str(user.get("login") or user.get("username") or "")
    found = {str(user.get(key) or "") for key in ("email", "commit_email", "public_email")}
    if user.get("id") is not None and login:
        join = "+" if forge == "github" else "-"
        found.add(f"{user['id']}{join}{login}@users.noreply.{host}")
    if forge == "github" and login:
        found.add(f"{login}@users.noreply.{host}")
    return {email.lower() for email in found if email}


def _warnings(root: Path, forge: str, host: str, account: str, user: dict) -> list[str]:
    found = []
    login, where = _push_login(root, forge, host)
    if login and login.lower() != account.lower():
        found.append(f"push sign-in {login} ({where}) differs from the forge account {account}")
    email = _git(root, "config", "user.email")
    if email and email.lower() not in _account_emails(forge, host, user):
        found.append(f"commit email {email} is not an email the host shows for the forge account {account}")
    return found


def check_forge_account(root: Path, account: str, timeout: float = TIMEOUT) -> dict:
    """Ask the forge host whether it accepts `account` for `root`; save it only on acceptance."""
    account = account.strip()
    answer = {"account": account, "accepted": False, "saved": None, "warnings": []}
    if not account or account.lower() == "none":
        return {**answer, "cause": "name the forge account to check"}
    forge = str(ac.get(ac.load(root), "forge") or "none")
    host, _ = helper.host_and_account(root)
    host = host or {"github": "github.com", "gitlab": "gitlab.com"}.get(forge, "")
    answer.update(forge=forge, host=host)
    if forge not in ("github", "gitlab"):
        return {**answer, "cause": f"this repository's forge is {forge}; a forge account needs github or gitlab"}
    cli = "gh" if forge == "github" else "glab"
    if not shutil.which(cli):
        return {**answer, "cause": f"the `{cli}` CLI is not on PATH"}
    deadline = time.monotonic() + timeout
    try:
        ask = _ask_github if forge == "github" else _ask_gitlab
        user, cause = ask(host, account, deadline)
    except Unreachable:
        return {**answer, "cause": f"{host} did not answer within {timeout:g} s; nothing was saved"}
    if user is None:
        return {**answer, "cause": cause}
    saved = dv.save_forge_account(root, account)
    return {**answer, "accepted": True, "saved": str(saved),
            "warnings": _warnings(root, forge, host, account, user)}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--account", required=True)
    parser.add_argument("--repo", default=None)
    args = parser.parse_args(argv)
    root = ac.git_root(Path(args.repo)) if args.repo else ac.git_root()
    if root is None:
        sys.stderr.write("forge_account_check: run inside a git checkout, or name one with --repo\n")
        return 2
    try:
        answer = check_forge_account(root, args.account)
    except (ac.ConfigError, helper.AccountError, ValueError) as problem:
        sys.stderr.write(f"forge_account_check: {problem}\n")
        return 2
    sys.stdout.write(json.dumps(answer, indent=2) + "\n")
    return 0 if answer["accepted"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
