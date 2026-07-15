#!/usr/bin/env bash
# Render the workflow lesson ledger — the grammar's ONLY parsing site
# (format + resolution: skills/afk/lessons/LEDGER-FORMAT.md; lockstep with
# lesson-append.sh, the only emitting site). Read-only, never blocks.
#
# Usage: lesson-digest.sh [--count | --all]
#   (default)  open lessons, newest first: "L-NNNN | class | target | summary"
#   --count    just the number of open lessons (a bare integer)
#   --all      status counts + one line per lesson with its current status
#
# LESSON_LEDGER_DISABLE=1 → behaves as an empty ledger.
# LESSON_LEDGER_FILE relocates (default: <main-checkout>/.claude/lessons/LEDGER.jsonl).
set -uo pipefail

MODE="${1:-}"

empty() {
  if [ "$MODE" = "--count" ]; then echo 0; else echo "no lessons recorded"; fi
  exit 0
}

[ "${LESSON_LEDGER_DISABLE:-0}" = "1" ] && empty

if [ -z "${LESSON_LEDGER_FILE:-}" ]; then
  common=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null) || empty
  LESSON_LEDGER_FILE="$(dirname "$common")/.claude/lessons/LEDGER.jsonl"
fi
[ -f "$LESSON_LEDGER_FILE" ] || empty

python - "$LESSON_LEDGER_FILE" "$MODE" <<'PY' 2>/dev/null || empty
import json, sys

path, mode = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "")
lessons, order = {}, []
with open(path, encoding="utf-8") as f:
    for raw in f:
        raw = raw.strip()
        if not raw:
            continue
        try:
            e = json.loads(raw)
        except ValueError:
            continue
        lid = e.get("id")
        if not lid:
            continue
        if lid not in lessons:
            lessons[lid] = {}
            order.append(lid)
        lessons[lid].update(e)  # last event wins; opened payload persists

def row(lid):
    l = lessons[lid]
    return f"{lid} | {l.get('class','?')} | {l.get('target','?')} | {l.get('summary','')}"

open_ids = [i for i in order if lessons[i].get("event") == "opened"]

if mode == "--count":
    print(len(open_ids))
elif mode == "--all":
    counts = {}
    for i in order:
        counts[lessons[i].get("event", "?")] = counts.get(lessons[i].get("event", "?"), 0) + 1
    print("status: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    for i in reversed(order):
        print(f"{lessons[i].get('event','?'):<10} {row(i)}")
else:
    if not open_ids:
        print("no open lessons")
    for i in reversed(open_ids):
        print(row(i))
PY
