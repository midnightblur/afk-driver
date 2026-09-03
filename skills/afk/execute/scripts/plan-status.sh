#!/usr/bin/env bash
# plan-status.sh — single-writer helper for /afk-toolkit:execute: sets ONE subtask row's
# Status cell in PLAN.md's `## Progress tracker` table and stamps the header
# `> Last updated:` date with today, preserving every other byte of the file.
# Table shape owned by skills/afk/to-subtasks/PLAN-TEMPLATE.md; the allowed
# status set is owned by skills/afk/execute/SKILL.md (progress-tracker status
# column) — a change there is a lockstep change here.
#
# Usage: plan-status.sh <plan-dir> <NNNN-slug> <status>
#
#   <plan-dir>    dir containing PLAN.md (e.g. …/{TICKET-ID}/plan)
#   <NNNN-slug>   the subtask id — its Subtask-column cell value
#   <status>      pending | designing | developing | verifying | reviewing |
#                 done | blocked(<reason>)   (quote statuses with spaces)
#
# Touches nothing outside the matched row's Status cell + the first
# `> Last updated:` line (date token or {YYYY-MM-DD} placeholder replaced).
# Other tables carrying a Status column (feature smoke gate) are never touched
# — only the table under the `## Progress tracker` heading is scanned.
#
#   EXIT_OK=0          row updated + date stamped
#   EXIT_NO_ROW=1      no row for <NNNN-slug> in the progress tracker
#   EXIT_NO_TABLE=2    PLAN.md or its progress-tracker table not found (also bad usage)
#   EXIT_BAD_STATUS=3  <status> not in the allowed set
set -u

EXIT_OK=0
EXIT_NO_ROW=1
EXIT_NO_TABLE=2
EXIT_BAD_STATUS=3

usage() {
  echo "usage: plan-status.sh <plan-dir> <NNNN-slug> <status>" >&2
}

if [ "$#" -ne 3 ]; then
  usage
  exit "$EXIT_NO_TABLE"
fi

PLAN_DIR="$1"
SLUG="$2"
STATUS="$3"

# status gate first — refuse before touching anything
case "$STATUS" in
  pending|designing|developing|verifying|reviewing|done) ;;
  "blocked("?*")") ;;
  *)
    echo "plan-status: status '${STATUS}' not in allowed set (pending|designing|developing|verifying|reviewing|done|blocked(<reason>) — skills/afk/execute/SKILL.md)" >&2
    exit "$EXIT_BAD_STATUS" ;;
esac

PLAN="${PLAN_DIR%/}/PLAN.md"
if [ ! -f "$PLAN" ]; then
  echo "plan-status: ${PLAN} not found" >&2
  exit "$EXIT_NO_TABLE"
fi

TODAY="$(date +%F)"
TMP="$(mktemp 2>/dev/null || mktemp -t plan-status)"

awk -v SLUG="$SLUG" -v STATUS="$STATUS" -v TODAY="$TODAY" '
BEGIN { in_pt = 0; header_seen = 0; status_col = 0; sub_col = 0; table = 0; row_done = 0; stamped = 0 }
{
  line = $0

  # header date stamp — first `> Last updated:` line only
  if (!stamped && line ~ /^> Last updated:/) {
    if (sub(/[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]/, TODAY, line)) stamped = 1
    else if (sub(/\{YYYY-MM-DD\}/, TODAY, line)) stamped = 1
    print line; next
  }

  if (line ~ /^## Progress tracker/) { in_pt = 1; print line; next }
  if (in_pt && line ~ /^## /) { in_pt = 0 }

  if (in_pt && line ~ /^\|/) {
    n = split(line, a, "|")
    if (!header_seen) {
      for (i = 1; i <= n; i++) {
        c = a[i]; gsub(/^[ \t]+/, "", c); gsub(/[ \t\r]+$/, "", c)
        if (c == "Status") status_col = i
        if (c == "Subtask") sub_col = i
      }
      if (status_col && sub_col) { header_seen = 1; table = 1 }
      print line; next
    }
    if (!row_done) {
      c = a[sub_col]; gsub(/^[ \t]+/, "", c); gsub(/[ \t\r]+$/, "", c)
      if (c == SLUG) {
        a[status_col] = " " STATUS " "
        out = a[1]
        for (i = 2; i <= n; i++) out = out "|" a[i]
        line = out
        row_done = 1
      }
    }
  }
  print line
}
END {
  if (!table) exit 2
  if (!row_done) exit 1
}
' "$PLAN" > "$TMP"
rc=$?

if [ "$rc" -ne 0 ]; then
  rm -f "$TMP"
  if [ "$rc" -eq 2 ]; then
    echo "plan-status: no ## Progress tracker table in ${PLAN}" >&2
    exit "$EXIT_NO_TABLE"
  fi
  echo "plan-status: no row for '${SLUG}' in the progress tracker of ${PLAN}" >&2
  exit "$EXIT_NO_ROW"
fi

mv "$TMP" "$PLAN"
echo "plan-status: ${SLUG} -> ${STATUS} (Last updated ${TODAY})"
exit "$EXIT_OK"
