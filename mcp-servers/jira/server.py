"""Jira MCP server — REST API v3, API-token auth.

Tools: jira_get, jira_search, jira_transitions, jira_transition,
jira_changelog, jira_comment, jira_attachments, jira_create, jira_edit.

Registration: user-scoped `jira` entry in ~/.claude.json `mcpServers`
(command: python, args: [<absolute path to this file>], env: the S1
credential variables). MUST stay user-scoped under the key `jira` — a
plugin-bundled MCP registration renames the tools to
`mcp__plugin_afk_jira__*`, breaking every `mcp__jira__*` reference.

Config via environment variables (the registration's `env` block):
  JIRA_BASE_URL   e.g. https://<site>.atlassian.net
  JIRA_EMAIL      Atlassian account email
  JIRA_API_TOKEN  Atlassian API token
  JIRA_DEFAULT_PROJECT  (optional)
"""
from __future__ import annotations

import os
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

BASE_URL = os.environ.get("JIRA_BASE_URL", "").rstrip("/")
EMAIL = os.environ.get("JIRA_EMAIL", "")
TOKEN = os.environ.get("JIRA_API_TOKEN", "")
DEFAULT_PROJECT = os.environ.get("JIRA_DEFAULT_PROJECT", "")
DEFAULT_FIELDS = "summary,status,issuetype,assignee,reporter,priority,created,updated,labels,components"

if not (BASE_URL and EMAIL and TOKEN):
    raise SystemExit("JIRA_BASE_URL, JIRA_EMAIL, and JIRA_API_TOKEN must be set")

mcp = FastMCP("jira")
_client = httpx.Client(
    base_url=BASE_URL,
    auth=(EMAIL, TOKEN),
    headers={"Accept": "application/json", "Content-Type": "application/json"},
    timeout=30.0,
)


def _req(method: str, path: str, json: Any = None, params: dict | None = None) -> Any:
    r = _client.request(method, path, json=json, params=params)
    if r.status_code >= 400:
        return {"error": True, "status": r.status_code, "body": r.text}
    if not r.content:
        return {"ok": True}
    try:
        return r.json()
    except Exception:
        return {"raw": r.text}


def _adf(text: str) -> dict:
    """Wrap plain text in Atlassian Document Format."""
    return {
        "type": "doc",
        "version": 1,
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}],
    }


@mcp.tool()
def jira_get(ticket_key: str, fields: str = "") -> Any:
    """Fetch a Jira issue. `fields` is a comma-separated list; empty = default set."""
    return _req("GET", f"/rest/api/3/issue/{ticket_key}", params={"fields": fields or DEFAULT_FIELDS})


@mcp.tool()
def jira_search(jql: str, max_results: int = 50, fields: list[str] | None = None) -> Any:
    """Search issues with JQL."""
    body = {
        "jql": jql,
        "maxResults": max_results,
        "fields": fields or ["summary", "status", "issuetype", "assignee", "priority", "created", "updated"],
    }
    return _req("POST", "/rest/api/3/search/jql", json=body)


@mcp.tool()
def jira_transitions(ticket_key: str) -> Any:
    """List available workflow transitions for an issue."""
    return _req("GET", f"/rest/api/3/issue/{ticket_key}/transitions")


@mcp.tool()
def jira_transition(ticket_key: str, transition_id: str) -> Any:
    """Transition an issue to a new status by transition id."""
    return _req("POST", f"/rest/api/3/issue/{ticket_key}/transitions", json={"transition": {"id": transition_id}})


@mcp.tool()
def jira_changelog(ticket_key: str) -> Any:
    """Get an issue with its change history expanded."""
    return _req("GET", f"/rest/api/3/issue/{ticket_key}", params={"expand": "changelog"})


@mcp.tool()
def jira_comment(ticket_key: str, text: str) -> Any:
    """Add a plain-text comment to an issue."""
    return _req("POST", f"/rest/api/3/issue/{ticket_key}/comment", json={"body": _adf(text)})


@mcp.tool()
def jira_attachments(ticket_key: str) -> Any:
    """List attachments on an issue (id, filename, mimeType, size)."""
    data = _req("GET", f"/rest/api/3/issue/{ticket_key}", params={"fields": "attachment"})
    if isinstance(data, dict) and "fields" in data:
        atts = data.get("fields", {}).get("attachment", []) or []
        return [
            {
                "id": a.get("id"),
                "filename": a.get("filename"),
                "mimeType": a.get("mimeType"),
                "size": a.get("size"),
                "created": a.get("created"),
                "author": (a.get("author") or {}).get("displayName"),
                "content": a.get("content"),
            }
            for a in atts
        ]
    return data


@mcp.tool()
def jira_create(
    summary: str,
    issue_type: str,
    project: str = "",
    description: str = "",
    epic: str = "",
    fix_version: str = "",
    assignee: str = "",
    status: str = "",
) -> Any:
    """Create an issue. Optionally assign and transition after creation.

    `project` defaults to JIRA_DEFAULT_PROJECT if unset.
    `assignee` is a display-name / email query, resolved via assignable-user search.
    `status` is the target transition name after creation.
    """
    proj = project or DEFAULT_PROJECT
    if not proj:
        return {"error": True, "message": "project is required (no JIRA_DEFAULT_PROJECT set)"}

    fields: dict[str, Any] = {
        "project": {"key": proj},
        "issuetype": {"name": issue_type},
        "summary": summary,
    }
    if description:
        fields["description"] = _adf(description)
    if epic:
        fields["parent"] = {"key": epic}
    if fix_version:
        fields["fixVersions"] = [{"name": fix_version}]

    created = _req("POST", "/rest/api/3/issue", json={"fields": fields})
    key = created.get("key") if isinstance(created, dict) else None
    if not key:
        return created

    result: dict[str, Any] = {"key": key, "id": created.get("id")}

    if assignee:
        users = _req(
            "GET",
            "/rest/api/3/user/assignable/search",
            params={"query": assignee, "project": proj},
        )
        account_id = users[0]["accountId"] if isinstance(users, list) and users else None
        if account_id:
            _req("PUT", f"/rest/api/3/issue/{key}", json={"fields": {"assignee": {"accountId": account_id}}})
            result["assignee"] = {"accountId": account_id, "query": assignee}
        else:
            result["assignee_warning"] = f"could not resolve '{assignee}'"

    if status:
        trs = _req("GET", f"/rest/api/3/issue/{key}/transitions")
        match = None
        for t in (trs or {}).get("transitions", []) if isinstance(trs, dict) else []:
            if t.get("name", "").lower() == status.lower():
                match = t["id"]
                break
        if match:
            _req("POST", f"/rest/api/3/issue/{key}/transitions", json={"transition": {"id": match}})
            result["transitioned_to"] = status
        else:
            result["status_warning"] = f"no transition named '{status}'"

    return result


@mcp.tool()
def jira_edit(ticket_key: str, fields: dict[str, Any]) -> Any:
    """Update issue fields. Pass a fields dict in Jira's native shape, e.g.
    {"priority": {"name": "High"}, "labels": ["a","b"]}.
    """
    return _req("PUT", f"/rest/api/3/issue/{ticket_key}", json={"fields": fields})


if __name__ == "__main__":
    mcp.run()
