"""The gate record: the one reader and writer of the proof of high-level tests (SDD §4 "Gate record").

The record is 1 JSON file on the local run branch. Evidence and log paths are relative to its folder.
Each function raises `Refusal` with a code; `verify` adds every failure to `GateRefusal.failures`.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from afkv2_config import Refusal  # noqa: E402
from other_provider import VERDICT_SCHEMA  # noqa: E402

VERSION = 1
LANES = ("medium", "small")
LEVELS = ("static", "unit", "integration", "contract", "api", "ui-e2e", "acceptance")
MAX_RUNS = 2
FAILED = ("fail", "flaky")
PICKS = ("fix-in-place", "fix-now", "ticket", "dropped")
FOUND_FIELDS = ("id", "what", "where", "how")
FOUND_ID = re.compile(r"FB-\d{2,}")
GO_FIELDS = ("card", "head", "at")
ROW_TEXT = ("row", "behavior", "ran")
PROOF_FIELDS = ("behavior", "level", "ran", "evidence")
DEVELOPER = "developer"
GIT_SECONDS = 60
SHORT_DIGEST = 12
# The picture and video types a tracker attaches (ADR-0005: GitHub takes pictures and video only).
PICTURE_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".mp4", ".mov", ".webm")
SHIP_CODES = ("gate-not-passed", "verdict-no-description", "evidence-changed", "gate-head-stale", "proof-missing",
              "proof-field-missing", "found-open")


def file_digest(path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read(record_path) -> dict:
    """The stored record. Refuses `no-gate`, `gate-unreadable` and `gate-version-unknown`."""
    path = Path(record_path)
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise Refusal("no-gate", f"no gate record at {path}: run the end gate") from None
    except (OSError, ValueError) as error:
        raise Refusal("gate-unreadable", f"cannot read the gate record {path}: {error}") from None
    if not isinstance(record, dict) or not isinstance(record.get("rows"), list):
        raise Refusal("gate-unreadable", f"{path} is not a gate record")
    if record.get("version") != VERSION:
        raise Refusal("gate-version-unknown", f"gate record version {record.get('version')!r}: this module reads version {VERSION}")
    return record


def write_run(record_path, *, lane, head, verification, rows, found=None, go=None) -> dict:
    """Write 1 gate run. A second run at the same (head, VERIFICATION.md digest) writes nothing.

    `rows`: 1 entry per high-level row, `{row, behavior, level, ran, runs[{exit, started, seconds, log, evidence[]}],
    waiting, lower}`. `found`: the bugs `{id, what, where, how, pick, by}` this run adds or changes.
    `go`: the developer's go `{card, head, at}`, small lane only."""
    path = Path(record_path)
    folder = path.parent
    digest = file_digest(verification)
    previous = read(path) if path.exists() else None
    if previous and previous["head"] == head and previous["verification_digest"] == digest:
        return _run_answer(path, previous, written=False)
    if lane not in LANES:
        raise Refusal("bad-payload", f"lane {lane!r}: medium or small")
    if not isinstance(head, str) or not re.fullmatch(r"[0-9a-f]{40}", head):
        raise Refusal("bad-payload", "head: the full commit hash the tests ran at")
    stored_rows = _rows(rows, folder)
    go = go if go is not None else (previous or {}).get("go")
    _check_go(lane, go)
    failed = (previous or {}).get("failed_runs", 0) + any(row["result"] in FAILED for row in stored_rows)
    record = {"version": VERSION, "lane": lane, "head": head, "verification_digest": digest, "rows": stored_rows,
              "found": _found((previous or {}).get("found", []), found or []), "go": go, "failed_runs": failed}
    _save(path, record)
    return _run_answer(path, record, written=True)


def _run_answer(path, record, *, written) -> dict:
    return {"ok": True, "written": written, "path": str(path), "failed_runs": record["failed_runs"],
            "results": {row["row"]: row["result"] for row in record["rows"]}}


