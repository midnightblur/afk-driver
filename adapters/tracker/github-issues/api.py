#!/usr/bin/env python3
"""tracker/github-issues — the GitHub Issues adapter.

Answers the nine `tracker_*` operations through the `gh` CLI, so authentication
is whatever `gh auth login` already established and no token lives in a
configuration file.

GitHub Issues has no workflow engine, so two things are modelled rather than
mapped one to one (`CONTRACT.md` states the same):

- A STATE is a label. `github-issues.state-labels` maps a state name to its
  label; `tracker_transitions` lists those states, and `tracker_transition`
  swaps the current state label for the requested one. The transition id IS the
  state name — there is nothing else to key on.
- A PARENT is a tracking issue. `tracker_create` with `parent` adds a task-list
  line to that issue rather than setting a field.

`tracker_attachments` reports the files GitHub already hosts for the issue: it
lists the asset URLs found in the issue body and its comments. GitHub has no
attachment API to enumerate, so a file that was never referenced in text cannot
be reported, and the operation says so instead of pretending the list is
complete.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

OPERATIONS = (
    "tracker_get", "tracker_search", "tracker_create", "tracker_edit",
    "tracker_comment", "tracker_transition", "tracker_transitions",
    "tracker_attachments", "tracker_changelog",
)


# The shared payload reader (adapters/tracker/payload.py). The adapters folder
# is not a package root, so it is loaded by file, the way this adapter itself is
# loaded by scripts/tracker_api.py.
def _payload_module():
    spec = importlib.util.spec_from_file_location(
        "afk_tracker_payload", Path(__file__).resolve().parent.parent / "payload.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


payload_reader = _payload_module()

PLUGIN_ROOT = Path(__file__).resolve().parents[3]
ASSET_URL = re.compile(
    r"https://(?:user-images\.githubusercontent\.com|github\.com/[^/\s)]+/[^/\s)]+/(?:files|assets))/[^\s)\"']+")


# ---------------------------------------------------------------------------
# configuration
# ---------------------------------------------------------------------------
_CONFIG = None


def config():
    """The `github-issues:` block, read through the one configuration reader."""
    global _CONFIG
    if _CONFIG is None:
        spec = importlib.util.spec_from_file_location(
            "afk_config", PLUGIN_ROOT / "scripts" / "afk-config.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _CONFIG = module.get(module.load(Path.cwd()), "github-issues") or {}
    return _CONFIG


def repo():
    """`github-issues.repo`, else whatever repository the checkout points at."""
    return config().get("repo") or os.environ.get("GH_REPO") or ""


def state_labels():
    """state name -> label. Empty when the repository declared none."""
    labels = config().get("state-labels")
    return labels if isinstance(labels, dict) else {}


# ---------------------------------------------------------------------------
# gh
# ---------------------------------------------------------------------------
def _gh(*args, stdin=None):
    """Run `gh` and answer parsed JSON, or a described error. Never raises: an
    operation that throws tells the caller nothing about the far side."""
    if not shutil.which("gh"):
        return {"unavailable": True,
                "reason": "tracker: github-issues — the `gh` CLI is not on PATH"}
    argv = ["gh", *args]
    try:
        done = subprocess.run(argv, input=stdin, capture_output=True,
                              text=True, timeout=60)
    except Exception as e:
        return {"error": True, "reason": f"{type(e).__name__}: {e}"}
    if done.returncode != 0:
        return {"error": True, "status": done.returncode,
                "body": (done.stderr or done.stdout).strip()[:2000]}
    out = done.stdout.strip()
    if not out:
        return {"ok": True}
    try:
        return _pages(out)
    except ValueError:
        return {"raw": out[:2000]}


def _pages(text):
    """One value from an answer that may arrive as several JSON documents.

    `gh api --paginate` prints one document per page, so a reader that calls
    json.loads sees page 2 as trailing data and loses every page after the
    first. Decode the documents in order; when they are arrays, join them into
    the single list the caller asked for.
    """
    decoder = json.JSONDecoder()
    index, documents = 0, []
    while True:
        while index < len(text) and text[index].isspace():
            index += 1
        if index >= len(text):
            break
        value, index = decoder.raw_decode(text, index)
        documents.append(value)
    if not documents:
        raise ValueError("no JSON document in the answer")
    if len(documents) == 1:
        return documents[0]
    items = []
    for document in documents:
        if isinstance(document, list):
            items.extend(document)
        else:
            items.append(document)
    return items


def _repo_args():
    return ["--repo", repo()] if repo() else []


def _number(ticket_key):
    """Accept `123`, `#123` or `owner/repo#123` — a caller should not have to
    know which spelling this tracker wants."""
    text = str(ticket_key)
    if "#" in text:
        text = text.rsplit("#", 1)[1]
    return text.lstrip("#")


# ---------------------------------------------------------------------------
# operations
# ---------------------------------------------------------------------------
ISSUE_FIELDS = ("number,title,state,labels,assignees,author,createdAt,"
                "updatedAt,body,url,milestone,comments")


def _op_get(p):
    fields = p.get("fields") or ISSUE_FIELDS
    return _gh("issue", "view", _number(p["ticket_key"]), *_repo_args(),
               "--json", fields)


def _op_search(p):
    limit = str(int(p.get("max_results") or 50))
    args = ["issue", "list", *_repo_args(), "--limit", limit,
            "--json", "number,title,state,labels,assignees,updatedAt,url"]
    query = p.get("query") or ""
    if query:
        args += ["--search", query]
    return _gh(*args)


def _op_transitions(p):
    """The states this repository declared, as transitions. The id is the state
    name; there is no workflow engine underneath to give ids of its own."""
    labels = state_labels()
    current = _op_get({"ticket_key": p["ticket_key"], "fields": "labels,state"})
    current = current if isinstance(current, dict) else {}
    held = {l.get("name") for l in (current.get("labels") or [])}
    state = str(current.get("state") or "").lower()
    # GitHub's own two states are always available; `state-labels` only adds the
    # repository's workflow states on top of them.
    transitions = [
        {"id": "open", "name": "open", "native": True, "current": state == "open"},
        {"id": "closed", "name": "closed", "native": True, "current": state == "closed"},
    ]
    transitions += [
        {"id": name, "name": name, "label": label, "current": label in held}
        for name, label in labels.items()]
    answer = {"transitions": transitions}
    if not labels:
        answer["reason"] = ("tracker: github-issues — no `github-issues.state-labels` "
                            "in .afk/config.yaml, so `open` and `closed` are the only states")
    return answer


def _op_transition(p):
    labels = state_labels()
    target = p["transition_id"]
    # `open` and `closed` are GitHub's own issue states, not workflow labels, so
    # they work whether or not the repository configured `state-labels`. An
    # issue that cannot be closed is an issue nothing can finish.
    if target in ("closed", "close", "open", "reopen"):
        verb = "close" if target in ("closed", "close") else "reopen"
        answer = _gh("issue", verb, _number(p["ticket_key"]), *_repo_args())
        if isinstance(answer, dict) and (answer.get("error") or answer.get("unavailable")):
            return answer
        return {"ok": True, "ticket_key": _number(p["ticket_key"]),
                "state": "closed" if verb == "close" else "open"}
    if target not in labels:
        return {"error": True, "reason":
                f"tracker: github-issues — no state `{target}` in "
                f"`github-issues.state-labels` (have: {', '.join(labels) or 'none'}); "
                f"`open` and `closed` always work"}
    number = _number(p["ticket_key"])
    args = ["issue", "edit", number, *_repo_args(), "--add-label", labels[target]]
    # Exactly one state label at a time: leaving the previous one on makes the
    # issue read as being in two states, and nothing else would remove it.
    for name, label in labels.items():
        if name != target:
            args += ["--remove-label", label]
    answer = _gh(*args)
    if isinstance(answer, dict) and (answer.get("error") or answer.get("unavailable")):
        return answer
    return {"ok": True, "ticket_key": number, "state": target, "label": labels[target]}


def _op_changelog(p):
    """GitHub's timeline is the change history."""
    return _gh("api", f"repos/{repo()}/issues/{_number(p['ticket_key'])}/timeline",
               "--paginate") if repo() else {
        "error": True,
        "reason": "tracker: github-issues — set `github-issues.repo` in .afk/config.yaml"}


