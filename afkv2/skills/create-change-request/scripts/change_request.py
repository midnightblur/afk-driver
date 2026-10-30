"""The one Draft change of a branch: `change_request.py <verb> [json-payload]`, or the payload on stdin."""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ci_watch import (  # noqa: E402
    Refusal, call_forge, change_ref, envelope, error_of, forge_answer, need, ok, passed_on, refusal_of, shell)

ROLES = ("assignee", "reviewer")
PERSON = re.compile(r"[0-9A-Za-z][0-9A-Za-z._-]*")
BRANCH = re.compile(r"[0-9A-Za-z_][0-9A-Za-z._/-]*")
FETCH_LIMIT = 120
SECTIONS = (("What changes", "description"), ("Why it can merge", "mergeability"), ("Self-critique", "self_critique"))


def _bad(reason):
    return Refusal("bad-payload", reason)


def _is_text(value):
    return isinstance(value, str) and bool(value.strip())


def _text(parts, key):
    if not _is_text(parts.get(key)):
        raise _bad(f"`{key}` must be a text that is not blank")
    return parts[key].strip()


def _entries(parts, key):
    value = parts.get(key)
    if not isinstance(value, list) or not value:
        raise _bad(f"`{key}` must be a list with at least one entry")
    return value


def _requests(parts):
    people, seen = [], set()
    for item in _entries(parts, "requests"):
        whole = (isinstance(item, dict) and isinstance(item.get("person"), str) and PERSON.fullmatch(item["person"])
                 and item.get("role") in ROLES and _is_text(item.get("request")))
        if not whole:
            raise _bad(f"`requests`: each entry needs `person` (a login, no @), `role` ({' or '.join(ROLES)}) and `request`, not {item!r}")
        if item["person"].lower() in seen:
            raise _bad(f"`requests`: one request per person; {item['person']} has 2")
        seen.add(item["person"].lower())
        people.append(item)
    return people


def _proofs(parts):
    for item in _entries(parts, "proofs"):
        if not (isinstance(item, dict) and _is_text(item.get("claim")) and _is_text(item.get("evidence"))):
            raise _bad(f"`proofs`: each entry needs `claim` and `evidence`, not {item!r}")
    return parts["proofs"]


def build_body(parts):
    """The description of the change. Every part is required, so a change never opens without one."""
    what, case, critique = (_text(parts, key) for _, key in SECTIONS)
    requests = "\n".join(f"- @{item['person']} ({item['role']}): {item['request'].strip()}" for item in _requests(parts))
    proofs = "\n".join(f"- {item['claim'].strip()}: {item['evidence'].strip()}" for item in _proofs(parts))
    return "\n\n".join((f"## What changes\n\n{what}", f"## Requests\n\n{requests}", f"## Proofs\n\n{proofs}",
                        f"## Why it can merge\n\n{case}", f"## Self-critique\n\n{critique}")) + "\n"


def _branch(value, key):
    name = value.removeprefix("origin/") if isinstance(value, str) else ""
    if not BRANCH.fullmatch(name) or ".." in name:
        raise _bad(f"`{key}` must be a branch name, not {value!r}")
    return name


def _current_branch(payload):
    if payload.get("source"):
        return _branch(payload["source"], "source")
    done = shell.run_tool("git", ["rev-parse", "--abbrev-ref", "HEAD"])
    name = done.stdout.strip() if done.returncode == 0 else ""
    if not name or name == "HEAD":
        raise Refusal("no-branch", "no branch is checked out: pass `id` or `source`")
    return name


def _existing(payload):
    """The open change of the branch, or None. Only `not-found` means none: another failure must not make a second change."""
    if payload.get("id"):
        view = forge_answer("change-view", payload, id=change_ref(payload))
        if view.get("state") != "opened":
            raise Refusal("change-not-open", f"change {payload['id']} is {view.get('state')}")
        return view
    answer = call_forge("change-view", {**passed_on(payload), "id": _current_branch(payload)})
    if answer.get("ok"):
        return answer if answer.get("state") == "opened" else None
    if error_of(answer).get("code") == "not-found":
        return None
    raise refusal_of(answer, "forge change-view")


def _people(requests, role):
    return [item["person"] for item in requests if item["role"] == role]


def _create(payload, body):
    title = need(payload, "title")
    if not _is_text(title):
        raise _bad("`title` must be a text that is not blank")
    target = _branch(need(payload, "target"), "target")
    requests = _requests(payload)
    created = forge_answer("change-create-draft", payload, title=title, body=body, target=target, source=_current_branch(payload),
                           assignee=_people(requests, "assignee"), reviewer=_people(requests, "reviewer"))
    view = forge_answer("change-view", payload, id=created["id"])
    if not view.get("draft"):
        raise Refusal("not-draft", f"change {created['id']} did not open as Draft: {view.get('url')}", id=created["id"], url=view.get("url"))
    return ok(id=created["id"], url=view.get("url") or created.get("url") or "", draft=True, created=True)


def open_change(payload):
    """Create the Draft change of the branch, or write the description of its open change."""
    body = build_body(payload)
    view = _existing(payload)
    if view is None:
        return _create(payload, body)
    forge_answer("change-update-body", payload, id=view["id"], body=body)
    return ok(id=view["id"], url=view.get("url") or "", draft=bool(view.get("draft")), created=False)


def _resolved_target(name):
    for candidate in (f"origin/{name}", name):
        if shell.run_tool("git", ["rev-parse", "--verify", "--quiet", f"{candidate}^{{commit}}"]).returncode == 0:
            return candidate
    raise Refusal("no-target", f"no branch {name} here or on origin")


def _count(*args):
    done = shell.run_tool("git", ["rev-list", "--count", *args])
    return int(done.stdout.strip()) if done.returncode == 0 else None


def merge_facts(payload):
    """What git says about merging the target into HEAD. No file and no branch changes."""
    name = _branch(need(payload, "target"), "target")
    fetched = shell.run_tool("git", ["fetch", "--quiet", "origin", name], timeout=FETCH_LIMIT).returncode == 0
    target = _resolved_target(name)
    done = shell.run_tool("git", ["merge-tree", "--write-tree", "--name-only", "--no-messages", target, "HEAD"])
    if done.returncode not in (0, 1):
        raise Refusal("no-merge-answer", f"git merge-tree failed: {done.stderr.strip()[:500]}")
    conflicts = [line for line in done.stdout.splitlines()[1:] if line]
    return ok(target=target, fetched=fetched, clean=done.returncode == 0, conflicts=conflicts,
              ahead=_count(f"{target}..HEAD"), behind=_count(f"HEAD..{target}"))


VERBS = {"open": open_change, "merge-facts": merge_facts}


def main(argv=None):
    return envelope.serve(VERBS, sys.argv[1:] if argv is None else argv)


if __name__ == "__main__":
    sys.exit(main())
