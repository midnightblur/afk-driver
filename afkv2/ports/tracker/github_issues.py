"""GitHub-issue reads through gh, ported from v1, and the one write: comment-put."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from . import proof, shell
from .envelope import Refusal, need, ok

ISSUE_FIELDS = "number,title,state,labels,assignees,author,createdAt,updatedAt,body,url,milestone,comments"
SEARCH_FIELDS = "number,title,state,labels,assignees,updatedAt,url"
DEFAULT_LIMIT = 50
GH_FLOOR = (2, 99, 0)
ATTACH_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".mp4", ".mov", ".webm"}
VIDEO_SUFFIXES = {".mp4", ".mov", ".webm"}
ATTACH_LIMIT = 10 * 1024 * 1024
ATTACH_COUNT = 50
PUSH_PERMISSIONS = {"ADMIN", "MAINTAIN", "WRITE"}
_VERSION = re.compile(r"gh version (\d+)\.(\d+)\.(\d+)")
_COMMENT_ID = re.compile(r"#issuecomment-(\d+)")


def _repo_args(repo):
    return ["--repo", str(repo)] if repo else []


def _repo_and_number(payload):
    """`7`, `#7`, or `owner/name#7`. A key that names another repository than `repo` is refused, never read."""
    named, _, number = str(need(payload, "key")).rpartition("#")
    repo = payload.get("repo")
    if named and repo and named.lower() != str(repo).lower():
        raise Refusal("bad-payload", f"`key` names {named}, and `repo` is {repo}")
    if not (number.isascii() and number.isdigit()) or named.startswith("-"):
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


def _check_files(paths):
    """GitHub takes pictures and video only, 10 MB each, 50 per command. gh reads `#` as the alt-text mark."""
    for path in paths:
        if path.suffix.lower() not in ATTACH_SUFFIXES:
            raise Refusal("not-supported", f"GitHub attaches only {', '.join(sorted(ATTACH_SUFFIXES))}: {path.name}")
        if "#" in str(path):
            raise Refusal("bad-payload", f"a picture path must not hold `#`: {path}")
    if len(paths) > ATTACH_COUNT:
        raise Refusal("too-large", f"{len(paths)} pictures; gh attaches at most {ATTACH_COUNT} per comment")
    proof.check_sizes(paths, ATTACH_LIMIT, "GitHub")


def _check_gh():
    found = _VERSION.search(shell.checked("gh", ["--version"]))
    version = tuple(int(part) for part in found.groups()) if found else None
    if version is None or version < GH_FLOOR:
        named = ".".join(map(str, version)) if version else "unknown"
        raise Refusal("gh-too-old", f"gh {named}: `gh issue comment --attach` needs gh 2.99.0 or later")


def _check_repo(repo):
    data = shell.json_answer("gh", ["repo", "view", *([str(repo)] if repo else []), "--json", "url,viewerPermission"])
    if not isinstance(data, dict):
        raise Refusal("bad-answer", "gh repo view answered no JSON object")
    host = (urlparse(str(data.get("url") or "")).hostname or "").lower()
    if host != "github.com":
        raise Refusal("not-supported", f"the repository is on {host or 'an unknown host'}: "
                                       "gh attach does not work on GitHub Enterprise Server")
    if data.get("viewerPermission") not in PUSH_PERMISSIONS:
        raise Refusal("no-push-access", f"gh attach needs push access; the permission is {data.get('viewerPermission')}")


def _comment_id(url, fallback=None):
    found = _COMMENT_ID.search(str(url or ""))
    return found.group(1) if found else fallback


def _existing(repo, number, receipt):
    data = shell.json_answer("gh", ["issue", "view", number, *_repo_args(repo), "--json", "comments"])
    comments = data.get("comments") if isinstance(data, dict) else None
    if not isinstance(comments, list):
        raise Refusal("bad-answer", "gh issue view answered no comment list")
    return next((item for item in comments if isinstance(item, dict) and proof.holds_receipt(item.get("body"), receipt)), None)


def _attach_arg(path):
    """Video takes no alt text; a picture gets its file name."""
    return str(path) if path.suffix.lower() in VIDEO_SUFFIXES else f"{path}#{path.name}"


def comment_put(payload):
    _, body, paths, receipt = proof.request(payload)
    repo, number = _repo_and_number(payload)
    _check_files(paths)
    _check_gh()
    _check_repo(repo)
    found = _existing(repo, number, receipt)
    if found:
        return ok(comment_id=_comment_id(found.get("url"), found.get("id")), url=found.get("url"), attached=[], posted=False)
    args = ["issue", "comment", number, *_repo_args(repo), "--body-file", "-"]
    for path in paths:
        args += ["--attach", _attach_arg(path)]
    url = shell.checked("gh", args, stdin_text=body).strip().splitlines()
    url = url[-1].strip() if url else ""
    return ok(comment_id=_comment_id(url), url=url, attached=[path.name for path in paths], posted=True)
