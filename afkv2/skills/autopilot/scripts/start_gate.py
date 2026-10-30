"""The start gate of a run: `start_gate.py check [json-payload]`, or the payload on stdin."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from plan_contract import PLUGIN, contract_failures, cycle_of, header_of, plan_file, read_contract, read_text, read_tracker  # noqa: E402
from tracker import envelope  # noqa: E402
from tracker.envelope import Refusal, need, ok  # noqa: E402
from autopilot_v1_facts import V1_HEADER_MARK, V1_SEAM_MARK  # noqa: E402

CHECK_PLAN = PLUGIN / "skills" / "to-subtasks" / "scripts" / "check_plan.py"
FORGE = PLUGIN / "ports" / "forge" / "forge_cli.py"
LIMIT = 120
APP_LIMIT = 5
RUN_SUFFIX = "-run"
APPROVAL = re.compile(r"> Division: approved (\d{4}-\d{2}-\d{2})\s*")
NOT_APPLICABLE = "not applicable:"
LIVE_TIERS = {"api", "e2e", "browser", "e2e/browser", "ui-e2e"}
SPAN = re.compile(r"`([^`]+)`")
PROGRAM = re.compile(r"[a-z0-9][\w.-]*")
V1_OPTIONS = ["finish on v1", "slice again with `/afkv2:to-subtasks`"]


def failure(code, where, reason, **extra):
    return {"code": code, "where": where, "reason": reason, **extra}


def git_line(cwd, *args):
    """git's answer with no outer space, or None when git refuses."""
    try:
        done = subprocess.run(["git", *args], cwd=cwd, capture_output=True, stdin=subprocess.DEVNULL, timeout=LIMIT)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return done.stdout.decode("utf-8", "replace").strip() if done.returncode == 0 else None


def run_branch_of(plan):
    """The branch of the plan folder when it is `plan/` at the root of a run branch; else None."""
    branch, top = git_line(plan, "rev-parse", "--abbrev-ref", "HEAD"), git_line(plan, "rev-parse", "--show-toplevel")
    if not branch or not top or not branch.endswith(RUN_SUFFIX):
        return None
    try:
        same = os.path.samefile(Path(top) / "plan", plan)
    except OSError:
        same = False
    return branch if same else None


def _v1_signs(plan, text):
    """Each sign that this plan folder was cut for v1."""
    signs = []
    if any(V1_HEADER_MARK in line for line in header_of(text)):
        signs.append(f"the PLAN.md header names `{V1_HEADER_MARK}`")
    if run_branch_of(plan) is None:
        signs.append(f"the folder is not `plan/` at the root of a `<feature branch>{RUN_SUFFIX}` branch")
    for path in sorted(Path(plan).glob("*.md")):
        if path.name != "PLAN.md" and V1_SEAM_MARK in read_text(path):
            signs.append(f"{path.name} holds a materialized seam")
    return signs


def approval_failures(text):
    for line in header_of(text):
        match = APPROVAL.fullmatch(line)
        if match:
            try:
                date.fromisoformat(match.group(1))
            except ValueError:
                return [failure("bad-approval", "PLAN.md", f"the approval date {match.group(1)} is no date")]
            return []
    return [failure("no-approval", "PLAN.md", "the PLAN.md header has no `> Division: approved <YYYY-MM-DD>` line",
                    next="approve the division through `/afkv2:to-subtasks`")]


def _check_item(item):
    if isinstance(item, dict):
        return failure(str(item.get("code") or "plan-check"), str(item.get("where") or item.get("file") or "plan"),
                       str(item.get("reason") or item.get("message") or json.dumps(item)))
    return failure("plan-check", "plan", str(item))


def plan_check_failures(plan):
    """Every failure of the plan check. Every answer other than a clean pass refuses."""
    if not Path(CHECK_PLAN).is_file():
        return [failure("plan-check-missing", str(CHECK_PLAN), "the plan check script is not in this plugin tree")]
    try:
        done = subprocess.run([sys.executable, str(CHECK_PLAN), str(plan)], capture_output=True,
                              stdin=subprocess.DEVNULL, timeout=LIMIT)
        answer = json.loads(done.stdout)
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        return [failure("plan-check-unreadable", str(plan), f"the plan check gave no answer: {error}")]
    if not isinstance(answer, dict):
        return [failure("plan-check-unreadable", str(plan), "the plan check answer is not one JSON object")]
    error = answer.get("error") if isinstance(answer.get("error"), dict) else {}
    items = answer.get("failures") or error.get("failures") or []
    items = items if isinstance(items, list) else [items]
    if done.returncode == 0 and answer.get("ok") is True and not items:
        return []
    if done.returncode not in (0, 1):
        return [failure("plan-check-unreadable", str(plan), f"the plan check gave exit {done.returncode}: {error.get('reason') or 'no reason'}")]
    if items:
        return [_check_item(item) for item in items]
    return [failure(str(error.get("code") or "plan-check"), str(plan), str(error.get("reason") or "the plan check refused and listed no failure"))]


