#!/usr/bin/env bash
# Shared latency-metrics emitter for the harness gates. Source it and call
# gate_metrics_begin once the gate has decided it must do real work (never on
# a scope-check no-op — skips would drown the signal), then gate_metrics_emit
# on every exit path that follows.
#
# Emits one JSONL line per gate run to <git common dir>/afk/metrics/gate-latency.jsonl,
# one file for every worktree of the gated repo (GATE_METRICS_FILE overrides):
#   {"ts":"2026-07-07T12:34:56Z","gate":"maven-compile","result":"pass","duration_ms":45210,...}
# result: pass | blocked (Stop gates) or ok | code_failure | env_failure | timeout (app-start).
# Extra fields (lock_wait_ms, detail, module, ...) are passed as a raw JSON fragment.
#
# Emission must never break a gate: every write is best-effort (|| true).
# Outside a repository, with no override, nothing is written.
# Summarize with gate-metrics-report.sh. Disable with GATE_METRICS_DISABLE=1.

GATE_METRICS_FILE="${GATE_METRICS_FILE:-}"

# gate_metrics_file — set _GATE_METRICS_PATH; false when there is nowhere to write.
gate_metrics_file() {
  _GATE_METRICS_PATH=$GATE_METRICS_FILE
  [ -n "$_GATE_METRICS_PATH" ] && return 0
  if ! declare -F gate_ctx_gitdirs >/dev/null; then
    local d=${BASH_SOURCE[0]%/*}
    [ "$d" = "${BASH_SOURCE[0]}" ] && d=.
    . "$d/gate-context.sh"
  fi
  gate_ctx_gitdirs
  [ -n "${AFK_CTX_COMMON_DIR:-}" ] || return 1
  _GATE_METRICS_PATH="$AFK_CTX_COMMON_DIR/afk/metrics/gate-latency.jsonl"
}

gate_metrics_now_ms() {
  local t
  t=$(date +%s%3N 2>/dev/null)
  case "$t" in
    ''|*[!0-9]*) echo $(( $(date +%s) * 1000 )) ;;  # non-GNU date: %N unsupported
    *) echo "$t" ;;
  esac
}

gate_metrics_begin() { GATE_METRICS_T0=$(gate_metrics_now_ms); }

# gate_metrics_emit <gate> <result> [extra-json-fields e.g. '"lock_wait_ms":120,"detail":"the module"']
gate_metrics_emit() {
  [ "${GATE_METRICS_DISABLE:-0}" = "1" ] && return 0
  [ -n "${GATE_METRICS_T0:-}" ] || return 0
  local dur extra
  dur=$(( $(gate_metrics_now_ms) - GATE_METRICS_T0 ))
  extra=${3:+,$3}
  gate_metrics_file || return 0
  case "$_GATE_METRICS_PATH" in
    */*) [ -d "${_GATE_METRICS_PATH%/*}" ] || mkdir -p "${_GATE_METRICS_PATH%/*}" 2>/dev/null || return 0 ;;
  esac
  printf '{"ts":"%s","gate":"%s","result":"%s","duration_ms":%s%s}\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" "$2" "$dur" "$extra" \
    >> "$_GATE_METRICS_PATH" 2>/dev/null || true
}
