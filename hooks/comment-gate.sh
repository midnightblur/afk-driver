#!/usr/bin/env bash
# Commit-time comment gate (policy: RATIONALE.md, engine: lib/comment_gate.py).
# Sourced by precommit-gates.sh on agent commits; COMMENT_GATE_DISABLE=1 skips it.

set -u

gate_comment() {
  [ "${COMMENT_GATE_DISABLE:-0}" = "1" ] && return 0
  local dir root py="${AFK_PYTHON:-afk-python}" rc=0 keys=""
  dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
  root=$(cd "$dir/.." && pwd)
  git diff --cached --quiet 2>/dev/null && return 0
  [ "${AFK_CFG_TRACKER:-}" = "jira" ] && keys=${AFK_CFG_JIRA_PROJECT:-}
  gate_metrics_begin
  "$py" "$dir/lib/comment_gate.py" --plugin-root "$root" \
    --tracker "${AFK_CFG_TRACKER:-}" --project-keys "$keys" || rc=$?
  if [ "$rc" -eq 2 ]; then
    gate_metrics_emit comment blocked
    printf '[afk] comment gate blocked. Move the rationale to the change: RATIONALE.md.\n' >&2
    return 2
  fi
  [ "$rc" -ne 0 ] && return "$rc"
  gate_metrics_emit comment pass
  return 0
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
  repo_root=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
  cd "$repo_root" || exit 0
  . "$SCRIPT_DIR/lib/provider.sh"
  . "$SCRIPT_DIR/lib/config.sh"; afk_config_load
  . "$SCRIPT_DIR/gate-metrics.sh"
  gate_comment
fi
