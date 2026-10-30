"""Jira values: find them as v1 does, store them as v1 does, never show the token.

Lookup order (SDD §5 Secrets): the environment, then the tracker entry in the
Claude user config (`~/.claude.json`), then the Codex config
(`[mcp_servers.tracker.env]`).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Mapping

from places import Places, write_atomic
import v1_facts

KEYS = ("JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN")
SECRET = "JIRA_API_TOKEN"


def _tracker_env(obj) -> dict | None:
    """The first `tracker` server's env block, at any depth (v1's walk)."""
    if isinstance(obj, dict):
        server = obj.get(v1_facts.TRACKER_SERVER)
        if isinstance(server, dict) and isinstance(server.get("env"), dict):
            return server["env"]
        for value in obj.values():
            found = _tracker_env(value)
            if found:
                return found
    return None


def _claude_env(places: Places) -> dict | None:
    try:
        return _tracker_env(json.loads(places.claude_user_config.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return None


def _codex_env(places: Places) -> dict | None:
    try:
        import tomllib

        data = tomllib.loads(places.codex_config.read_text(encoding="utf-8"))
    except (OSError, ValueError, ImportError):
        return None
    return _tracker_env(data.get("mcp_servers") or {})


def lookup(places: Places, env: Mapping[str, str]) -> dict[str, tuple[str, str]]:
    """key -> (value, source) for each key some source resolves."""
    found = {k: (env[k], "environment") for k in KEYS if env.get(k)}
    for source, block in (("claude user config", _claude_env(places)),
                          ("codex config", _codex_env(places))):
        for key in KEYS:
            if block and key not in found and block.get(key):
                found[key] = (str(block[key]), source)
    return found


def status(places: Places, env: Mapping[str, str]) -> dict:
    """Which keys resolve and from where; the values stay out of the answer."""
    found = lookup(places, env)
    return {"complete": len(found) == len(KEYS),
            "sources": {k: (found[k][1] if k in found else None) for k in KEYS}}


def store_jira_values(places: Places, values: Mapping[str, str],
                      set_user_env: Callable[[str, str], None] | None) -> dict:
    """Write the 3 values where v1 keeps them; back up a file before its edit.

    The v1 tracker entry in the Claude user config is the target when it
    exists; otherwise the user environment, the first source of the lookup.
    """
    path = places.claude_user_config
    try:
        config = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    except ValueError:
        return {"ok": False, "error": {"code": "bad-config",
                                       "reason": f"{path} is not valid JSON"}}
    block = _tracker_env(config) if config else None
    if block is not None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        saved = places.backup / "claude-user-config" / f"claude.json.{stamp}"
        saved.parent.mkdir(parents=True, exist_ok=True)
        saved.write_bytes(path.read_bytes())
        block.update({k: values[k] for k in KEYS})
        write_atomic(path, (json.dumps(config, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
        return {"ok": True, "stored_in": "claude user config", "backup": str(saved)}
    if set_user_env is None:
        return {"ok": False, "error": {
            "code": "no-store",
            "reason": "no v1 tracker entry and no user environment store on this system; "
                      "export JIRA_BASE_URL, JIRA_EMAIL and JIRA_API_TOKEN in your shell profile"}}
    for key in KEYS:
        set_user_env(key, values[key])
    return {"ok": True, "stored_in": "user environment"}


def windows_user_env_setter(name: str, value: str) -> None:
    import winreg

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)


def ask_values(current: Mapping[str, tuple[str, str]], ask: Callable[[str], str],
               ask_secret: Callable[[str], str]) -> dict:
    """Ask for the 3 values in the developer's own terminal. Enter keeps a value."""
    values = {}
    for key, prompt in (("JIRA_BASE_URL", "Jira base URL (https://<site>.atlassian.net)"),
                        ("JIRA_EMAIL", "Jira account email")):
        old = current.get(key, ("", ""))[0]
        answer = ask(f"{prompt} [{old}]: " if old else f"{prompt}: ").strip()
        values[key] = (answer or old).rstrip("/") if key == "JIRA_BASE_URL" else (answer or old)
    has_token = SECRET in current
    token = ask_secret("Jira API token (hidden; Enter keeps the stored one): " if has_token
                       else "Jira API token (hidden): ").strip()
    values[SECRET] = token or (current[SECRET][0] if has_token else "")
    if not values["JIRA_BASE_URL"].startswith("https://"):
        raise ValueError("the base URL must start with https://")
    if "@" not in values["JIRA_EMAIL"]:
        raise ValueError("the email has no @")
    if not values[SECRET]:
        raise ValueError("the token is empty")
    return values