def _rows(rows, folder: Path) -> list[dict]:
    if not isinstance(rows, list):
        raise Refusal("bad-payload", "rows: a list of gate rows")
    stored, ids = [], set()
    for row in rows:
        if not isinstance(row, dict):
            raise Refusal("bad-payload", "each row is an object")
        name = row.get("row")
        for key in ROW_TEXT:
            if not isinstance(row.get(key), str) or not row[key].strip():
                raise Refusal("bad-payload", f"row {name!r}: `{key}` is required")
        if name in ids:
            raise Refusal("bad-payload", f"row {name}: 2 entries in 1 gate run")
        ids.add(name)
        if row.get("level") not in LEVELS:
            raise Refusal("bad-payload", f"row {name}: level {row.get('level')!r} is not one of {', '.join(LEVELS)}")
        lower = row.get("lower")
        if lower is not None and (not isinstance(lower, dict) or lower.get("level") not in LEVELS
                                  or not (lower.get("mark") or lower.get("quote"))):
            raise Refusal("bad-payload", f"row {name}: `lower` needs a level and the developer's mark or quote")
        runs, waiting = row.get("runs") or [], row.get("waiting") or None
        stored.append({"row": name, "behavior": row["behavior"], "level": row["level"], "ran": row["ran"],
                       "runs": [_run(name, n, run, folder) for n, run in enumerate(runs, 1)],
                       "result": _result(name, [run.get("exit") for run in runs], waiting),
                       "waiting": waiting, "lower": lower, "verdict": None})
    return stored


def _result(name, exits, waiting) -> str:
    if waiting:
        return "waiting"
    if not exits or len(exits) > MAX_RUNS or (exits[0] == 0 and len(exits) > 1):
        raise Refusal("bad-payload", f"row {name}: 1 run, or 2 after a fail; {len(exits)} given")
    if exits[0] == 0:
        return "pass"
    return "flaky" if len(exits) == 2 and exits[1] == 0 else "fail"


def _run(name, n, run, folder: Path) -> dict:
    if not isinstance(run, dict) or not isinstance(run.get("exit"), int) or isinstance(run.get("exit"), bool):
        raise Refusal("bad-payload", f"row {name}, run {n}: `exit` is an integer")
    if not isinstance(run.get("seconds"), (int, float)) or not isinstance(run.get("started"), str):
        raise Refusal("bad-payload", f"row {name}, run {n}: `started` and `seconds` are required")
    evidence = run.get("evidence") or []
    if not isinstance(evidence, list):
        raise Refusal("bad-payload", f"row {name}, run {n}: `evidence` is a list of paths")
    log = run.get("log")
    return {"n": n, "exit": run["exit"], "started": run["started"], "seconds": run["seconds"],
            "log": _file(name, log, folder) if log else None, "evidence": [_file(name, item, folder) for item in evidence]}


def _file(name, given, folder: Path) -> dict:
    path = Path(str(given))
    full = path if path.is_absolute() else folder / path
    if not full.is_file():
        raise Refusal("evidence-missing", f"row {name}: no file at {full}")
    try:
        stored = full.resolve().relative_to(folder.resolve()).as_posix()
    except ValueError:
        stored = str(full.resolve())
    return {"path": stored, "sha256": file_digest(full), "bytes": full.stat().st_size}


def _found(previous, given) -> list[dict]:
    if not isinstance(given, list):
        raise Refusal("bad-payload", "found: a list of found bugs")
    merged = {item["id"]: item for item in previous}
    ids = set()
    for item in given:
        if not isinstance(item, dict):
            raise Refusal("bad-payload", "each found bug is an object")
        for key in FOUND_FIELDS:
            if not isinstance(item.get(key), str) or not item[key].strip():
                raise Refusal("bad-payload", f"found bug {item.get('id')!r}: `{key}` is required")
        if not FOUND_ID.fullmatch(item["id"]) or item["id"] in ids:
            raise Refusal("bad-payload", f"found bug {item['id']!r}: a unique id FB-NN")
        ids.add(item["id"])
        pick, by = item.get("pick"), item.get("by")
        if pick is not None and (pick not in PICKS or not by):
            raise Refusal("bad-payload", f"found bug {item['id']}: pick is one of {', '.join(PICKS)}, with `by`")
        merged[item["id"]] = {**{key: item[key] for key in FOUND_FIELDS}, "pick": pick, "by": by if pick else None}
    return sorted(merged.values(), key=lambda item: int(item["id"][3:]))


def _check_go(lane, go) -> None:
    if lane == "medium" and go is not None:
        raise Refusal("bad-payload", "go: the small lane only")
    if lane == "small" and (not isinstance(go, dict) or any(not go.get(key) for key in GO_FIELDS)):
        raise Refusal("bad-payload", "go: the small lane needs the developer's go `{card, head, at}`")


