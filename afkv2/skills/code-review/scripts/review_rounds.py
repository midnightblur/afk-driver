"""The rounds of one subtask's review: `review_rounds.py <verb> [json-payload]`, or the payload on stdin."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[3]
FORGE = PLUGIN / "ports" / "forge" / "cli.py"
sys.path.insert(0, str(PLUGIN / "ports"))

from tracker import envelope  # noqa: E402
from tracker.envelope import Refusal, need, ok  # noqa: E402

CAP = 3
FORGE_LIMIT = 300
SEVERITIES = ("critical", "high", "medium", "low")
TO_FIX = SEVERITIES[:2]
TO_POST = SEVERITIES[2:]
SUBTASK_ID = re.compile(r"[0-9A-Za-z][0-9A-Za-z._-]*")
TEXT_FIELDS = ("concern", "finding", "why", "fix")
SIDES = ("new", "old", "context")


def next_round(rounds_done):
    """The round after `rounds_done` finished rounds; None once the cap is reached."""
    return rounds_done + 1 if rounds_done < CAP else None


def route(findings):
    """Split findings by severity: (to fix, to post)."""
    return ([f for f in findings if f["severity"] in TO_FIX],
            [f for f in findings if f["severity"] in TO_POST])


def call_forge(verb, payload):
    """One call of the forge command. Every failure comes back as the failure answer."""
    try:
        done = subprocess.run([sys.executable, str(FORGE), verb], input=json.dumps(payload).encode("utf-8"),
                              capture_output=True, timeout=FORGE_LIMIT)
        answer = json.loads(done.stdout)
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        return envelope.fail("forge-failed", f"the forge command gave no answer: {error}")
    if not isinstance(answer, dict) or "ok" not in answer:
        return envelope.fail("forge-failed", "the forge command gave no answer object")
    return answer


def _bad(reason):
    return Refusal("bad-payload", reason)


def _state_path(payload):
    plan, subtask = Path(str(need(payload, "plan"))), str(need(payload, "subtask"))
    if not SUBTASK_ID.fullmatch(subtask):
        raise _bad(f"`subtask` must be a subtask id, not {subtask!r}")
    if not plan.is_dir():
        raise _bad(f"no plan folder at {plan}")
    return plan / "review" / f"{subtask}.rounds.json"


def _load(path, subtask):
    """The state of `subtask`, or None when its review has not started."""
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as error:
        raise Refusal("bad-state", f"the state file {path} is unreadable: {error}") from None
    if not isinstance(state, dict) or state.get("subtask") != subtask:
        raise Refusal("bad-state", f"the state file {path} does not hold subtask {subtask}")
    return state


def _started(path, subtask):
    state = _load(path, subtask)
    if state is None:
        raise Refusal("no-review", f"no review of {subtask} has started: run `begin`")
    return state


def _save(path, state):
    """Write through a temporary file, so a crash leaves the last whole state."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(state, indent=1, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


def _is_text(value):
    return isinstance(value, str) and bool(value.strip())


def _named_reasons(payload, key):
    """A list of {name, why}, each value a text that is not blank."""
    value = payload.get(key)
    if not isinstance(value, list) or not all(
            isinstance(item, dict) and _is_text(item.get("name")) and _is_text(item.get("why")) for item in value):
        raise _bad(f"`{key}` must be a list of objects with `name` and `why`")
    return [{"name": item["name"], "why": item["why"]} for item in value]


def _done(state):
    return sum(1 for entry in state["rounds"] if entry["recorded"])


def _open_round(state):
    return next((entry for entry in state["rounds"] if not entry["recorded"]), None)


def _is_open_fix(entry):
    return entry["severity"] in TO_FIX and entry["outcome"] is None


def _is_new_fix(entry, rounds_done):
    return entry["outcome"] == "fixed" and entry["last_round"] == rounds_done


def _refuse_unless_running(state):
    if state["stopped_by"] is not None:
        raise Refusal("review-over", f"the review of {state['subtask']} stopped: {state['stopped_by']}")


def _refuse_open_fixes(state):
    waiting = [entry["id"] for entry in state["findings"] if _is_open_fix(entry)]
    if waiting:
        raise Refusal("fix-open", f"these findings have no outcome: {', '.join(waiting)}")


def begin(payload):
    path, change = _state_path(payload), str(need(payload, "change"))
    concerns = _named_reasons(payload, "concerns")
    if not concerns:
        raise _bad("`concerns` needs at least one concern")
    deferred = _named_reasons(payload, "deferred") if payload.get("deferred") is not None else []
    state = _load(path, payload["subtask"]) or {"subtask": payload["subtask"], "rounds": [], "findings": [], "stopped_by": None}
    _refuse_unless_running(state)
    if state.get("change", change) != change:
        raise Refusal("change-mismatch", f"this review posts on change {state['change']}, not {change}")
    current = _open_round(state)
    resumed = current is not None
    if current is None:
        current = _new_round(state)
    current.update(concerns=concerns, deferred=deferred)
    state["change"] = change
    _save(path, state)
    return ok(round=current["round"], cap=CAP, resumed=resumed)


