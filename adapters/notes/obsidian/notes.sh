#!/usr/bin/env bash
# notes/obsidian — the same Markdown tree, rooted inside `obsidian.vault` so
# the vault indexes it, and linked with wikilinks so the vault's graph sees the
# links. The verbs and their JSON shapes live in ../common.sh.
set -uo pipefail

AFK_OB_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

notes_kind() { printf 'obsidian'; }

notes_root() {
  afk_config_load
  local vault=${AFK_CFG_OBSIDIAN_VAULT:-}
  if [ -z "$vault" ]; then
    printf '{"error": "no `obsidian.vault` in .afk/config.yaml - notes/obsidian has no tree to write into"}\n'
    return 2
  fi
  if [ ! -d "$vault" ]; then
    printf '{"unavailable": true, "reason": "`obsidian.vault` names %s, which is not a directory on this machine"}\n' "$vault"
    return 4
  fi
  printf '%s' "$vault"
}

notes_link_form() { printf 'wikilink'; }

# shellcheck source=/dev/null
. "$AFK_OB_DIR/../common.sh"
notes_main "$@"
