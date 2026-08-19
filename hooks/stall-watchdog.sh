#!/usr/bin/env bash
# Stall watchdog (ships with the afk plugin): the orchestrator's wake-up for a
# hung child. Only completion re-invokes a waiting orchestrator — a child that
# hangs never completes, so a time cap held in prose cannot fire. Run this
# script in a BACKGROUND shell in the same message as the spawn; its exit is
# the wake-up. When to arm and the fire/park protocol: DELEGATION.md
# "Stall watchdog" (plugin root).
#
# NOT a Stop hook. Invoked on demand:
#   bash .../stall-watchdog.sh --path <p> [--path <p>]... \
#        [--stale-min N] [--cap-min M] [--poll-sec S] [--label <text>]
#
# Polls the --path set (files or dirs, recursive; a path may not exist yet)
# for anything modified since the last observed activity. The watchdog's own
# start counts as activity, so a slow-starting child gets one full stale
# window. Point it at paths the child's work actually touches — the worktree's
# .git dir (stages, commits, ref updates), the plan dir (journal, tracker),
# the module's build output dir, the evidence/scratch dir — never a whole
# worktree root (a fully-stale poll walks every file under each path).
#
# Exit codes (prints one STALL-WATCHDOG line first):
#   2 = usage error
#   3 = stale — nothing under the watched paths changed for --stale-min
#       (default 20) minutes
#   4 = cap — total runtime reached --cap-min (default 90) minutes with the
#       child still active
# It never exits 0: on the child's normal completion, disarm by killing this
# background task; a fire that lands for an already-completed child is a no-op.
set -u

STALE_MIN=20 CAP_MIN=90 POLL_SEC=60 LABEL=''
PATHS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --path)      PATHS+=("${2:-}"); shift 2 ;;
    --stale-min) STALE_MIN="${2:-20}"; shift 2 ;;
    --cap-min)   CAP_MIN="${2:-90}"; shift 2 ;;
    --poll-sec)  POLL_SEC="${2:-60}"; shift 2 ;;
    --label)     LABEL="${2:-}"; shift 2 ;;
    *) echo "stall-watchdog: unknown arg '$1'" >&2; exit 2 ;;
  esac
done
[ ${#PATHS[@]} -gt 0 ] || { echo "stall-watchdog: at least one --path required" >&2; exit 2; }

start=$(date +%s)
last_active=$start
stamp=$(mktemp "${TMPDIR:-/tmp}/stall-watchdog-XXXXXX.stamp")
trap 'rm -f "$stamp"' EXIT

while :; do
  sleep "$POLL_SEC"
  now=$(date +%s)
  if [ $(( now - start )) -ge $(( CAP_MIN * 60 )) ]; then
    echo "STALL-WATCHDOG: cap — child still running after ${CAP_MIN} min${LABEL:+ ($LABEL)}"
    exit 4
  fi
  # One find per poll, short-circuiting on the first file newer than the last
  # observed activity (subprocess count is the cost model, hooks/README.md).
  touch -d "@$last_active" "$stamp" 2>/dev/null || touch "$stamp"
  hit=$(find "${PATHS[@]}" -newer "$stamp" -print -quit 2>/dev/null)
  if [ -n "$hit" ]; then
    last_active=$now
  elif [ $(( now - last_active )) -ge $(( STALE_MIN * 60 )) ]; then
    echo "STALL-WATCHDOG: stale — no change under watched paths for ${STALE_MIN} min${LABEL:+ ($LABEL)}"
    exit 3
  fi
done