def _op_comment(p):
    answer = _gh("issue", "comment", _number(p["ticket_key"]), *_repo_args(),
                 "--body-file", "-", stdin=p["text"])
    return answer if isinstance(answer, dict) else {"ok": True, "raw": answer}


def _op_attachments(p):
    number = _number(p["ticket_key"])
    issue = _op_get({"ticket_key": number, "fields": "body"})
    if not isinstance(issue, dict):
        return issue
    text = issue.get("body") or ""
    comments = _gh("issue", "view", number, *_repo_args(), "--json", "comments")
    if isinstance(comments, dict):
        for c in comments.get("comments") or []:
            text += "\n" + (c.get("body") or "")
    urls = sorted(set(ASSET_URL.findall(text)))
    return {"attachments": [{"id": u.rsplit("/", 1)[-1], "content": u} for u in urls],
            "partial": True,
            "reason": "GitHub has no attachment API; this lists the asset URLs "
                      "referenced in the issue body and its comments"}


def _op_edit(p):
    """`fields` is GitHub's own shape: title, body, labels, assignees, milestone."""
    fields = p["fields"] or {}
    args = ["issue", "edit", _number(p["ticket_key"]), *_repo_args()]
    if "title" in fields:
        args += ["--title", str(fields["title"])]
    if "body" in fields:
        args += ["--body", str(fields["body"])]
    if "milestone" in fields:
        args += ["--milestone", str(fields["milestone"])]
    for label in fields.get("labels") or []:
        args += ["--add-label", str(label)]
    for label in fields.get("remove_labels") or []:
        args += ["--remove-label", str(label)]
    for user in fields.get("assignees") or []:
        args += ["--add-assignee", str(user)]
    unknown = set(fields) - {"title", "body", "milestone", "labels",
                             "remove_labels", "assignees"}
    answer = _gh(*args)
    # A GitHub label has to exist in the repository before it can be applied,
    # and gh reports that as a bare "'<label>' not found". Say which label and
    # why, rather than passing the tool's stderr through; creating the label
    # here would change the repository's settings on a caller's behalf.
    if isinstance(answer, dict) and answer.get("error"):
        body = str(answer.get("body") or "")
        for label in (fields.get("labels") or []) + (fields.get("remove_labels") or []):
            if f"'{label}' not found" in body:
                answer = dict(answer)
                answer["operation"] = "tracker_edit"
                answer["reason"] = (
                    f"label `{label}` does not exist in {repo()} - GitHub labels "
                    f"must be created in the repository before an issue can carry "
                    f"one; nothing was written")
                break
    if unknown and isinstance(answer, dict):
        answer = dict(answer)
        answer["ignored_fields"] = sorted(unknown)
        answer["reason"] = ("tracker: github-issues edits title, body, milestone, "
                            "labels and assignees; the listed fields have no "
                            "GitHub Issues equivalent and were NOT written")
    return answer


