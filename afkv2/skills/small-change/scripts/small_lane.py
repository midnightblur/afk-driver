"""The small-lane record of one branch: `small_lane.py <verb> [json-payload]`, or the payload on stdin, from the
worktree of the branch (SDD §3 row S-8; §6 I-10).

Verbs: `start` the lane line; `diagnose` the verdict of a bug; `go` the developer's go mark; `grow` the stop that
proposes the medium lane; `before` the failing high-level test of a bug before its fix; `gate` the small gate: 1
high-level test, the judge, and the gate record that ship reads. Each payload may hold `repo` (default: the current
folder). The record lives in the git folder of the worktree, never in a commit.
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

PLUGIN = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PLUGIN / "ports"))
sys.path.insert(0, str(PLUGIN / "scripts"))
sys.path.insert(0, str(PLUGIN / "skills" / "use-lavish" / "scripts"))
sys.path.insert(0, str(PLUGIN / "skills" / "execute" / "scripts"))

from tracker import envelope  # noqa: E402
from tracker.envelope import Refusal, need, ok  # noqa: E402

import afkv2_config  # noqa: E402
import gate_record  # noqa: E402
import live_build  # noqa: E402
import grill_common  # noqa: E402
import other_provider  # noqa: E402
import page_home  # noqa: E402
import round_document  # noqa: E402
from tdd_log import _uncommitted, is_test_file  # noqa: E402

LANE_FOLDER = "afkv2-small"
PAGE_SKILL = "small-change"
LANE_FILE = "lane.json"
TEST_PLAN = "TEST-PLAN.md"
GATE_FOLDER = "gate"
BEFORE_LOG = "before.log"
KINDS = ("bug", "enhancement")
VERDICTS = ("one-fix", "several-fixes", "spec-gap", "works-as-specified", "cannot-reproduce")
HIGH_LEVELS = ("api", "ui-e2e", "acceptance")
ROW = "SL-1"
EVIDENCE_VARIABLE = "AFKV2_EVIDENCE"
TEST_LIMIT = 1800
GIT_LIMIT = 120
TAIL_LINES = 20


# ---------------------------------------------------------------- the record

def _repo(payload):
    return Path(str(payload.get("repo") or ".")).resolve()


def _git(repo, *args):
    done = subprocess.run(["git", *args], cwd=repo, capture_output=True, stdin=subprocess.DEVNULL, timeout=GIT_LIMIT)
    if done.returncode != 0:
        raise Refusal("git-failed", f"git {args[0]}: {done.stderr.decode('utf-8', 'replace').strip()}")
    return done.stdout.decode("utf-8", "replace").strip()


def lane_folder(repo):
    """The folder of the lane in the git folder of this worktree: every worktree has its own, none is committed."""
    return Path(_git(repo, "rev-parse", "--absolute-git-dir")) / LANE_FOLDER


def read_lane(repo):
    path = lane_folder(repo) / LANE_FILE
    if not path.is_file():
        raise Refusal("no-lane", "no small lane is started in this worktree: run `start`")
    return json.loads(path.read_text(encoding="utf-8"))


def _save_lane(repo, lane):
    path = lane_folder(repo) / LANE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(lane, indent=1), encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _line(text, key):
    value = str(text or "").strip()
    if not value or "\n" in value:
        raise Refusal("bad-payload", f"`{key}` is 1 line of text")
    return value


def _code_changes(repo, since):
    """The code files that commits after `since` or uncommitted changes touch."""
    names = _git(repo, "diff", "--name-only", since, "HEAD").splitlines()
    names += _uncommitted(repo)
    return _code_of(repo, names)


def _code_of(repo, names):
    """The code files among `names`: a test file, or a file of the spec folder such as a page round, is no code."""
    config = afkv2_config.read_config(repo, with_live=False)
    spec = None
    if config.get("ok"):
        spec = Path(config["spec_folder"]).resolve().relative_to(Path(config["repo_root"]).resolve()).as_posix() + "/"
    return sorted({name for name in names
                   if name and not is_test_file(name) and not (spec and name.startswith(spec))})


def _open_lane(repo):
    lane = read_lane(repo)
    if lane.get("grew"):
        raise Refusal("grew-past-small", f"the work grew past small: {lane['grew']['reason']}; the developer picks the "
                                         "medium lane or a smaller fix")
    return lane


def _go_of(repo, lane):
    """The go of the lane, after the check that no code commit came before it (invariant I-10)."""
    go = lane.get("go")
    if not go:
        raise Refusal("no-go-mark", "no go mark of the developer is on record: run `go` after the developer's sign mark")
    early = _code_of(repo, _git(repo, "diff", "--name-only", lane["base"], go["head"]).splitlines())
    if early:
        raise Refusal("code-before-go", f"commits before the developer's go changed code: {', '.join(early)}")
    return go


# ---------------------------------------------------------------- start, diagnose, go, grow

def start(payload):
    """The lane line: `Lane: small (<kind>): <why>`. A new start replaces the record of an earlier lane."""
    repo, kind = _repo(payload), str(need(payload, "kind"))
    if kind not in KINDS:
        raise Refusal("bad-payload", f"kind {kind!r}: one of {', '.join(KINDS)}")
    why = _line(need(payload, "why"), "why")
    folder = lane_folder(repo)
    shutil.rmtree(folder, ignore_errors=True)
    lane = {"version": 1, "kind": kind, "why": why, "base": _git(repo, "rev-parse", "HEAD"), "started": _now(),
            "diagnosis": None, "go": None, "grew": None, "before": None}
    _save_lane(repo, lane)
    return ok(line=f"Lane: small ({kind}): {why}", base=lane["base"], folder=str(folder),
              gate=str(folder / GATE_FOLDER / gate_record_name()), **_page(payload.get("ticket")))


def _page(ticket):
    """The page document of the round: in the ticket's spec folder, else in the data folder; named for the round
    builder, which reads the writer from the file name."""
    try:
        pages = page_home._spec_pages(ticket) if ticket else page_home._data_pages()
    except grill_common.Refusal as error:
        raise Refusal(error.code, error.reason) from None
    session = page_home._new_session(pages)
    doc = pages / f"{PAGE_SKILL}-{session}.json"
    return {"doc": doc.as_posix(), "session": session, "raw_file": doc.with_name(f"{doc.stem}.raw.txt").as_posix()}


def gate_record_name():
    return "record.json"


def diagnose(payload):
    repo, verdict = _repo(payload), str(need(payload, "verdict"))
    if verdict not in VERDICTS:
        raise Refusal("bad-payload", f"verdict {verdict!r}: one of {', '.join(VERDICTS)}")
    lane = _open_lane(repo)
    lane["diagnosis"] = {"verdict": verdict, "cause": str(need(payload, "cause")), "at": _now()}
    _save_lane(repo, lane)
    return ok(diagnosis=lane["diagnosis"])


def record_go(repo, doc, card, test_plan):
    """Record the developer's go: the card holds the sign mark, and no code changed since the start of the lane."""
    repo = Path(repo)
    lane = _open_lane(repo)
    if lane["kind"] == "bug" and not lane["diagnosis"]:
        raise Refusal("no-diagnosis", "a bug gets its go only after the diagnosis verdict: run `diagnose`")
    items = [item for rnd in round_document.read_json(Path(doc)).get("rounds", []) for item in rnd.get("items", [])
             if item.get("id") == card]
    if not items or not round_document.holds_sign_mark(items[-1]):
        raise Refusal("no-go-mark", f"card {card} holds no sign mark of the developer")
    early = _code_changes(repo, lane["base"])
    if early:
        raise Refusal("code-before-go", f"code changed before the developer's go: {', '.join(early)}")
    go = {"card": card, "head": _git(repo, "rev-parse", "HEAD"), "at": _now()}
    folder = lane_folder(repo)
    (folder / TEST_PLAN).write_text(str(test_plan).strip() + "\n", encoding="utf-8", newline="\n")
    lane["go"] = go
    _save_lane(repo, lane)
    return go


