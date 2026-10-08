#!/usr/bin/env bash
# worktree-prune.sh - SessionStart: remove this repository's plugin-made worktrees whose
# owning session is gone (clean, nothing unpushed), then show worktrees a past session kept.
# Also clears fallback-notice markers older than a day.

set -u

DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
AFK_ROOT_DIR=${AFK_PLUGIN_ROOT:-$(cd "$DIR/.." && pwd)}
common=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null) || exit 0
[ -d "$common/afk-session" ] && find "$common/afk-session" -name '*.fallback' -mmin +1440 -delete 2>/dev/null
[ -d "$common/afk-worktrees" ] || exit 0
py="${AFK_PYTHON:-afk-python}"
"$py" "$AFK_ROOT_DIR/scripts/remove-worktree.py" --prune >&2
"$py" "$AFK_ROOT_DIR/scripts/remove-worktree.py" --report-kept
exit 0
