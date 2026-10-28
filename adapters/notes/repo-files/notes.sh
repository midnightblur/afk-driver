#!/usr/bin/env bash
# notes/repo-files — the canonical store: Markdown inside the consuming
# repository, under the directory `repo-files.spec-dir` renders for the work
# item. The verbs and their JSON shapes live in ../common.sh; this file states
# only what makes this kind itself.
set -uo pipefail

AFK_RF_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

notes_kind() { printf 'repo-files'; }

notes_link_form() { printf 'md'; }

# shellcheck source=/dev/null
. "$AFK_RF_DIR/../common.sh"
notes_main "$@"
