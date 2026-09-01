#!/usr/bin/env bash
# Provider detection and native hook-envelope smoke tests.

set -uo pipefail

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
workflow=$(cd "$here/../.." && pwd)
repo=$(git -C "$workflow" rev-parse --show-toplevel)
envelopes="$here/envelopes"
shim="$workflow/hooks/lib/provider.sh"
guard="$repo/tools/payable/ai-agents/harness/hooks/crowdstrike-guard.sh"
counter="$repo/tools/payable/ai-agents/harness/hooks/explore-counter.sh"
lavish="$workflow/hooks/lavish-dark.sh"
lavish_tips="$workflow/hooks/lavish-tips.sh"

command -v jq >/dev/null 2>&1 || { echo "SKIP: jq not on PATH" >&2; exit 0; }

fails=0
pass() { echo "  ok: $1"; }
fail() { echo "  FAIL: $1" >&2; fails=$((fails + 1)); }

detect() {
  env AFK_PROVIDER="${AFK_PROVIDER_CASE:-}" \
      PLUGIN_ROOT="${PLUGIN_ROOT_CASE:-}" PLUGIN_DATA="${PLUGIN_DATA_CASE:-}" \
      CLAUDE_PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT_CASE:-}" \
      CLAUDE_PLUGIN_DATA="${CLAUDE_PLUGIN_DATA_CASE:-}" \
      CLAUDECODE="${CLAUDECODE_CASE:-}" \
      bash -c '. "$1"; afk_provider' _ "$shim"
}

assert_detect() {
  local label=$1 expected=$2 actual
  actual=$(detect)
  if [ "$actual" = "$expected" ]; then
    pass "$label"
  else
    fail "$label (expected=$expected actual=$actual)"
  fi
}

AFK_PROVIDER_CASE=claude PLUGIN_ROOT_CASE=/codex CLAUDECODE_CASE=1 \
  assert_detect "AFK_PROVIDER override wins" claude
AFK_PROVIDER_CASE= PLUGIN_ROOT_CASE=/codex CLAUDE_PLUGIN_ROOT_CASE=/compat CLAUDECODE_CASE=1 \
  assert_detect "PLUGIN_ROOT wins over inherited CLAUDECODE" codex
AFK_PROVIDER_CASE= PLUGIN_ROOT_CASE= CLAUDE_PLUGIN_ROOT_CASE=/claude CLAUDECODE_CASE= \
  assert_detect "CLAUDE_PLUGIN_ROOT detects Claude" claude
AFK_PROVIDER_CASE= PLUGIN_ROOT_CASE= CLAUDE_PLUGIN_ROOT_CASE= CLAUDECODE_CASE=1 \
  assert_detect "CLAUDECODE fallback detects Claude" claude
AFK_PROVIDER_CASE= PLUGIN_ROOT_CASE= CLAUDE_PLUGIN_ROOT_CASE= CLAUDECODE_CASE= \
  assert_detect "no marker is unknown" unknown

actual=$(PLUGIN_ROOT=/codex-root PLUGIN_DATA=/codex-data \
  CLAUDE_PLUGIN_ROOT=/compat-root CLAUDE_PLUGIN_DATA=/compat-data CLAUDECODE=1 \
  bash -c '. "$1"; printf "%s|%s" "$(afk_plugin_root)" "$(afk_plugin_data)"' _ "$shim")
if [ "$actual" = "/codex-root|/codex-data" ]; then
  pass "Codex prefers native root and data variables"
else
  fail "Codex root/data precedence (actual=$actual)"
fi

actual=$(PLUGIN_ROOT= PLUGIN_DATA= CLAUDE_PLUGIN_ROOT=/claude-root \
  CLAUDE_PLUGIN_DATA=/claude-data CLAUDECODE=1 \
  bash -c '. "$1"; printf "%s|%s" "$(afk_plugin_root)" "$(afk_plugin_data)"' _ "$shim")
if [ "$actual" = "/claude-root|/claude-data" ]; then
  pass "Claude uses compatibility root and data variables"
else
  fail "Claude root/data precedence (actual=$actual)"
fi

