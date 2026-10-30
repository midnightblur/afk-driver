"""Jira values: find them as v1 does, store them as v1 does, never show the token.

Lookup order (SDD §5 Secrets): the environment, then the tracker entry in the
Claude user config (`~/.claude.json`), then the Codex config
(`[mcp_servers.tracker.env]`).

Switch-back restores what `store_jira_values` changed. Its backups hold a token
in plain text, so no answer, log or error carries a value from them.
"""

from __future__ import annotations

import contextlib
import json
from pathlib import Path
from typing import Callable, Mapping, NamedTuple

from places import Places, backup_once, write_atomic
from tools import broadcast_environment_change
import setup_v1_facts

KEYS = ("JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN")
SECRET = "JIRA_API_TOKEN"


class UserEnv(NamedTuple):
    """The user environment store of this system."""

    get: Callable[[str], str | None]
    set: Callable[[str, str], None]
    delete: Callable[[str], None]


def _claude_backup(places: Places) -> Path:
    return places.backup / "claude-user-config" / "claude.json"


def _env_backup(places: Places) -> Path:
    return places.backup / "user-env" / "values.json"


def _tracker_env(obj) -> dict | None:
    """The first `tracker` server's env block, at any depth (v1's walk)."""
    if isinstance(obj, dict):
        server = obj.get(setup_v1_facts.TRACKER_SERVER)
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


def store_jira_values(places: Places, values: Mapping[str, str], user_env: UserEnv | None) -> dict:
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
        saved = _claude_backup(places)
        backup_once(path, saved)
        block.update({k: values[k] for k in KEYS})
        write_atomic(path, (json.dumps(config, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
        return {"ok": True, "stored_in": "claude user config", "backup": str(saved)}
    if user_env is None:
        return {"ok": False, "error": {
            "code": "no-store",
            "reason": "no v1 tracker entry and no user environment store on this system; "
                      "export JIRA_BASE_URL, JIRA_EMAIL and JIRA_API_TOKEN in your shell profile"}}
    _keep_env_values(places, user_env)
    for key in KEYS:
        user_env.set(key, values[key])
    return {"ok": True, "stored_in": "user environment"}


def _read_env_backup(saved: Path) -> dict:
    kept = json.loads(saved.read_text(encoding="utf-8"))
    if not isinstance(kept, dict):
        raise ValueError(f"{saved} must hold one JSON object")
    for key, entry in kept.items():
        if not (isinstance(entry, dict) and (entry == {"absent": True} or isinstance(entry.get("value"), str))):
            raise ValueError(f"{saved}: the entry of {key} is not readable")
    return kept


def _keep_env_values(places: Places, user_env: UserEnv) -> None:
    """Record each key's value, or that it was absent. A recorded key keeps its first record."""
    saved = _env_backup(places)
    kept = _read_env_backup(saved) if saved.exists() else {}
    fresh = {}
    for key in KEYS:
        if key not in kept:
            value = user_env.get(key)
            fresh[key] = {"absent": True} if value is None else {"value": value}
    if fresh:
        write_atomic(saved, json.dumps({**kept, **fresh}, indent=1).encode("utf-8"), private=True)


def _drop_backup(saved: Path) -> None:
    saved.unlink()
    with contextlib.suppress(OSError):
        saved.parent.rmdir()


def _put_back_tracker_values(path: Path, before: bytes) -> str:
    """Only the Jira keys of the tracker entry change; the harness keeps every later write."""
    old_env = _tracker_env(json.loads(before.decode("utf-8")))
    current = json.loads(path.read_bytes().decode("utf-8"))
    env = _tracker_env(current)
    if old_env is None or env is None:
        return "no-entry"
    for key in KEYS:
        if key in old_env:
            env[key] = old_env[key]
        else:
            env.pop(key, None)
    if current == json.loads(before.decode("utf-8")):
        write_atomic(path, before)
        return "restored"
    write_atomic(path, (json.dumps(current, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    return "merged"


def restore_claude_user_config(places: Places) -> dict:
    saved = _claude_backup(places)
    if not saved.exists():
        return {"action": "no-backup"}
    path = places.claude_user_config
    try:
        before = saved.read_bytes()
        if path.exists():
            action = _put_back_tracker_values(path, before)
        else:
            write_atomic(path, before)
            action = "restored"
        _drop_backup(saved)
    except (ValueError, OSError) as exc:
        return {"action": "failed", "reason": f"{type(exc).__name__} on {path}", "backup": str(saved)}
    return {"action": action}


def restore_user_env(places: Places, user_env: UserEnv | None) -> dict:
    """Put each recorded value back, or delete a key that was absent. A failure keeps the backup."""
    saved = _env_backup(places)
    if not saved.exists():
        return {"action": "no-backup"}
    if user_env is None:
        return {"action": "failed", "reason": "no user environment store on this system", "backup": str(saved)}
    try:
        kept = _read_env_backup(saved)
    except (ValueError, OSError) as exc:
        return {"action": "failed", "reason": f"{type(exc).__name__} on the backup", "backup": str(saved)}
    keys = {}
    for key, entry in kept.items():
        try:
            if "value" in entry:
                user_env.set(key, entry["value"])
                keys[key] = "restored"
            else:
                user_env.delete(key)
                keys[key] = "deleted"
        except OSError as exc:
            keys[key] = f"failed: {type(exc).__name__}"
    if any(state.startswith("failed") for state in keys.values()):
        return {"action": "failed", "reason": "a key was not restored", "keys": keys, "backup": str(saved)}
    try:
        _drop_backup(saved)
    except OSError as exc:
        return {"action": "failed", "reason": f"{type(exc).__name__} on the backup", "keys": keys, "backup": str(saved)}
    return {"action": "restored", "keys": keys}


def windows_user_env_setter(name: str, value: str) -> None:
    import winreg

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
    broadcast_environment_change()


def windows_user_env_getter(name: str) -> str | None:
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_QUERY_VALUE) as key:
            return str(winreg.QueryValueEx(key, name)[0])
    except FileNotFoundError:
        return None


def windows_user_env_deleter(name: str) -> None:
    import winreg

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE) as key:
        with contextlib.suppress(FileNotFoundError):
            winreg.DeleteValue(key, name)
    broadcast_environment_change()


WINDOWS_USER_ENV = UserEnv(windows_user_env_getter, windows_user_env_setter, windows_user_env_deleter)


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