def _op_create(p):
    args = ["issue", "create", *_repo_args(), "--title", p["summary"]]
    body = p.get("description") or ""
    args += ["--body-file", "-"]
    # The work item type is a label here, as is the opening state.
    for label in filter(None, [p.get("issue_type"), state_labels().get(p.get("status") or "")]):
        args += ["--label", str(label)]
    if p.get("assignee"):
        args += ["--assignee", str(p["assignee"])]
    if p.get("fix_version"):
        args += ["--milestone", str(p["fix_version"])]
    answer = _gh(*args, stdin=body)
    url = answer.get("raw", "") if isinstance(answer, dict) else ""
    if isinstance(answer, dict) and (answer.get("error") or answer.get("unavailable")):
        return answer
    key = url.rstrip("/").rsplit("/", 1)[-1] if url else ""
    result = {"key": key, "url": url.strip()}

    parent = p.get("parent")
    if parent and key:
        # No parent field exists; a tracking issue's task list is the convention.
        note = _gh("issue", "comment", _number(parent), *_repo_args(),
                   "--body-file", "-", stdin=f"- [ ] #{key}")
        if isinstance(note, dict) and note.get("error"):
            result["parent_warning"] = note.get("body") or note.get("reason")
        else:
            result["parent"] = _number(parent)
    return result


_DISPATCH = {
    "tracker_get": _op_get,
    "tracker_search": _op_search,
    "tracker_create": _op_create,
    "tracker_edit": _op_edit,
    "tracker_comment": _op_comment,
    "tracker_transition": _op_transition,
    "tracker_transitions": _op_transitions,
    "tracker_attachments": _op_attachments,
    "tracker_changelog": _op_changelog,
}


def call(operation, payload=None):
    """The one entry point every tracker adapter exposes."""
    fn = _DISPATCH.get(operation)
    if fn is None:
        return {"unsupported": True, "operation": operation,
                "reason": f"tracker/github-issues has no operation {operation}"}
    try:
        return fn(payload or {})
    except KeyError as e:
        return {"error": True, "operation": operation,
                "reason": f"missing required argument {e}"}


def main(argv):
    if argv and argv[0] == "--list-tools":
        for name in OPERATIONS:
            print(name)
        return 0
    if not argv:
        print(json.dumps({"operations": list(OPERATIONS)}))
        return 0
    payload, unreadable = payload_reader.parse(
        argv[1] if len(argv) > 1 else None, argv[0])
    if unreadable is not None:
        print(json.dumps(unreadable))
        return payload_reader.EXIT_UNREADABLE_PAYLOAD
    answer = call(argv[0], payload)
    print(json.dumps(answer))
    return 3 if isinstance(answer, dict) and answer.get("unsupported") else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
