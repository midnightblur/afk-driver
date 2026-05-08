"""JiraWorld — in-memory state machine + workflow rules + fault injection.

Mirrors the subset of Jira Cloud the AFK driver depends on:

- ``POST /rest/api/3/search/jql`` — JQL search
- ``GET  /rest/api/3/issue/{key}`` — read fields
- ``GET  /rest/api/3/issue/{key}/transitions`` — list candidate transitions
- ``POST /rest/api/3/issue/{key}/transitions`` — execute transition
- ``PUT  /rest/api/3/issue/{key}`` — write fields
- ``POST /rest/api/3/issue/{key}/comment`` — add comment
- ``GET  /rest/api/3/myself`` — authenticated account id

The eight rules in the docstring of each helper section are drawn from Jira
rejections that have actually broken the driver. **Not a Jira simulator** —
adding a rule means a real bug happened. See ``TESTING.md``.

``FakeTransport`` implements ``afk_driver.jira_client.HttpTransport`` and
routes all calls into the world, applying queued faults first so tests can
exercise the runner's best-effort wrappers (``_try_jira`` / ``_try_sub``)
without needing real flaky network.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Optional

from afk_driver.jira_client import JiraError


# Custom-field IDs the runner / config use. Hard-coded here because real Jira
# also hard-codes them (the workflow validator looks them up by id).
CF_TARGET_BRANCH = "customfield_13706"
CF_MR_LINK = "customfield_12700"
CF_SRED_ELIGIBILITY = "customfield_14005"
CF_TIME_ESTIMATION = "customfield_14006"
CF_SRED_RATIONALE = "customfield_14003"  # rich-text — ADF only
CF_APLUS_CLARITY = "customfield_13894"

_GATE_FIELDS_FOR_REQUEST_CR_AND_MERGE = (
    CF_MR_LINK,
    CF_SRED_ELIGIBILITY,
    CF_TIME_ESTIMATION,
    CF_SRED_RATIONALE,
)

# Rich-text customfields whose values must be ADF documents (dict with
# ``type=="doc"``). Jira rejects a plain string with HTTP 400 + "Operation
# value must be an Atlassian Document".
_RICH_TEXT_FIELDS = frozenset({CF_SRED_RATIONALE})

# Workflow graph by status. Enhancement + SubTask share this graph; Bug
# diverges by skipping the Designing step (P2P-1228 empirical).
_GRAPH_DEFAULT: Mapping[str, list[tuple[str, str]]] = {
    "Dev-Pending": [
        ("Start Designing", "Dev-Designing"),
        ("Start Development", "Dev-Developing"),
        ("Request Development", "Dev-Pending"),
    ],
    "Dev-Designing": [
        ("Start Development", "Dev-Developing"),
        ("Request Development", "Dev-Pending"),
    ],
    "Dev-Developing": [
        ("Request CR & Merge", "Dev-CR/Merge"),
        ("Request Development", "Dev-Pending"),
    ],
    "Dev-CR/Merge": [
        ("Request Development", "Dev-Pending"),
    ],
}

_GRAPH_BUG: Mapping[str, list[tuple[str, str]]] = {
    "Dev-Pending": [
        ("Start Development", "Dev-Developing"),
        ("Request Development", "Dev-Pending"),
    ],
    "Dev-Designing": [
        ("Start Development", "Dev-Developing"),
        ("Request Development", "Dev-Pending"),
    ],
    "Dev-Developing": [
        ("Request CR & Merge", "Dev-CR/Merge"),
        ("Request Development", "Dev-Pending"),
    ],
    "Dev-CR/Merge": [
        ("Request Development", "Dev-Pending"),
    ],
}

_TRANSITION_IDS: Mapping[str, str] = {
    "Start Designing": "11",
    "Start Development": "21",
    "Request CR & Merge": "31",
    "Request Development": "41",
}


FaultMatcher = Callable[[str, str, Optional[dict], Optional[Mapping[str, str]]], bool]


@dataclass
class JiraIssue:
    key: str
    summary: str
    status: str
    issuetype: str  # "Enhancement" | "Bug" | "SubTask"
    parent_key: Optional[str] = None
    labels: list[str] = field(default_factory=list)
    fix_versions: list[str] = field(default_factory=list)
    components: list[str] = field(default_factory=list)
    assignee: Optional[dict] = None  # {"accountId": "..."} or None
    description: Optional[dict] = None  # ADF doc
    custom_fields: dict[str, Any] = field(default_factory=dict)
    comments: list[dict] = field(default_factory=list)


@dataclass
class JiraWorld:
    account_id: str = "fake-account-id-scenario"
    issues: dict[str, JiraIssue] = field(default_factory=dict)
    _faults: list[tuple[FaultMatcher, Any]] = field(default_factory=list)
    # Recorded events for assertion convenience (runner-seam tests already do
    # this on FakeJira; mirror the shape so scenarios can read at the same
    # granularity).
    events: list[tuple[str, str, Any]] = field(default_factory=list)

    def add_issue(self, issue: JiraIssue) -> JiraIssue:
        self.issues[issue.key] = issue
        return issue

    def queue_fault(self, matcher: FaultMatcher, response: Any) -> None:
        """Inject a one-shot fault. ``matcher(method, path, body, params)``
        receives the next request; first match consumes the entry. ``response``
        is either an Exception (raised) or a dict (returned as-if a 2xx body).
        """
        self._faults.append((matcher, response))


class FakeTransport:
    """``afk_driver.jira_client.HttpTransport`` impl over a JiraWorld.

    All routing happens here; JiraWorld is the data + rule store.
    """

    def __init__(self, world: JiraWorld) -> None:
        self.world = world
        self.calls: list[tuple[str, str, Optional[dict], Optional[Mapping[str, str]]]] = []

    def send(
        self,
        method: str,
        path: str,
        *,
        json_body: Optional[dict] = None,
        params: Optional[Mapping[str, str]] = None,
    ) -> dict:
        self.calls.append((method, path, json_body, dict(params) if params else None))
        # Faults take precedence over normal handling.
        for i, (matcher, response) in enumerate(self.world._faults):
            try:
                hit = matcher(method, path, json_body, params)
            except Exception:
                hit = False
            if hit:
                self.world._faults.pop(i)
                if isinstance(response, Exception):
                    raise response
                return response  # type: ignore[return-value]
        return _route(self.world, method, path, json_body, params)


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------


def _route(
    world: JiraWorld,
    method: str,
    path: str,
    body: Optional[dict],
    params: Optional[Mapping[str, str]],
) -> dict:
    if path == "/rest/api/3/myself" and method == "GET":
        return {"accountId": world.account_id}
    if path == "/rest/api/3/search/jql" and method == "POST":
        return _search(world, body or {})
    m = re.match(r"^/rest/api/3/issue/([^/]+)/transitions$", path)
    if m and method == "GET":
        return _list_transitions(world, m.group(1))
    if m and method == "POST":
        return _post_transition(world, m.group(1), body or {})
    m = re.match(r"^/rest/api/3/issue/([^/]+)/comment$", path)
    if m and method == "POST":
        return _post_comment(world, m.group(1), body or {})
    m = re.match(r"^/rest/api/3/issue/([^/]+)$", path)
    if m and method == "GET":
        return _get_issue(world, m.group(1))
    if m and method == "PUT":
        return _put_issue(world, m.group(1), body or {})
    raise JiraError(f"FakeTransport: unhandled {method} {path}")


# ---------------------------------------------------------------------------
# Search — JQL minimal-parse
# ---------------------------------------------------------------------------


def _search(world: JiraWorld, body: dict) -> dict:
    jql = body.get("jql", "")
    project = _extract_token(jql, r"project\s*=\s*([\w\-]+)")
    status = _extract_token(jql, r'status\s*=\s*"([^"]+)"')
    label = _extract_token(jql, r'labels\s*=\s*"([^"]+)"')
    subtask_only = "subTaskIssueTypes()" in jql

    out: list[dict] = []
    for issue in world.issues.values():
        if project and not issue.key.startswith(f"{project}-"):
            continue
        if status and issue.status != status:
            continue
        if label and label not in issue.labels:
            continue
        if subtask_only and issue.issuetype != "SubTask":
            continue
        out.append(_issue_to_search_payload(issue))
    return {"issues": out, "maxResults": body.get("maxResults", 100), "total": len(out)}


def _issue_to_search_payload(issue: JiraIssue) -> dict:
    return {
        "key": issue.key,
        "fields": {
            "summary": issue.summary,
            "status": {"name": issue.status},
            "issuetype": {"name": issue.issuetype},
            "parent": {"key": issue.parent_key} if issue.parent_key else None,
            "labels": list(issue.labels),
            "fixVersions": [{"name": v} for v in issue.fix_versions],
        },
    }


def _extract_token(jql: str, pattern: str) -> Optional[str]:
    m = re.search(pattern, jql)
    return m.group(1) if m else None


# ---------------------------------------------------------------------------
# Issue read
# ---------------------------------------------------------------------------


def _get_issue(world: JiraWorld, key: str) -> dict:
    issue = world.issues.get(key)
    if issue is None:
        raise JiraError(f"GET /rest/api/3/issue/{key} -> 404: not found")
    fields: dict[str, Any] = {
        "summary": issue.summary,
        "status": {"name": issue.status},
        "issuetype": {"name": issue.issuetype},
        "fixVersions": [{"name": v} for v in issue.fix_versions],
        "components": [{"name": c} for c in issue.components],
        "description": issue.description,
        "assignee": issue.assignee,
    }
    if issue.parent_key is not None:
        fields["parent"] = {"key": issue.parent_key}
    fields.update(issue.custom_fields)
    return {"key": key, "fields": fields}


# ---------------------------------------------------------------------------
# Issue write — Rule 4 (ADF rich-text) + Rule 5 (set_field_if_unset)
# ---------------------------------------------------------------------------


def _put_issue(world: JiraWorld, key: str, body: dict) -> dict:
    issue = _require_issue(world, key)
    fields = body.get("fields") or {}
    for cf in _RICH_TEXT_FIELDS:
        if cf in fields:
            value = fields[cf]
            if not (isinstance(value, dict) and value.get("type") == "doc"):
                raise JiraError(
                    f"PUT /rest/api/3/issue/{key} -> 400: "
                    f"Operation value must be an Atlassian Document for {cf}"
                )
    if "description" in fields:
        issue.description = fields["description"]
    if "assignee" in fields:
        issue.assignee = fields["assignee"]
    if "summary" in fields:
        issue.summary = fields["summary"]
    for k, v in fields.items():
        if k in ("description", "assignee", "summary"):
            continue
        issue.custom_fields[k] = v
    world.events.append(("set_fields", key, dict(fields)))
    return {}


# ---------------------------------------------------------------------------
# Transitions — Rules 1, 2, 3
# ---------------------------------------------------------------------------


def _list_transitions(world: JiraWorld, key: str) -> dict:
    issue = _require_issue(world, key)
    graph = _GRAPH_BUG if issue.issuetype == "Bug" else _GRAPH_DEFAULT
    out: list[dict] = []
    for name, target in graph.get(issue.status, []):
        out.append(
            {
                "id": _TRANSITION_IDS[name],
                "name": name,
                "to": {"name": target},
            }
        )
    return {"transitions": out}


def _post_transition(world: JiraWorld, key: str, body: dict) -> dict:
    issue = _require_issue(world, key)
    transition_id = ((body.get("transition") or {}).get("id")) or ""
    name_for_id = {v: k for k, v in _TRANSITION_IDS.items()}
    if transition_id not in name_for_id:
        raise JiraError(
            f"POST transitions on {key} -> 400: unknown transition id {transition_id!r}"
        )
    name = name_for_id[transition_id]
    graph = _GRAPH_BUG if issue.issuetype == "Bug" else _GRAPH_DEFAULT
    candidates = dict(graph.get(issue.status, []))
    if name not in candidates:
        raise JiraError(
            f"POST transitions on {key} -> 400: transition {name!r} not "
            f"available from status {issue.status!r}"
        )
    target_status = candidates[name]
    # Rule 1: assignee required for any transition that advances development.
    if name in ("Start Designing", "Start Development", "Request CR & Merge"):
        if not issue.assignee or not issue.assignee.get("accountId"):
            raise JiraError(
                f"POST transitions on {key} -> 400: "
                "Assignee must be specified before this transition"
            )
    # Rule 3: Request CR & Merge requires the four gate fields.
    if name == "Request CR & Merge":
        missing = [
            cf for cf in _GATE_FIELDS_FOR_REQUEST_CR_AND_MERGE
            if not issue.custom_fields.get(cf)
        ]
        if missing:
            raise JiraError(
                f"POST transitions on {key} -> 400: "
                f"required fields not populated: {missing}"
            )
    issue.status = target_status
    world.events.append(("transition", key, name))
    return {}


# ---------------------------------------------------------------------------
# Comment
# ---------------------------------------------------------------------------


def _post_comment(world: JiraWorld, key: str, body: dict) -> dict:
    issue = _require_issue(world, key)
    issue.comments.append(body)
    world.events.append(("comment", key, body))
    return {"id": str(len(issue.comments))}


def _require_issue(world: JiraWorld, key: str) -> JiraIssue:
    issue = world.issues.get(key)
    if issue is None:
        raise JiraError(f"issue {key} not in world")
    return issue


# ---------------------------------------------------------------------------
# Convenience seeders
# ---------------------------------------------------------------------------


_DEFAULT_PARENT_DESCRIPTION_ADF = {
    "type": "doc",
    "version": 1,
    "content": [
        {
            "type": "paragraph",
            "content": [
                {"type": "text", "text": "Parent ticket description (fixture)."}
            ],
        }
    ],
}

_DEFAULT_SUBTASK_DESCRIPTION_ADF = {
    "type": "doc",
    "version": 1,
    "content": [
        {
            "type": "heading",
            "attrs": {"level": 2},
            "content": [{"type": "text", "text": "Goal"}],
        },
        {
            "type": "paragraph",
            "content": [{"type": "text", "text": "Do the thing."}],
        },
        {
            "type": "heading",
            "attrs": {"level": 2},
            "content": [{"type": "text", "text": "Acceptance"}],
        },
        {
            "type": "bulletList",
            "content": [
                {
                    "type": "listItem",
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [
                                {"type": "text", "text": "[ ] thing happens"}
                            ],
                        }
                    ],
                }
            ],
        },
    ],
}


def seed_enhancement_parent_with_subtasks(
    world: JiraWorld,
    parent_key: str,
    *,
    summary: str = "AFK fixture parent",
    target_branch: str = "MASTER",
    fix_versions: tuple[str, ...] = ("core/1.2.0",),
    parent_status: str = "Dev-Pending",
    subtask_specs: tuple[tuple[str, str], ...],
) -> tuple[JiraIssue, list[JiraIssue]]:
    parent = JiraIssue(
        key=parent_key,
        summary=summary,
        status=parent_status,
        issuetype="Enhancement",
        parent_key=None,
        labels=[],
        fix_versions=list(fix_versions),
        components=["payable"],
        description=_DEFAULT_PARENT_DESCRIPTION_ADF,
        custom_fields={CF_TARGET_BRANCH: {"value": target_branch}},
    )
    world.add_issue(parent)
    subs = []
    for sub_key, sub_summary in subtask_specs:
        sub = JiraIssue(
            key=sub_key,
            summary=sub_summary,
            status="Dev-Pending",
            issuetype="SubTask",
            parent_key=parent_key,
            labels=["afk-agents"],
            fix_versions=list(fix_versions),
            description=_DEFAULT_SUBTASK_DESCRIPTION_ADF,
        )
        world.add_issue(sub)
        subs.append(sub)
    return parent, subs


def seed_standalone(
    world: JiraWorld,
    key: str,
    *,
    summary: str = "standalone fixture",
    issuetype: str = "Enhancement",
    target_branch: str = "MASTER",
    fix_versions: tuple[str, ...] = ("core/1.2.0",),
) -> JiraIssue:
    """Seed a labelled top-level ticket with no SubTasks under it.

    The driver's standalone path treats the ticket as both parent and
    its only unit of work. Description follows the SubTask Markdown
    contract so ``flip_acceptance_checkboxes`` finds a checkbox to flip
    (in real life ``/afk-go`` also reads from this shape).
    """
    issue = JiraIssue(
        key=key,
        summary=summary,
        status="Dev-Pending",
        issuetype=issuetype,
        parent_key=None,
        labels=["afk-agents"],
        fix_versions=list(fix_versions),
        components=["payable"],
        description=_DEFAULT_SUBTASK_DESCRIPTION_ADF,
        custom_fields={CF_TARGET_BRANCH: {"value": target_branch}},
    )
    world.add_issue(issue)
    return issue


def seed_bug_parent_with_subtask(
    world: JiraWorld,
    parent_key: str,
    *,
    summary: str = "AFK fixture bug",
    target_branch: str = "MASTER",
    subtask_key: str = "P2P-2001",
    subtask_summary: str = "fix bug",
) -> tuple[JiraIssue, JiraIssue]:
    parent = JiraIssue(
        key=parent_key,
        summary=summary,
        status="Dev-Pending",
        issuetype="Bug",
        parent_key=None,
        labels=[],
        fix_versions=["core/1.2.0"],
        components=["payable"],
        description=_DEFAULT_PARENT_DESCRIPTION_ADF,
        custom_fields={CF_TARGET_BRANCH: {"value": target_branch}},
    )
    world.add_issue(parent)
    sub = JiraIssue(
        key=subtask_key,
        summary=subtask_summary,
        status="Dev-Pending",
        issuetype="SubTask",
        parent_key=parent_key,
        labels=["afk-agents"],
        fix_versions=["core/1.2.0"],
        description=_DEFAULT_SUBTASK_DESCRIPTION_ADF,
    )
    world.add_issue(sub)
    return parent, sub
