"""The CI watch and the Ready gate: `ci_watch.py <verb> [json-payload]`, or the payload on stdin."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[3]
FORGE = PLUGIN / "ports" / "forge" / "forge_cli.py"
REVIEW = PLUGIN / "skills" / "code-review" / "scripts" / "review_rounds.py"
TRACKER = PLUGIN / "ports" / "tracker" / "cli.py"
sys.path.insert(0, str(PLUGIN / "ports"))

from tracker import envelope, shell  # noqa: E402
from tracker.envelope import Refusal, need, ok  # noqa: E402

sys.path.insert(0, str(PLUGIN / "scripts"))
import afkv2_config  # noqa: E402
import gate_record  # noqa: E402

sys.path.insert(0, str(PLUGIN / "skills" / "autopilot" / "scripts"))
import plan_contract  # noqa: E402

COMMAND_LIMIT = 300
REVIEW_LIMIT = 900
READ_MARGIN = 300
DEFAULT_BUDGET = 5400
SLICE = 600
LOST_AFTER = 3 * SLICE
HEAD_GRACE = 300
HEAD_PAUSE = 15
PASSED_ON = ("forge", "repo")
NOT_OPEN = ("merged", "closed")
CI_REFUSALS = {"failed": "ci-red", "canceled": "ci-red", "running": "ci-running", "": "ci-none"}
REVIEW_CAN_RUN = {"no-review", "review-owed", "fix-open", "round-open"}
REVIEW_CAN_RETRY = {"command-failed"}
FILE_TRIES, FILE_PAUSE = 20, 0.1
SUBTASK_FILE = re.compile(r"[0-9]{4}-.+\.md")
_NOT_A_FILE_NAME = re.compile(r"[^0-9A-Za-z._-]")
GITHUB_TRACKER = "github-issues"
GITHUB_CHANGE = re.compile(r"https://github\.com/(?P<repo>[^/]+/[^/]+)/pull/(?P<number>[0-9]+)/?")
PUBLIC_NOTICE = "This comment goes to GitHub: on a public repository anyone can open its pictures."
RECEIPT_PLACEHOLDER = "0" * 64
PROOF_FOLDER = "afkv2-proof"
PARTS_FOLDER = "afkv2-change"
SHIP_ORDER = (*gate_record.SHIP_CODES, "proof-not-posted")


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


def _parts_path(change):
    """The proof lines and found bugs that `open` wrote into the description of `change`, kept for the ship check."""
    file_name = _NOT_A_FILE_NAME.sub("_", change)
    return _record_path(change).parent.parent / PARTS_FOLDER / f"{file_name}.json"


def write_parts(change, proofs, found):
    _write_record(_parts_path(change), {"id": change, "proofs": proofs, "found": found})


def read_parts(change):
    """`{id, proofs, found}` of the last `open` of `change`, or None when `open` never ran here."""
    path = _parts_path(change)
    try:
        kept = json.loads(_with_retries(lambda: path.read_text(encoding="utf-8")))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as error:
        raise Refusal("bad-record", f"the kept parts {path} are unreadable: {error}; run `open` again") from None
    if not isinstance(kept, dict) or not isinstance(kept.get("proofs"), list) or not isinstance(kept.get("found"), list):
        raise Refusal("bad-record", f"{path} holds no kept parts; run `open` again")
    return kept


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
    record = {"id": change, "token": uuid.uuid4().hex, "state": "watching", "status": "", "head_sha": head, "reason": "",
              "change_state": "", "beat_at": time.time()}
    _write_record(path, record)
    return record


def _no_result(change, state, reason):
    return ok(id=change, state=state, status="", head_sha="", current_head=False, reason=reason, change_state="")


def _report(change, record):
    if record is None:
        return _no_result(change, "none", "no watch has run on this change")
    state, reason = record["state"], record.get("reason") or ""
    if state == "watching" and time.time() - record.get("beat_at", 0) > LOST_AFTER:
        state, reason = "lost", "the watch stopped with no result: run `start`"
    return ok(id=change, state=state, status=record.get("status") or "", head_sha=record.get("head_sha") or "",
              current_head=bool(record.get("head_sha")) and record["head_sha"] == _local_head(), reason=reason,
              change_state=record.get("change_state") or "")


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


def _write_end(path, record, fields):
    """Write the result unless a newer watch took over."""
    if not _is_current(path, record["token"]):
        return _superseded(record["id"])
    final = {**record, "change_state": "", **fields, "beat_at": time.time()}
    _write_record(path, final)
    return _report(record["id"], final)


def _end(payload, path, record, state, status_word, reason=""):
    """Write the result, with the commit the forge now shows, unless a newer watch took over. A merged or closed change ends it as such."""
    view = _change_view(payload, record["id"])
    merged = watch_end_on_merge(path, record, view)
    if merged is not None:
        return merged
    head = view.get("head_sha") or record["head_sha"]
    return _write_end(path, record, {"state": state, "status": status_word, "head_sha": head, "reason": reason})


def watch_end_on_merge(path, record, view):
    """End the watch on a merged or closed change, from the change view of a slice or of the end; None while the change is open."""
    state = view.get("state")
    if state not in NOT_OPEN:
        return None
    return _write_end(path, record, {"state": "change-not-open", "status": "", "head_sha": view.get("head_sha") or record["head_sha"],
                                     "reason": f"change {record['id']} is {state}", "change_state": state})


def _watched_record(payload, path, change):
    """The record of the child that `start` made, or a new record for a watch run by hand; None when a newer watch took over."""
    token = payload.get("token")
    if not token:
        return _new_record(path, change, _local_head())
    record = _read_record(path)
    return record if record is not None and record["token"] == token else None


def _change_view(payload, change):
    """The change view; empty when the forge call failed."""
    try:
        return forge_answer("change-view", payload, id=change)
    except Refusal:
        return {}


def _forge_behind(view, record):
    """True while the forge shows another commit than the one this watch started on. Right after a push, its answers are those of the last commit."""
    head = view.get("head_sha")
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
    head_seen = False
    while True:
        left = max(0, int(deadline - time.monotonic()))
        wait = min(SLICE, left)
        view = _change_view(payload, change)
        ended = watch_end_on_merge(path, record, view)
        if ended is not None:
            return ended
        head_seen = head_seen or not _forge_behind(view, record)
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
            if head_seen or not left or time.monotonic() - started >= HEAD_GRACE:
                return _end(payload, path, record, "finished", answer.get("status") or "")
            time.sleep(HEAD_PAUSE)
            if not _is_current(path, record["token"]):
                return _superseded(change)
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
    delta = answer.get("delta") or {}
    if delta.get("parked"):
        return "a delta check parked these fixes: " + _ids(delta["parked"]), "developer"
    if delta.get("owed"):
        return "these fixes wait for a delta check: " + _ids(delta["owed"]), "run-review"
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
        raise Refusal("change-not-open", f"change {change} is {view.get('state')}", change_state=view.get("state") or "")
    local = _local_head()
    if not local or local != view.get("head_sha"):
        raise Refusal("head-differs", f"the local head {local} is not the head {view.get('head_sha')} of the change: push, or run from the branch of the change")
    return view


def _refuse_unless_green(payload, change):
    ci = forge_answer("ci-status", payload, id=change)
    word = ci.get("status") or ""
    if word != "success":
        raise Refusal(CI_REFUSALS.get(word, "ci-none"), f"CI on change {change} is not green: {word or 'no checks'}", status=word, url=ci.get("url") or "")


# ---------------------------------------------------------------- the gate record at ship


def call_tracker(verb, payload):
    return _call(TRACKER, verb, payload, COMMAND_LIMIT)


def _config():
    """The repository config, or None when this repository has none."""
    answer = afkv2_config.read_config()
    return answer if answer.get("ok") else None


def _rules(plan):
    """The rule set of the plan; a folder with no PLAN.md has no `> Rules: 2` line, so it keeps the old rules."""
    path = plan_contract.plan_file(plan)
    return plan_contract.rules_of(plan_contract.read_text(path)) if path.is_file() else 1


def _gate_path(payload, plan):
    """The gate record of the ship, or None for a plan of the old rules, which ships on the review check alone."""
    if payload.get("gate"):
        return Path(str(payload["gate"]))
    if plan is not None and _rules(plan) != 2:
        return None
    raise Refusal("no-gate", "no gate record: pass `gate`, the path that the end gate or the small lane answered")


def _read_gate(path):
    try:
        return gate_record.read(path)
    except afkv2_config.Refusal as refusal:
        raise Refusal(refusal.code, refusal.reason) from None


def _where(payload, view):
    """Where the proof comment goes, and the tracker payload that posts it; None for a change on another forge."""
    ticket = payload.get("ticket")
    if ticket:
        tracker = ((_config() or {}).get("tracker") or {}).get("kind")
        return {"kind": "ticket", "key": str(ticket)}, {"key": str(ticket)}, tracker == GITHUB_TRACKER
    match = GITHUB_CHANGE.fullmatch(view.get("url") or "")
    if match:
        return ({"kind": "change", "key": match["number"]},
                {"tracker": GITHUB_TRACKER, "repo": match["repo"], "key": match["number"]}, True)
    return {"kind": "change", "key": str(view.get("id"))}, None, False


def _scan(text):
    spec = importlib.util.spec_from_file_location("afkv2_engine_notices", PLUGIN / "engine" / "notices.py")
    notices = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(notices)
    return [{"line": line, "shape": shape} for line, shape in notices.scan_text(text)]


def build_preview(payload, view, path, record):
    """The exact proof comment (SDD §4 "Proof comment"), where it goes and its receipt. The receipt is the sha256 of
    the place, the comment after its first line and the bytes of each picture: the developer's ship mark names it."""
    where, post, github = _where(payload, view)
    change = view.get("url") or str(view.get("id"))
    draft = gate_record.proof_comment(record, receipt=RECEIPT_PLACEHOLDER, change=change, folder=path.parent)
    digest = hashlib.sha256(f"{where['kind']} {where['key']}\n".encode("utf-8"))
    digest.update(draft["body"].split("\n", 1)[1].encode("utf-8"))
    for picture in draft["pictures"]:
        digest.update(gate_record.file_digest(picture).encode("ascii"))
    receipt = digest.hexdigest()
    comment = gate_record.proof_comment(record, receipt=receipt, change=change, folder=path.parent)
    return {"receipt": receipt, "body": comment["body"], "pictures": comment["pictures"], "where": where, "post": post,
            "notice": PUBLIC_NOTICE if github else "", "secrets": _scan(comment["body"])}


