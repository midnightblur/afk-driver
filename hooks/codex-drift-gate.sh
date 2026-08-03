#!/usr/bin/env bash
# Stop gate (ships with the afk plugin): codex-drift gate — the generated
# OpenAI Codex layer (.agents/skills, .codex, harness provider.sh sync,
# AGENTS.md block, config-fragment.toml) must stay in sync with its canonical
# sources (plugin skills/agents/hooks, project skills, root CLAUDE.md).
#
# Fast path: no changed file intersects the canonical-source or generated
# globs -> silent pass without ever starting Python. Otherwise runs
#   python tools/payable/ai-agents/codex-sync/generate.py --check
# and blocks (exit 2) on drift, printing the regenerate command.
#
# Disable: CODEX_DRIFT_GATE_DISABLE=1, or repo file .claude/hooks/.gate-disabled.

set -u

gate_codex_drift() {
  [ "${CODEX_DRIFT_GATE_DISABLE:-0}" = "1" ] && return 0
  [ -f .claude/hooks/.gate-disabled ] && return 0

  local GENERATOR="tools/payable/ai-agents/codex-sync/generate.py"
  [ -f "$GENERATOR" ] || return 0   # not this plugin's checkout

  # ---- scope: canonical sources + generated trees. Worktree/untracked changes
  # come from the shared context (fork-free); committed-but-unpushed needs a diff.
  local PLUGIN_DIR="tools/payable/ai-agents/plugins/workflow"
  local -a scope_paths=(
    "$PLUGIN_DIR/skills" "$PLUGIN_DIR/agents" "$PLUGIN_DIR/hooks" "$PLUGIN_DIR/.claude-plugin"
    "tools/payable/ai-agents/harness/hooks" "tools/payable/ai-agents/harness/.claude-plugin"
    "tools/payable/ai-agents/codex-sync" ".claude/skills" ".agents" ".codex"
  )
  local changed=""
  gate_ctx_any AFK_CTX_CHANGED \
    "$PLUGIN_DIR/skills/*" "$PLUGIN_DIR/agents/*" "$PLUGIN_DIR/hooks/*" \
    "$PLUGIN_DIR/.claude-plugin/*" "tools/payable/ai-agents/harness/hooks/*" \
    "tools/payable/ai-agents/harness/.claude-plugin/*" "tools/payable/ai-agents/codex-sync/*" \
    ".claude/skills/*" ".agents/*" ".codex/*" && changed=1
  if [ -z "$changed" ]; then
    gate_ctx_mergebase
    changed=$(git diff --name-only "$AFK_CTX_MERGEBASE" -- "${scope_paths[@]}" 2>/dev/null | head -1)
  fi
  [ -z "$changed" ] && return 0   # scope no-op

  # Inputs are exactly the canonical sources and generated trees above.
  local cache_key
  cache_key=$(gate_cache_key codex-drift \
    "$PLUGIN_DIR/skills/*" "$PLUGIN_DIR/agents/*" "$PLUGIN_DIR/hooks/*" \
    "$PLUGIN_DIR/.claude-plugin/*" "tools/payable/ai-agents/harness/hooks/*" \
    "tools/payable/ai-agents/harness/.claude-plugin/*" "tools/payable/ai-agents/codex-sync/*" \
    ".claude/skills/*" ".agents/*" ".codex/*" "CLAUDE.md" "AGENTS.md")
  gate_cache_hit codex-drift "$cache_key" && return 0

  gate_metrics_begin

  local py=python out
  command -v python >/dev/null 2>&1 || py=python3
  command -v "$py" >/dev/null 2>&1 || return 0   # no python — cannot check, fail open

  if ! out=$("$py" "$GENERATOR" --check 2>&1); then
    gate_metrics_emit codex-drift blocked
    {
      echo "Codex-drift gate: generated Codex layer is out of sync with its canonical sources."
      printf '%s\n' "$out"
      echo
      echo "Fix: python $GENERATOR   (root mirror is gitignored per-machine; commit only config-fragment.toml / provider.sh sync if they changed)"
    } >&2
    return 2
  fi

  gate_metrics_emit codex-drift pass
  gate_cache_store codex-drift "$cache_key"
  return 0
}

# ---- standalone invocation
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  _d=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
  _root=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
  cd "$_root" || exit 0
  . "$_d/gate-context.sh"; gate_ctx_build
  . "$_d/gate-cache.sh"
  . "$_d/gate-metrics.sh"
  gate_codex_drift; exit $?
fi
