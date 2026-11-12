"""The end gate of a run: `end_gate.py run|back [json-payload]`, or the payload on stdin, from the worktree of the
feature branch (SDD §3 rows S-6, S-7; §6 I-14; design ADR-0006).

`run` runs each high-level row of VERIFICATION.md once against the live build; a failed row runs once more, and
fail then pass is flaky. It calls the judge when every row passed, and writes the gate record
`plan/gate/record.json` on the run branch. A row that cannot reach the app, the browser driver or its credentials
waits for the developer at ship. `back` moves the subtasks behind failed rows from `done` to `pending`.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import walk  # noqa: E402
from plan_contract import PLUGIN, plan_file, read_text, rules_of, write_status  # noqa: E402
from start_gate import APP_CONFIG, LIVE_TIERS, SPAN, app_failure, plan_app  # noqa: E402
from tracker import envelope  # noqa: E402
from tracker.envelope import Refusal, need, ok  # noqa: E402

sys.path.insert(0, str(PLUGIN / "scripts"))

import afkv2_config  # noqa: E402
import gate_record  # noqa: E402
import live_build  # noqa: E402
import other_provider  # noqa: E402

GATE_FOLDER = "gate"
RECORD_FILE = "record.json"
VERIFICATION = "VERIFICATION.md"
FAILED_CAP = 3
TEST_LIMIT = 1800
EVIDENCE_VARIABLE = "AFKV2_EVIDENCE"
DRIVER_LEVELS = ("ui-e2e",)
DRIVER_KEY = "browser_driver"
NO_ROW = {"", "-", "—", "none"}
SKIPPED = ("method:", "not applicable")


def record_path(plan):
    return Path(plan) / GATE_FOLDER / RECORD_FILE


def _refusal(error):
    """An `afkv2_config.Refusal` of a shared module, as the envelope refusal of this command."""
    return Refusal(error.code, error.reason)


def _verification_files():
    sys.path.insert(0, str(PLUGIN / "skills" / "propose-verification" / "scripts"))
    import verification_files
    return verification_files


# ---------------------------------------------------------------- the rows


def _ids(cell):
    return [item for item in (part.strip().strip("`") for part in (cell or "").split(",")) if item.lower() not in NO_ROW]


def _command(check):
    """The command of a check cell: its first code span, else the whole cell. A method or `not applicable` has none."""
    text = (check or "").strip()
    if not text or text.lower().startswith(SKIPPED):
        return None
    spans = SPAN.findall(text)
    return spans[0].strip() if spans else text


def gate_rows(contracts, verification):
    """Each live row of VERIFICATION.md that covers a high level, with the subtasks whose contracts name it and the
    command of its contract row (a live tier first)."""
    vf = _verification_files()
    try:
        rows = vf.read_rows(verification)
    except Exception as error:  # the reader raises the refusal class of its own skill
        raise Refusal(getattr(error, "code", "bad-verification"), getattr(error, "reason", str(error))) from None
    found = []
    for row in rows:
        if not vf._covers_high(row):
            continue
        named = [(item, gate) for item in contracts for gate in item.rows if row["id"] in _ids(gate.plan_row)]
        named.sort(key=lambda pair: pair[1].tier.strip("` ").lower() not in LIVE_TIERS)
        lower = vf.LOWER.fullmatch(row["status"])
        found.append({"id": row["id"], "journey": row["story"], "behavior": row["then"], "level": row["level"], "row": row,
                      "subtasks": list(dict.fromkeys(item.id for item, _ in named)),
                      "check": named[0][1].check if named else None,
                      "command": next((command for _, gate in named if (command := _command(gate.check))), None),
                      "lower": {"level": lower.group(2), "mark": lower.group(3)} if lower else None})
    return found


def _driver_proven():
    """The install record holds a green browser-driver proof of setup."""
    try:
        path = afkv2_config.data_folder() / "install.txt"
        lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    except (afkv2_config.Refusal, OSError):
        return False
    return any(line.partition(" ")[0] == DRIVER_KEY and line.partition(" ")[2].strip() for line in lines)


def _own_waiting(row, driver):
    """Why this row cannot run, before the app is asked; None when it can."""
    if not row["command"]:
        return f"no command the gate can run: {row['check'] or 'no contract names ' + row['id']}"
    if row["level"] in DRIVER_LEVELS and not driver:
        return "browser driver: the install record has no green driver proof; run the browser-driver step of /afkv2:setup"
    return None


@contextmanager
def _app(plan_text, repo, needed):
    """Yields why the rows cannot reach the app, or None. It starts the live block when it is not up and stops it after."""
    app = plan_app(plan_text)
    if not needed or app is None:
        yield None
        return
    if app != APP_CONFIG:
        problem = app_failure("PLAN.md", app)
        yield f"live build: {problem['reason']}" if problem else None
        return
    config = afkv2_config.read_config(repo)
    if not config["ok"] or "live" not in config:
        error = config.get("error") or {"code": "live-undefined", "reason": "the repository config has no live block"}
        yield f"live build: {error['code']}: {error['reason']}; prove the live block with /afkv2:propose-verification"
        return
    live = config["live"]
    missing = [name for name in live["needs"] if not os.environ.get(name)]
    if missing:
        yield f"credentials: {', '.join(missing)} is not set in the environment of the run"
        return
    if app_failure("live", live["address"]) is None:
        yield None
        return
    try:
        handle = live_build.start_live(repo)
    except afkv2_config.Refusal as error:
        yield f"live build: {error.code}: {error.reason}"
        return
    try:
        yield None
    finally:
        try:
            live_build.stop_live(handle)
        except afkv2_config.Refusal:
            pass  # stop_live kills the process tree in any case


def _run_once(row, folder, repo, n):
    name = f"{row['id']}-{n}"
    evidence, log = folder / name, folder / f"{name}.log"
    shutil.rmtree(evidence, ignore_errors=True)
    evidence.mkdir(parents=True)
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    clock = time.monotonic()
    with open(log, "wb") as output:
        try:
            code = subprocess.run(row["command"], shell=True, cwd=repo, stdout=output, stderr=subprocess.STDOUT,
                                  stdin=subprocess.DEVNULL, timeout=TEST_LIMIT,
                                  env={**os.environ, EVIDENCE_VARIABLE: str(evidence)}).returncode
        except subprocess.TimeoutExpired:
            output.write(f"\nthe end gate stopped the test after {TEST_LIMIT} s\n".encode("utf-8"))
            code = -1
    files = sorted(str(path) for path in evidence.rglob("*") if path.is_file())
    if not files:
        shutil.rmtree(evidence, ignore_errors=True)
    return {"exit": code, "started": started, "seconds": round(time.monotonic() - clock, 3), "log": str(log), "evidence": files}


def _runs(row, folder, repo):
    first = _run_once(row, folder, repo, 1)
    return [first] if first["exit"] == 0 else [first, _run_once(row, folder, repo, 2)]


def _gate_run(rows, path, head, verification, plan_text, repo):
    folder = path.parent / head[:12]
    shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True)
    driver = _driver_proven()
    waiting = {row["id"]: _own_waiting(row, driver) for row in rows}
    entries = []
    with _app(plan_text, repo, needed=not all(waiting.values())) as unreachable:
        for row in rows:
            reason = waiting[row["id"]] or unreachable
            entry = {"row": row["id"], "behavior": row["behavior"], "level": row["level"],
                     "ran": row["command"] or row["check"] or "nothing ran", "lower": row["lower"]}
            entries.append({**entry, "waiting": reason, "runs": []} if reason else {**entry, "runs": _runs(row, folder, repo)})
    try:
        gate_record.write_run(path, lane="medium", head=head, verification=verification, rows=entries)
    except afkv2_config.Refusal as error:
        raise _refusal(error) from None


# ---------------------------------------------------------------- the judge


def _tests_of(plan, row):
    """The test files that the test-first records of the row's subtasks name for it."""
    files = []
    for subtask in row["subtasks"]:
        for cycle in walk.tdd_log.record(plan, subtask)["cycles"]:
            if cycle.get("row") == row["id"] and cycle.get("test"):
                files.append(cycle["test"].split("::", 1)[0])
    return list(dict.fromkeys(files))