def go(payload):
    repo = _repo(payload)
    answer = record_go(repo, need(payload, "doc"), str(need(payload, "card")), need(payload, "test_plan"))
    return ok(go=answer, folder=str(lane_folder(repo)))


def grow(payload):
    """The stop: no more code; the developer reads the proposal on the page and picks the lane."""
    repo = _repo(payload)
    reason = _line(need(payload, "reason"), "reason")
    lane = read_lane(repo)
    lane["grew"] = {"reason": reason, "head": _git(repo, "rev-parse", "HEAD"), "at": _now()}
    _save_lane(repo, lane)
    return ok(proposal=f"Stop: this work grew past small ({reason}). Proposal: the medium lane, from "
                       "/afkv2:grill-requirements. The developer decides.")


# ---------------------------------------------------------------- the tests

def _run(command, repo, output, evidence=None):
    """The exit code of 1 command in the named shell; past TEST_LIMIT its tree stops and the code is -1."""
    try:
        args = live_build.shell_argv(command)
    except afkv2_config.Refusal as error:
        raise Refusal(error.code, error.reason) from None
    env = live_build.shell_env({EVIDENCE_VARIABLE: str(evidence)} if evidence else None)
    try:
        process = subprocess.Popen(args, cwd=repo, stdout=output, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                   env=env, **other_provider._group())
    except OSError as error:
        output.write(f"the test did not start: {error}\n".encode("utf-8"))
        return -1
    try:
        return process.wait(timeout=TEST_LIMIT)
    except subprocess.TimeoutExpired:
        other_provider._stop_tree(process)
        output.write(f"\nthe small gate stopped the test after {TEST_LIMIT} s\n".encode("utf-8"))
        return -1


