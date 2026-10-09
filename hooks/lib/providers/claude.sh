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

afk_claude_plugin_data() {
  if [ -n "${CLAUDE_PLUGIN_DATA:-}" ]; then
    printf '%s\n' "$CLAUDE_PLUGIN_DATA"
  elif [ -n "${PLUGIN_DATA:-}" ]; then
    printf '%s\n' "$PLUGIN_DATA"
  fi
}

# This harness's user-global instruction file. Contract: `hooks/lib/provider.sh`
# afk_user_instruction_file. A static path from env or default — safe to call
# regardless of which harness is the current session.
afk_claude_user_instruction_file() {
  printf '%s\n' "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/CLAUDE.md"
}

# This harness's installed plugin root, resolved WITHOUT assuming the current
# session is this harness — used to install/audit this harness's own target
# from a different session (e.g. setup running under Codex). Prints nothing
# and fails when the root cannot be independently verified: the
# caller must then leave this harness's target unchanged, never write a
# guessed root. Resolution: `claude_resolve.py`, beside this adapter (the one
# home for this algorithm; not restated here).
afk_claude_installed_root() {
  local py="${AFK_PYTHON:-afk-python}" script
  script="$AFK_PROVIDER_CORE_DIR/providers/claude_resolve.py"
  [ -f "$script" ] || return 1
  "$py" "$script"
}

# This harness's plugin enablement state: enabled|disabled|absent. Always has
# a value — unlike a root, enablement is never "unresolved". Resolution:
# `claude_resolve.py`, beside this adapter (the one home; not restated here).
afk_claude_enablement() {
  local py="${AFK_PYTHON:-afk-python}" script
  script="$AFK_PROVIDER_CORE_DIR/providers/claude_resolve.py"
  if [ -f "$script" ]; then
    "$py" "$script" --enablement
  else
    printf 'absent\n'
  fi
}