def contracts_of(plan):
    """(tracker rows, contracts in rank order, every failure of the tracker and the contracts)."""
    try:
        rows = read_tracker(plan)
    except Refusal as refusal:
        return [], [], [failure(refusal.code, "PLAN.md", refusal.reason)]
    contracts, failures = [], []
    for subtask, _ in rows:
        path = Path(plan) / f"{subtask}.md"
        if not path.is_file():
            failures.append(failure("no-contract", subtask, f"no contract file {path.name}"))
            continue
        contract = read_contract(plan, subtask)
        contracts.append(contract)
        failures.extend(failure("bad-contract", subtask, reason) for reason in contract_failures(contract))
    known = {subtask for subtask, _ in rows}
    for contract in contracts:
        for blocker in contract.blocked_by:
            if blocker not in known:
                failures.append(failure("unknown-blocker", contract.id, f"`## Blocked by` names {blocker}, which has no tracker row"))
    loop = cycle_of(contracts)
    if loop:
        failures.append(failure("blocked-by-cycle", loop, "this subtask waits on itself through `## Blocked by`"))
    return rows, contracts, failures


def _programs(check):
    """The program of each code span in a check cell that reads as a command: 2 or more words, a lower-case name first."""
    for span in SPAN.findall(check):
        words = span.split()
        if len(words) >= 2 and PROGRAM.fullmatch(words[0]):
            yield words[0]


def app_failure(where, app):
    """Why the app at `app` cannot serve a live gate; None when it answers. Any HTTP answer counts."""
    if not re.match(r"https?://", str(app)):
        return failure("app-unreachable", where, f"the app address {app} is not http or https")
    try:
        urllib.request.urlopen(str(app), timeout=APP_LIMIT).close()
    except urllib.error.HTTPError:
        return None
    except (OSError, ValueError) as error:
        return failure("app-unreachable", where, f"the app at {app} does not answer: {error}")
    return None


def is_not_applicable(row):
    return row.check.startswith(NOT_APPLICABLE) and bool(row.check[len(NOT_APPLICABLE):].strip())


def gate_failures(contract, app=None):
    """Each `## Verification` row of this contract that cannot run in this repository."""
    failures = []
    fix = f"correct the plan: mark the row `{NOT_APPLICABLE} <reason>`, or slice again"
    for row in contract.rows:
        where = f"{contract.id} tier {row.tier}"
        if row.check.lower().startswith("not applicable"):
            if not is_not_applicable(row):
                failures.append(failure("bad-not-applicable", where, f"write the cell as `{NOT_APPLICABLE} <reason>`"))
            continue
        if row.tier.lower() in LIVE_TIERS:
            if not app:
                failures.append(failure("gate-cannot-run", where, "this tier needs a running app, and the run has no `app`", next=f"{fix}, or pass `app`"))
            else:
                problem = app_failure(where, app)
                if problem:
                    failures.append(problem)
        for program in _programs(row.check):
            if not shutil.which(program):
                failures.append(failure("gate-cannot-run", where, f"the command `{program}` is not on PATH", next=fix))
    return failures


def forge_answer(code):
    """The forge port's answer on who is signed in, in the repository at `code`."""
    try:
        done = subprocess.run([sys.executable, str(FORGE), "auth-status"], cwd=code, input=b"{}", capture_output=True, timeout=LIMIT)
        return json.loads(done.stdout)
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        return envelope.fail("command-failed", f"the forge command gave no answer: {error}")


def forge_failures(code):
    answer = forge_answer(code)
    if answer.get("ok") and answer.get("authenticated"):
        return []
    reason = answer.get("reason") or (answer.get("error") or {}).get("reason") or "not signed in"
    return [failure("forge-not-ready", "forge", f"the Draft change and the review need the forge: {reason}")]


def worktree_failures(code, run_branch):
    failures = []
    branch = git_line(code, "rev-parse", "--abbrev-ref", "HEAD")
    if not branch or branch + RUN_SUFFIX != run_branch:
        failures.append(failure("wrong-branch", str(code), f"this worktree is on {branch}; the plan is on {run_branch}",
                                next=f"run from the worktree of {run_branch[:-len(RUN_SUFFIX)]}"))
    if git_line(code, "status", "--porcelain"):
        failures.append(failure("dirty-worktree", str(code), "the worktree has uncommitted changes, and a subtask commit could take them"))
    return failures


def check_start(plan, code=".", app=None):
    """Whether a run can start on this plan: one answer that lists every failure. It writes nothing."""
    plan = Path(plan)
    if not plan_file(plan).is_file():
        return envelope.fail("start-refused", f"no plan at {plan}", failures=[
            failure("no-plan", str(plan), "the folder has no PLAN.md", next="slice with `/afkv2:to-subtasks`")])
    text = read_text(plan_file(plan))
    signs = _v1_signs(plan, text)
    if signs:
        return envelope.fail("start-refused", "this is a v1 plan folder", options=V1_OPTIONS, failures=[
            failure("v1-plan", str(plan), "; ".join(signs), options=V1_OPTIONS)])
    rows, contracts, failures = contracts_of(plan)
    failures = [*plan_check_failures(plan), *approval_failures(text), *failures]
    finished = {subtask for subtask, status in rows if status == "done"}
    for contract in contracts:
        if contract.id not in finished:
            failures.extend(gate_failures(contract, app))
    failures.extend(worktree_failures(code, run_branch_of(plan)))
    failures.extend(forge_failures(code))
    if failures:
        return envelope.fail("start-refused", f"{len(failures)} failures stop this run", failures=failures)
    return ok(plan=str(plan), run_branch=run_branch_of(plan), subtasks=[item.id for item in contracts])


def _check(payload):
    return check_start(need(payload, "plan"), payload.get("code") or ".", payload.get("app"))


VERBS = {"check": _check}


def main(argv=None):
    return envelope.serve(VERBS, sys.argv[1:] if argv is None else argv)


if __name__ == "__main__":
    sys.exit(main())