run_hook() {
  local script=$1 fixture=$2 provider=$3 data=$4
  if [ "$provider" = codex ]; then
    out=$(AFK_PROVIDER= PLUGIN_ROOT="$workflow" PLUGIN_DATA="$data" \
          CLAUDE_PLUGIN_ROOT="$workflow" CLAUDE_PLUGIN_DATA="$data" CLAUDECODE=1 \
          CLAUDE_PROJECT_DIR="$repo" bash "$script" < "$fixture" 2>/dev/null)
  else
    out=$(AFK_PROVIDER= PLUGIN_ROOT= PLUGIN_DATA= \
          CLAUDE_PLUGIN_ROOT="$workflow" CLAUDE_PLUGIN_DATA="$data" CLAUDECODE=1 \
          CLAUDE_PROJECT_DIR="$repo" bash "$script" < "$fixture" 2>/dev/null)
  fi
  rc=$?
}

for adapter in "$workflow"/hooks/lib/providers/*.sh; do
  provider=${adapter##*/}
  provider=${provider%.sh}
  provider_envelopes="$envelopes/$provider"
  echo "== provider: $provider =="

  for event in session-start pretooluse-bash-safe stop; do
    fixture="$provider_envelopes/$event.json"
    parsed=$(AFK_PROVIDER="$provider" bash -c \
      '. "$1"; afk_hook_input; printf "%s" "$(afk_hook_field hook_event_name)"' \
      _ "$shim" < "$fixture")
    case "$event:$parsed" in
      session-start:SessionStart|pretooluse-bash-safe:PreToolUse|stop:Stop)
        pass "$event envelope parses" ;;
      *) fail "$event envelope parse (actual=$parsed)" ;;
    esac
  done

  data_dir=$(mktemp -d)
  run_hook "$guard" "$provider_envelopes/pretooluse-bash-danger.json" "$provider" "$data_dir"
  if [ "$rc" = 0 ] && printf '%s' "$out" | jq -e \
      '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null; then
    pass "crowdstrike-guard denies system-root find"
  else
    fail "crowdstrike-guard deny (rc=$rc out=$out)"
  fi

  run_hook "$guard" "$provider_envelopes/pretooluse-bash-safe.json" "$provider" "$data_dir"
  if [ "$rc" = 0 ] && [ -z "$out" ]; then
    pass "crowdstrike-guard allows scoped find"
  else
    fail "crowdstrike-guard allow (rc=$rc out=$out)"
  fi

  run_hook "$guard" "$provider_envelopes/pretooluse-grep-danger.json" "$provider" "$data_dir"
  if [ "$rc" = 0 ] && printf '%s' "$out" | jq -e \
      '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null; then
    pass "crowdstrike-guard denies Grep on system root"
  else
    fail "crowdstrike-guard Grep deny (rc=$rc out=$out)"
  fi

  ec_out=""
  for _ in 1 2 3; do
    run_hook "$counter" "$provider_envelopes/pretooluse-grep.json" "$provider" "$data_dir"
    ec_out=$out
    ec_rc=$rc
  done
  if [ "$ec_rc" = 0 ] && printf '%s' "$ec_out" | jq -e \
      '.hookSpecificOutput.additionalContext | length > 0' >/dev/null; then
    pass "explore-counter emits reminder at third search"
  else
    fail "explore-counter reminder (rc=$ec_rc out=$ec_out)"
  fi
  rm -rf "$data_dir"

  out=$(AFK_PROVIDER="$provider" bash "$lavish" \
    < "$provider_envelopes/pretooluse-bash-safe.json" 2>/dev/null)
  rc=$?
  if [ "$rc" = 0 ]; then
    pass "lavish-dark passes non-render command"
  else
    fail "lavish-dark pass-through (rc=$rc)"
  fi

  out=$(AFK_PROVIDER="$provider" bash "$lavish_tips" \
    < "$provider_envelopes/pretooluse-bash-safe.json" 2>/dev/null)
  rc=$?
  if [ "$rc" = 0 ]; then
    pass "lavish-tips passes non-render command"
  else
    fail "lavish-tips pass-through (rc=$rc)"
  fi
done

echo
if [ "$fails" -gt 0 ]; then
  echo "hook-smoke: $fails failure(s)" >&2
  exit 1
fi
echo "hook-smoke: all green"
