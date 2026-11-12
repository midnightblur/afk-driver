"""GitHub issues through gh: reads ported from v1, the managed PRD block of the issue body, and comment-put."""

from __future__ import annotations

import hashlib
import re
from urllib.parse import urlparse

from . import proof, shell
from .envelope import Refusal, need, ok
from .jira import preview_for

ISSUE_FIELDS = "number,title,state,labels,assignees,author,createdAt,updatedAt,body,url,milestone,comments"
SEARCH_FIELDS = "number,title,state,labels,assignees,updatedAt,url"
DEFAULT_LIMIT = 50
BEGIN_LINE = "<!-- afkv2:prd:start -->"
END_LINE = "<!-- afkv2:prd:end -->"
MARKER_WORD = re.compile(r"afkv2:prd:(?:start|end)")
FENCE = re.compile(r"^ *(`{3,}|~{3,})")
BODY_LIMIT = 65536

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


def _view(repo, number, fields):
    data = shell.json_answer("gh", ["issue", "view", number, *_repo_args(repo), "--json", fields])
    if not isinstance(data, dict):
        raise Refusal("bad-answer", "gh issue view answered no JSON object")
    return data


def issue_get(payload):
    """The gh fields, plus the publish facts of the body: `description_hash`, `block`, `length_without_block`,
    and `block_problem` when the block is broken."""
    repo, number = _repo_and_number(payload)
    fields = payload.get("fields") or ISSUE_FIELDS
    if not isinstance(fields, str):
        fields = ",".join(fields)
    if "body" not in fields.split(","):
        fields += ",body"
    data = _view(repo, number, fields)
    answer = ok(key=number, **{name: value for name, value in data.items() if name not in ("ok", "key")})
    return {**answer, **_block_facts(data.get("body") or "")}


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


def body_hash(body):
    """The stale check compares this: any change of the body, a line end included, changes it."""
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _lines(text):
    return text.replace("\r\n", "\n").split("\n")


def block_text(markdown):
    """The canonical form of a block: LF line ends, no trailing spaces, no blank lines at the start or the end."""
    return "\n".join(line.rstrip() for line in _lines(markdown)).strip("\n")


def find_block(lines):
    """`(begin, end)` line indexes of the one block; None when there is none; `bad-block` otherwise.
    A line inside a code fence quotes a marker and holds none."""
    begins, ends, fence = [], [], None
    for index, line in enumerate(lines):
        found = FENCE.match(line)
        if fence is not None:
            if found and found.group(1)[0] == fence[0] and len(found.group(1)) >= len(fence):
                fence = None
            continue
        if found:
            fence = found.group(1)
        elif line.strip() == BEGIN_LINE:
            begins.append(index)
        elif line.strip() == END_LINE:
            ends.append(index)
        elif MARKER_WORD.search(line):
            raise Refusal("bad-block", f"a block line stands inside line {index + 1}, not alone on its own line")
    if len(begins) > 1 or len(ends) > 1:
        raise Refusal("bad-block", "2 or more block lines of one kind: the issue body holds a doubled block")
    if begins and not ends:
        raise Refusal("bad-block", "a begin line without an end line")
    if ends and not begins:
        raise Refusal("bad-block", "an end line without a begin line")
    if not begins:
        return None
    if ends[0] < begins[0]:
        raise Refusal("bad-block", "the end line stands before the begin line")
    return begins[0], ends[0]


def _summary(text):
    """What a read-back compares. A GitHub block has no pictures: GitHub draws each Mermaid fence itself."""
    return {"family": "afkv2", "text": block_text(text), "media_ids": []}


def _block_facts(body):
    facts = {"description_hash": body_hash(body), "block": None, "length_without_block": len(body)}
    lines = _lines(body)
    try:
        span = find_block(lines)
    except Refusal as refusal:
        return {**facts, "block_problem": refusal.reason}
    if span:
        facts["block"] = _summary("\n".join(lines[span[0] + 1:span[1]]))
        facts["length_without_block"] = len("\n".join(lines[:span[0]] + lines[span[1] + 1:]))
    return facts


def block_text_verb(payload):
    return ok(block_text=block_text(need(payload, "markdown")))


def description_put(payload):
    """Write the block into the issue body. Only the lines between the block lines change; a first publish
    appends the block at the end."""
    key, markdown, expect_hash = need(payload, "key"), need(payload, "markdown"), need(payload, "expect_hash")
    repo, number = _repo_and_number(payload)
    preview = preview_for(payload, key)
    if preview.get("description_hash") != expect_hash:
        raise Refusal("bad-receipt", "`expect_hash` is not the body hash the preview showed")
    text = block_text(markdown)
    seen = hashlib.sha256((key + text + "".join(preview.get("picture_hashes") or [])).encode("utf-8")).hexdigest()
    if seen != payload["receipt"]:
        raise Refusal("bad-receipt", "this text is not what the receipt covers: show a new preview")
    if any(MARKER_WORD.search(line) for line in _lines(text)):
        raise Refusal("bad-block", "the new text holds a block line: it would break the next publish")
    body = _view(repo, number, "body").get("body") or ""
    if body_hash(body) != expect_hash:
        raise Refusal("stale", "the issue body changed after the preview: show a new preview")
    lines = _lines(body)
    span = find_block(lines)
    framed = [BEGIN_LINE, *text.split("\n"), END_LINE]
    if span:
        new_lines = [*lines[:span[0]], *framed, *lines[span[1] + 1:]]
    else:
        kept = "\n".join(lines).rstrip("\n")
        new_lines = [*([kept, ""] if kept else []), *framed]
    new_body = "\n".join(new_lines)
    if len(new_body) > BODY_LIMIT:
        raise Refusal("too-large", f"the new issue body has {len(new_body)} characters; GitHub takes {BODY_LIMIT}")
    shell.checked("gh", ["issue", "edit", number, *_repo_args(repo), "--body-file", "-"], stdin_text=new_body)
    return ok(key=key, replaced="afkv2" if span else None, block=_summary(text))


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
