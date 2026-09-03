#!/usr/bin/env bash
# ci-wait.sh — CI-babysit background poll, bundled with the /afk-toolkit:preflight
# skill (PF-6/PF-7). Design ADR: adr/design/0005-ci-babysit-background-poll.md
# in the feature that specified it; the exit-code contract below is the
# frozen public interface (see SKILL.md PF-6/PF-7) — any change here is a
# lockstep change with SKILL.md.
#
# Usage: ci-wait.sh <mr-ref> <budget-seconds> <interval-seconds> [repo]
#
#   <mr-ref>            branch name or MR IID `glab mr view` accepts
#   <budget-seconds>     wall-clock budget before giving up (SDD default: 5400 = 90 min)
#   <interval-seconds>   poll cadence (SDD default: 180 = 3 min)
#   [repo]                optional `OWNER/GROUP/REPO` passed to `glab -R`
#
# Loops `glab mr view <mr-ref> -F json`, reading `.head_pipeline.status` (or
# `.pipeline.status` as a fallback field name), until a terminal pipeline
# state or the budget elapses. Launched as a background Bash task by
# /afk-toolkit:preflight PF-6; the caller session resumes on task completion and
# routes on this exit code (PF-7).
#
# `EXIT_BUDGET_EXHAUSTED` is this script's `## Produces` anchor: the
# exit-envelope carrier read by /afk-toolkit:preflight PF-7 and by the SKILL.md
# doc that mirrors this table.
#   EXIT_OK=0                 pipeline reached "success"
#   EXIT_RED=1                pipeline reached "failed" or "canceled"
#   EXIT_BUDGET_EXHAUSTED=2   budget elapsed, pipeline still non-terminal (park != cancel — it keeps running)
#   EXIT_FLAKE=3              pipeline unreadable — 3 consecutive glab read errors, or no
#                             usable Python 3 (auth/network/env fault — never a fix cycle)
set -u

EXIT_OK=0
EXIT_RED=1
EXIT_BUDGET_EXHAUSTED=2
EXIT_FLAKE=3

usage() {
  echo "usage: ci-wait.sh <mr-ref> <budget-seconds> <interval-seconds> [repo]" >&2
}

if [ "$#" -lt 3 ]; then
  usage
  exit "$EXIT_FLAKE"
fi

MR_REF="$1"
BUDGET="$2"
INTERVAL="$3"
REPO="${4:-}"

repo_flag=()
if [ -n "$REPO" ]; then
  repo_flag=(-R "$REPO")
fi

# Resolve a working Python 3 ONCE, by *executing* each candidate rather than
# trusting `command -v`: on Windows `python3` is normally the Microsoft Store
# stub, which is on PATH, prints its nag to stderr, and emits nothing on stdout
# — indistinguishable from a glab read failure, so every poll counted as an
# error and the run false-parked EXIT_FLAKE after 3 intervals. Execution
# probing also rejects a `python` that is really Python 2. Candidate set and
# the stub caveat mirror the dependency register (skills/afk/setup/MANIFEST.md
# P1 / H6).
PY=()
resolve_python() {
  local candidate
  for candidate in "python3" "python" "py -3"; do
    if [ "$($candidate -c 'print("afk")' 2>/dev/null)" = "afk" ]; then
      PY=($candidate)
      return 0
    fi
  done
  return 1
}

if ! resolve_python; then
  echo "ci-wait: no working Python 3 on PATH (tried: python3, python, py -3) — park (environment fault, no fix cycle spent; see skills/afk/setup/MANIFEST.md P1)" >&2
  exit "$EXIT_FLAKE"
fi

# Reads the pipeline status for MR_REF via glab, one attempt. Prints the
# GitLab pipeline status string ("success" | "failed" | "canceled" |
# "running" | "pending" | "created" | "manual" | "skipped") or nothing on
# any read/parse failure — the caller counts empty reads as flakes.
read_status() {
  glab mr view "$MR_REF" "${repo_flag[@]}" -F json 2>/dev/null \
    | "${PY[@]}" -c '
import json
import sys

try:
    doc = json.load(sys.stdin)
    pipeline = doc.get("head_pipeline") or doc.get("pipeline") or {}
    print(pipeline.get("status", ""))
except Exception:
    print("")
'
}

consecutive_errors=0
elapsed=0

while [ "$elapsed" -lt "$BUDGET" ]; do
  status="$(read_status)"

  if [ -z "$status" ]; then
    consecutive_errors=$((consecutive_errors + 1))
    if [ "$consecutive_errors" -ge 3 ]; then
      echo "ci-wait: 3 consecutive glab read errors on '${MR_REF}' — park (auth/network flake, no fix cycle spent)" >&2
      exit "$EXIT_FLAKE"
    fi
  else
    consecutive_errors=0
    case "$status" in
      success)
        echo "ci-wait: pipeline success on '${MR_REF}' after ${elapsed}s"
        exit "$EXIT_OK"
        ;;
      failed | canceled)
        echo "ci-wait: pipeline ${status} on '${MR_REF}' after ${elapsed}s" >&2
        exit "$EXIT_RED"
        ;;
      *)
        : # running / pending / created / manual / skipped — not terminal, keep waiting
        ;;
    esac
  fi

  sleep "$INTERVAL"
  elapsed=$((elapsed + INTERVAL))
done

echo "ci-wait: budget (${BUDGET}s) exhausted on '${MR_REF}', pipeline still running — park (pipeline keeps running; resume re-reads live status first)" >&2
exit "$EXIT_BUDGET_EXHAUSTED"
