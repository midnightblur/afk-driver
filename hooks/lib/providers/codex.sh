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

# Nested-steering policy. This harness loads instruction files once at the start
# of a run (project root down to the launch directory), so an AGENTS.md nested
# below the launch directory never reaches it — always inject. It also has no
# native path-scoped rules, so inject matching `.claude/rules` bodies.
afk_codex_nested_inject_mode() { printf 'always\n'; }
afk_codex_nested_inject_rules() { printf '1\n'; }

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
  local py=python script
  command -v python >/dev/null 2>&1 || py=python3
  script="$AFK_PROVIDER_CORE_DIR/providers/codex_resolve.py"
  [ -f "$script" ] || return 1
  "$py" "$script"
}

# This harness's plugin enablement state: enabled|disabled|absent. Always has
# a value — unlike a root, enablement is never "unresolved". Resolution:
# `codex_resolve.py`, beside this adapter (the one home; not restated here).
afk_codex_enablement() {
  local py=python script
  command -v python >/dev/null 2>&1 || py=python3
  script="$AFK_PROVIDER_CORE_DIR/providers/codex_resolve.py"
  if [ -f "$script" ]; then
    "$py" "$script" --enablement
  else
    printf 'absent\n'
  fi
}

# Protected-branch guard declarations (hooks/protected-branch-guard.sh).
# Class H-2: the session moves with the harness's own `/cd` command.
afk_codex_harness_class() { printf 'H-2\n'; }

afk_codex_tool_class() {
  case "$1" in
    apply_patch|Edit|Write|MultiEdit|NotebookEdit) printf 'edit\n' ;;
    Bash|shell|shell_command|exec_command|local_shell|unified_exec|write_stdin|container.exec) printf 'shell\n' ;;
    Read|read_file|list_dir|grep_files|view_image|update_plan|web_search|request_user_input|spawn_agent|send_input|wait|wait_agent|close_agent|resume_agent|list_mcp_resources|list_mcp_resource_templates|read_mcp_resource|tool_search) printf 'allow\n' ;;
    *) printf 'other\n' ;;
  esac
}

afk_codex_move_hint() {
  printf 'move the session into a linked worktree: start the harness through the plugin launch command, or create one with `scripts/create-worktree` and type `/cd <worktree path>`.'
}
