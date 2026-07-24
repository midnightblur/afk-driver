#!/usr/bin/env bash
# Stop hook (ships with the afk plugin): codex-drift gate — the generated
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

[ "${CODEX_DRIFT_GATE_DISABLE:-0}" = "1" ] && exit 0

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

repo_root=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
cd "$repo_root" || exit 0

[ -f .claude/hooks/.gate-disabled ] && exit 0

GENERATOR="tools/payable/ai-agents/codex-sync/generate.py"
[ -f "$GENERATOR" ] || exit 0   # not this plugin's checkout

# ---- scope: canonical sources + generated trees, vs upstream + worktree + untracked
upstream=$(git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null || true)
[ -z "$upstream" ] && git rev-parse --verify -q origin/master >/dev/null 2>&1 && upstream=origin/master
[ -z "$upstream" ] && upstream=HEAD

base=$(git merge-base "$upstream" HEAD 2>/dev/null || echo HEAD)

scope_paths=(
  "tools/payable/ai-agents/plugins/workflow/skills"
  "tools/payable/ai-agents/plugins/workflow/agents"
  "tools/payable/ai-agents/plugins/workflow/hooks"
  "tools/payable/ai-agents/plugins/workflow/.claude-plugin"
  "tools/payable/ai-agents/harness/hooks"
  "tools/payable/ai-agents/harness/.claude-plugin"
  "tools/payable/ai-agents/codex-sync"
  ".claude/skills"
  ".agents"
  ".codex"
)

changed=$(
  { git diff --name-only "$base" -- "${scope_paths[@]}" 2>/dev/null
    git ls-files --others --exclude-standard -- "${scope_paths[@]}" 2>/dev/null
  } | head -1
)
[ -z "$changed" ] && exit 0   # scope no-op

. "$SCRIPT_DIR/gate-cache.sh"
cache_key=$(gate_cache_key codex-drift)
gate_cache_hit codex-drift "$cache_key" && exit 0

. "$SCRIPT_DIR/gate-metrics.sh"
gate_metrics_begin

py=python
command -v python >/dev/null 2>&1 || py=python3
command -v "$py" >/dev/null 2>&1 || exit 0   # no python — cannot check, fail open

if ! out=$("$py" "$GENERATOR" --check 2>&1); then
  gate_metrics_emit codex-drift blocked
  {
    echo "Codex-drift gate: generated Codex layer is out of sync with its canonical sources."
    printf '%s\n' "$out"
    echo
    echo "Fix: python $GENERATOR   (then commit the regenerated artifacts with your change)"
  } >&2
  exit 2
fi

gate_metrics_emit codex-drift pass
gate_cache_store codex-drift "$cache_key"
exit 0