def _new_round(state):
    done = _done(state)
    number = next_round(done)
    if number is None:
        raise Refusal("round-cap", f"round {done} was the last: run `finish`")
    _refuse_open_fixes(state)
    if done and not any(_is_new_fix(entry, done) for entry in state["findings"]):
        raise Refusal("no-fix-to-review", f"round {done} left no fix to review: run `finish`")
    current = {"round": number, "recorded": False}
    state["rounds"].append(current)
    return current


def _checked_finding(item, index):
    if not isinstance(item, dict):
        raise _bad(f"finding {index} is not an object")
    severity, file, line, side = item.get("severity"), item.get("file"), item.get("line"), item.get("side") or "new"
    if severity not in SEVERITIES:
        raise _bad(f"finding {index}: `severity` must be one of {', '.join(SEVERITIES)}")
    for field in TEXT_FIELDS:
        if not _is_text(item.get(field)):
            raise _bad(f"finding {index}: `{field}` must be a text that is not blank")
    if file is not None and not _is_text(file):
        raise _bad(f"finding {index}: `file` must be a path or null")
    if line is not None and (type(line) is not int or line < 1):
        raise _bad(f"finding {index}: `line` must be a line number or null")
    if side not in SIDES:
        raise _bad(f"finding {index}: `side` must be one of {', '.join(SIDES)}")
    file = file.replace("\\", "/") if file else None
    return {"severity": severity, "file": file, "line": line, "side": "old" if side == "old" else "new", **{field: item[field] for field in TEXT_FIELDS}}


def _key(found):
    """The same defect across rounds: its line can move, so the line is not part of the key."""
    words = " ".join(found["finding"].lower().split())
    return hashlib.sha256(f"{found['file']}\n{words}".encode("utf-8")).hexdigest()


def _entry_of(state, key, found, number):
    """The entry with the same text and the nearest line. In one round, the same text at another line is another defect."""
    same = [item for item in state["findings"] if item["key"] == key and (item["last_round"] != number or item["line"] == found["line"])]
    return min(same, key=lambda item: abs((item["line"] or 0) - (found["line"] or 0)), default=None)


def _merge(state, found, number):
    key = _key(found)
    entry = _entry_of(state, key, found, number)
    if entry is None:
        state["findings"].append({"id": f"f{len(state['findings']) + 1}", "key": key, "first_round": number, "last_round": number,
                                  "outcome": None, "sha": None, "reason": None, "comment": None, "post_error": None,
                                  "replaces": None, "reopened": 0, **found})
        return
    if entry["last_round"] == number and SEVERITIES.index(entry["severity"]) < SEVERITIES.index(found["severity"]):
        found["severity"] = entry["severity"]
    if entry["outcome"] == "fixed":
        entry["reopened"] += 1
    if entry["severity"] in TO_POST and found["severity"] in TO_FIX and entry["comment"]:
        entry.update(replaces=entry["comment"]["url"], comment=None)
    entry.update(found, last_round=number, outcome=None, sha=None, reason=None)


def _comment_text(entry):
    place = f"`{entry['file']}:{entry['line']}`" if entry["file"] and entry["line"] else f"`{entry['file']}`" if entry["file"] else None
    lines = [f"**{entry['severity']}** ({entry['concern']}): {entry['finding']}", ""]
    if place:
        lines.append(f"Location: {place}")
    lines += [f"Why: {entry['why']}", f"Fix: {entry['fix']}"]
    if entry["reason"]:
        lines.append(f"Not fixed: {entry['reason']}")
    if entry["replaces"]:
        lines.append(f"Replaces: {entry['replaces']}")
    return "\n".join(lines)


def _comment_payload(state, entry):
    payload = {"id": state["change"], "text": _comment_text(entry)}
    if entry["file"] and entry["line"]:
        payload["file"] = entry["file"]
        if entry["side"] == "old":
            payload.update(side="old", old_line=entry["line"])
        else:
            payload["line"] = entry["line"]
    return payload


def _post(path, state, entries):
    """Post each entry and save after each one, so a crash does not post it twice."""
    for entry in entries:
        answer = call_forge("change-comment", _comment_payload(state, entry))
        if answer.get("ok"):
            entry["comment"] = {field: answer.get(field) for field in ("comment", "url", "inline", "reason")}
            entry["post_error"] = None
        else:
            error = answer.get("error")
            entry["post_error"] = error.get("reason") if isinstance(error, dict) else "the forge command gave no reason"
        _save(path, state)


