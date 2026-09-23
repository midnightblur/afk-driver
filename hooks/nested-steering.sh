#!/usr/bin/env bash
# On-demand handler (ships with the afk plugin): nested-steering injector.
#
# Injects the AGENTS.md chain (+ matching .claude/rules bodies) below the launch
# directory for a harness that loaded only the launch-directory chain, and resets
# its per-session dedup markers on a fresh/cleared session and after compaction.
# Registered in hooks/hooks.json + hooks/hooks.codex.json on PostToolUse (`*`),
# PostCompact (`*`), and SessionStart (`startup|clear`). Launched by
# hooks/run-hook.py as `plugin nested-steering.sh`.
#
# Provider policy (inject / never / agent-only, and whether to inject path-scoped
# rules) lives in hooks/lib/providers/<name>.sh; the mechanical collection lives
# in hooks/lib/nested_steering.py. This handler only wires the two together and
# emits the injection through the provider library.
#
# Disable: NESTED_STEERING_DISABLE=1.
set -u

[ "${NESTED_STEERING_DISABLE:-0}" = "1" ] && exit 0

dir=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=/dev/null
. "$dir/lib/provider.sh"

afk_hook_input                                   # AFK_HOOK_INPUT <- stdin
event=$(afk_hook_field hook_event_name)
data=$(afk_plugin_data)
py=python
command -v python >/dev/null 2>&1 || py=python3

module="$dir/lib/nested_steering.py"

# Reset events fire on both harnesses regardless of injection policy: a cleared
# or fresh session and a compaction drop the loaded context, so the markers that
# said "already injected" must go too.
case "$event" in
  SessionStart|PostCompact)
    printf '%s' "$AFK_HOOK_INPUT" | "$py" "$module" \
      --provider "$(afk_provider)" --mode never --rules 0 --data-dir "$data" \
      >/dev/null 2>>"$data/nested-steering.log" || true
    exit 0 ;;
esac

mode=$(afk_nested_inject_mode)
[ "$mode" = never ] && exit 0
rules=$(afk_nested_inject_rules)

out=$(printf '%s' "$AFK_HOOK_INPUT" | "$py" "$module" \
  --provider "$(afk_provider)" --mode "$mode" --rules "$rules" --data-dir "$data" \
  2>>"$data/nested-steering.log")

[ -n "$out" ] && afk_emit_context "$event" "$out"
exit 0
