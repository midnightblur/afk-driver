#!/usr/bin/env bash
# worktree-prune.sh - SessionStart: remove this repository's plugin-made worktrees whose
# owning session is gone (clean, nothing unpushed). A repository with none costs one stat.

set -u

DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
AFK_ROOT_DIR=${AFK_PLUGIN_ROOT:-$(cd "$DIR/.." && pwd)}
common=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null) || exit 0
[ -d "$common/afk-worktrees" ] || exit 0
py=python
command -v python >/dev/null 2>&1 || py=python3
"$py" "$AFK_ROOT_DIR/scripts/remove-worktree.py" --prune >&2
exit 0
