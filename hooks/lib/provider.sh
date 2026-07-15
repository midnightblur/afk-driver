#!/usr/bin/env bash
# provider.sh — provider-abstraction shim for AFK hook scripts.
#
# One home for every provider-specific surface a hook touches: agent-runtime
# detection, plugin root/data paths, the stdin hook-event envelope, and the
# decision-output contracts. Hook scripts source this and call the afk_*
# functions; gate LOGIC stays provider-free.
#
# Canonical copy: plugins/workflow/hooks/lib/provider.sh
# Synced copy:    harness/hooks/lib/provider.sh   (byte-identical; plugins are
# installed as snapshots, so a hook can't source across plugin roots at runtime.
# codex-sync/generate.py re-emits the copy; its --check mode flags divergence.)
#
# Supported providers:
#   claude — Claude Code. Detected via CLAUDE_PLUGIN_ROOT / CLAUDECODE.
#   codex  — OpenAI Codex CLI. Detected via CODEX_HOME / CODEX_THREAD_ID /
#            CODEX_SANDBOX (UNVERIFIED against a live Codex install — the CLI's
#            hook-env contract isn't documented; until live-verified, set
#            AFK_PROVIDER=codex explicitly, e.g. in .codex/hooks.json commands).
#   unknown — neither marker present (manual shell run, CI).
# Override everything: AFK_PROVIDER=claude|codex.

# ---- detection --------------------------------------------------------------

afk_provider() {
  if [ -n "${AFK_PROVIDER:-}" ]; then
    printf '%s\n' "$AFK_PROVIDER"
  elif [ -n "${CLAUDE_PLUGIN_ROOT:-}" ] || [ -n "${CLAUDECODE:-}" ]; then
    printf 'claude\n'
  elif [ -n "${CODEX_HOME:-}" ] || [ -n "${CODEX_THREAD_ID:-}" ] || [ -n "${CODEX_SANDBOX:-}" ]; then
    printf 'codex\n'
  else
    printf 'unknown\n'
  fi
}

# True when ANY agent runtime is acting (vs a human shell). Used by gates that
# must never get in a human's way (e.g. the git branch-name gate carries an
# inlined Lockstep copy of this check — it can't source plugin files).
afk_agent_session() {
  [ "$(afk_provider)" != "unknown" ]
}

# ---- paths ------------------------------------------------------------------

# Plugin root: Claude injects CLAUDE_PLUGIN_ROOT; Codex invokes hooks by
# repo-relative path with no env, so fall back to this file's location
# (lib/ is one level under the plugin's hooks/ dir).
afk_plugin_root() {
  if [ -n "${CLAUDE_PLUGIN_ROOT:-}" ]; then
    printf '%s\n' "$CLAUDE_PLUGIN_ROOT"
  else
    (cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
  fi
}

# Writable per-plugin state dir (logs, counters). Claude provides
# CLAUDE_PLUGIN_DATA; elsewhere use a neutral home-dir location.
afk_plugin_data() {
  local dir
  if [ -n "${CLAUDE_PLUGIN_DATA:-}" ]; then
    dir="$CLAUDE_PLUGIN_DATA"
  else
    dir="$HOME/.afk/data/$(basename "$(afk_plugin_root)")"
  fi
  mkdir -p "$dir" 2>/dev/null || true
  printf '%s\n' "$dir"
}

# ---- stdin envelope ---------------------------------------------------------

# Slurp the hook-event JSON once into AFK_HOOK_INPUT (both providers deliver
# the same core fields: hook_event_name, session_id, cwd, tool_name, tool_input).
afk_hook_input() {
  AFK_HOOK_INPUT=$(cat)
}

# afk_hook_field <jq-path> — extract a field from the slurped envelope.
# jq when available; grep/sed fallback for simple string fields ("a.b.c" paths,
# no arrays), matching the pre-shim parsing style of crowdstrike-guard.sh.
afk_hook_field() {
  local path="$1"
  if command -v jq >/dev/null 2>&1; then
    printf '%s' "${AFK_HOOK_INPUT:-}" | jq -r ".${path} // \"\"" 2>/dev/null || printf ''
  else
    local leaf="${path##*.}"
    { printf '%s' "${AFK_HOOK_INPUT:-}" \
      | grep -oE "\"${leaf}\":\"([^\"\\\\]|\\\\.)*\"" | head -1 \
      | sed "s/^\"${leaf}\":\"//;s/\"\$//" \
      | sed 's/\\"/"/g;s/\\\\/\\/g;s/\\n/ /g;s/\\t/ /g;s/\\r/ /g'; } || true
  fi
}

# ---- decision output --------------------------------------------------------

# JSON-escape a string for the no-jq fallback paths (quotes, backslashes,
# real newlines/tabs). Messages may carry real newlines; jq handles them
# natively, the fallback must escape them.
afk__json_escape() {
  printf '%s' "$1" | sed 's/\\/\\\\/g;s/"/\\"/g' | awk 'NR>1{printf "\\n"}{printf "%s",$0}' | sed 's/\t/\\t/g'
}

# PreToolUse hard deny. Claude and Codex both accept the hookSpecificOutput
# permissionDecision envelope (Codex schema researched 2026-07, unverified live
# — if it diverges, this function is the only change point).
afk_emit_deny() {
  local reason="$1"
  if command -v jq >/dev/null 2>&1; then
    jq -n --arg r "$reason" \
      '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$r}}'
  else
    printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"%s"}}\n' "$(afk__json_escape "$reason")"
  fi
}

# PreToolUse context injection (non-blocking system reminder). Same envelope
# on both providers.
afk_emit_context() {
  local msg="$1"
  if command -v jq >/dev/null 2>&1; then
    jq -n --arg msg "$msg" \
      '{hookSpecificOutput:{hookEventName:"PreToolUse",additionalContext:$msg}}'
  else
    printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext":"%s"}}\n' "$(afk__json_escape "$msg")"
  fi
}

# Stop-gate block: stderr + exit 2 is the confirmed-portable contract on both
# providers (Claude documented; Codex documented 2026-07).
afk_block_stop() {
  printf '%s\n' "$1" >&2
  exit 2
}
