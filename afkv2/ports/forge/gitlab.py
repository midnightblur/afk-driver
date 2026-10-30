"""The forge commands on GitLab, through glab."""

from __future__ import annotations

import json
import re
import urllib.parse

from tracker import shell
from tracker.envelope import Refusal, fail, need, ok

from . import common

_CHANGE_URL = re.compile(r"https?://\S+/-/merge_requests/\d+")
_JSON_HEADER = ["-H", "Content-Type: application/json"]
NOTES_QUERY = """
query($path:ID!,$iid:String!,$endCursor:String) {
  project(fullPath:$path) {
    mergeRequest(iid:$iid) {
      notes(first:100,after:$endCursor) {
        nodes { id author { id } lastEditedBy { id } }
        pageInfo { hasNextPage endCursor }
      }
    }
  }
}"""


def _flag(payload):
    return ["-R", str(payload["repo"])] if payload.get("repo") else []


def _project(payload):
    return urllib.parse.quote(str(payload["repo"]), safe="") if payload.get("repo") else ":id"


def _view(change, payload):
    data = shell.json_answer("glab", ["mr", "view", change, *_flag(payload), "-F", "json"])
    if not isinstance(data, dict):
        raise Refusal("bad-answer", "glab mr view answered no JSON object")
    return data


def _iid(data):
    iid = data.get("iid") or data.get("id")
    if not iid:
        raise Refusal("bad-answer", "glab mr view named no merge request number")
    return iid


def _pipeline(data):
    return data.get("head_pipeline") or data.get("pipeline") or {}


_CI_WORDS = {"success": "success", "skipped": "success", "failed": "failed", "canceled": "canceled"}


def _ci_word(pipeline):
    """The contract word. GitLab has more: all that is not final reads `running`, and `skipped` is GitHub's success."""
    word = pipeline.get("status")
    if not word:
        return ""
    return _CI_WORDS.get(word, "running")


def _blob_base(data):
    source = (data.get("source_project") or {}).get("web_url")
    if source:
        return f"{source}/-/blob"
    project = data.get("source_project_id")
    if not project:
        return ""
    try:
        url = shell.json_answer("glab", ["api", f"projects/{project}"]).get("web_url")
    except (Refusal, AttributeError):
        return ""
    return f"{url}/-/blob" if url else ""


def _normalize(data):
    number = data.get("iid") or data.get("id") or ""
    title = data.get("title") or ""
    refs = data.get("diff_refs") or {}
    source_id, target_id = data.get("source_project_id"), data.get("target_project_id")
    return {
        "id": str(number),
        "url": data.get("web_url") or "",
        "title": title,
        "draft": bool(data.get("draft") or data.get("work_in_progress") or title.lower().startswith(("draft:", "wip:"))),
        "state": data.get("state") or "",
        "source": data.get("source_branch") or "",
        "target": data.get("target_branch") or "",
        "author": (data.get("author") or {}).get("username") or "",
        "head_sha": data.get("sha") or refs.get("head_sha") or "",
        "base_sha": refs.get("base_sha") or "",
        "head_ref": f"merge-requests/{number}/head",
        "cross_fork": bool(source_id and target_id and source_id != target_id),
        "blob_base": _blob_base(data),
        "pipeline": {"status": _ci_word(_pipeline(data))},
    }


def auth_status(payload):
    if shell.run_tool("glab", ["auth", "status"]).returncode != 0:
        return ok(authenticated=False, reason="not logged in: run `glab auth login`")
    return ok(authenticated=True, user=(shell.json_answer("glab", ["api", "user"]) or {}).get("username") or "")


def change_view(payload):
    return ok(**_normalize(_view(common.ref(payload), payload)))


def change_diff(payload):
    return common.diff_answer(shell.checked("glab", ["mr", "diff", common.ref(payload), *_flag(payload), "--color=never"]))


def change_create_draft(payload):
    args = ["mr", "create", *_flag(payload), "--draft", "--yes", "--title", str(need(payload, "title")),
            "--description", str(payload.get("body") or "")]
    for key, flag in (("target", "--target-branch"), ("source", "--source-branch"), ("reviewer", "--reviewer"), ("assignee", "--assignee")):
        value = common.joined(payload.get(key))
        if value:
            args += [flag, value]
    out = shell.checked("glab", args)
    found = _CHANGE_URL.findall(out)
    if not found:
        raise Refusal("bad-answer", f"glab mr create printed no change URL: {out[:300]}")
    return ok(url=found[-1], id=found[-1].rsplit("/", 1)[-1], draft=True)


