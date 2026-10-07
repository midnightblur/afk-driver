#!/usr/bin/env bash
# worktree-create.sh - the harness's worktree-creation hook: every worktree the
# harness makes goes through scripts/create-worktree. Stdout is the bare path.

set -u

DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
AFK_ROOT_DIR=${AFK_PLUGIN_ROOT:-$(cd "$DIR/.." && pwd)}
py="${AFK_PYTHON:-afk-python}"

envelope=$(cat)
field() {
  printf '%s' "$envelope" | "$py" -c 'import json,sys
try:
    print(json.load(sys.stdin).get(sys.argv[1]) or "")
except Exception:
    print("")' "$1"
}
name=$(field name)
cwd=$(field cwd)
session=$(field session_id)
[ -n "$name" ] || name="session-$(date +%s)"
[ -n "$cwd" ] && cd "$cwd" 2>/dev/null

out=$(AFK_PLUGIN_ROOT="$AFK_ROOT_DIR" bash "$AFK_ROOT_DIR/scripts/create-worktree" --name "$name" --session "$session")
rc=$?
path=$(printf '%s\n' "$out" | sed -n 's/^WORKTREE_PATH=//p' | tail -1)
if [ "$rc" -ne 0 ] || [ -z "$path" ]; then
  exit "${rc/#0/1}"
fi
printf '%s\n' "$path"