def proof_preview(payload):
    """The proof comment that mark-ready posts, for the ship page. Posts nothing."""
    change = change_ref(payload)
    view = forge_answer("change-view", payload, id=change)
    path = Path(str(need(payload, "gate")))
    preview = build_preview(payload, view, path, _read_gate(path))
    return ok(**{key: value for key, value in preview.items() if key != "post"})


def _gate_failures(payload, view, path):
    """Each S-10 failure of the gate record at the local head (SDD §3 S-10), and the preview of the proof comment."""
    kept = read_parts(str(view.get("id"))) or {"proofs": [], "found": []}
    record = _read_gate(path)
    config = _config()
    failures = []
    try:
        gate_record.verify(path, kept["proofs"], _local_head(), spec_folder=(config or {}).get("spec_folder") or "",
                           repo=(config or {}).get("repo_root") or _git_line("rev-parse", "--show-toplevel") or ".")
    except gate_record.GateRefusal as refusal:
        failures.extend(refusal.failures)
    except afkv2_config.Refusal as refusal:
        failures.append({"code": refusal.code, "row": None, "reason": refusal.reason})
    for bug in kept["found"]:
        if not bug.get("pick"):
            failures.append({"code": "found-open", "row": None, "reason": f"found bug {bug['id']} ({bug['what']}) waits for the developer's pick"})
    preview = build_preview(payload, view, path, record)
    if payload.get("receipt") != preview["receipt"]:
        why = "has no ship mark" if not payload.get("receipt") else "changed after the developer's ship mark"
        failures.append({"code": "proof-not-posted", "row": None,
                         "reason": f"the proof comment {why}: show the comment of `proof-preview` and pass the receipt the developer marked"})
    order = {code: n for n, code in enumerate(SHIP_ORDER)}
    failures.sort(key=lambda failure: order.get(failure["code"], len(order)))
    return failures, preview