def _is_draft(change, payload):
    return bool(_view(change, payload).get("draft"))


def _draft_kept(change, payload):
    """A read that fails after the write proves nothing: the caller sets the flag again."""
    try:
        return _is_draft(change, payload)
    except Refusal:
        return False


def change_update_body(payload):
    """`glab mr update` clears the draft flag: read it first, put it back after. A failed first read writes nothing."""
    change, body = common.ref(payload), common.body_text(payload)
    was_draft = _is_draft(change, payload)
    shell.checked("glab", ["mr", "update", change, *_flag(payload), "--description", body])
    restored = False
    if was_draft and not _draft_kept(change, payload):
        repair = ["mr", "update", change, *_flag(payload), "--draft"]
        if shell.run_tool("glab", repair).returncode != 0:
            return fail("draft-lost", f"the body changed, but the draft flag is off and could not be set again: run `glab {' '.join(repair)}`", id=change)
        restored = True
    return ok(id=change, was_draft="true" if was_draft else "false", draft_restored=restored)


def change_ready(payload):
    change = common.ref(payload)
    shell.checked("glab", ["mr", "update", change, *_flag(payload), "--ready"])
    return ok(id=change, draft=False)


def _post(path, fields):
    return shell.json_answer("glab", ["api", "-X", "POST", *_JSON_HEADER, path, "--input", "-"], stdin_text=json.dumps(fields))


def _note_url(change_url, ident):
    return f"{change_url}#note_{ident}" if change_url and ident else ""


def _plain_note(project, iid, text, change_url, **extra):
    data = _post(f"projects/{project}/merge_requests/{iid}/notes", {"body": text})
    ident = common.comment_id(data)
    return ok(inline=False, thread="", comment=ident,
              url=data.get("web_url") or _note_url(change_url, ident), **extra)


def _degraded(payload, project, iid, ident, url):
    reason = common.PLAIN_NOTE_REASON
    if not payload.get("require_inline"):
        return ok(inline=False, thread="", comment=ident, url=url, reason=reason)
    if shell.run_tool("glab", ["api", "-X", "DELETE", f"projects/{project}/merge_requests/{iid}/notes/{ident}"]).returncode == 0:
        return fail("position-rejected", reason, cleaned=True)
    return fail("position-rejected", "the position degraded to a plain note and cleanup failed", note=ident)


def change_comment(payload):
    """An inline comment needs the four diff refs, which only the API takes: `glab mr note` posts a plain note."""
    change, text, target = common.ref(payload), str(need(payload, "text")), common.inline_target(payload)
    meta = _view(change, payload)
    iid, project, change_url = _iid(meta), _project(payload), meta.get("web_url") or ""
    if target is None:
        return _plain_note(project, iid, text, change_url)
    refs = meta.get("diff_refs") or {}
    position = {"position_type": "text", "new_path": target.new_path, "old_path": target.old_path,
                "base_sha": refs.get("base_sha"), "start_sha": refs.get("start_sha"), "head_sha": refs.get("head_sha")}
    if target.side in ("new", "context"):
        position["new_line"] = target.line
    if target.side in ("old", "context"):
        position["old_line"] = target.old_line
    try:
        data = _post(f"projects/{project}/merge_requests/{iid}/discussions", {"body": text, "position": position})
    except Refusal as refusal:
        if refusal.code not in ("bad-request", "unprocessable"):
            raise
        if payload.get("require_inline"):
            raise Refusal("position-rejected", refusal.reason) from None
        return _plain_note(project, iid, text, change_url, reason=common.PLAIN_NOTE_REASON)
    note = ((data.get("notes") or [{}])[0]) if isinstance(data, dict) else {}
    ident = common.comment_id(note)
    url = note.get("web_url") or data.get("web_url") or _note_url(change_url, ident)
    if note.get("type") != "DiffNote":
        return _degraded(payload, project, iid, ident, url)
    return ok(inline=True, thread=str(data.get("id") or ""), comment=ident, url=url)


