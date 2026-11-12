"""The MCP server entries setup writes for Claude and Codex, each file backed up before the write.

Claude: user scope, `mcpServers` in `~/.claude.json`. Codex: `[mcp_servers.<name>]` in `~/.codex/config.toml`.
Every other key in both files stays as it is.
"""

from __future__ import annotations

import json
import re
import shutil
import tomllib
from pathlib import Path
from typing import Callable, Mapping

from places import PROVIDERS, Places, write_atomic


def _file(places: Places, provider: str) -> Path:
    return places.claude_user_config if provider == "claude" else places.codex_config


def _installed(places: Places, provider: str) -> bool:
    if provider == "claude":
        return places.claude_dir.exists() or places.claude_user_config.exists()
    return places.codex_dir.exists()


def backup_folder(places: Places) -> Path:
    return places.backup / "mcp"


def _owned_file(places: Places, provider: str) -> Path:
    return backup_folder(places) / provider / "owned.txt"


def _owned(places: Places, provider: str) -> set[str]:
    """The entry names setup wrote into the harness file of `provider`."""
    path = _owned_file(places, provider)
    return set(path.read_text(encoding="utf-8").split()) if path.exists() else set()


# ----------------------------------------------------------------- Claude

def _claude_servers(text: str) -> dict:
    data = json.loads(text) if text.strip() else {}
    if not isinstance(data, dict) or not isinstance(data.get("mcpServers", {}), dict):
        raise ValueError("the Claude user config is not a JSON object with an mcpServers object")
    return data


def _claude_entry(entry: Mapping) -> dict:
    return {"type": "stdio", "command": entry["command"], "args": list(entry["args"]), "env": {}}


def _claude_put(text: str, entries: Mapping[str, Mapping]) -> str:
    data = _claude_servers(text)
    data.setdefault("mcpServers", {}).update({name: _claude_entry(e) for name, e in entries.items()})
    return json.dumps(data, indent=2) + "\n"


def _claude_drop(text: str, names) -> str:
    data = _claude_servers(text)
    for name in names:
        data.get("mcpServers", {}).pop(name, None)
    return json.dumps(data, indent=2) + "\n"


def _claude_names(text: str) -> set[str]:
    return set(_claude_servers(text).get("mcpServers", {}))


def _claude_has(text: str, entries: Mapping[str, Mapping]) -> bool:
    servers = _claude_servers(text).get("mcpServers", {})
    return all(servers.get(name) == _claude_entry(e) for name, e in entries.items())


# ------------------------------------------------------------------ Codex

def _codex_header(name: str) -> re.Pattern:
    key = re.escape(name)
    return re.compile(rf'^\s*\[\s*mcp_servers\s*\.\s*(?:"{key}"|{key})\s*(?:\.[^\]]*)?\]\s*$')


def _codex_drop(text: str, names) -> str:
    """The config without the tables of `names`, sub-tables included."""
    heads = [_codex_header(name) for name in names]
    kept, skipping = [], False
    for line in text.splitlines(keepends=True):
        body = line.rstrip("\r\n")
        if body.lstrip().startswith("["):
            skipping = any(head.match(body) for head in heads)
        if not skipping:
            kept.append(line)
    return "".join(kept)


def _codex_put(text: str, entries: Mapping[str, Mapping]) -> str:
    eol = "\r\n" if "\r\n" in text else "\n"
    out = _codex_drop(text, entries).rstrip("\r\n")
    for name, entry in entries.items():
        # A JSON string is a valid TOML basic string.
        block = [f"[mcp_servers.{json.dumps(name)}]", f"command = {json.dumps(entry['command'])}",
                 f"args = [{', '.join(json.dumps(a) for a in entry['args'])}]"]
        out += (eol * 2 if out else "") + eol.join(block)
    return out + eol


def _codex_has(text: str, entries: Mapping[str, Mapping]) -> bool:
    servers = tomllib.loads(text).get("mcp_servers", {})
    return all(servers.get(name) == {"command": e["command"], "args": list(e["args"])} for name, e in entries.items())