def _first_line(text):
    return str(text or "").split("\n", 1)[0].strip()


def _post(payload, view, preview):
    """Post the proof comment once: the tracker port, or a note of a change on a forge it cannot reach."""
    body = preview["body"]
    if preview["post"] is not None:
        answer = call_tracker("comment-put", {**preview["post"], "body": body, "pictures": preview["pictures"], "receipt": preview["receipt"]})
        if not answer.get("ok"):
            raise refusal_of(answer, "tracker comment-put")
        return {"posted": bool(answer.get("posted")), "url": answer.get("url") or "", "receipt": preview["receipt"]}
    change = str(view.get("id"))
    notes = forge_answer("note-list", payload, id=change).get("notes") or []
    same = next((note for note in notes if isinstance(note, dict) and _first_line(note.get("body")) == _first_line(body)), None)
    if same is not None:
        return {"posted": False, "url": same.get("url") or "", "receipt": preview["receipt"]}
    answer = forge_answer("change-comment", payload, id=change, text=body)
    return {"posted": True, "url": answer.get("url") or "", "receipt": preview["receipt"]}


def _proof_marker(cwd, record_bytes):
    """The local mark that the proof comment of this exact gate record is posted, in the shared git folder of the
    repository: every worktree sees it, and gc reads it before it deletes a run branch (SDD §6 I-12)."""
    done = subprocess.run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=cwd, capture_output=True,
                          stdin=subprocess.DEVNULL, timeout=COMMAND_LIMIT)
    folder = done.stdout.decode("utf-8", "replace").strip()
    if done.returncode != 0 or not folder:
        raise Refusal("no-repository", f"{cwd} is not inside a git repository")
    # Line ends do not count: git can check the committed record out with other line ends than the written file.
    digest = hashlib.sha256(record_bytes.replace(b"\r\n", b"\n")).hexdigest()
    return Path(folder) / PROOF_FOLDER / f"{digest}.json"


