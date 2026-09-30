"""The user-scoped `tracker` MCP server entry `setup_secrets.py` writes into the
harness config, and which existing entries count as afk's own.

Split out of `setup_secrets.py` (which runs on import) so a test can drive it.
"""
from __future__ import annotations

import json
from pathlib import Path

MCP_KEY = "tracker"
LEGACY_MCP_KEY = "jira"        # a machine set up before the server was renamed

# How afk's own server shows up in an entry's args: a direct path (both names it
# has had) or the launcher script of `.mcp.json`.
_TAILS = ("mcp-servers/tracker/server.py", "mcp-servers/jira/server.py")
_LAUNCHER_MARK = '"mcp-servers", "tracker", "server.py"'


def is_afk_entry(entry) -> bool:
    """Whether `entry` starts afk's tracker server. An unrelated server that
    happens to be named `jira` is not afk's, so it is never reused or removed."""
    if not isinstance(entry, dict):
        return False
    for arg in entry.get("args") or []:
        text = str(arg)
        if _LAUNCHER_MARK in text or text.replace("\\", "/").endswith(_TAILS):
            return True
    return False


def prior_env(servers: dict) -> dict:
    """The env block of the entry a re-run should update in place."""
    legacy = servers.get(LEGACY_MCP_KEY)
    prior = servers.get(MCP_KEY) or (legacy if is_afk_entry(legacy) else None)
    return dict(prior.get("env") or {}) if isinstance(prior, dict) else {}


def _in_harness_cache(root: Path) -> bool:
    parts = root.resolve().parts
    return any(a == "plugins" and b == "cache" for a, b in zip(parts, parts[1:]))


def entry(env: dict, plugin_root: Path, python: str) -> dict:
    """The registration: the plugin's own `.mcp.json` launcher, so the server
    starts with no plugin-root variable in the environment.

    Under a harness cache the placeholder is dropped and the launcher finds the
    newest installed version, so a plugin update needs no re-run of setup. A
    checkout outside a cache has nothing to find, so its root is passed.
    """
    launcher = json.loads((plugin_root / ".mcp.json").read_text(encoding="utf-8"))
    args = list(launcher["mcpServers"][MCP_KEY]["args"][:-1])   # the last arg is the root placeholder
    if not _in_harness_cache(plugin_root):
        args.append(str(plugin_root))
    # Absolute interpreter: a fresh install is absent from an older process's PATH.
    return {"type": "stdio", "command": python, "args": args, "env": env}


def register(servers: dict, env: dict, plugin_root: Path, python: str) -> dict:
    """`servers` with the tracker entry written; afk's own legacy `jira` entry
    is dropped, any other server is left exactly as it was."""
    result = dict(servers)
    result[MCP_KEY] = entry(env, plugin_root, python)
    if is_afk_entry(result.get(LEGACY_MCP_KEY)):
        del result[LEGACY_MCP_KEY]
    return result
