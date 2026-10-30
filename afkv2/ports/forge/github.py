"""The forge commands on GitHub, through gh."""

from __future__ import annotations

import json
import re

from tracker import shell
from tracker.envelope import Refusal, need, ok

from . import common

VIEW_FIELDS = ("number,url,title,state,isDraft,headRefName,baseRefName,headRefOid,baseRefOid,"
               "isCrossRepository,headRepository,author,statusCheckRollup")
STATES = {"OPEN": "opened", "MERGED": "merged", "CLOSED": "closed"}
_CHANGE_URL = re.compile(r"https?://\S+/pull/\d+")
THREADS_QUERY = """
query($owner:String!,$name:String!,$number:Int!,$endCursor:String) {
  repository(owner:$owner,name:$name) {
    pullRequest(number:$number) {
      reviewThreads(first:100,after:$endCursor) {
        nodes { id isResolved comments(first:100) { nodes { databaseId lastEditedAt } } }
        pageInfo { hasNextPage endCursor }
      }
    }
  }
}"""
COMMENTS_QUERY = """
query($owner:String!,$name:String!,$number:Int!,$endCursor:String) {
  repository(owner:$owner,name:$name) {
    pullRequest(number:$number) {
      comments(first:100,after:$endCursor) {
        nodes { databaseId lastEditedAt }
        pageInfo { hasNextPage endCursor }
      }
    }
  }
}"""


def _flag(payload):
    return ["--repo", str(payload["repo"])] if payload.get("repo") else []


def _repo(payload):
    if payload.get("repo"):
        return str(payload["repo"])
    data = shell.json_answer("gh", ["repo", "view", "--json", "nameWithOwner"])
    name = data.get("nameWithOwner") if isinstance(data, dict) else None
    if not name:
        raise Refusal("bad-answer", "gh repo view named no project")
    return name


def _view(change, payload, fields=VIEW_FIELDS):
    data = shell.json_answer("gh", ["pr", "view", change, *_flag(payload), "--json", fields])
    if not isinstance(data, dict):
        raise Refusal("bad-answer", "gh pr view answered no JSON object")
    return data


def _number(change, payload):
    number = _view(change, payload, "number").get("number")
    if not number:
        raise Refusal("bad-answer", f"gh pr view named no number for {change}")
    return number


def _rollup(data):
    checks = data.get("statusCheckRollup") or []
    seen = {(check.get("conclusion") or check.get("state") or check.get("status") or "").upper() for check in checks}
    if not checks:
        return ""
    if seen & {"FAILURE", "TIMED_OUT", "STARTUP_FAILURE", "ERROR", "STALE"}:
        return "failed"
    if seen & {"CANCELLED", "CANCELED"}:
        return "canceled"
    return "success" if seen <= {"SUCCESS", "NEUTRAL", "SKIPPED"} else "running"


def _blob_base(data):
    head = data.get("headRepository") or {}
    base = head.get("url") or (f"https://github.com/{head['nameWithOwner']}" if head.get("nameWithOwner") else "")
    return f"{base}/blob" if base else ""


def _normalize(data):
    state = data.get("state") or ""
    return {
        "id": str(data.get("number") or ""),
        "url": data.get("url") or "",
        "title": data.get("title") or "",
        "draft": bool(data.get("isDraft")),
        "state": STATES.get(state, state.lower()),
        "source": data.get("headRefName") or "",
        "target": data.get("baseRefName") or "",
        "author": (data.get("author") or {}).get("login") or "",
        "head_sha": data.get("headRefOid") or "",
        "base_sha": data.get("baseRefOid") or "",
        "head_ref": f"pull/{data.get('number') or ''}/head",
        "cross_fork": bool(data.get("isCrossRepository")),
        "blob_base": _blob_base(data),
        "pipeline": {"status": _rollup(data)},
    }


def auth_status(payload):
    if shell.run_tool("gh", ["auth", "status"]).returncode != 0:
        return ok(authenticated=False, reason="not logged in: run `gh auth login`")
    return ok(authenticated=True, user=(shell.json_answer("gh", ["api", "user"]) or {}).get("login") or "")


def change_view(payload):
    return ok(**_normalize(_view(common.ref(payload), payload)))


