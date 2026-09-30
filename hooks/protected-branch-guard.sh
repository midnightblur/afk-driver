#!/usr/bin/env bash
# protected-branch-guard.sh - PreToolUse gate: an agent changes a repository only
# from a linked worktree on an unprotected branch. Judge: lib/protected_branch_guard.py.

set -u

[ "${AFK_ALLOW_PROTECTED:-}" = "1" ] && exit 0

DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=/dev/null
. "$DIR/lib/provider.sh"

# The envelope of a Write can outgrow an environment block: keep it in a file.
envelope=$(mktemp) || exit 0
trap 'rm -f "$envelope"' EXIT
cat >"$envelope"

tool=$(grep -o '"tool_name"[[:space:]]*:[[:space:]]*"[^"]*"' "$envelope" | head -1 | sed 's/.*:[[:space:]]*"//;s/"$//')

class=other
case "$tool" in
  mcp__*)
    # An MCP tool is judged by its name: a mutating verb makes it a change.
    if printf '%s' "$tool" | grep -Eiq '(write|edit|create|update|delete|replace|rename|move|exec|execute|run|terminal|apply|patch|commit|push|insert|set)'; then
      class=other
    else
      class=allow
    fi ;;
  *) class=$(afk_provider_declared tool_class "$tool") || class=other ;;
esac
[ "$class" = "allow" ] && exit 0

# A verdict that cannot be computed inside a git work tree is a refusal; outside
# one it is an allow.
fault() {
  local dir=$PWD next reason
  reason="protected-branch guard: refused to act. Cause: the guard could not compute a verdict ($1). Move: fix the guard fault, then retry."
  while :; do
    if [ -e "$dir/.git" ]; then
      printf '%s\n' "$reason" >&2
      printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"%s"}}\n' "${reason//\"/\'}"
      exit 2
    fi
    next=$(dirname "$dir")
    [ "$next" = "$dir" ] && break
    dir=$next
  done
  exit 0
}

py=python
command -v python >/dev/null 2>&1 || py=python3
command -v "$py" >/dev/null 2>&1 || fault "python is not installed"
AFK_GUARD_TOOL_CLASS=$class \
AFK_GUARD_HARNESS_CLASS=$(afk_provider_declared harness_class || printf 'H-2') \
AFK_GUARD_HINT=$(afk_provider_declared move_hint || printf 'create a linked worktree with `scripts/create-worktree` and continue there.') \
AFK_PLUGIN_ROOT=${AFK_PLUGIN_ROOT:-$(afk_plugin_root)} \
  "$py" "$DIR/lib/protected_branch_guard.py" <"$envelope"
rc=$?
case "$rc" in 0|2) exit "$rc" ;; *) fault "the helper exited $rc" ;; esac
