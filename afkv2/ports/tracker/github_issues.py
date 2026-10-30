"""GitHub-issue reads through gh. Ported from v1; no write verb."""

from __future__ import annotations

from . import shell
from .envelope import Refusal, need, ok

ISSUE_FIELDS = "number,title,state,labels,assignees,author,createdAt,updatedAt,body,url,milestone,comments"
SEARCH_FIELDS = "number,title,state,labels,assignees,updatedAt,url"
DEFAULT_LIMIT = 50


def _repo_args(repo):
    return ["--repo", str(repo)] if repo else []


def _repo_and_number(payload):
    """`7`, `#7`, or `owner/name#7`. A key that names another repository than `repo` is refused, never read."""
    named, _, number = str(need(payload, "key")).rpartition("#")
    repo = payload.get("repo")
    if named and repo and named.lower() != str(repo).lower():
        raise Refusal("bad-payload", f"`key` names {named}, and `repo` is {repo}")
    if number.startswith("-") or named.startswith("-"):
        raise Refusal("bad-payload", f"`key` {payload['key']} is no issue reference")
    return named or repo, number


def issue_get(payload):
    repo, number = _repo_and_number(payload)
    fields = payload.get("fields") or ISSUE_FIELDS
    if not isinstance(fields, str):
        fields = ",".join(fields)
    data = shell.json_answer("gh", ["issue", "view", number, *_repo_args(repo), "--json", fields])
    if not isinstance(data, dict):
        raise Refusal("bad-answer", "gh issue view answered no JSON object")
    return ok(key=number, **{name: value for name, value in data.items() if name not in ("ok", "key")})


def issue_search(payload):
    try:
        limit = int(payload.get("max_results") or DEFAULT_LIMIT)
    except (TypeError, ValueError):
        raise Refusal("bad-payload", "`max_results` must be a number") from None
    args = ["issue", "list", *_repo_args(payload.get("repo")), "--limit", str(limit), "--json", SEARCH_FIELDS]
    if payload.get("query"):
        args += ["--search", str(payload["query"])]
    data = shell.json_answer("gh", args)
    if not isinstance(data, list):
        raise Refusal("bad-answer", "gh issue list answered no JSON list")
    return ok(issues=data, count=len(data))