def _local_diff(change, payload):
    """`gh pr diff` breaks off on a very large change, so prefer the local commits."""
    try:
        data = _view(change, payload, "baseRefOid,headRefOid")
        base, head = data.get("baseRefOid"), data.get("headRefOid")
        if not (base and head):
            return None
        for commit in (base, head):
            if shell.run_tool("git", ["cat-file", "-e", f"{commit}^{{commit}}"]).returncode != 0:
                return None
        done = shell.run_tool("git", ["-c", "core.quotePath=true", "diff", "--no-color", "--no-ext-diff", "--no-textconv",
                                      "--no-relative", "-M", "--unified=3", "--diff-algorithm=myers", "--src-prefix=a/",
                                      "--dst-prefix=b/", f"{base}...{head}"])
    except Refusal:
        return None
    return done.stdout if done.returncode == 0 else None


def change_diff(payload):
    change = common.ref(payload)
    diff = _local_diff(change, payload)
    if diff is None:
        diff = shell.checked("gh", ["pr", "diff", change, *_flag(payload)])
    return common.diff_answer(diff)


def change_create_draft(payload):
    args = ["pr", "create", *_flag(payload), "--draft", "--title", str(need(payload, "title")), "--body-file", "-"]
    for key, flag in (("target", "--base"), ("source", "--head"), ("reviewer", "--reviewer"), ("assignee", "--assignee")):
        value = common.joined(payload.get(key))
        if value:
            args += [flag, value]
    out = shell.checked("gh", args, stdin_text=str(payload.get("body") or ""))
    found = _CHANGE_URL.findall(out)
    if not found:
        raise Refusal("bad-answer", f"gh pr create printed no change URL: {out[:300]}")
    return ok(url=found[-1], id=found[-1].rsplit("/", 1)[-1], draft=True)


def change_update_body(payload):
    change, body = common.ref(payload), common.body_text(payload)
    was_draft = "true" if _view(change, payload, "isDraft").get("isDraft") else "false"
    shell.checked("gh", ["pr", "edit", change, *_flag(payload), "--body-file", "-"], stdin_text=body)
    return ok(id=change, was_draft=was_draft, draft_restored=False)


def change_ready(payload):
    change = common.ref(payload)
    shell.checked("gh", ["pr", "ready", change, *_flag(payload)])
    return ok(id=change, draft=False)


def _post(path, fields):
    data = shell.json_answer("gh", ["api", "-X", "POST", path, "--input", "-"], stdin_text=json.dumps(fields))
    return data, common.comment_id(data)


def _plain_comment(repo, number, text, **extra):
    data, ident = _post(f"repos/{repo}/issues/{number}/comments", {"body": text})
    return ok(inline=False, thread="", comment=ident, url=data.get("html_url") or "", **extra)


def change_comment(payload):
    change, text, target = common.ref(payload), str(need(payload, "text")), common.inline_target(payload)
    repo = _repo(payload)
    if target is None:
        return _plain_comment(repo, _number(change, payload), text)
    meta = _view(change, payload, "number,headRefOid")
    if not (meta.get("number") and meta.get("headRefOid")):
        raise Refusal("bad-answer", f"gh pr view named no number and head commit for {change}")
    left = target.side == "old"
    fields = {"body": text, "commit_id": meta["headRefOid"], "path": target.old_path if left else target.new_path,
              "line": target.old_line if left else target.line, "side": "LEFT" if left else "RIGHT"}
    try:
        data, ident = _post(f"repos/{repo}/pulls/{meta['number']}/comments", fields)
    except Refusal as refusal:
        if refusal.code != "unprocessable":
            raise
        if payload.get("require_inline"):
            raise Refusal("position-rejected", refusal.reason) from None
        return _plain_comment(repo, meta["number"], text, reason=common.PLAIN_NOTE_REASON)
    return ok(inline=True, thread=ident, comment=ident, url=data.get("html_url") or "")


def _graphql(query, repo, number):
    owner, name = repo.split("/", 1)
    documents = shell.as_items(shell.json_answer("gh", ["api", "graphql", "--paginate", "-f", f"owner={owner}", "-f", f"name={name}",
                                                        "-F", f"number={number}", "-f", f"query={query}"]))
    pulls = []
    for document in documents:
        pull = ((document.get("data") or {}).get("repository") or {}).get("pullRequest") if isinstance(document, dict) else None
        if not isinstance(pull, dict) or document.get("errors"):
            raise Refusal("bad-answer", "the GraphQL answer holds no pull request")
        pulls.append(pull)
    return pulls


def _edited(comment):
    return bool(comment["lastEditedAt"]) if "lastEditedAt" in comment else None


