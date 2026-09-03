"""tracker MCP server — the nine tracker operations, routed to the configured kind.

The server registers the same nine tools whatever the repository uses, so a
skill's prose never changes with the tracker. `tracker:` in `.afk/config.yaml`
picks the adapter under `adapters/tracker/<kind>/`, and each kind's `api.py`
answers `call(operation, payload)` (ADAPTERS.md).

`tracker: none` is a valid answer, not an error: every tool then returns
`{"unsupported": true, "reason": ...}` and the skill writes through the `notes`
adapter instead. A missing tool would leave a skill guessing; a refusal that
names the configuration key does not.

Registration: the plugin's `.mcp.json` / `.mcp.codex.json`, server name
`tracker`, with the plugin root passed as the first argument. Credentials stay
in that registration's `env` block — a configuration file holds variable NAMES,
never values.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP


def _plugin_root() -> Path:
    """The toolkit root. Passed by the registration; the environment is the
    fallback for a hand-started server. Never searched for — a cache scan finds
    a stale copy as readily as the live one."""
    if len(sys.argv) > 1 and sys.argv[1]:
        return Path(sys.argv[1]).resolve()
    for name in ("AFK_PLUGIN_ROOT", "CLAUDE_PLUGIN_ROOT", "PLUGIN_ROOT"):
        value = os.environ.get(name)
        if value:
            return Path(value).resolve()
    raise SystemExit(
        "tracker MCP server: no plugin root. Pass it as the first argument "
        "(the plugin's .mcp.json does) or set AFK_PLUGIN_ROOT.")


PLUGIN_ROOT = _plugin_root()


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _adapter():
    """The configured kind's api.py, loaded once at start-up so a misconfigured
    tracker fails where a human is watching rather than on the first tool call."""
    config = _load(PLUGIN_ROOT / "scripts" / "afk-config.py", "afk_config")
    kind = config.get(config.load(Path.cwd()), "tracker") or "none"
    api = PLUGIN_ROOT / "adapters" / "tracker" / str(kind) / "api.py"
    if not api.is_file():
        raise SystemExit(
            f"tracker MCP server: unknown tracker adapter `{kind}` "
            f"(set by `tracker:` in .afk/config.yaml); no {api}")
    return str(kind), _load(api, "afk_tracker_api")


KIND, API = _adapter()

mcp = FastMCP("tracker")


def _call(operation: str, **payload: Any) -> Any:
    return API.call(operation, {k: v for k, v in payload.items() if v not in (None, "")})


@mcp.tool()
def tracker_get(ticket_key: str, fields: str = "") -> Any:
    """Fetch one work item. `fields` is a comma-separated list; empty = the
    tracker's default set."""
    return _call("tracker_get", ticket_key=ticket_key, fields=fields)


@mcp.tool()
def tracker_search(query: str, max_results: int = 50, fields: list[str] | None = None) -> Any:
    """Search work items. `query` is in the tracker's own query language — JQL
    for Jira, the issue-search syntax for GitHub Issues."""
    return _call("tracker_search", query=query, max_results=max_results, fields=fields)


@mcp.tool()
def tracker_transitions(ticket_key: str) -> Any:
    """List the state changes available on a work item right now."""
    return _call("tracker_transitions", ticket_key=ticket_key)


@mcp.tool()
def tracker_transition(ticket_key: str, transition_id: str) -> Any:
    """Move a work item to a new state by transition id (from tracker_transitions)."""
    return _call("tracker_transition", ticket_key=ticket_key, transition_id=transition_id)


@mcp.tool()
def tracker_changelog(ticket_key: str) -> Any:
    """The work item with its change history."""
    return _call("tracker_changelog", ticket_key=ticket_key)


@mcp.tool()
def tracker_comment(ticket_key: str, text: str) -> Any:
    """Add a plain-text comment to a work item."""
    return _call("tracker_comment", ticket_key=ticket_key, text=text)


@mcp.tool()
def tracker_attachments(ticket_key: str) -> Any:
    """List the files attached to a work item (id, filename, mimeType, size)."""
    return _call("tracker_attachments", ticket_key=ticket_key)


@mcp.tool()
def tracker_create(
    summary: str,
    issue_type: str,
    project: str = "",
    description: str = "",
    parent: str = "",
    fix_version: str = "",
    assignee: str = "",
    status: str = "",
) -> Any:
    """Create a work item, optionally assigning it and moving it to a state.

    `issue_type` and `status` are the tracker's own names — take them from
    `tracker.issue-types` and `tracker.transitions` in `.afk/config.yaml` rather
    than inventing them. `parent` is the parent work item's key.
    """
    return _call("tracker_create", summary=summary, issue_type=issue_type,
                 project=project, description=description, parent=parent,
                 fix_version=fix_version, assignee=assignee, status=status)


@mcp.tool()
def tracker_edit(ticket_key: str, fields: dict[str, Any]) -> Any:
    """Update fields on a work item. `fields` is in the tracker's native shape,
    e.g. {"priority": {"name": "High"}, "labels": ["a","b"]} for Jira."""
    return _call("tracker_edit", ticket_key=ticket_key, fields=fields)


if __name__ == "__main__":
    mcp.run()