def _judge(plan, record, rows, path, session, repo, judge):
    """1 judge call on the rows, the evidence of their last runs and their tests. The answer is why no verdict was
    written, or None."""
    folder = path.parent / f"{record['head'][:12]}-judge"
    shutil.rmtree(folder, ignore_errors=True)
    (folder / "tests").mkdir(parents=True)
    (folder / "evidence").mkdir()
    by_id = {row["id"]: row for row in rows}
    inputs = []
    for stored in record["rows"]:
        row = by_id[stored["row"]]
        run = stored["runs"][-1]
        inputs.append({**{key: row["row"][key] for key in ("id", "criteria", "story", "given", "when", "then", "level",
                                                           "data", "environment")},
                       "ran": stored["ran"], "runs": [{"n": item["n"], "exit": item["exit"]} for item in stored["runs"]]})
        target = folder / "evidence" / stored["row"]
        target.mkdir()
        for item in ([run["log"]] if run["log"] else []) + run["evidence"]:
            source = path.parent / item["path"]
            shutil.copyfile(source, target / source.name)
        for name in _tests_of(plan, row):
            source = repo / name
            if source.is_file():
                (folder / "tests" / name).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, folder / "tests" / name)
    (folder / "rows.json").write_text(json.dumps(inputs, indent=1), encoding="utf-8")
    try:
        judged = (judge or other_provider.judge)(folder, session)
        gate_record.write_verdict(path, judged, head=record["head"])
    except afkv2_config.Refusal as error:
        return f"judge: {error.code}: {error.reason}"
    finally:
        shutil.rmtree(folder, ignore_errors=True)
    return None


