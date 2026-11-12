"""The one Draft change of a branch: `change_request.py <verb> [json-payload]`, or the payload on stdin."""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ci_watch import (  # noqa: E402
    Refusal, call_forge, change_ref, envelope, error_of, forge_answer, gate_record, need, ok, passed_on, refusal_of, shell,
    write_parts)

ROLES = ("assignee", "reviewer")
PERSON = re.compile(r"[0-9A-Za-z][0-9A-Za-z._-]*")
BRANCH = re.compile(r"[0-9A-Za-z_][0-9A-Za-z._/-]*")
FETCH_LIMIT = 120
SECTIONS = (("What changes", "description"), ("Why it can merge", "mergeability"), ("Self-critique", "self_critique"))
PROOF_SHAPE = "{row, behavior, level, ran, evidence}"
PROOF_FIELDS = ("row", "behavior", "level", "ran", "evidence")
FOUND_HEADING = "## Found along the way"
FOUND_FIELDS = ("what", "where", "how")
# Only the developer picks a found bug, except fix-in-place: a bug that blocks a planned proof or corrupts data (SDD §6).
AGENT_PICK = "fix-in-place"
NEEDS_REASON = ("dropped", AGENT_PICK)


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
    """The proof lines: 1 per plan row or changed behavior, each with every field the ship check reads."""
    value = parts.get("proofs")
    if not isinstance(value, list):
        raise _bad(f"`proofs` must be a list of {PROOF_SHAPE}; an empty list for a change with no user-visible behavior")
    proofs = []
    for item in value:
        if isinstance(item, dict) and "claim" in item:
            raise _bad(f"`proofs`: the old {{claim, evidence}} shape is gone; give each proof as {PROOF_SHAPE}, "
                       f"with `row` the plan row id, or a short name of the behavior with no plan row")
        if not isinstance(item, dict):
            raise _bad(f"`proofs`: each entry is an object {PROOF_SHAPE}, not {item!r}")
        for key in PROOF_FIELDS:
            if not _is_text(item.get(key)):
                raise _bad(f"`proofs`: the proof line {item.get('row')!r} needs `{key}`")
        if item["level"] not in gate_record.LEVELS:
            raise _bad(f"`proofs`: level {item['level']!r} of {item['row']!r} is not one of {', '.join(gate_record.LEVELS)}")
        proofs.append({key: item[key].strip() for key in PROOF_FIELDS})
    return proofs


def _found(parts):
    """The bugs seen along the way, numbered FB-01 on in their order. A pick other than fix-in-place is the developer's."""
    value = parts.get("found", [])
    if not isinstance(value, list):
        raise _bad("`found` must be a list of {what, where, how}")
    found = []
    for n, item in enumerate(value, 1):
        if not isinstance(item, dict) or not all(_is_text(item.get(key)) for key in FOUND_FIELDS):
            raise _bad(f"`found`: each bug needs `what`, `where` and `how`, not {item!r}")
        pick, by, reason = item.get("pick"), item.get("by"), item.get("reason")
        if pick is not None:
            if pick not in gate_record.PICKS:
                raise _bad(f"`found`: pick {pick!r} is one of {', '.join(gate_record.PICKS)}")
            if by != gate_record.DEVELOPER and pick != AGENT_PICK:
                raise _bad(f"`found`: only the developer picks {pick}; give `by: {gate_record.DEVELOPER}` with the developer's mark")
            if not _is_text(by):
                raise _bad("`found`: a pick needs `by`")
            if pick in NEEDS_REASON and not _is_text(reason):
                raise _bad(f"`found`: the pick {pick} needs `reason`")
        found.append({"id": f"FB-{n:02d}", **{key: item[key].strip() for key in FOUND_FIELDS}, "pick": pick,
                      "by": by if pick else None, "reason": reason.strip() if pick and _is_text(reason) else None})
    return found


def _found_line(bug):
    pick = "waits for the developer"
    if bug["pick"]:
        pick = f"{bug['pick']}, by {bug['by']}" + (f": {bug['reason']}" if bug["reason"] else "")
    return f"- {bug['id']}: {bug['what']}. Where: {bug['where']}. Seen: {bug['how']}. Pick: {pick}"


def build_body(parts):
    """The description of the change. Every part is required, so a change never opens without one."""
    what, case, critique = (_text(parts, key) for _, key in SECTIONS)
    requests = "\n".join(f"- @{item['person']} ({item['role']}): {item['request'].strip()}" for item in _requests(parts))
    proofs = "\n".join(f"- {item['row']} ({item['level']}): {item['behavior']}. Ran: {item['ran']}. Evidence: {item['evidence']}"
                       for item in _proofs(parts)) or "None."
    found = "\n".join(_found_line(bug) for bug in _found(parts)) or "None."
    return "\n\n".join((f"## What changes\n\n{what}", f"## Requests\n\n{requests}", f"## Proofs\n\n{proofs}",
                        f"{FOUND_HEADING}\n\n{found}", f"## Why it can merge\n\n{case}", f"## Self-critique\n\n{critique}")) + "\n"


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
            raise Refusal("change-not-open", f"change {payload['id']} is {view.get('state')}", change_state=view.get("state") or "")
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


def _refuse_another_target(payload, view):
    """The case in the description rests on the target it was given, so a different target must not pass with no message."""
    if payload.get("target") and view.get("target") and _branch(payload["target"], "target") != view["target"]:
        raise Refusal("target-differs", f"change {view['id']} targets {view['target']}, not {payload['target']}", target=view["target"])


def open_change(payload):
    """Create the Draft change of the branch, or write the description of its open change."""
    body = build_body(payload)
    view = _existing(payload)
    if view is None:
        answer = _create(payload, body)
    else:
        _refuse_another_target(payload, view)
        forge_answer("change-update-body", payload, id=view["id"], body=body)
        answer = ok(id=view["id"], url=view.get("url") or "", draft=bool(view.get("draft")), created=False)
    write_parts(str(answer["id"]), _proofs(payload), _found(payload))
    return answer


def _resolved_target(name):
    for candidate in (f"origin/{name}", name):
        if shell.run_tool("git", ["rev-parse", "--verify", "--quiet", f"{candidate}^{{commit}}"]).returncode == 0:
            return candidate
    raise Refusal("no-target", f"no branch {name} here or on origin")


def _count(*args):
    done = shell.run_tool("git", ["rev-list", "--count", *args])
    return int(done.stdout.strip()) if done.returncode == 0 else None


def _fetched(name):
    """A fetch that fails or runs past its limit leaves the facts of the last fetch, and the answer says so. The full refspec moves the tracking ref in a clone that does not track this branch."""
    refspec = f"+refs/heads/{name}:refs/remotes/origin/{name}"
    try:
        return shell.run_tool("git", ["fetch", "--quiet", "origin", refspec], timeout=FETCH_LIMIT).returncode == 0
    except Refusal:
        return False


def merge_facts(payload):
    """What git says about merging the target into HEAD. No file and no branch changes."""
    name = _branch(need(payload, "target"), "target")
    fetched = _fetched(name)
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
