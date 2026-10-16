#!/usr/bin/env afk-python
"""Publish REPORT.md beside a validated, stamped coverage ledger.

The header line is computed from the ledger (`LEDGER-FORMAT.md` § "REPORT.md").
The body arrives on stdin, written to `LANGUAGE.md` (plugin root) §3.

Usage:
  write_report.py --ledger <ledger dir>/COVERAGE.json < body.md

Exit codes: 0 wrote REPORT.md, 1 the ledger or the body is refused, 2 usage
or an unreadable ledger.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate_coverage  # noqa: E402

BODY_LIMIT = 40
DONE = ("closed", "n/a")


def header(document: dict, ledger_path: str) -> str:
    run = document.get("run") or {}
    classes = [row for row in document.get("boundaries") or [] if isinstance(row, dict)]
    done = sum(1 for row in classes if row.get("status") in DONE)
    unverified = [row for row in document.get("claims") or []
                  if isinstance(row, dict) and row.get("kind") == "unverified"]
    load_bearing = sum(1 for row in unverified if row.get("load_bearing"))
    return (f"{run.get('repository')}@{run.get('head')} · {run.get('verdict')} · "
            f"boundaries {done}/{len(classes)} · unverified {len(unverified)} "
            f"(load-bearing {load_bearing}) · ledger: {ledger_path}")


def refusal(document: dict, body: str) -> str | None:
    """Why this ledger and body cannot be published, or None."""
    defects, verdict = validate_coverage.validate(document)
    if defects:
        return f"the ledger carries {len(defects)} defect(s), first: {defects[0]}"
    stamped = (document.get("run") or {}).get("verdict")
    if stamped != verdict:
        return (f"run.verdict is {stamped!r}, the validator computes {verdict!r}; "
                "stamp the verdict before publishing")
    lines = body.strip("\n").splitlines()
    if not body.strip():
        return "the body is empty; it carries the answer and the lists"
    if len(lines) > BODY_LIMIT:
        return f"the body is {len(lines)} lines, past the {BODY_LIMIT} the format allows"
    return None


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", required=True, help="the published COVERAGE.json")
    args = parser.parse_args(argv)
    path = Path(args.ledger)
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"write_report: {path}: cannot read the ledger: {error}", file=sys.stderr)
        return 2
    if not isinstance(document, dict):
        print(f"write_report: {path}: a ledger is one object", file=sys.stderr)
        return 2
    body = sys.stdin.buffer.read().decode("utf-8").replace("\r\n", "\n")
    reason = refusal(document, body)
    if reason:
        print(f"write_report: {path}: {reason}", file=sys.stderr)
        return 1
    report = path.parent / "REPORT.md"
    report.write_text(f"{header(document, path.as_posix())}\n\n{body.strip(chr(10))}\n",
                      encoding="utf-8")
    print(f"write_report: {report}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
