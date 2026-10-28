#!/usr/bin/env bash
# notes/obsidian — the same Markdown tree in the checkout's spec folder, linked
# with wikilinks. The verbs and their JSON shapes live in ../common.sh.
set -uo pipefail

AFK_OB_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

notes_kind() { printf 'obsidian'; }

notes_link_form() { printf 'wikilink'; }

# shellcheck source=/dev/null
. "$AFK_OB_DIR/../common.sh"
notes_main "$@"
