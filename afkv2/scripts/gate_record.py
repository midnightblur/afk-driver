"""The gate record: the one reader and writer of the proof of high-level tests (SDD §4 "Gate record").

The record is 1 JSON file on the local run branch. Evidence and log paths are relative to its folder.
Each function raises `Refusal` with a code; `verify` adds every failure to `GateRefusal.failures`.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from afkv2_config import Refusal  # noqa: E402

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
