#!/usr/bin/env bash
# build-gate/maven — the adapter entry adapter.json names.
#
# Two forms, one implementation:
#   sourced  — defines afk_bg_maven_discover / afk_bg_maven_run / afk_bg_maven_app_start,
#              which the commit runner calls in ITS process so the shared gate
#              context, pass cache and metrics stay live (see hooks/stop-gates.sh
#              on why gate cost is measured in subprocesses).
#   executed — the CLI form the contract documents:
#                bash gates.sh gate-discover
#                bash gates.sh gate-run <name>
#                bash gates.sh app-start [module]
#
# Gate names: java-format, maven-compile. `app-start` is a verb, not a gate: it
# boots the application and is never part of a commit.

set -u

AFK_BG_MAVEN_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=/dev/null
. "$AFK_BG_MAVEN_DIR/maven-lib.sh"

# Which of this adapter's gates the current change set needs, one name per line.
# Empty when the repository names no Maven reactor or nothing Java changed.
afk_bg_maven_discover() {
  afk_maven_available || return 0
  gate_ctx_any AFK_CTX_LIVE '*.java' || return 0
  printf 'java-format\nmaven-compile\n'
}

# Run one gate by name. 0 passes, 2 blocks, 3 means this adapter has no such gate.
afk_bg_maven_run() {
  case ${1:-} in
    java-format)
      # shellcheck source=/dev/null
      . "$AFK_BG_MAVEN_DIR/java-format-gate.sh" || return 4
      gate_java_format ;;
    maven-compile)
      # shellcheck source=/dev/null
      . "$AFK_BG_MAVEN_DIR/maven-compile-gate.sh" || return 4
      gate_maven_compile ;;
    *)
      printf '{"unsupported": true, "verb": "gate-run", "reason": "build-gate/maven has no gate %s"}\n' "${1:-}"
      return 3 ;;
  esac
}

afk_bg_maven_app_start() {
  bash "$AFK_BG_MAVEN_DIR/app-start-gate.sh" "$@"
}

# ---- CLI form
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  _hooks="${AFK_PLUGIN_ROOT:-$(cd "$AFK_BG_MAVEN_DIR/../../.." && pwd)}/hooks"
  _root=$(git rev-parse --show-toplevel 2>/dev/null) || exit 2
  cd "$_root" || exit 2
  # shellcheck source=/dev/null
  . "$_hooks/lib/config.sh"; afk_config_load
  case ${1:-} in
    gate-discover)
      # shellcheck source=/dev/null
      . "$_hooks/gate-context.sh"; gate_ctx_build
      _names=$(afk_bg_maven_discover | paste -sd, - | sed 's/[^,]*/"&"/g')
      printf '{"gates": [%s]}\n' "$_names"
      exit 0 ;;
    gate-run)
      # shellcheck source=/dev/null
      . "$_hooks/gate-context.sh"; gate_ctx_build
      # shellcheck source=/dev/null
      . "$_hooks/gate-cache.sh"
      # shellcheck source=/dev/null
      . "$_hooks/gate-metrics.sh"
      shift; afk_bg_maven_run "$@"; exit $? ;;
    app-start)
      shift; afk_bg_maven_app_start "$@"; exit $? ;;
    *)
      printf '{"unsupported": true, "reason": "build-gate/maven verbs: gate-discover, gate-run <name>, app-start [module]"}\n'
      exit 3 ;;
  esac
fi
