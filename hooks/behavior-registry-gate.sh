#!/usr/bin/env bash
# Plugin-source gate for the managed behavior registry and its transport parity.
# Disable with BEHAVIOR_REGISTRY_GATE_DISABLE=1.

set -u

gate_behavior_registry() {
  [ "${BEHAVIOR_REGISTRY_GATE_DISABLE:-0}" = "1" ] && return 0
  [ "${AFK_IGNORE_GATE_SENTINEL:-0}" = 1 ] || [ ! -f .claude/hooks/.gate-disabled ] || return 0

  local PLUGIN_DIR PLUGIN_SCOPE JUDGE_DIR cache_key py rc=0
  PLUGIN_DIR=$(afk_plugin_dir)
  PLUGIN_SCOPE=$(afk_plugin_scope)
  [ -f "$PLUGIN_DIR/BEHAVIORS.md" ] || return 0

  cache_key=$(gate_cache_key behavior-registry "$PLUGIN_SCOPE*")
  gate_cache_hit behavior-registry "$cache_key" && return 0
  gate_metrics_begin

  py="${AFK_PYTHON:-afk-python}"
  JUDGE_DIR=$(afk_judge_dir 2>/dev/null) || JUDGE_DIR=$PLUGIN_DIR
  "$py" "$JUDGE_DIR/scripts/behavior_registry.py" validate \
    --registry "$PLUGIN_DIR/BEHAVIORS.md" \
    --plugin-root "$PLUGIN_DIR" \
    --dispositions "$PLUGIN_DIR/hooks/behavior-dispositions.tsv" \
    --parity-root "$PLUGIN_DIR" || rc=$?

  if [ "$rc" -ne 0 ]; then
    gate_metrics_emit behavior-registry blocked
    printf '[afk] behavior registry gate blocked.\n' >&2
    return 2
  fi

  gate_cache_store behavior-registry "$cache_key"
  gate_metrics_emit behavior-registry pass
  return 0
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
  repo_root=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
  cd "$repo_root" || exit 0
  . "$SCRIPT_DIR/lib/provider.sh"
  . "$SCRIPT_DIR/lib/config.sh"; afk_config_load
  . "$SCRIPT_DIR/gate-context.sh"; gate_ctx_build
  . "$SCRIPT_DIR/gate-cache.sh"
  . "$SCRIPT_DIR/gate-metrics.sh"
  gate_behavior_registry
fi