# ---------------------------------------------------------------- the outcome


def _why_failed(stored):
    if stored["result"] == "fail":
        return "it failed twice"
    if stored["result"] == "flaky":
        return "it failed, then passed: flaky counts as a fail"
    verdict = stored["verdict"]
    if verdict and verdict.get("result") != "pass":
        checks = [item.get("check") for item in verdict.get("checks") or [] if item.get("result") != "pass"]
        return "the judge failed it" + (f" on {', '.join(checks)}" if checks else ": what it saw does not match the row")
    return None


def _outcome(record, rows, judge_problem=None):
    """(result, failed rows, waiting rows) of a gate record."""
    by_id = {row["id"]: row for row in rows}
    failed, waiting = [], []
    for stored in record["rows"]:
        row = by_id.get(stored["row"], {})
        entry = {"row": stored["row"], "journey": row.get("journey"), "behavior": stored["behavior"],
                 "result": stored["result"], "subtasks": row.get("subtasks", [])}
        why = _why_failed(stored)
        if why:
            failed.append({**entry, "why": why})
        elif stored["result"] == "waiting":
            waiting.append({**entry, "why": stored["waiting"]})
        elif stored["verdict"] is None:
            waiting.append({**entry, "why": judge_problem or "no verdict: the judge runs only when every row passed"})
    return ("failed" if failed else "waiting" if waiting else "passed"), failed, waiting


def _read_record(path):
    if not path.is_file():
        return None
    try:
        return gate_record.read(path)
    except afkv2_config.Refusal as error:
        raise _refusal(error) from None


def _not_finished(plan, repo):
    failures = [{"subtask": subtask, "reason": f"{subtask} is {status}, not done"}
                for subtask, status in walk._statuses(plan).items() if status != "done"]
    dirty = walk._git(repo, "status", "--porcelain", "--untracked-files=no")
    if dirty:
        failures.append({"subtask": None, "reason": f"the feature worktree has uncommitted changes: {dirty.splitlines()[0]}"})
    return failures


