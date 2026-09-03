#!/usr/bin/env bash
# Summarize the gate-latency metrics emitted by gate-metrics.sh.
# Per gate: runs, blocked/failed count, p50 and p95 duration (wall-clock the
# agent actually waited). Read this before optimizing any gate — the budget
# decision is data-driven, not vibes-driven (see hooks/README.md "Latency
# metrics & budget").
#
# Usage (from the gated repo root):
#   bash "$AFK_PLUGIN_ROOT/hooks/gate-metrics-report.sh" [metrics-file]
# Default metrics file: .claude/metrics/gate-latency.jsonl

set -u

file=${1:-.claude/metrics/gate-latency.jsonl}
[ -f "$file" ] || { echo "no metrics yet: $file" >&2; exit 0; }

# Extract "gate result duration_ms" per line, sort by gate then duration,
# then compute per-gate percentiles in one awk pass over the grouped stream.
sed -nE 's/.*"gate":"([^"]+)".*"result":"([^"]+)".*"duration_ms":([0-9]+).*/\1 \2 \3/p' "$file" \
  | sort -k1,1 -k3,3n \
  | awk '
    function flush() {
      if (n == 0) return
      p50 = v[int((n - 1) * 0.50) + 1]
      p95 = v[int((n - 1) * 0.95) + 1]
      printf "%-16s runs=%-5d red=%-4d p50=%.1fs p95=%.1fs max=%.1fs\n", g, n, red, p50/1000, p95/1000, v[n]/1000
    }
    $1 != g { flush(); g = $1; n = 0; red = 0; delete v }
    { v[++n] = $3; if ($2 != "pass" && $2 != "ok") red++ }
    END { flush() }
  '