def _tail(path):
    return "\n".join(Path(path).read_text(encoding="utf-8", errors="replace").splitlines()[-TAIL_LINES:])


def before(payload):
    """The before evidence of a bug: the high-level test fails at a head whose code is the code of the go."""
    repo, command = _repo(payload), str(need(payload, "command"))
    lane = _open_lane(repo)
    go = _go_of(repo, lane)
    changed = _code_changes(repo, go["head"])
    if changed:
        raise Refusal("fix-before-before", f"the fix started before the before run: {', '.join(changed)}")
    folder = lane_folder(repo) / GATE_FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    log = folder / BEFORE_LOG
    with _live(repo) as unreachable, open(log, "wb") as output:
        if unreachable:
            raise Refusal("live-start-failed", unreachable)
        code = _run(command, repo, output)
    if code == 0:
        raise Refusal("not-red", "the test passes before the fix: it proves nothing about the bug", output=_tail(log))
    lane["before"] = {"command": command, "exit": code, "head": _git(repo, "rev-parse", "HEAD"), "log": str(log), "at": _now()}
    _save_lane(repo, lane)
    return ok(exit=code, log=str(log), output=_tail(log))


@contextmanager
def _live(repo):
    """Yields why the test cannot reach the app, or None. It starts the live block of the repository config when its
    address does not answer, and stops it after; with no live block the test owns its app."""
    config = afkv2_config.read_config(repo)
    if not config.get("ok") or "live" not in config or live_build._answers(config["live"]["address"]):
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


def _run_row(command, repo, folder, before_log):
    runs = []
    for n in (1, 2):
        evidence, log = folder / f"{ROW}-{n}", folder / f"{ROW}-{n}.log"
        shutil.rmtree(evidence, ignore_errors=True)
        evidence.mkdir(parents=True)
        if before_log and n == 1:
            shutil.copyfile(before_log, evidence / BEFORE_LOG)
        started, clock = _now(), time.monotonic()
        with open(log, "wb") as output:
            code = _run(command, repo, output, evidence)
        runs.append({"exit": code, "started": started, "seconds": round(time.monotonic() - clock, 3), "log": str(log),
                     "evidence": sorted(str(path) for path in evidence.rglob("*") if path.is_file())})
        if code == 0:
            return runs
    return runs


