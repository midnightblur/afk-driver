#!/usr/bin/env afk-python
"""The forge account a repository's forge calls act as: its host and account name, never a token.

    host_and_account(root) -> (host, account)
    token_variable(host)   -> "GH_TOKEN" | "GH_ENTERPRISE_TOKEN"
    afk-python forge_account.py [--checkout DIR]   ->   three lines: host, account, token variable

The host is the forge remote's host from the protected-branch lookup's `facts`
(`scripts/protected-lookup.py`); an SSH alias host is resolved with `ssh -G`.
The account is `developer.forgeAccount` through the settings reader. Either is
"" when unknown (no remote, no account set). Each forge wrapper fetches the
account's token itself, right before its own call, and passes it in the
variable `token_variable` names: gh reads `GH_TOKEN` for `github.com` and a
`ghe.com` host, `GH_ENTERPRISE_TOKEN` for an Enterprise Server host.

Exit codes: 0 answered; 2 the repository's settings could not be read (the
caller then refuses its forge call rather than act as the default login).
"""
from __future__ import annotations

import argparse
import importlib.util
import re
import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
SSH_TIMEOUT = 5.0


def _load(name: str, file: str):
    spec = importlib.util.spec_from_file_location(name, _HERE / file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


afk_config = _load("afk_config_for_forge_account", "afk-config.py")
_lookup = _load("afk_protected_lookup_for_forge_account", "protected-lookup.py")


class AccountError(Exception):
    """The repository's settings could not be read, so its account is unknown."""


def _ssh_host(alias: str) -> str:
    """The real host an SSH alias names, from `ssh -G`; the alias itself when ssh cannot tell."""
    try:
        done = subprocess.run(["ssh", "-G", alias], capture_output=True, text=True,
                              timeout=SSH_TIMEOUT, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return alias
    found = re.search(r"^hostname (\S+)", done.stdout, re.M) if done.returncode == 0 else None
    return found.group(1).lower() if found else alias


def host_and_account(root: Path | None = None) -> tuple[str, str]:
    """`(host, account)` for the repository at `root` (default: the current one); never a token."""
    root = afk_config.git_root(root) if root is not None else afk_config.project_root()
    if root is None:
        return "", ""
    try:
        account = afk_config.developer_value(afk_config.load(root), "forgeAccount", root) or ""
    except afk_config.ConfigError as problem:
        raise AccountError(str(problem)) from problem
    shared = afk_config.shared_overlay(root)
    host = _lookup.facts(root, shared.parent.parent, "")["host"] if shared is not None else ""
    if host and "." not in host:
        host = _ssh_host(host)
    return host, account.strip()


def token_variable(host: str) -> str:
    """The variable gh reads a token from for `host`."""
    host = (host or "github.com").lower()
    public = host == "github.com" or host == "ghe.com" or host.endswith(".ghe.com")
    return "GH_TOKEN" if public else "GH_ENTERPRISE_TOKEN"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--checkout", default=None)
    args = parser.parse_args(argv)
    try:
        host, account = host_and_account(Path(args.checkout) if args.checkout else None)
    except AccountError as problem:
        sys.stderr.write(f"forge account: the settings cannot be read: {problem}\n")
        return 2
    sys.stdout.write(f"{host}\n{account}\n{token_variable(host)}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