def _save(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(record, indent=1), encoding="utf-8", newline="\n")
    os.replace(temporary, path)


# ---------------------------------------------------------------- the verdict


def write_verdict(record_path, judged, *, head) -> dict:
    """Store the judge's verdict per row (`judged["verdicts"]`, from `other_provider.judge`). 1 judge call per passed
    gate run: a record whose rows carry a verdict already writes nothing."""
    path = Path(record_path)
    record = read(path)
    if record["head"] != head:
        raise Refusal("gate-key-differs", f"the verdict is for {head}; the gate record ran at {record['head']}")
    open_rows = [row["row"] for row in record["rows"] if row["result"] != "pass"]
    if open_rows:
        raise Refusal("gate-not-passed", f"the judge runs only when every row passed; not passed: {', '.join(open_rows)}")
    if record["rows"] and all(row["verdict"] is not None for row in record["rows"]):
        return {"ok": True, "written": False, "path": str(path)}
    verdicts = judged.get("verdicts") if isinstance(judged, dict) else None
    verdicts = verdicts if isinstance(verdicts, dict) else {}
    for row in record["rows"]:
        verdict = verdicts.get(row["row"])
        if verdict is None:
            raise Refusal("verdict-missing", f"row {row['row']}: the judge answer has no verdict")
        if not isinstance(verdict, dict) or sorted(verdict) != sorted(VERDICT_SCHEMA["required"]):
            raise Refusal("bad-verdict", f"row {row['row']}: a verdict has exactly {', '.join(VERDICT_SCHEMA['required'])}")
        row["verdict"] = verdict
    _save(path, record)
    return {"ok": True, "written": True, "path": str(path)}


# ---------------------------------------------------------------- the ship check


class GateRefusal(Refusal):
    """A refusal of `verify`: `code` is the first failure, `failures` lists each `{code, row, reason}`."""

    def __init__(self, failures: list[dict]) -> None:
        super().__init__(failures[0]["code"], "; ".join(failure["reason"] for failure in failures))
        self.failures = failures


def verify(gate_path, proofs, head, *, spec_folder, repo, changed=None) -> dict:
    """The ship check (SDD §3 S-10, invariants I-7, I-8, I-11). `proofs`: the proof lines `{row, behavior, level,
    ran, evidence}` of the change. `head`: the commit to mark Ready. `changed(old, new)` names the paths changed
    between 2 commits; the default asks git in `repo`, the repository root."""
    path = Path(gate_path)
    record = read(path)
    failures = []

    def fail(code, row, reason):
        failures.append({"code": code, "row": row, "reason": reason})

    for row in record["rows"]:
        name, verdict = row["row"], row["verdict"]
        if row["result"] != "pass":
            fail("gate-not-passed", name, f"row {name} is {row['result']}" + (f": {row['waiting']}" if row["waiting"] else ""))
        elif verdict is None:
            fail("gate-not-passed", name, f"row {name} has no verdict of the judge")
        elif verdict.get("result") != "pass":
            fail("gate-not-passed", name, f"the judge failed row {name}")
        if verdict is not None and not [text for text in verdict.get("seen") or [] if str(text).strip()]:
            fail("verdict-no-description", name, f"the verdict of row {name} does not describe what the judge saw")
        for stored in _stored_files(row):
            problem = _changed_file(path.parent, stored)
            if problem:
                fail("evidence-changed", name, f"row {name}: {stored['path']} {problem}; run the gate again")
    if head != record["head"]:
        outside, problem = _outside_spec(record["head"], head, spec_folder, Path(repo), changed or _git_changed(Path(repo)))
        if problem or outside:
            fail("gate-head-stale", None, f"the gate ran at {record['head']}; "
                 + (problem or f"changes after it lie outside the spec folder: {', '.join(outside)}") + "; run the gate again")
    by_row = {proof.get("row"): proof for proof in proofs if isinstance(proof, dict)}
    for row in record["rows"]:
        proof = by_row.get(row["row"])
        if proof is None:
            fail("proof-missing", row["row"], f"row {row['row']} ({row['behavior']}) has no proof line")
            continue
        missing = [key for key in PROOF_FIELDS if not str(proof.get(key) or "").strip()]
        if missing:
            fail("proof-field-missing", row["row"], f"the proof line of row {row['row']} lacks {', '.join(missing)}")
    for bug in record["found"]:
        if bug["pick"] is None or (bug["pick"] != "fix-in-place" and bug["by"] != DEVELOPER):
            fail("found-open", None, f"found bug {bug['id']} ({bug['what']}) waits for the developer's pick")
    if failures:
        raise GateRefusal(sorted(failures, key=lambda failure: SHIP_CODES.index(failure["code"])))
    return {"ok": True, "gate": record}


