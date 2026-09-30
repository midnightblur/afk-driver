#!/usr/bin/env bash
# worktree-remove.sh - worktree-removal and session-end hook: runs remove-worktree.py.
# The path is `worktree_path` when the event carries one, else `cwd`.

set -u

DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PLUGIN_ROOT=${AFK_PLUGIN_ROOT:-$(cd "$DIR/.." && pwd)}
py=python
command -v python >/dev/null 2>&1 || py=python3

target=$("$py" -c 'import json,sys
try:
    d = json.load(sys.stdin)
    print(d.get("worktree_path") or d.get("cwd") or "")
except Exception:
    print("")')
[ -n "$target" ] || exit 0
"$py" "$PLUGIN_ROOT/scripts/remove-worktree.py" --path "$target" >&2
exit 0