def _codex_names(text: str) -> set[str]:
    return set(tomllib.loads(text).get("mcp_servers", {}))


EDITS = {"claude": (_claude_put, _claude_has, _claude_drop, _claude_names),
         "codex": (_codex_put, _codex_has, _codex_drop, _codex_names)}


# ------------------------------------------------------------------ verbs

def register(places: Places, entries: Mapping[str, Mapping], lock: Callable[[Path], None]) -> dict:
    """Write `entries` for each installed harness. Each file is copied to the backup folder before its write;
    an entry the harness file does not read back after the write restores that copy (`register-failed`).
    An entry of the same name that setup did not write refuses `register-failed`, with nothing written.
    `lock` limits the backup folder to the current user first: both files can hold the Jira token."""
    done: dict = {}
    locked = False
    for provider in PROVIDERS:
        path = _file(places, provider)
        if not _installed(places, provider):
            done[provider] = {"action": "not-installed"}
            continue
        put, has, _drop, names = EDITS[provider]
        before = path.read_bytes() if path.exists() else None
        text = before.decode("utf-8") if before is not None else ""
        try:
            if before is not None and has(text, entries):
                done[provider] = {"action": "present", "file": str(path)}
                continue
            foreign = sorted((names(text) & set(entries)) - _owned(places, provider))
            if foreign:
                return _failed(done, provider, f"{path} has an entry {', '.join(foreign)} that setup did not write; "
                                               "rename or remove it, then run this step again; nothing was written")
            after = put(text, entries)
        except (ValueError, tomllib.TOMLDecodeError) as exc:
            return _failed(done, provider, f"{path}: {exc}; nothing was written")
        if not locked:
            try:
                lock(places.backup)
            except OSError as exc:
                return _failed(done, provider, f"{exc}; nothing was written")
            locked = True
        saved = backup_folder(places) / provider / (path.name if before is not None else path.name + ".absent")
        write_atomic(saved, before or b"")
        write_atomic(path, after.encode("utf-8"))
        try:
            read_back = has(path.read_bytes().decode("utf-8"), entries)
        except (ValueError, OSError, tomllib.TOMLDecodeError) as exc:
            read_back, why = False, str(exc)
        else:
            why = "the entry does not read back"
        if not read_back:
            _restore(path, before)
            return _failed(done, provider, f"{path}: {why}; the backup was restored")
        write_atomic(_owned_file(places, provider),
                     "\n".join(sorted(_owned(places, provider) | set(entries))).encode("utf-8") + b"\n")
        done[provider] = {"action": "written", "file": str(path), "backup": str(saved)}
    return {"ok": True, **done}


def _restore(path: Path, before: bytes | None) -> None:
    if before is None:
        path.unlink(missing_ok=True)
    else:
        write_atomic(path, before)


def _failed(done: dict, provider: str, reason: str) -> dict:
    return {"ok": False, **done, provider: {"action": "failed"},
            "error": {"code": "register-failed", "reason": f"{provider}: {reason}"}}


def unregister(places: Places, names) -> dict[str, str]:
    """Remove the entries of `names` that setup wrote; every other line the harnesses wrote since stays."""
    done = {}
    for provider in PROVIDERS:
        path = _file(places, provider)
        drop = EDITS[provider][2]
        mine = sorted(set(names) & _owned(places, provider))
        try:
            text = path.read_bytes().decode("utf-8") if path.exists() else ""
            after = drop(text, mine) if text and mine else text
            if after == text or (provider == "claude" and _claude_servers(after) == _claude_servers(text)):
                done[provider] = "absent"
                continue
            write_atomic(path, after.encode("utf-8"))
        except (ValueError, OSError):
            done[provider] = "failed"
            continue
        done[provider] = "removed"
    if "failed" not in done.values():
        shutil.rmtree(backup_folder(places), ignore_errors=True)
    return done
