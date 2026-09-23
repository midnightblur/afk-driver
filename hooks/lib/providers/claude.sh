#!/usr/bin/env bash

afk_claude_priority() {
  printf '20\n'
}

afk_claude_detect() {
  [ -n "${CLAUDE_PLUGIN_ROOT:-}" ] || [ -n "${CLAUDECODE:-}" ]
}

afk_claude_plugin_root() {
  if [ -n "${CLAUDE_PLUGIN_ROOT:-}" ]; then
    printf '%s\n' "$CLAUDE_PLUGIN_ROOT"
  else
    (cd "$AFK_PROVIDER_CORE_DIR/../.." && pwd)
  fi
}

# Directories this harness owns its plugin copies in (its marketplace clones
# and its version cache), one per line. Contract: `hooks/lib/provider.sh`
# afk_managed_plugin_dirs. With no configuration directory and no home to
# resolve one from, this cannot answer, and it says so with exit 1 rather than
# printing a guess: the caller then reads UNDECIDABLE, never "not managed".
afk_claude_managed_plugin_dirs() {
  if [ -n "${CLAUDE_CONFIG_DIR:-}" ]; then
    printf '%s/plugins\n' "$CLAUDE_CONFIG_DIR"
  elif [ -n "${HOME:-}" ]; then
    printf '%s/plugins\n' "$HOME/.claude"
  else
    return 1
  fi
}

afk_claude_stop_block_code() {
  printf '0\n'
}

# Nested-steering policy. In an interactive main session this harness reads a
# nested AGENTS.md natively once the root CLAUDE.md bridge is present and
# instructionFiles=claude-md-and-agents-md (setup H11), so the main session is
# not injected. A subagent does NOT inherit that nested load — a conformance
# probe (providers/CONFORMANCE.md, 2026-09-23, Claude 2.1.280) showed a spawned
# subagent reading a file below the launch directory never sees the nested
# AGENTS.md. So the injector fires for subagent tool calls only (P3.7 amendment):
# `agent-only` injects when the envelope carries an agent_id, and stays silent in
# the main session where the native load already applies.
afk_claude_nested_inject_mode() { printf 'agent-only\n'; }
afk_claude_nested_inject_rules() { printf '0\n'; }   # native .claude/rules paths:

afk_claude_plugin_data() {
  if [ -n "${CLAUDE_PLUGIN_DATA:-}" ]; then
    printf '%s\n' "$CLAUDE_PLUGIN_DATA"
  elif [ -n "${PLUGIN_DATA:-}" ]; then
    printf '%s\n' "$PLUGIN_DATA"
  fi
}
