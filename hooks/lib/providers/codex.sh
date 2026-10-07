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

# Directories this harness owns its plugin copies in, one per line. Contract:
# `hooks/lib/provider.sh` afk_managed_plugin_dirs. No home to resolve means no
# answer: exit 1, and the caller reads UNDECIDABLE rather than "not managed".
afk_codex_managed_plugin_dirs() {
  if [ -n "${CODEX_HOME:-}" ]; then
    printf '%s/plugins\n' "$CODEX_HOME"
  elif [ -n "${HOME:-}" ]; then
    printf '%s/plugins\n' "$HOME/.codex"
  else
    return 1
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

# This harness's user-global instruction file. Contract: `hooks/lib/provider.sh`
# afk_user_instruction_file. A static path from env or default — safe to call
# regardless of which harness is the current session.
afk_codex_user_instruction_file() {
  printf '%s\n' "${CODEX_HOME:-$HOME/.codex}/AGENTS.md"
}

# This harness's installed plugin root, resolved WITHOUT assuming the current
# session is this harness — used to install/audit this harness's own target
# from a different session (e.g. setup running under Claude). Prints nothing
# and fails when the root cannot be independently verified: the
# caller must then leave this harness's target unchanged, never write a
# guessed root. Resolution: `codex_resolve.py`, beside this adapter (the one
# home for this algorithm; not restated here).
afk_codex_installed_root() {
  local py="${AFK_PYTHON:-afk-python}" script
  script="$AFK_PROVIDER_CORE_DIR/providers/codex_resolve.py"
  [ -f "$script" ] || return 1
  "$py" "$script"
}

# This harness's plugin enablement state: enabled|disabled|absent. Always has
# a value — unlike a root, enablement is never "unresolved". Resolution:
# `codex_resolve.py`, beside this adapter (the one home; not restated here).
afk_codex_enablement() {
  local py="${AFK_PYTHON:-afk-python}" script
  script="$AFK_PROVIDER_CORE_DIR/providers/codex_resolve.py"
  if [ -f "$script" ]; then
    "$py" "$script" --enablement
  else
    printf 'absent\n'
  fi
}