def proof_posted(cwd, record_bytes):
    """True when mark-ready posted the proof comment of the gate record whose file holds `record_bytes`."""
    return _proof_marker(cwd, record_bytes).is_file()


def _mark_posted(path, posted):
    _write_record(_proof_marker(".", path.read_bytes()), {"gate": str(path), **posted})


def mark_ready_if_green(payload):
    """Mark the change Ready on the local head of an open change, a verified gate record, settled reviews and green
    CI; the proof comment goes out just before Ready. The CI answer names no commit.

    The gate record is verified first, so a ship that cannot pass stops before the reviews. `finish` stops a review,
    so a wrong change or head refuses first. The reviews can take minutes, so the change and its head are read again,
    and CI last. A plan of the old rules ships with no gate record, on the review check alone.
    """
    change = change_ref(payload)
    plan = Path(str(payload["plan"])) if payload.get("plan") else None
    if plan is not None and not plan.is_dir():
        raise _bad(f"no plan folder at {plan}")
    view = _head_view(payload, change)
    path = _gate_path(payload, plan)
    preview = None
    if path is not None:
        failures, preview = _gate_failures(payload, view, path)
        if failures:
            raise Refusal(failures[0]["code"], "; ".join(failure["reason"] for failure in failures), failures=failures)
    if plan is not None:
        open_reviews = _open_reviews(plan, {change, str(view.get("id")), view.get("url")})
        if open_reviews:
            raise Refusal("review-open", f"{len(open_reviews)} review(s) are not settled", reviews=open_reviews)
        view = _head_view(payload, change)
    _refuse_unless_green(payload, change)
    fields = {}
    if preview is not None:
        posted = _post(payload, view, preview)
        _mark_posted(path, posted)
        fields["comment"] = posted
    if not view.get("draft"):
        return ok(id=change, draft=False, marked=False, url=view.get("url") or "", **fields)
    forge_answer("change-ready", payload, id=change)
    return ok(id=change, draft=False, marked=True, url=view.get("url") or "", **fields)


VERBS = {"start": start_watch, "watch": watch_ci, "status": status, "proof-preview": proof_preview, "mark-ready": mark_ready_if_green}


def main(argv=None):
    return envelope.serve(VERBS, sys.argv[1:] if argv is None else argv)


if __name__ == "__main__":
    sys.exit(main())
