"""The user-scoped `tracker` MCP server entry `setup_secrets.py` writes into the
harness config, and which existing entries count as afk's own.

Split out of `setup_secrets.py` (which runs on import) so a test can drive it.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

MCP_KEY = "tracker"
LEGACY_MCP_KEY = "jira"        # a machine set up before the server was renamed

# afk's own server under a harness cache: `plugins/cache/<market>/<plugin>/<version>/`.
_CACHE_SERVER = re.compile(
    r"/plugins/cache/[^/]+/(?:afk|afk-dev|afk-toolkit)/[^/]+/mcp-servers/(?:tracker|jira)/server\.py$")
_LAUNCHER_MARK = '"mcp-servers", "tracker", "server.py"'


def _posix(text: str) -> str:
    return text.replace("\\", "/")


def is_afk_entry(entry, plugin_root: Path) -> bool:
    """Whether `entry` starts afk's own tracker server: the launcher, a path
    under this plugin root, or a path in a harness cache of the `afk` plugin.

    A path ending `mcp-servers/jira/server.py` is not enough: another plugin
    ships a server by that name, and it is not afk's to reuse or remove.
    """
    if not isinstance(entry, dict):
        return False
    root = os.path.normcase(_posix(str(plugin_root.resolve())).rstrip("/") + "/")
    for arg in entry.get("args") or []:
        text = str(arg)
        if _LAUNCHER_MARK in text:
            return True
        path = _posix(text)
        if os.path.normcase(path).startswith(root) or _CACHE_SERVER.search(path):
            return True
    return False


def foreign_legacy(servers: dict, plugin_root: Path) -> bool:
    """A `jira` server is configured that is not afk's: setup leaves it alone."""
    legacy = servers.get(LEGACY_MCP_KEY)
    return isinstance(legacy, dict) and not is_afk_entry(legacy, plugin_root)


def prior_env(servers: dict, plugin_root: Path) -> dict:
    """The env block of the entry a re-run should update in place."""
    legacy = servers.get(LEGACY_MCP_KEY)
    prior = servers.get(MCP_KEY) or (legacy if is_afk_entry(legacy, plugin_root) else None)
    return dict(prior.get("env") or {}) if isinstance(prior, dict) else {}


def entry(env: dict, plugin_root: Path, python: str) -> dict:
    """The registration: the plugin's own `.mcp.json` launcher with this plugin
    root as its argument, so the server starts with no plugin-root variable in
    the environment. The root is versioned under a harness cache, so a plugin
    update needs setup run again."""
    launcher = json.loads((plugin_root / ".mcp.json").read_text(encoding="utf-8"))
    args = list(launcher["mcpServers"][MCP_KEY]["args"][:-1])   # the last arg is the root placeholder
    args.append(str(plugin_root))
    # Absolute interpreter: a fresh install is absent from an older process's PATH.
    return {"type": "stdio", "command": python, "args": args, "env": env}


def register(servers: dict, env: dict, plugin_root: Path, python: str) -> dict:
    """`servers` with the tracker entry written; afk's own legacy `jira` entry
    is dropped, any other server is left exactly as it was."""
    result = dict(servers)
    result[MCP_KEY] = entry(env, plugin_root, python)
    if is_afk_entry(result.get(LEGACY_MCP_KEY), plugin_root):
        del result[LEGACY_MCP_KEY]
    return result
