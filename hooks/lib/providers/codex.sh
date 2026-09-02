#!/usr/bin/env bash

afk_codex_priority() {
  printf '10\n'
}

afk_codex_detect() {
  [ -n "${PLUGIN_ROOT:-}" ]
}

afk_codex_plugin_root() {
  if [ -n "${PLUGIN_ROOT:-}" ]; then
    printf '%s\n' "$PLUGIN_ROOT"
  elif [ -n "${CLAUDE_PLUGIN_ROOT:-}" ]; then
    printf '%s\n' "$CLAUDE_PLUGIN_ROOT"
  else
    (cd "$AFK_PROVIDER_CORE_DIR/../.." && pwd)
  fi
}

afk_codex_stop_block_code() {
  printf '0\n'
}

afk_codex_plugin_data() {
  if [ -n "${PLUGIN_DATA:-}" ]; then
    printf '%s\n' "$PLUGIN_DATA"
  elif [ -n "${CLAUDE_PLUGIN_DATA:-}" ]; then
    printf '%s\n' "$CLAUDE_PLUGIN_DATA"
  fi
}