def note_list(payload):
    change = common.ref(payload)
    repo, number = _repo(payload), _number(change, payload)
    edited = {}
    for pull in _graphql(COMMENTS_QUERY, repo, number):
        for comment in (pull.get("comments") or {}).get("nodes") or []:
            if comment.get("databaseId") is not None:
                edited[str(comment["databaseId"])] = _edited(comment)
    notes = []
    for item in shell.as_items(shell.json_answer("gh", ["api", "--paginate", f"repos/{repo}/issues/{number}/comments?per_page=100"])):
        ident = str(item.get("id") or "")
        if edited.get(ident) is None:
            raise Refusal("bad-answer", f"GraphQL edit state missing for comment {ident}")
        notes.append({"id": ident, "author": (item.get("user") or {}).get("login") or "", "body": item.get("body") or "",
                      "created_at": item.get("created_at") or "", "updated_at": item.get("updated_at") or "",
                      "edited": edited[ident]})
    notes.sort(key=lambda note: (note["created_at"], note["id"]))
    return ok(notes=notes, count=len(notes))


def _thread_state(repo, number):
    threads, edited = {}, {}
    for pull in _graphql(THREADS_QUERY, repo, number):
        for thread in (pull.get("reviewThreads") or {}).get("nodes") or []:
            comments = (thread.get("comments") or {}).get("nodes") or []
            if comments and comments[0].get("databaseId") is not None:
                threads[str(comments[0]["databaseId"])] = bool(thread.get("isResolved"))
            for comment in comments:
                if comment.get("databaseId") is not None:
                    edited[str(comment["databaseId"])] = _edited(comment)
    return threads, edited


def _thread(root, comments, resolved, edited):
    notes = sorted(comments, key=lambda note: (note.get("created_at") or "", str(note.get("id") or "")))
    first = notes[0]
    side = "old" if (first.get("side") or "RIGHT") == "LEFT" else "new"
    old_line = None
    if side == "old":
        old_line = first.get("line") if first.get("line") is not None else first.get("original_line")
    return {
        "id": str(root),
        "resolved": resolved[str(root)],
        "file": first.get("path"),
        "side": side,
        "line": first.get("line") if side == "new" else None,
        "old_line": old_line,
        "old_path": first.get("old_path") or first.get("path"),
        "new_path": first.get("new_path") or first.get("path"),
        "url": first.get("html_url") or "",
        "notes": [{"id": note.get("id"), "author": (note.get("user") or {}).get("login"), "type": "ReviewComment",
                   "body": note.get("body") or "", "created_at": note.get("created_at") or "",
                   "updated_at": note.get("updated_at") or "", "edited": edited[str(note.get("id"))]} for note in notes],
    }


def thread_list(payload):
    """GitHub has no discussion object: a thread is a root comment plus the comments that reply to it."""
    change = common.ref(payload)
    repo, number = _repo(payload), _number(change, payload)
    resolved, edited = _thread_state(repo, number)
    groups = {}
    for item in shell.as_items(shell.json_answer("gh", ["api", "--paginate", f"repos/{repo}/pulls/{number}/comments?per_page=100"])):
        groups.setdefault(item.get("in_reply_to_id") or item.get("id"), []).append(item)
    missing = [str(root) for root in groups if str(root) not in resolved]
    if missing:
        raise Refusal("bad-answer", f"GraphQL review thread missing for roots: {', '.join(missing)}")
    unknown = [str(note.get("id")) for notes in groups.values() for note in notes if edited.get(str(note.get("id"))) is None]
    if unknown:
        raise Refusal("bad-answer", f"GraphQL edit state missing for review comments: {', '.join(unknown)}")
    threads = [_thread(root, notes, resolved, edited) for root, notes in groups.items()]
    threads.sort(key=lambda thread: (thread["notes"][0]["created_at"], thread["id"]))
    return ok(threads=threads, count=len(threads))


def ci_status(payload):
    data = _view(common.ref(payload), payload, "url,statusCheckRollup")
    return ok(status=_rollup(data), url=data.get("url") or "")


def ci_wait(payload):
    return common.ci_wait(payload, lambda change: _rollup(_view(change, payload, "statusCheckRollup")))


VERBS = {
    "auth-status": auth_status,
    "change-view": change_view,
    "change-diff": change_diff,
    "change-create-draft": change_create_draft,
    "change-update-body": change_update_body,
    "change-ready": change_ready,
    "change-comment": change_comment,
    "note-list": note_list,
    "thread-list": thread_list,
    "ci-status": ci_status,
    "ci-wait": ci_wait,
}
