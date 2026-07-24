#!/usr/bin/env bash
# Append one event to the workflow lesson ledger — the grammar's ONLY emitting
# site (format, class enum, resolution rule: skills/afk/lessons/LEDGER-FORMAT.md;
# lockstep with lesson-digest.sh, the only parsing site).
#
# Usage (run from anywhere inside the target repo):
#   lesson-append.sh opened  --class <c> --target <path> --summary <s> \
#       [--draft <text> | --draft-file <f>] [--miss <m>] [--source <id>] \
#       [--evidence <path:line>] [--writer <skill>] [--id L-NNNN]
#   lesson-append.sh <applied|verified|rejected|superseded> --id L-NNNN \
#       [--note <n>] [--writer <skill>]
#
# Prints the event's id on success. Best-effort: ALWAYS exits 0 — a failed
# append is a stderr note, never a reason to block the capturing task.
# LESSON_LEDGER_DISABLE=1 silences; LESSON_LEDGER_FILE relocates the ledger
# (default: <main-checkout>/.claude/lessons/LEDGER.jsonl).
set -uo pipefail

[ "${LESSON_LEDGER_DISABLE:-0}" = "1" ] && exit 0

bail() { echo "lesson-append: $*" >&2; exit 0; }

EVENT="${1:-}"; shift 2>/dev/null || true
case "$EVENT" in
  opened|applied|verified|rejected|superseded) ;;
  *) bail "unknown or missing event '$EVENT'" ;;
esac

CLASS='' MISS='' TARGET='' SUMMARY='' DRAFT='' SOURCE='' EVIDENCE='' WRITER='' ID='' NOTE=''
while [ $# -gt 0 ]; do
  case "$1" in
    --class)      CLASS="${2:-}"; shift 2 ;;
    --miss)       MISS="${2:-}"; shift 2 ;;
    --target)     TARGET="${2:-}"; shift 2 ;;
    --summary)    SUMMARY="${2:-}"; shift 2 ;;
    --draft)      DRAFT="${2:-}"; shift 2 ;;
    --draft-file) DRAFT="$(cat "${2:-/dev/null}" 2>/dev/null || true)"; shift 2 ;;
    --source)     SOURCE="${2:-}"; shift 2 ;;
    --evidence)   EVIDENCE="${2:-}"; shift 2 ;;
    --writer)     WRITER="${2:-}"; shift 2 ;;
    --id)         ID="${2:-}"; shift 2 ;;
    --note)       NOTE="${2:-}"; shift 2 ;;
    *) bail "unknown arg '$1'" ;;
  esac
done

if [ -z "${LESSON_LEDGER_FILE:-}" ]; then
  common=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null) \
    || bail "not inside a git repo and LESSON_LEDGER_FILE unset"
  LESSON_LEDGER_FILE="$(dirname "$common")/.claude/lessons/LEDGER.jsonl"
fi

if [ "$EVENT" = "opened" ]; then
  [ -n "$CLASS" ] && [ -n "$TARGET" ] && [ -n "$SUMMARY" ] \
    || bail "opened requires --class, --target, --summary"
  case "$CLASS" in
    missed-instruction|missing-instruction|wrong-term|weak-checklist|test-dodge|wrong-design) ;;
    *) bail "unknown class '$CLASS' (enum: skills/afk/lessons/LEDGER-FORMAT.md)" ;;
  esac
  if [ -z "$ID" ]; then
    max=$(grep -oE '"id":"L-[0-9]+"' "$LESSON_LEDGER_FILE" 2>/dev/null \
            | grep -oE '[0-9]+' | sort -n | tail -1)
    ID=$(printf 'L-%04d' $(( 10#${max:-0} + 1 )))
  fi
else
  [ -n "$ID" ] || bail "$EVENT requires --id"
fi

mkdir -p "$(dirname "$LESSON_LEDGER_FILE")" 2>/dev/null || bail "cannot create ledger dir"

line=$(EV_TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)" EV_ID="$ID" EV_EVENT="$EVENT" \
  EV_WRITER="$WRITER" EV_CLASS="$CLASS" EV_MISS="$MISS" EV_TARGET="$TARGET" \
  EV_SUMMARY="$SUMMARY" EV_DRAFT="$DRAFT" EV_SOURCE="$SOURCE" \
  EV_EVIDENCE="$EVIDENCE" EV_NOTE="$NOTE" python -c '
import json, os
g = os.environ.get
e = {"ts": g("EV_TS"), "id": g("EV_ID"), "event": g("EV_EVENT"),
     "writer": g("EV_WRITER") or "unknown"}
if e["event"] == "opened":
    e["class"], e["target"], e["summary"] = g("EV_CLASS"), g("EV_TARGET"), g("EV_SUMMARY")
    for key, var in (("draft","EV_DRAFT"),("miss","EV_MISS"),
                     ("source","EV_SOURCE"),("evidence","EV_EVIDENCE")):
        if g(var): e[key] = g(var)
elif g("EV_NOTE"):
    e["note"] = g("EV_NOTE")
# ensure_ascii stays ON: python -c stdout uses the console codepage on Windows,
# so raw non-ASCII here would land as non-UTF-8 bytes in the ledger
print(json.dumps(e, separators=(",", ":")))
' 2>/dev/null) || bail "json build failed (python unavailable?)"

printf '%s\n' "$line" >> "$LESSON_LEDGER_FILE" 2>/dev/null || bail "append failed"
echo "$ID"
