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
#   lesson-append.sh filed --id L-NNNN --issue <url | queued path> \
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
  opened|applied|verified|rejected|superseded|filed) ;;
  *) bail "unknown or missing event '$EVENT'" ;;
esac

CLASS='' MISS='' TARGET='' SUMMARY='' DRAFT='' SOURCE='' EVIDENCE='' WRITER='' ID='' NOTE='' ISSUE=''
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
    --issue)      ISSUE="${2:-}"; shift 2 ;;
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
else
  [ -n "$ID" ] || bail "$EVENT requires --id"
  [ "$EVENT" != "filed" ] || [ -n "$ISSUE" ] || bail "filed requires --issue"
fi

mkdir -p "$(dirname "$LESSON_LEDGER_FILE")" 2>/dev/null || bail "cannot create ledger dir"

build_line() {
  EV_TS='' EV_ID="$ID" EV_EVENT="$EVENT" \
  EV_WRITER="$WRITER" EV_CLASS="$CLASS" EV_MISS="$MISS" EV_TARGET="$TARGET" \
  EV_SUMMARY="$SUMMARY" EV_DRAFT="$DRAFT" EV_SOURCE="$SOURCE" \
  EV_EVIDENCE="$EVIDENCE" EV_NOTE="$NOTE" EV_ISSUE="$ISSUE" "${AFK_PYTHON:-afk-python}" -c '
import json, os
g = os.environ.get
e = {"ts": g("EV_TS"), "id": g("EV_ID"), "event": g("EV_EVENT"),
     "writer": g("EV_WRITER") or "unknown"}
if e["event"] == "opened":
    e["class"], e["target"], e["summary"] = g("EV_CLASS"), g("EV_TARGET"), g("EV_SUMMARY")
    for key, var in (("draft","EV_DRAFT"),("miss","EV_MISS"),
                     ("source","EV_SOURCE"),("evidence","EV_EVIDENCE")):
        if g(var): e[key] = g(var)
else:
    if e["event"] == "filed":
        e["issue"] = g("EV_ISSUE")
    if g("EV_NOTE"):
        e["note"] = g("EV_NOTE")
# ensure_ascii stays ON: afk-python -c stdout uses the console codepage on Windows,
# so raw non-ASCII here would land as non-UTF-8 bytes in the ledger
print(json.dumps(e, separators=(",", ":")))
' 2>/dev/null
}

# One writer at a time mints and appends, under a folder lock beside the ledger.
# Stale after 10 s and taken over by an atomic mv; a waiter gives up after 30 s.
lock_dir="$(dirname "$LESSON_LEDGER_FILE")/lesson-append.lock"
token="$$.$RANDOM.$RANDOM" held=0 lock_note='' given_id="$ID"

lock_age() {
  local m
  m=$(stat -c %Y "$1" 2>/dev/null) || m=$(stat -f %m "$1" 2>/dev/null) || return 1
  case "$m" in ''|*[!0-9]*) return 1 ;; esac
  echo $(( $(date +%s) - m ))
}

holds_lock() {
  local owner=''
  { read -r owner < "$lock_dir/owner"; } 2>/dev/null
  [ "$owner" = "$token" ]
}

release_lock() {
  [ "$held" = 1 ] || return 0
  held=0
  holds_lock && rm -rf "$lock_dir" 2>/dev/null
  return 0
}

take_stale_lock() {
  local age seen='' moved='' grave="$lock_dir.$token"
  { read -r seen < "$lock_dir/owner"; } 2>/dev/null
  age=$(lock_age "$lock_dir") || return 1
  [ "$age" -ge 10 ] || return 1
  mv "$lock_dir" "$grave" 2>/dev/null || return 1
  { read -r moved < "$grave/owner"; } 2>/dev/null
  # Another waiter took the stale lock first and this mv moved its fresh one: hand it back.
  if [ "$moved" != "$seen" ]; then
    [ -e "$lock_dir" ] || mv "$grave" "$lock_dir" 2>/dev/null
    rm -rf "$grave" 2>/dev/null
    return 1
  fi
  rm -rf "$grave" 2>/dev/null
  return 0
}

acquire_lock() {
  local missing=0 polls=0
  while :; do
    if [ ! -d "$lock_dir" ] && mkdir "$lock_dir" 2>/dev/null; then
      printf '%s\n' "$token" > "$lock_dir/owner" 2>/dev/null && { held=1; return 0; }
      rmdir "$lock_dir" 2>/dev/null
      lock_note="cannot write $lock_dir/owner; nothing written"; return 1
    fi
    if [ -d "$lock_dir" ]; then
      missing=0 polls=$((polls + 1))
      if [ $((polls % 5)) -eq 1 ] && take_stale_lock; then continue; fi
    else
      missing=$((missing + 1))
      [ "$missing" -lt 3 ] || { lock_note="cannot create $lock_dir; nothing written"; return 1; }
      continue
    fi
    [ $((SECONDS - start)) -lt 30 ] \
      || { lock_note="gave up after 30 s waiting for $lock_dir; nothing written"; return 1; }
    sleep 0.2
  done
}

trap release_lock EXIT
trap 'release_lock; exit 129' HUP
trap 'release_lock; exit 130' INT
trap 'release_lock; exit 143' TERM
# The line carries "ts":"" and, to mint, "id":"" until the lock is held; the append fills both in.
line=$(build_line) || bail "json build failed (afk-python not found; run /afk:setup)"
start=$SECONDS
while :; do
  acquire_lock || bail "$lock_note"
  if [ -z "$given_id" ]; then
    max=$(awk '{ s = $0; while (match(s, /"id":"L-[0-9]+"/)) {
                   n = substr(s, RSTART + 8, RLENGTH - 9) + 0; if (n > m) m = n
                   s = substr(s, RSTART + RLENGTH) } } END { print m + 0 }' \
            "$LESSON_LEDGER_FILE" 2>/dev/null)
    printf -v ID 'L-%04d' $(( 10#${max:-0} + 1 ))
  fi
  stamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  # A holder slower than the stale test lost its lock: take it again, mint again.
  holds_lock && break
  held=0
done

line=${line/\"ts\":\"\"/\"ts\":\"$stamp\"}
printf '%s\n' "${line/\"id\":\"\"/\"id\":\"$ID\"}" >> "$LESSON_LEDGER_FILE" 2>/dev/null \
  || bail "append failed"
release_lock
echo "$ID"
