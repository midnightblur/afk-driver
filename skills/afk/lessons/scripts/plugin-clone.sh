#!/usr/bin/env bash
# Is the plugin root an editable clone, or an installed copy?
#
#   plugin-clone.sh [PLUGIN_ROOT]
#
# PLUGIN_ROOT defaults to $AFK_PLUGIN_ROOT, else the plugin root holding this
# script. Clone = a git work tree contains PLUGIN_ROOT and tracks its plugin
# manifest (.claude-plugin/plugin.json or .codex-plugin/plugin.json). That holds
# for the plugin repository itself, a clone inside or outside the current
# repository, and a plugin tree committed inside a larger repository. It does
# not hold for an installed copy, including one that sits untracked or ignored
# inside an unrelated git work tree.
#
# stdout: `PLUGIN: clone <root>` | `PLUGIN: installed <root>`
# Exit: 0 clone, 1 installed, 2 PLUGIN_ROOT holds no plugin manifest.
set -u

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
root=${1:-${AFK_PLUGIN_ROOT:-$(cd "$here/../../../.." && pwd)}}

found=0
for manifest in .claude-plugin/plugin.json .codex-plugin/plugin.json; do
  [ -f "$root/$manifest" ] || continue
  found=1
  if [ "$(git -C "$root" rev-parse --is-inside-work-tree 2>/dev/null)" = true ] \
     && git -C "$root" ls-files --error-unmatch -- "$manifest" >/dev/null 2>&1; then
    echo "PLUGIN: clone $root"
    exit 0
  fi
done
[ "$found" = 1 ] || { echo "plugin-clone: $root holds no plugin manifest" >&2; exit 2; }
echo "PLUGIN: installed $root"
exit 1
