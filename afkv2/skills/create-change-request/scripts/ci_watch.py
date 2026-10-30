"""The CI watch and the Ready gate: `ci_watch.py <verb> [json-payload]`, or the payload on stdin."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[3]
FORGE = PLUGIN / "ports" / "forge" / "cli.py"
REVIEW = PLUGIN / "skills" / "code-review" / "scripts" / "review_rounds.py"
sys.path.insert(0, str(PLUGIN / "ports"))

from tracker import envelope, shell  # noqa: E402
from tracker.envelope import Refusal, need, ok  # noqa: E402

COMMAND_LIMIT = 300
REVIEW_LIMIT = 900
READ_MARGIN = 300
DEFAULT_BUDGET = 5400
SLICE = 600
LOST_AFTER = 3 * SLICE
HEAD_GRACE = 300
HEAD_PAUSE = 15
PASSED_ON = ("forge", "repo")
CI_REFUSALS = {"failed": "ci-red", "canceled": "ci-red", "running": "ci-running", "": "ci-none"}
REVIEW_CAN_RUN = {"no-review", "review-owed", "fix-open", "round-open"}
REVIEW_CAN_RETRY = {"command-failed"}
FILE_TRIES, FILE_PAUSE = 20, 0.1
SUBTASK_FILE = re.compile(r"[0-9]{4}-.+\.md")
_NOT_A_FILE_NAME = re.compile(r"[^0-9A-Za-z._-]")


def _call(script, verb, payload, limit):
    """One call of a skill or port command. Every failure comes back as the failure answer."""
    try:
        done = subprocess.run([sys.executable, str(script), verb], input=json.dumps(payload).encode("utf-8"),
                              capture_output=True, timeout=limit)
        answer = json.loads(done.stdout)
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        return envelope.fail("command-failed", f"{script.name} {verb} gave no answer: {error}")
    if not isinstance(answer, dict) or "ok" not in answer:
        return envelope.fail("command-failed", f"{script.name} {verb} gave no answer object")
    return answer


def call_forge(verb, payload, limit=COMMAND_LIMIT):
    return _call(FORGE, verb, payload, limit)


def call_review(plan, subtask):
    """The report of the review: `finish` is the review's one public report, and it repeats after a stop."""
    return _call(REVIEW, "finish", {"plan": str(plan), "subtask": subtask}, REVIEW_LIMIT)


def _bad(reason):
    return Refusal("bad-payload", reason)


def change_ref(payload):
    value = str(need(payload, "id"))
    if value.startswith("-"):
        raise _bad(f"`id` {value} is no change reference")
    return value


def passed_on(payload):
    return {key: payload[key] for key in PASSED_ON if payload.get(key)}


def error_of(answer):
    """The error object of a failure answer, also when the answer holds none."""
    error = answer.get("error")
    return error if isinstance(error, dict) else {}


def refusal_of(answer, what):
    error = error_of(answer)
    return Refusal(error.get("code") or "command-failed", error.get("reason") or f"{what} gave no reason")


def forge_answer(verb, payload, **fields):
    """A forge answer, or its failure as this command's refusal."""
    answer = call_forge(verb, {**passed_on(payload), **fields})
    if not answer.get("ok"):
        raise refusal_of(answer, f"forge {verb}")
    return answer


def _seconds(payload, key, default):
    value = payload.get(key)
    if value is None or value == "":
        return default
    if type(value) is not int or value < 0:
        raise _bad(f"`{key}` must be a whole number of seconds")
    return value


def _git_line(*args):
    done = shell.run_tool("git", list(args))
    return done.stdout.strip() if done.returncode == 0 else None


def _local_head():
    return _git_line("rev-parse", "HEAD") or ""


def _record_path(change):
    """One record per change, in the git folder of this worktree: never a tracked file, and it goes with the worktree."""
    folder = _git_line("rev-parse", "--absolute-git-dir")
    if not folder:
        raise Refusal("no-repository", "the CI watch runs inside a git repository")
    file_name = _NOT_A_FILE_NAME.sub("_", change)
    return Path(folder) / "afkv2-ci" / f"{file_name}.json"


def _with_retries(action):
    """On Windows, a read and a replace of one file can refuse each other for a moment."""
    for _ in range(FILE_TRIES - 1):
        try:
            return action()
        except PermissionError:
            time.sleep(FILE_PAUSE)
    return action()


def _read_record(path):
    try:
        record = json.loads(_with_retries(lambda: path.read_text(encoding="utf-8")))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as error:
        raise Refusal("bad-record", f"the watch record {path} is unreadable: {error}; run `start`") from None
    if not isinstance(record, dict) or "token" not in record or "state" not in record or not isinstance(record.get("beat_at", 0), (int, float)):
        raise Refusal("bad-record", f"the watch record {path} holds no watch; run `start`")
    return record