def run_gate(plan, *, session, code=".", judge=None):
    """1 end-gate run (SDD §3 row S-6). `judge(folder, session)` replaces the other-provider call in tests."""
    plan = Path(plan)
    plan_text = read_text(plan_file(plan))
    if rules_of(plan_text) != 2:
        return ok(result="none", reason="a plan without `> Rules: 2` has no end gate", ran=False, failed=[], waiting=[])
    if session not in other_provider.PROVIDERS:
        raise Refusal("bad-payload", f"`session` is the provider of this session: {', '.join(other_provider.PROVIDERS)}")
    repo = Path(walk._git(code, "rev-parse", "--show-toplevel"))
    failures = _not_finished(plan, repo)
    if failures:
        raise Refusal("not-finished", "the end gate runs after every subtask is done", failures=failures)
    verification = repo / walk._spec_dir(plan, repo) / VERIFICATION
    if not verification.is_file():
        raise Refusal("no-verification", f"no {VERIFICATION} at {verification}: /afkv2:propose-verification writes it")
    rows = gate_rows(walk._contracts(plan), verification)
    state = walk._load(plan)
    gate = state.setdefault("gate", {})
    judge_failed = gate.setdefault("judge_failed", [])
    path, head = record_path(plan), walk._git(repo, "rev-parse", "HEAD")
    if not rows:
        gate.update(result="none", head=head)
        return _finish(plan, state, ok(result="none", reason=f"{VERIFICATION} has no high-level row", ran=False, failed=[], waiting=[]))
    record = _read_record(path)
    ran = not (record and record["head"] == head and record["verification_digest"] == gate_record.file_digest(verification)
               and not any(row["result"] == "waiting" for row in record["rows"]))
    if ran:
        failed_runs = (record or {}).get("failed_runs", 0) + len(judge_failed)
        if failed_runs >= FAILED_CAP:
            raise Refusal("gate-cap-reached", f"{failed_runs} gate runs of this ship failed: the run waits for the developer",
                          failed_runs=failed_runs)
        _gate_run(rows, path, head, verification, plan_text, repo)
        record = _read_record(path)
    problem = None
    if all(row["result"] == "pass" for row in record["rows"]) and any(row["verdict"] is None for row in record["rows"]):
        problem = _judge(plan, record, rows, path, session, repo, judge)
        record = _read_record(path)
        if any(_why_failed(row) for row in record["rows"]) and head not in judge_failed:
            judge_failed.append(head)
    result, failed, waiting = _outcome(record, rows, problem)
    verdicts = {row["row"]: row["verdict"] for row in record["rows"] if row["verdict"]}
    judged = next(iter(verdicts.values()), None)
    gate.update(result=result, head=head, failed=failed)
    return _finish(plan, state, ok(
        result=result, path=str(path), head=head, ran=ran, failed=failed, waiting=waiting,
        failed_runs=record["failed_runs"] + len(judge_failed), verdicts=verdicts,
        judge={key: judged[key] for key in ("provider", "model", "effort")} if judged else None))


def _finish(plan, state, answer):
    walk._save(plan, state)
    rows = ", ".join(item["row"] for item in answer["failed"] + answer["waiting"]) or "no row"
    walk._journal(plan, "autopilot", "run", f"end gate {answer['result']}",
                  f"the high-level tests ran against the live build; open: {rows}")
    walk._commit_run(plan, f"run: end gate {answer['result']}")
    return answer


def send_back(plan, rows):
    """Move the subtasks behind the failed rows from `done` to `pending` (SDD §3 row S-7). Each one starts again from
    a new base, so it needs a new commit; its brief names the rows."""
    plan = Path(plan)
    if not isinstance(rows, list) or not rows:
        raise Refusal("bad-payload", "`rows`: the ids of the failed rows of the last gate run")
    state = walk._load(plan)
    failed = {item["row"]: item for item in (state.get("gate") or {}).get("failed", [])}
    unknown = [row for row in rows if row not in failed]
    if unknown:
        raise Refusal("bad-payload", f"no failed row {', '.join(map(str, unknown))} in the last gate run")
    statuses, reopened = walk._statuses(plan), []
    for row in rows:
        for subtask in failed[row]["subtasks"]:
            if statuses.get(subtask) != "done":
                continue
            record = state["subtasks"].setdefault(subtask, {"attempts": 0})
            if subtask not in reopened:
                record.pop("base", None)
                record.update(attempts=0, back=[])
                write_status(plan, subtask, "pending")
                reopened.append(subtask)
            record["back"].append({"row": row, "why": failed[row]["why"], "behavior": failed[row]["behavior"]})
            walk._journal(plan, "autopilot", subtask, f"back({row})", f"the end gate sent this subtask back: {row} {failed[row]['why']}")
    walk._save(plan, state)
    walk._commit_run(plan, f"run: end gate sent back {', '.join(reopened) or 'nothing'}")
    return ok(reopened=reopened, rows=rows)


def ship_blocker(plan):
    """Why the gate record stops the ship; None when it passed or waits for the developer, or the plan has no gate."""
    plan = Path(plan)
    if rules_of(read_text(plan_file(plan))) != 2:
        return None
    gate = walk._load(plan).get("gate") or {}
    record = _read_record(record_path(plan))
    if record is None:
        return None if gate.get("result") == "none" else "the end gate has not run: run `end_gate.py run`"
    result, failed, _ = _outcome(record, [])
    return f"the end gate failed on {', '.join(item['row'] for item in failed)}" if result == "failed" else None


def _run(payload):
    return run_gate(walk._plan(payload), session=str(need(payload, "session")))


def _back(payload):
    return send_back(walk._plan(payload), need(payload, "rows"))


VERBS = {"run": _run, "back": _back}


def main(argv=None):
    return envelope.serve(VERBS, sys.argv[1:] if argv is None else argv)


if __name__ == "__main__":
    sys.exit(main())
