#!/usr/bin/env bash
# hitl-loop.template.sh — human-in-the-loop feedback loop (last resort, per
# SKILL.md Phase 1 method 10). Copy this file, fill in INSTRUCTIONS (and any
# automated capture commands), then run it. Each iteration prints the manual
# steps, waits for the human, records what they observed to a log, and repeats.
# The log is the loop's pass/fail signal — feed it back to the agent.
set -euo pipefail

LOG="${1:-hitl-loop.log}"
ITER=0

INSTRUCTIONS=$(cat <<'EOF'
1. <manual step the human performs, e.g. click X on screen Y>
2. <what to observe, e.g. the error toast / network tab / rendered value>
EOF
)

while true; do
  ITER=$((ITER + 1))
  echo "=== Iteration $ITER ==="
  echo "$INSTRUCTIONS"
  echo
  read -r -p "Press Enter when done (or q to stop): " ANSWER
  [ "${ANSWER:-}" = "q" ] && break
  read -r -p "Paste what you observed: " OBSERVED
  {
    echo "--- iteration $ITER $(date -Iseconds) ---"
    echo "$OBSERVED"
    # Optional: append automated captures too (app log tail, curl probe, …):
    # tail -n 50 /path/to/app.log
  } >>"$LOG"
  echo "Recorded to $LOG"
done

echo "Loop ended after $ITER iteration(s). Feed $LOG back to the agent."