def _write_record(path, record):
    """Write through a temporary file, so a reader never sees half a record."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(record, indent=1), encoding="utf-8")
    _with_retries(lambda: os.replace(temporary, path))


def _new_record(path, change, head):
    record = {"id": change, "token": uuid.uuid4().hex, "state": "watching", "status": "", "head_sha": head, "reason": "", "beat_at": time.time()}
    _write_record(path, record)
    return record


def _no_result(change, state, reason):
    return ok(id=change, state=state, status="", head_sha="", current_head=False, reason=reason)


def _report(change, record):
    if record is None:
        return _no_result(change, "none", "no watch has run on this change")
    state, reason = record["state"], record.get("reason") or ""
    if state == "watching" and time.time() - record.get("beat_at", 0) > LOST_AFTER:
        state, reason = "lost", "the watch stopped with no result: run `start`"
    return ok(id=change, state=state, status=record.get("status") or "", head_sha=record.get("head_sha") or "",
              current_head=bool(record.get("head_sha")) and record["head_sha"] == _local_head(), reason=reason)


def _spawn(payload):
    """Start the watch as a process of its own. CREATE_NO_WINDOW hides the console of each child, where DETACHED_PROCESS does not."""
    argv = [sys.executable, str(Path(__file__).resolve()), "watch", json.dumps(payload)]
    kwargs = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL, "close_fds": True}
    if os.name != "nt":
        subprocess.Popen(argv, start_new_session=True, **kwargs)
        return
    flags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
    try:
        subprocess.Popen(argv, creationflags=flags | subprocess.CREATE_BREAKAWAY_FROM_JOB, **kwargs)
    except OSError:
        subprocess.Popen(argv, creationflags=flags, **kwargs)


def _last_result(change, path):
    """What the last watch found. A broken record is a result here, so that it cannot stop the new watch."""
    try:
        return _report(change, _read_record(path))
    except Refusal as refusal:
        return _no_result(change, refusal.code, refusal.reason)


def start_watch(payload):
    """Start the watch of the commit just pushed and return at once, with the result of the last watch."""
    change = change_ref(payload)
    budget, interval = _seconds(payload, "budget", DEFAULT_BUDGET), _seconds(payload, "interval", None)
    path = _record_path(change)
    previous = _last_result(change, path)
    record = _new_record(path, change, _local_head())
    child = {**passed_on(payload), "id": change, "token": record["token"], "budget": budget}
    if interval is not None:
        child["interval"] = interval
    try:
        _spawn(child)
    except OSError as error:
        _write_record(path, {**record, "state": "no-verdict", "reason": f"the watch did not start: {error}"})
        raise Refusal("watch-not-started", f"the watch did not start: {error}") from None
    return ok(id=change, state="watching", previous=previous)


def _is_current(path, token):
    try:
        record = _read_record(path)
    except Refusal:
        return False
    return record is not None and record["token"] == token


def _superseded(change):
    return _no_result(change, "superseded", "a newer watch took over")


def _end(payload, path, record, state, status_word, reason=""):
    """Write the result, with the commit the forge now shows, unless a newer watch took over."""
    change = record["id"]
    head = record["head_sha"]
    try:
        head = forge_answer("change-view", payload, id=change).get("head_sha") or head
    except Refusal:
        pass
    if not _is_current(path, record["token"]):
        return _superseded(change)
    final = {**record, "state": state, "status": status_word, "head_sha": head, "reason": reason, "beat_at": time.time()}
    _write_record(path, final)
    return _report(change, final)


def _watched_record(payload, path, change):
    """The record of the child that `start` made, or a new record for a watch run by hand; None when a newer watch took over."""
    token = payload.get("token")
    if not token:
        return _new_record(path, change, _local_head())
    record = _read_record(path)
    return record if record is not None and record["token"] == token else None


def _forge_behind(payload, change, record):
    """True while the forge shows another commit than the one this watch started on. Right after a push, its answers are those of the last commit."""
    try:
        head = forge_answer("change-view", payload, id=change).get("head_sha")
    except Refusal:
        return False
    return bool(head) and head != record["head_sha"]


def watch_ci(payload):
    """Wait for the final CI status of the change and write it to the record. A red CI is a result, never a refusal."""
    change = change_ref(payload)
    budget, interval = _seconds(payload, "budget", DEFAULT_BUDGET), _seconds(payload, "interval", None)
    path = _record_path(change)
    record = _watched_record(payload, path, change)
    if record is None:
        return _superseded(change)
    started = time.monotonic()
    deadline = started + budget
    while True:
        left = max(0, int(deadline - time.monotonic()))
        wait = min(SLICE, left)
        fields = {"id": change, "budget": wait, **({} if interval is None else {"interval": interval})}
        answer = call_forge("ci-wait", {**passed_on(payload), **fields}, wait + READ_MARGIN)
        if not _is_current(path, record["token"]):
            return _superseded(change)
        if not answer.get("ok"):
            return _end(payload, path, record, "no-verdict", "", error_of(answer).get("reason") or "the forge gave no CI status")
        if answer.get("status") == "running":
            if left <= SLICE:
                return _end(payload, path, record, "no-verdict", "running", "the budget ended and the checks keep running")
        else:
            if not left or time.monotonic() - started >= HEAD_GRACE or not _forge_behind(payload, change, record):
                return _end(payload, path, record, "finished", answer.get("status") or "")
            time.sleep(HEAD_PAUSE)
        _write_record(path, {**record, "beat_at": time.time()})


def status(payload):
    change = change_ref(payload)
    return _report(change, _read_record(_record_path(change)))


def _subtasks(plan):
    return sorted(item.stem for item in plan.iterdir() if item.is_file() and SUBTASK_FILE.fullmatch(item.name))


def _ids(findings):
    return ", ".join(str(item.get("id")) for item in findings)


def _why_open(plan, subtask, change_ids):
    """Why the review of this subtask is not settled, and the next step; None when it is."""
    answer = call_review(plan, subtask)
    if not answer.get("ok"):
        error = error_of(answer)
        code = error.get("code")
        next_step = "run-review" if code in REVIEW_CAN_RUN else "mark-again" if code in REVIEW_CAN_RETRY else "developer"
        return error.get("reason") or "the review command gave no reason", next_step
    left = answer.get("left")
    if not isinstance(left, dict) or not answer.get("stopped_by"):
        return "the review command gave no report", "developer"
    if str(answer.get("change")) not in change_ids:
        return f"the review posted on change {answer.get('change')}, not on this change", "developer"
    if left.get("blocking"):
        return "critical or high findings are not fixed: " + _ids(left["blocking"]), "developer"
    if left.get("not_posted"):
        return "findings are not on the change: " + _ids(left["not_posted"]), "mark-again"
    return None


def _open_reviews(plan, change_ids):
    subtasks = _subtasks(plan)
    if not subtasks:
        return [{"subtask": "(none)", "why": f"the plan folder {plan} holds no subtask contract", "next": "developer"}]
    reasons = [(subtask, _why_open(plan, subtask, change_ids)) for subtask in subtasks]
    return [{"subtask": subtask, "why": found[0], "next": found[1]} for subtask, found in reasons if found]


def _head_view(payload, change):
    """The view of the open change at the local head, or the refusal."""
    view = forge_answer("change-view", payload, id=change)
    if view.get("state") != "opened":
        raise Refusal("change-not-open", f"change {change} is {view.get('state')}")
    local = _local_head()
    if not local or local != view.get("head_sha"):
        raise Refusal("head-differs", f"the local head {local} is not the head {view.get('head_sha')} of the change: push, or run from the branch of the change")
    return view


def _refuse_unless_green(payload, change):
    ci = forge_answer("ci-status", payload, id=change)
    word = ci.get("status") or ""
    if word != "success":
        raise Refusal(CI_REFUSALS.get(word, "ci-none"), f"CI on change {change} is not green: {word or 'no checks'}", status=word, url=ci.get("url") or "")


def mark_ready_if_green(payload):
    """Mark the change Ready on the local head of an open change, settled reviews and green CI. The CI answer names no commit.

    `finish` stops a review, so a wrong change or head refuses first. The reviews can take minutes, so the change and its head are read again, and CI last.
    """
    change = change_ref(payload)
    plan = Path(str(need(payload, "plan")))
    if not plan.is_dir():
        raise _bad(f"no plan folder at {plan}")
    view = _head_view(payload, change)
    open_reviews = _open_reviews(plan, {change, str(view.get("id")), view.get("url")})
    if open_reviews:
        raise Refusal("review-open", f"{len(open_reviews)} review(s) are not settled", reviews=open_reviews)
    view = _head_view(payload, change)
    _refuse_unless_green(payload, change)
    if not view.get("draft"):
        return ok(id=change, draft=False, marked=False, url=view.get("url") or "")
    forge_answer("change-ready", payload, id=change)
    return ok(id=change, draft=False, marked=True, url=view.get("url") or "")


VERBS = {"start": start_watch, "watch": watch_ci, "status": status, "mark-ready": mark_ready_if_green}


def main(argv=None):
    return envelope.serve(VERBS, sys.argv[1:] if argv is None else argv)


if __name__ == "__main__":
    sys.exit(main())