def _judge_input(record, payload, repo, path, folder):
    """rows.json, the evidence of the last run under evidence/SL-1/, and the test file under tests/."""
    (folder / "tests").mkdir(parents=True)
    target = folder / "evidence" / ROW
    target.mkdir(parents=True)
    stored = record["rows"][0]
    run = stored["runs"][-1]
    for item in ([run["log"]] if run["log"] else []) + run["evidence"]:
        source = path.parent / item["path"]
        shutil.copyfile(source, target / source.name)
    test = payload.get("test")
    if test:
        source = (repo / str(test)).resolve()
        if source.is_relative_to(repo) and source.is_file():
            (folder / "tests" / source.relative_to(repo)).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, folder / "tests" / source.relative_to(repo))
    row = {"id": ROW, "criteria": "small lane", "story": stored["behavior"], "given": "the code before the fix",
           "when": stored["ran"], "then": stored["behavior"], "level": stored["level"], "data": "—",
           "environment": "—", "ran": stored["ran"], "runs": [{"n": item["n"], "exit": item["exit"]} for item in stored["runs"]]}
    (folder / "rows.json").write_text(json.dumps([row], indent=1), encoding="utf-8")


def gate(payload, judge=None):
    """The small gate: 1 high-level test, once, once more after a fail; the judge when it passed; the gate record.
    `judge(folder, session)` replaces the other-provider call in tests."""
    repo = _repo(payload)
    behavior, command = str(need(payload, "behavior")), str(need(payload, "command"))
    level, session = str(need(payload, "level")), str(need(payload, "session"))
    if level not in HIGH_LEVELS:
        raise Refusal("bad-payload", f"level {level!r}: the proof of the small lane is 1 high-level test ({', '.join(HIGH_LEVELS)})")
    lane = _open_lane(repo)
    go = _go_of(repo, lane)
    if lane["kind"] == "bug" and not lane.get("before"):
        raise Refusal("no-before", "a bug needs its before evidence: run `before` before the fix")
    head = _git(repo, "rev-parse", "HEAD")
    lane_dir = lane_folder(repo)
    path = lane_dir / GATE_FOLDER / gate_record_name()
    try:
        if _kept(path, head, lane_dir / TEST_PLAN):
            # The record keeps its runs at this head: running again would overwrite the evidence it cites.
            written = gate_record.write_run(path, lane="small", head=head, verification=lane_dir / TEST_PLAN,
                                            rows=[], go=go)
        else:
            folder = path.parent / head[:12]
            shutil.rmtree(folder, ignore_errors=True)
            folder.mkdir(parents=True)
            before_log = Path(lane["before"]["log"]) if lane.get("before") else None
            with _live(repo) as waiting:
                runs = [] if waiting else _run_row(command, repo, folder, before_log)
            row = {"row": ROW, "behavior": behavior, "level": level, "ran": command, "runs": runs, "waiting": waiting}
            written = gate_record.write_run(path, lane="small", head=head, verification=lane_dir / TEST_PLAN,
                                            rows=[row], go=go)
        record = gate_record.read(path)
    except afkv2_config.Refusal as error:
        raise Refusal(error.code, error.reason) from None
    result = record["rows"][0]["result"]
    problem = None
    if result == "pass" and record["rows"][0]["verdict"] is None:
        problem = _judge(record, payload, repo, path, session, judge)
        record = gate_record.read(path)
    verdict = record["rows"][0]["verdict"]
    return ok(path=str(path), written=written["written"], result=result, judge=problem,
              verdict=verdict["result"] if verdict else None)


def _kept(path, head, test_plan):
    """True when the gate record keeps its rows at this head and test plan: no row waits."""
    if not path.exists():
        return False
    record = gate_record.read(path)
    return (record["head"] == head and record["verification_digest"] == gate_record.file_digest(test_plan)
            and not any(row["result"] == "waiting" for row in record["rows"]))


def _judge(record, payload, repo, path, session, judge):
    folder = path.parent / f"{record['head'][:12]}-judge"
    shutil.rmtree(folder, ignore_errors=True)
    try:
        _judge_input(record, payload, repo, path, folder)
        judged = (judge or other_provider.judge)(folder, session)
        gate_record.write_verdict(path, judged, head=record["head"])
    except afkv2_config.Refusal as error:
        return f"judge: {error.code}: {error.reason}"
    except OSError as error:
        return f"judge: the input folder could not be built: {error}"
    finally:
        shutil.rmtree(folder, ignore_errors=True)
    return None


VERBS = {"start": start, "diagnose": diagnose, "go": go, "grow": grow, "before": before, "gate": gate}


def main(argv=None):
    return envelope.serve(VERBS, sys.argv[1:] if argv is None else argv)


if __name__ == "__main__":
    sys.exit(main())