def _note_edits(payload, iid):
    """{note id: edited}. A null editor proves "unedited" only when the author is visible."""
    path = str(payload.get("repo") or "")
    if not path:
        data = shell.json_answer("glab", ["api", "projects/:id"])
        path = data.get("path_with_namespace") if isinstance(data, dict) else ""
    if not path:
        raise Refusal("bad-answer", "the project path could not be resolved for GraphQL")
    edited, hidden = {}, []
    documents = shell.json_answer("glab", ["api", "graphql", "--paginate", "-f", f"path={path}", "-f", f"iid={iid}", "-f", f"query={NOTES_QUERY}"])
    for document in shell.as_items(documents):
        merge_request = ((document.get("data") or {}).get("project") or {}).get("mergeRequest") if isinstance(document, dict) else None
        if not isinstance(merge_request, dict) or document.get("errors"):
            raise Refusal("bad-answer", "the GraphQL answer holds no merge request")
        for node in (merge_request.get("notes") or {}).get("nodes") or []:
            ident = str(node.get("id") or "").rsplit("/", 1)[-1]
            if not ident:
                continue
            editor, author = node.get("lastEditedBy", ...), node.get("author", ...)
            if editor is ... or author is ...:
                edited[ident] = None
            elif editor is not None or author is not None:
                edited[ident] = editor is not None
            else:
                edited[ident] = None
                hidden.append(ident)
    return edited, hidden


def _edit_problem(unknown, hidden):
    why = " (author and editor hidden: the token cannot read users)" if set(unknown) & set(hidden) else ""
    return Refusal("bad-answer", f"GraphQL edit state missing for notes: {', '.join(unknown)}{why}")


def _is_line_note(note):
    return note.get("type") == "DiffNote" or bool(note.get("position"))


def note_list(payload):
    iid = _iid(_view(common.ref(payload), payload))
    edited, hidden = _note_edits(payload, iid)
    path = f"projects/{_project(payload)}/merge_requests/{iid}/notes?per_page=100&sort=asc&order_by=created_at"
    items = [item for item in shell.as_items(shell.json_answer("glab", ["api", "--paginate", path]))
             if not (item.get("system") or _is_line_note(item))]
    unknown = [str(item.get("id") or "") for item in items if edited.get(str(item.get("id") or "")) is None]
    if unknown:
        raise _edit_problem(unknown, hidden)
    notes = [{"id": str(item["id"]), "author": (item.get("author") or {}).get("username") or "", "body": item.get("body") or "",
              "created_at": item.get("created_at") or "", "updated_at": item.get("updated_at") or "",
              "edited": edited[str(item["id"])]} for item in items]
    notes.sort(key=lambda note: (note["created_at"], note["id"]))
    return ok(notes=notes, count=len(notes))


def _thread(discussion, change_url, edited):
    notes = sorted(discussion.get("notes") or [], key=lambda note: (note.get("created_at") or "", str(note.get("id") or "")))
    root = notes[0] if notes else {}
    position = root.get("position") or {}
    new_line, old_line = position.get("new_line"), position.get("old_line")
    return {
        "id": discussion.get("id"),
        "resolved": any(note.get("resolved") for note in notes),
        "file": position.get("new_path") or position.get("old_path"),
        "side": "context" if new_line and old_line else ("old" if old_line else "new"),
        "line": new_line,
        "old_line": old_line,
        "old_path": position.get("old_path"),
        "new_path": position.get("new_path"),
        "url": root.get("web_url") or discussion.get("web_url") or _note_url(change_url, root.get("id")),
        "notes": [{"id": note.get("id"), "author": (note.get("author") or {}).get("username"), "type": note.get("type"),
                   "body": note.get("body") or "", "created_at": note.get("created_at") or "",
                   "updated_at": note.get("updated_at") or "", "edited": edited[str(note.get("id"))]} for note in notes],
    }


def _on_a_line(discussion):
    root = (discussion.get("notes") or [{}])[0]
    return _is_line_note(root) and not root.get("system")


def thread_list(payload):
    meta = _view(common.ref(payload), payload)
    iid = _iid(meta)
    edited, hidden = _note_edits(payload, iid)
    path = f"projects/{_project(payload)}/merge_requests/{iid}/discussions?per_page=100"
    discussions = [item for item in shell.as_items(shell.json_answer("glab", ["api", "--paginate", path])) if _on_a_line(item)]
    unknown = [str(note.get("id")) for discussion in discussions for note in discussion.get("notes") or []
               if edited.get(str(note.get("id"))) is None]
    if unknown:
        raise _edit_problem(unknown, hidden)
    threads = [_thread(discussion, meta.get("web_url") or "", edited) for discussion in discussions]
    threads.sort(key=lambda thread: ((thread["notes"][0]["created_at"] if thread["notes"] else ""), str(thread["id"] or "")))
    return ok(threads=threads, count=len(threads))


def ci_status(payload):
    pipeline = _pipeline(_view(common.ref(payload), payload))
    return ok(status=_ci_word(pipeline), url=pipeline.get("web_url") or "")


def ci_wait(payload):
    return common.ci_wait(payload, lambda change: _ci_word(_pipeline(_view(change, payload))))


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
