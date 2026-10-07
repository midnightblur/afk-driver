#!/usr/bin/env bash
# Is the plugin root an editable clone, or an installed copy?
#
#   plugin-clone.sh [PLUGIN_ROOT]
#
# PLUGIN_ROOT defaults to $AFK_PLUGIN_ROOT, else the plugin root holding this
# script. Installed wins first: a tree under a harness-managed plugin directory
# (each adapter declares its own — `hooks/lib/provider.sh`
# afk_managed_plugin_dirs) is installed whatever it looks like, because the
# harness rewrites everything there on its next update, including the
# marketplace clone it keeps as a git work tree. Otherwise clone = a git work
# tree contains PLUGIN_ROOT and tracks its plugin manifest
# (.claude-plugin/plugin.json or .codex-plugin/plugin.json). That holds for the
# plugin repository itself, a maintainer's clone inside or outside the current
# repository, and a plugin tree committed inside a larger repository. It does
# not hold for an installed copy, including one that sits untracked or ignored
# inside an unrelated git work tree.
#
# Fail closed. When the managed-path question cannot be answered — no home
# directory to resolve, an adapter that does not declare its directories, the
# provider library absent — the answer is `installed`. A wrong `installed`
# costs one issue filed instead of one edit; a wrong `clone` writes an edit the
# harness silently erases.
#
# stdout: `PLUGIN: clone <root>` | `PLUGIN: installed <root>`
# Exit: 0 clone, 1 installed, 2 PLUGIN_ROOT holds no plugin manifest.
set -u

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
root=${1:-${AFK_PLUGIN_ROOT:-$(cd "$here/../../../.." && pwd)}}
# shellcheck source=/dev/null
. "$here/../../../../hooks/lib/provider.sh"

found=0
for manifest in .claude-plugin/plugin.json .codex-plugin/plugin.json; do
  [ -f "$root/$manifest" ] || continue
  found=1
  # Only a clear "not managed" (exit 1) lets the git test run.
  afk_harness_managed_path "$root"
  [ "$?" = 1 ] || break
  if [ "$(git -C "$root" rev-parse --is-inside-work-tree 2>/dev/null)" = true ] \
     && git -C "$root" ls-files --error-unmatch -- "$manifest" >/dev/null 2>&1; then
    echo "PLUGIN: clone $root"
    exit 0
  fi
done
[ "$found" = 1 ] || { echo "plugin-clone: $root holds no plugin manifest" >&2; exit 2; }
echo "PLUGIN: installed $root"
exit 1