def record(payload):
    path = _state_path(payload)
    findings = payload.get("findings")
    if not isinstance(findings, list):
        raise _bad("the payload needs `findings`, a list")
    checked = [_checked_finding(item, index) for index, item in enumerate(findings)]
    state = _load(path, payload["subtask"])
    current = _open_round(state) if state else None
    if current is None:
        raise Refusal("no-open-round", "no round is open: run `begin`")
    number = current["round"]
    for found in checked:
        _merge(state, found, number)
    current["recorded"] = True
    _save(path, state)
    seen = [entry for entry in state["findings"] if entry["last_round"] == number]
    fix, post = route(seen)
    new_posts = [entry for entry in post if entry["comment"] is None]
    _post(path, state, new_posts)
    return ok(round=number, cap=CAP, next=_next_step(fix, number),
              fix=[_for_the_fixer(entry) for entry in fix],
              posted=[_posted(entry) for entry in new_posts if entry["comment"]],
              post_failed=[{"id": entry["id"], "reason": entry["post_error"]} for entry in new_posts if not entry["comment"]])


def _next_step(fix, number):
    if not fix:
        return "stop"
    return "fix" if next_round(number) else "fix-then-finish"


def _for_the_fixer(entry):
    return {field: entry[field] for field in ("id", "severity", "concern", "file", "line", "side", "finding", "why", "fix")}


def _posted(entry):
    return {"id": entry["id"], "url": entry["comment"]["url"], "inline": entry["comment"]["inline"],
            "reason": entry["comment"]["reason"]}


def outcome(payload):
    path = _state_path(payload)
    state = _started(path, payload["subtask"])
    _refuse_unless_running(state)
    ident, result = need(payload, "id"), need(payload, "result")
    entry = next((item for item in state["findings"] if item["id"] == ident), None)
    if entry is None or entry["severity"] not in TO_FIX:
        raise Refusal("no-such-finding", f"no critical or high finding has the id {ident}")
    if result == "fixed":
        entry.update(outcome="fixed", sha=str(need(payload, "sha")), reason=None)
    elif result == "unfixed":
        entry.update(outcome="unfixed", sha=None, reason=str(need(payload, "reason")))
    else:
        raise _bad("`result` must be fixed or unfixed")
    _save(path, state)
    return ok(id=ident, result=result)


def _stop_reason(state):
    """Why the review may stop now; a refusal while the review still owes a fix or a round."""
    done = _done(state)
    if done < CAP:
        _refuse_open_fixes(state)
        if any(_is_new_fix(entry, done) for entry in state["findings"]):
            raise Refusal("review-owed", f"a fix of round {done} waits for its review: run `begin`")
    blocking = [entry for entry in state["findings"] if entry["severity"] in TO_FIX]
    if done >= CAP and any(entry["last_round"] == done for entry in blocking):
        return "cap"
    return "unfixed" if any(entry["outcome"] == "unfixed" for entry in blocking) else "clean"


def _summary(entry):
    comment = entry["comment"] or {}
    return {"id": entry["id"], "severity": entry["severity"], "concern": entry["concern"], "file": entry["file"], "line": entry["line"],
            "finding": entry["finding"], "reason": entry["reason"], "url": comment.get("url"), "replaces": entry["replaces"],
            "post_error": entry["post_error"]}


def _report(state):
    done = _done(state)
    findings = state["findings"]
    fixed = [{"id": entry["id"], "sha": entry["sha"], "finding": entry["finding"], "reviewed": entry["last_round"] < done}
             for entry in findings if entry["outcome"] == "fixed"]
    left = [entry for entry in findings if entry["outcome"] != "fixed"]
    ran = {concern["name"] for entry in state["rounds"] for concern in entry["concerns"]}
    deferred = {item["name"]: item for entry in state["rounds"] for item in entry["deferred"] if item["name"] not in ran}
    return ok(stopped_by=state["stopped_by"], rounds=done, cap=CAP, change=state["change"],
              concerns=[{"round": entry["round"], "concerns": entry["concerns"]} for entry in state["rounds"]],
              deferred=list(deferred.values()), fixed=fixed,
              reopened=[entry["id"] for entry in findings if entry["reopened"]],
              left={"blocking": [_summary(entry) for entry in left if entry["severity"] in TO_FIX],
                    "posted": [_summary(entry) for entry in left if entry["severity"] in TO_POST and entry["comment"]],
                    "not_posted": [_summary(entry) for entry in left if not entry["comment"]]})


def finish(payload):
    path = _state_path(payload)
    state = _started(path, payload["subtask"])
    if _open_round(state) is not None:
        raise Refusal("round-open", "a round has no findings yet: run `record`")
    if state["stopped_by"] is None:
        state["stopped_by"] = _stop_reason(state)
        _save(path, state)
    _post(path, state, [entry for entry in state["findings"] if entry["outcome"] != "fixed" and entry["comment"] is None])
    return _report(state)


VERBS = {"begin": begin, "record": record, "outcome": outcome, "finish": finish}


def main(argv=None):
    return envelope.serve(VERBS, sys.argv[1:] if argv is None else argv)


if __name__ == "__main__":
    sys.exit(main())