def _stored_files(row) -> list[dict]:
    return [item for run in row["runs"] for item in ([run["log"]] if run["log"] else []) + run["evidence"]]


def _changed_file(folder: Path, stored: dict) -> str | None:
    path = Path(stored["path"])
    full = path if path.is_absolute() else folder / path
    if not full.is_file():
        return "is missing"
    if full.stat().st_size != stored["bytes"] or file_digest(full) != stored["sha256"]:
        return "changed after the run"
    return None


def _outside_spec(old, new, spec_folder, repo: Path, changed):
    folder = Path(spec_folder)
    if folder.is_absolute():
        try:
            folder = folder.resolve().relative_to(repo.resolve())
        except ValueError:
            return [], f"the spec folder {spec_folder} is outside the repository {repo}"
    prefix = folder.as_posix().strip("/") + "/"
    try:
        paths = changed(old, new)
    except Refusal as refusal:
        return [], refusal.reason
    return [name for name in paths if not name.replace("\\", "/").startswith(prefix)], None


def _git_changed(repo: Path):
    def changed(old, new):
        try:
            done = subprocess.run(["git", "-C", str(repo), "diff", "--name-only", old, new], capture_output=True,
                                  stdin=subprocess.DEVNULL, timeout=GIT_SECONDS)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise Refusal("git-failed", f"git diff {old} {new}: {error}") from None
        if done.returncode != 0:
            raise Refusal("git-failed", f"git diff {old} {new}: {done.stderr.decode('utf-8', 'replace').strip()}")
        return [line for line in done.stdout.decode("utf-8", "replace").splitlines() if line]
    return changed


# ---------------------------------------------------------------- the proof


def proof_lines(gate) -> list[dict]:
    """1 proof line per high-level row of the record `gate`: row, behavior, level, what ran, result, and the evidence
    of the row's last run as path and sha256 prefix."""
    return [{"row": row["row"], "behavior": row["behavior"], "level": row["level"], "ran": row["ran"],
             "result": row["result"],
             "evidence": ", ".join(f"{item['path']} (sha256 {item['sha256'][:SHORT_DIGEST]})" for item in _last(row)["evidence"])}
            for row in gate["rows"]]


def proof_comment(gate, *, receipt, change, folder) -> dict:
    """The ticket comment of the record `gate` (SDD §4 "Proof comment"): `body` and `pictures`, the picture files of
    each row's last run under `folder`, the record's folder. Logs go as name and sha256; the files stay local."""
    for key, value in (("receipt", receipt), ("change", change)):
        if not isinstance(value, str) or not value.strip():
            raise Refusal("bad-payload", f"the proof comment needs `{key}`")
    lines, pictures, logs, judge = [f"afkv2 proof v1 {receipt}"], [], [], None
    for row in gate["rows"]:
        verdict = row["verdict"]
        lines.append(" · ".join([row["row"], row["behavior"], row["level"], row["result"],
                                 _sentence(verdict["seen"]) if verdict else "not judged"]))
        judge = judge or verdict
        run = _last(row)
        for item in ([run["log"]] if run["log"] else []) + run["evidence"]:
            name = Path(item["path"])
            if name.suffix.lower() in PICTURE_SUFFIXES:
                pictures.append(str(name if name.is_absolute() else Path(folder) / name))
            else:
                logs.append(f"{name.name} sha256 {item['sha256']}")
    lines.append("Pictures: " + (", ".join(Path(picture).name for picture in pictures) or "none"))
    lines.append("Logs: " + (", ".join(logs) or "none"))
    named = " ".join(judge[key] for key in ("provider", "model", "effort")) if judge else "none"
    lines.append(f"Head {gate['head']} · change {change} · judge {named}")
    return {"body": "\n".join(lines), "pictures": pictures}


def _last(row) -> dict:
    return row["runs"][-1] if row["runs"] else {"log": None, "evidence": []}


def _sentence(seen) -> str:
    text = " ".join(str(seen[0]).split()) if seen else ""
    end = re.search(r"[.!?](\s|$)", text)
    return text[: end.start() + 1] if end else text
