#!/usr/bin/env bash
# Advisory SessionStart check for the opt-in managed behavior block.
#
# Checks only this session's own provider target against this session's own
# resolved root — never the other harness's file. Each harness runs its own
# copy of this hook at its own SessionStart, so the other target is checked
# there, with its own root.

set -u

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
AFK_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)

[ -f "$AFK_ROOT/BEHAVIORS.md" ] || exit 0

# shellcheck source=lib/provider.sh
. "$SCRIPT_DIR/lib/provider.sh"

# An unrecognized provider has no known target to check — never guess one.
afk_agent_session || exit 0
TARGET=$(afk_user_instruction_file)
[ -n "$TARGET" ] || exit 0

grep -Eq '<!-- afk:(behaviors|plain-language|lavish-sessions|investigation):(start|end) -->' "$TARGET" 2>/dev/null \
  || exit 0

py="${AFK_PYTHON:-afk-python}"

"$py" "$AFK_ROOT/scripts/behavior_registry.py" audit \
  --registry "$AFK_ROOT/BEHAVIORS.md" \
  --plugin-root "$AFK_ROOT" \
  --target "$TARGET" \
  --ignore-unmanaged >/dev/null 2>&1
status=$?

if [ "$status" -eq 1 ]; then
  printf '[afk] Managed behavior is stale; run /afk:setup.\n'
elif [ "$status" -gt 1 ]; then
  # A tool/config problem (unreadable registry, missing interpreter, ...) is
  # not drift: never tell the developer to run setup for something setup
  # cannot fix either.
  printf '[afk] Managed behavior check failed; see /afk:setup audit for detail.\n' >&2
fi

exit 0
