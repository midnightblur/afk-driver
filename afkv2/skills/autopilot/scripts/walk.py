"""The walk of one plan: `walk.py <verb> [json-payload]`, or the payload on stdin.

Every write lands in `plan/` on the run branch and is committed there. The feature branch gets no write.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "execute" / "scripts"))

import start_gate  # noqa: E402
import tdd_log  # noqa: E402
from plan_contract import PLUGIN, dependents, read_contract, read_text, read_tracker, write_atomic, write_status  # noqa: E402
from start_gate import RUN_SUFFIX, git_line, run_branch_of  # noqa: E402
from tracker import envelope  # noqa: E402
from tracker.envelope import Refusal, need, ok  # noqa: E402

REVIEW = PLUGIN / "skills" / "code-review" / "scripts" / "review_rounds.py"
CI_WATCH = PLUGIN / "skills" / "create-change-request" / "scripts" / "ci_watch.py"
COMMAND_LIMIT = 900
IN_FLIGHT = ("designing", "developing", "verifying", "reviewing")
STATUS_FLIPS = ("developing", "verifying", "reviewing")
ATTEMPT_CAP = 3
RULING_CAP = 3
RULED_KINDS = ("scope", "file-owner", "subtask-order")
PARK_KINDS = ("acceptance", "one-way", "cost")
JOURNAL_HEADER = "# Journal: append-only event log, one line per event. Newest last.\n"
LEDGER_HEADER = "# Decisions: taken hands-off, each one reversible on the record. Newest last.\n"
LEDGER_ID = re.compile(r"^## D-(\d+) ", re.MULTILINE)


def _bad(reason):
    return Refusal("bad-payload", reason)


def _one_line(value):
    return " ".join(str(value).split())


def _plan(payload):
    """The plan folder. Every verb stops here when the folder is not `plan/` on a run branch."""
    plan = Path(str(need(payload, "plan")))
    if not plan.is_dir() or run_branch_of(plan) is None:
        raise Refusal("not-run-branch", f"{plan} is not `plan/` at the root of a `<feature branch>{RUN_SUFFIX}` branch")
    return plan


def _git(cwd, *args):
    done = subprocess.run(["git", *args], cwd=cwd, capture_output=True, stdin=subprocess.DEVNULL, timeout=start_gate.LIMIT)
    if done.returncode != 0:
        raise Refusal("git-failed", f"git {args[0]}: {done.stderr.decode('utf-8', 'replace').strip()}")
    return done.stdout.decode("utf-8", "replace").strip()


def _commit_run(plan, message):
    """Commit the plan folder on the run branch; the answer is False when nothing changed."""
    top = _git(plan, "rev-parse", "--show-toplevel")
    _git(top, "add", "--", "plan")
    if git_line(top, "diff", "--cached", "--quiet") is not None:
        return False
    _git(top, "commit", "-qm", _one_line(message), "--", "plan")
    return True


def _state_path(plan):
    return plan / "run.json"


def _load(plan):
    path = _state_path(plan)
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"change": None, "subtasks": {}, "order": [], "rulings": []}
    except (OSError, ValueError) as error:
        raise Refusal("bad-state", f"cannot read {path}: {error}") from None
    if not isinstance(state, dict) or not {"subtasks", "order", "rulings"} <= set(state):
        raise Refusal("bad-state", f"{path} is not a run record")
    return state


def _save(plan, state):
    write_atomic(_state_path(plan), json.dumps(state, indent=1) + "\n")


def _journal(plan, writer, subject, event, plain):
    path = plan / "JOURNAL.md"
    text = read_text(path) if path.is_file() else JOURNAL_HEADER
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    write_atomic(path, f"{text.rstrip(chr(10))}\n{stamp} | {writer} | {subject} | {_one_line(event)} — {_one_line(plain)}\n")


def _ledger_entry(plan, title, by, lines):
    """Append one entry with the next free id; the answer is that id."""
    path = plan / "DECISIONS.md"
    text = read_text(path) if path.is_file() else LEDGER_HEADER
    number = max((int(found) for found in LEDGER_ID.findall(text)), default=0) + 1
    body = "\n".join(f"- {_one_line(line)}" for line in [f"{date.today().isoformat()} · decided by {by}", *lines])
    write_atomic(path, f"{text.rstrip(chr(10))}\n\n## D-{number} — {_one_line(title)}\n{body}\n")
    return f"D-{number}"


def _statuses(plan):
    return dict(read_tracker(plan))


def _contracts(plan):
    return [read_contract(plan, subtask) for subtask, _ in read_tracker(plan)]


def _order_pairs(state):
    return [(pair["first"], pair["then"]) for pair in state["order"]]


def _waiting_on(contract, state, statuses):
    """The subtasks that must be done before this one, and are not."""
    firsts = [first for first, then in _order_pairs(state) if then == contract.id]
    return [item for item in [*contract.blocked_by, *firsts] if statuses.get(item) != "done"]


def _in_flight(statuses):
    return next((subtask for subtask, status in statuses.items() if status in IN_FLIGHT), None)


def _rulings_for(state, subtask):
    return [{"id": item["id"], "ruling": item["ruling"], "question": item["question"]}
            for item in state["rulings"] if subtask in item["applies_to"]]


def _brief(plan, subtask, record, change, rulings, resume):
    lines = ["Run /afkv2:execute for one subtask. This prompt is all you get from the run.",
             f"subtask: {subtask}", f"plan: {plan}", f"contract: {plan / (subtask + '.md')}", f"base: {record['base']}",
             f"change: {change or 'none'}", f"python: {sys.executable}",
             "You may start read-only subagents for the review, one level down. They start no subagents."]
    if resume:
        lines.append(f"An earlier subagent worked on this subtask. Read `git log {record['base']}..HEAD`, read `{plan / 'review'}`, and go on from there.")
    if rulings:
        lines.append("Rulings of the orchestrator. Each one binds over the contract:")
        lines.extend(f"- {item['id']}: {_one_line(item['question'])} Ruling: {_one_line(item['ruling'])}" for item in rulings)
    return "\n".join(lines)


def locate(payload):
    """The worktree of the run branch of the current feature branch; it adds that worktree when none exists."""
    branch = git_line(".", "rev-parse", "--abbrev-ref", "HEAD")
    if not branch or branch == "HEAD" or branch.endswith(RUN_SUFFIX):
        raise Refusal("not-feature-branch", f"run this from the worktree of the feature branch, not {branch}")
    run_branch = branch + RUN_SUFFIX
    ref = f"refs/heads/{run_branch}"
    worktree = None
    for block in _git(".", "worktree", "list", "--porcelain").split("\n\n"):
        if f"branch {ref}" in block.splitlines():
            worktree = block.splitlines()[0].removeprefix("worktree ")
    created = False
    if worktree is None:
        if git_line(".", "rev-parse", "--verify", "--quiet", ref) is None and git_line(".", "fetch", "origin", f"{run_branch}:{run_branch}") is None:
            raise Refusal("no-run-branch", f"no branch {run_branch}. A feature with a v1 plan finishes on v1; else slice with `/afkv2:to-subtasks`",
                          options=start_gate.V1_OPTIONS)
        worktree = _git(".", "rev-parse", "--show-toplevel") + RUN_SUFFIX
        _git(".", "worktree", "add", "-q", worktree, run_branch)
        created = True
    return ok(branch=branch, run_branch=run_branch, worktree=worktree, plan=str(Path(worktree) / "plan"), created=created)


def next_subtask(payload):
    plan = _plan(payload)
    state, statuses = _load(plan), _statuses(plan)
    running = _in_flight(statuses)
    if running:
        attempts = state["subtasks"].get(running, {}).get("attempts", 0)
        return ok(subtask=running, resume=True, attempts=attempts, give_up=attempts >= ATTEMPT_CAP)
    for contract in _contracts(plan):
        if statuses[contract.id] == "pending" and not _waiting_on(contract, state, statuses):
            return ok(subtask=contract.id, resume=False, attempts=0, give_up=False)
    return ok(finished=True, **_tally(statuses))


def _tally(statuses):
    return {"done": [item for item, status in statuses.items() if status == "done"],
            "parked": [{"subtask": item, "status": status} for item, status in statuses.items() if status.startswith("blocked(")],
            "waiting": [item for item, status in statuses.items() if status == "pending"]}


def start(payload):
    plan, subtask = _plan(payload), str(need(payload, "subtask"))
    state, statuses = _load(plan), _statuses(plan)
    if subtask not in statuses:
        raise Refusal("no-such-subtask", f"the progress tracker has no row {subtask}")
    status = statuses[subtask]
    if status == "done":
        raise Refusal("already-done", f"{subtask} is done")
    if status.startswith("blocked("):
        raise Refusal("parked", f"{subtask} is parked: {status}. A human sets the row back to `pending`")
    running = _in_flight(statuses)
    if running and running != subtask:
        raise Refusal("subtask-in-flight", f"{running} is still running: finish or park it first")
    contract = read_contract(plan, subtask)
    waiting = _waiting_on(contract, state, statuses)
    if waiting:
        raise Refusal("blocked-by", f"{subtask} waits on {', '.join(waiting)}", waiting=waiting)
    for producer, path, anchor in contract.consumes:
        if not _holds(path, anchor):
            raise Refusal("contract-mismatch", f"{path} has no `{anchor}`, which {producer} must produce", producer=producer)
    failures = start_gate.gate_failures(contract, payload.get("app"))
    if failures:
        raise Refusal("gate-cannot-run", f"{subtask} has a gate that cannot run in this repository", failures=failures)
    record = state["subtasks"].setdefault(subtask, {"attempts": 0})
    resume = "base" in record
    record.setdefault("base", _git(".", "rev-parse", "HEAD"))
    record["attempts"] += 1
    _save(plan, state)
    if status == "pending":
        write_status(plan, subtask, "developing")
        _journal(plan, "autopilot", subtask, "developing", "a fresh helper starts work on this subtask")
    _commit_run(plan, f"run: {subtask}: start, attempt {record['attempts']}")
    rulings = _rulings_for(state, subtask)
    return ok(subtask=subtask, base=record["base"], change=state["change"], attempt=record["attempts"], resume=resume,
              rulings=rulings, brief=_brief(plan, subtask, record, state["change"], rulings, resume))


def set_status(payload):
    plan, subtask, status = _plan(payload), str(need(payload, "subtask")), str(need(payload, "status"))
    if status not in STATUS_FLIPS:
        raise _bad(f"`status` must be one of {', '.join(STATUS_FLIPS)}")
    if _statuses(plan).get(subtask) not in IN_FLIGHT:
        raise Refusal("not-running", f"{subtask} is not running")
    write_status(plan, subtask, status)
    _journal(plan, "execute", subtask, status, payload.get("plain") or f"this subtask moves to {status}")
    _commit_run(plan, f"run: {subtask}: {status}")
    return ok(subtask=subtask, status=status)


def set_change(payload):
    plan, change = _plan(payload), str(need(payload, "change"))
    state = _load(plan)
    if state["change"] and state["change"] != change:
        raise Refusal("change-differs", f"this run already has the Draft change {state['change']}, not {change}")
    if not state["change"]:
        state["change"] = change
        _save(plan, state)
        _journal(plan, "execute", "run", f"change {change}", "the one Draft change of this run is open")
        _commit_run(plan, f"run: change {change}")
    return ok(change=change)


def decide(payload):
    plan = _plan(payload)
    subject, by = payload.get("subtask") or "run", payload.get("by") or "execute"
    fork, options, chosen, evidence, reverse = (need(payload, key) for key in ("fork", "options", "chosen", "evidence", "reverse"))
    number = _ledger_entry(plan, fork, f"{by} ({subject})", [
        f"Options: {options}", f"Chosen: {chosen} — {evidence}", f"Supersedes: {payload.get('supersedes') or 'none'}", f"To reverse: {reverse}"])
    _journal(plan, by, subject, f"decision({number})", payload.get("plain") or f"the run chose: {chosen}")
    _commit_run(plan, f"run: {subject}: {number}")
    return ok(id=number)


def _park(plan, subtask, reason, fork, options, recommendation, by):
    contracts = _contracts(plan)
    statuses = _statuses(plan)
    state = _load(plan)
    if subtask not in statuses:
        raise Refusal("no-such-subtask", f"the progress tracker has no row {subtask}")
    if statuses[subtask] == "done":
        raise Refusal("already-done", f"{subtask} is done, so it cannot park")
    inherited = [item for item in dependents(contracts, subtask, _order_pairs(state))
                 if item != subtask and statuses[item] != "done"]
    write_status(plan, subtask, f"blocked({reason})")
    _journal(plan, by, subtask, f"parked({_one_line(reason)})", f"this subtask stops and needs a human: {fork}")
    newly = []
    for item in inherited:
        if not statuses[item].startswith("blocked("):
            write_status(plan, item, f"blocked(waits on {subtask})")
            _journal(plan, "autopilot", item, f"park-inherited(waiting on {subtask})", "this subtask cannot start until the parked one is settled")
            newly.append(item)
    number = _ledger_entry(plan, f"parked: {fork}", f"{by} ({subtask})", [
        f"Options: {options}", f"Recommendation: {recommendation}", f"Parked: {subtask}; dependents: {', '.join(inherited) or 'none'}",
        f"Reason: {reason}", "To resume: answer the fork, set these rows to `pending`, and run `/afkv2:autopilot` again"])
    _commit_run(plan, f"run: {subtask}: parked, {number}")
    return ok(parked=subtask, inherited=inherited, newly_blocked=newly, id=number, ruled=False)


def park(payload):
    plan, subtask = _plan(payload), str(need(payload, "subtask"))
    reason, fork, options, recommendation = (need(payload, key) for key in ("reason", "fork", "options", "recommendation"))
    return _park(plan, subtask, reason, fork, options, recommendation, payload.get("by") or "execute")


def _why_not_ruled(payload, kinds, state, subtask):
    """Why this plan call goes to the human; None when the orchestrator rules it."""
    for kind in PARK_KINDS:
        if kind in kinds:
            return f"plan call of kind {kind}"
    if not payload["reversible"]:
        return "plan call that is not reversible"
    if not payload["inside_goal"]:
        return "plan call outside the approved goal"
    if sum(item["subtask"] == subtask for item in state["rulings"]) >= RULING_CAP:
        return f"{RULING_CAP} rulings already on this subtask"
    return None


def _order_of(payload, plan, state, statuses):
    """The (first, then) pair of a subtask-order call, after its checks; the second value says it keeps the graph."""
    first, then = str(need(payload, "first")), str(need(payload, "then"))
    if first not in statuses or then not in statuses:
        raise _bad(f"`first` and `then` must name tracker rows, not {first} and {then}")
    keeps_graph = first not in dependents(_contracts(plan), then, _order_pairs(state))
    return (first, then), keeps_graph


def rule(payload):
    """An executor stopped on a plan call. Rule it and record it, or park it for the human."""
    plan, subtask = _plan(payload), str(need(payload, "subtask"))
    kinds = payload.get("kinds")
    if not isinstance(kinds, list) or not kinds or any(kind not in RULED_KINDS + PARK_KINDS for kind in kinds):
        raise _bad(f"`kinds` must be a list from {', '.join(RULED_KINDS + PARK_KINDS)}")
    for key in ("reversible", "inside_goal"):
        if not isinstance(payload.get(key), bool):
            raise _bad(f"`{key}` must be true or false")
    question, options = need(payload, "question"), need(payload, "options")
    state, statuses = _load(plan), _statuses(plan)
    if subtask not in statuses:
        raise Refusal("no-such-subtask", f"the progress tracker has no row {subtask}")
    why = _why_not_ruled(payload, kinds, state, subtask)
    pair = None
    if why is None and "subtask-order" in kinds:
        pair, keeps_graph = _order_of(payload, plan, state, statuses)
        if not keeps_graph:
            why = "plan call against the `## Blocked by` graph"
    if why:
        return _park(plan, subtask, why, question, options, payload.get("ruling") or payload.get("recommendation") or "none given", "autopilot")
    ruling, evidence, reverse = need(payload, "ruling"), need(payload, "evidence"), need(payload, "reverse")
    applies_to = payload.get("applies_to") or [subtask]
    if not isinstance(applies_to, list) or any(item not in statuses for item in applies_to):
        raise _bad("`applies_to` must be a list of tracker rows")
    number = _ledger_entry(plan, f"plan call: {question}", f"autopilot ({subtask} stopped on it)", [
        f"Options: {options}", f"Chosen: {ruling} — {evidence}", f"Supersedes: {payload.get('supersedes') or 'none'}", f"To reverse: {reverse}"])
    state["rulings"].append({"id": number, "subtask": subtask, "kinds": kinds, "question": question, "ruling": ruling, "applies_to": applies_to})
    if pair:
        state["order"].append({"first": pair[0], "then": pair[1]})
        if statuses[pair[1]] in IN_FLIGHT:
            write_status(plan, pair[1], "pending")
    if subtask in state["subtasks"]:
        state["subtasks"][subtask]["attempts"] = 0
    _save(plan, state)
    _journal(plan, "autopilot", subtask, f"decision({number})", f"the run settled a question about the plan: {question}")
    _commit_run(plan, f"run: {subtask}: ruling {number}")
    return ok(ruled=True, id=number, ruling=ruling, applies_to=applies_to)


def _call(script, verb, payload):
    """One call of a skill command. Every failure comes back as the failure answer."""
    try:
        done = subprocess.run([sys.executable, str(script), verb], input=json.dumps(payload).encode("utf-8"), capture_output=True, timeout=COMMAND_LIMIT)
        answer = json.loads(done.stdout)
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        return envelope.fail("command-failed", f"{Path(script).name} {verb} gave no answer: {error}")
    return answer if isinstance(answer, dict) and "ok" in answer else envelope.fail("command-failed", f"{Path(script).name} {verb} gave no answer object")


def review_report(plan, subtask):
    return _call(REVIEW, "finish", {"plan": str(plan), "subtask": subtask})


def ci_state(change):
    """What the record of the CI watch says; None when the command gives no answer."""
    answer = _call(CI_WATCH, "status", {"id": change})
    return answer.get("state") if answer.get("ok") else None


def _holds(path, anchor):
    try:
        return anchor in Path(path).read_bytes().decode("utf-8", "replace")
    except OSError:
        return False


def _own_commits(subtask, base):
    lines = _git(".", "log", "--first-parent", "--no-merges", "--format=%H%x09%s", f"{base}..HEAD").splitlines()
    return [line.split("\t")[0] for line in lines if line.split("\t", 1)[-1].startswith(f"[{subtask}]")]


def _finish_failures(plan, subtask, record, change):
    base = record["base"]
    failures = []
    if git_line(".", "merge-base", "--is-ancestor", base, "HEAD") is None:
        return [{"code": "base-lost", "reason": f"{base} is not an ancestor of HEAD"}], []
    commits = _own_commits(subtask, base)
    if not commits:
        failures.append({"code": "no-own-commits", "reason": f"no commit from {base} to HEAD starts with `[{subtask}]`"})
    failures.extend(tdd_log.verdict(plan, subtask, base))
    branch = _git(".", "rev-parse", "--abbrev-ref", "HEAD")
    if git_line(".", "rev-parse", f"origin/{branch}") != _git(".", "rev-parse", "HEAD"):
        failures.append({"code": "not-pushed", "reason": f"HEAD is not the head of origin/{branch}"})
    if not change:
        failures.append({"code": "no-change", "reason": "the run has no Draft change: run `set-change`"})
    elif ci_state(change) in (None, "none"):
        failures.append({"code": "no-ci-watch", "reason": f"no CI watch has run on change {change}"})
    report = review_report(plan, subtask)
    if not report.get("ok"):
        error = report.get("error") or {}
        failures.append({"code": error.get("code") or "no-review", "reason": error.get("reason") or "the review gave no report"})
    elif (report.get("left") or {}).get("blocking"):
        failures.append({"code": "review-blocking", "reason": "critical or high findings stay open: park this subtask", "findings": report["left"]["blocking"]})
    for path, anchor in read_contract(plan, subtask).produces:
        if not _holds(path, anchor):
            failures.append({"code": "produces-missing", "reason": f"{path} has no `{anchor}`"})
    return failures, commits


def done(payload):
    plan, subtask = _plan(payload), str(need(payload, "subtask"))
    state = _load(plan)
    if _statuses(plan).get(subtask) not in IN_FLIGHT:
        raise Refusal("not-running", f"{subtask} is not running")
    failures, commits = _finish_failures(plan, subtask, state["subtasks"][subtask], state["change"])
    if failures:
        raise Refusal("not-finished", f"{len(failures)} gaps stop {subtask} from done", failures=failures)
    write_status(plan, subtask, "done")
    _journal(plan, "execute", subtask, "done", payload.get("plain") or "this subtask is finished and its work is on the Draft change")
    _commit_run(plan, f"run: {subtask}: done")
    return ok(subtask=subtask, commits=commits)


def end(payload):
    plan = _plan(payload)
    state, statuses = _load(plan), _statuses(plan)
    tally = _tally(statuses)
    _journal(plan, "autopilot", "run", f"run end ({len(tally['done'])}/{len(statuses)} done, {len(tally['parked'])} parked)",
             "the walk of the plan has stopped")
    _commit_run(plan, "run: end")
    return ok(**tally, rulings=state["rulings"], change=state["change"], ship=len(tally["done"]) == len(statuses))


VERBS = {"locate": locate, "next": next_subtask, "start": start, "status": set_status, "set-change": set_change,
         "decide": decide, "park": park, "rule": rule, "done": done, "end": end}


def main(argv=None):
    return envelope.serve(VERBS, sys.argv[1:] if argv is None else argv)


if __name__ == "__main__":
    sys.exit(main())
