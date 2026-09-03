#!/usr/bin/env bash
# build-gate/npm — the adapter entry adapter.json names.
#
# Two forms, one implementation — see adapters/build-gate/maven/gates.sh for the
# reason the commit runner sources this rather than executing it.
#   sourced  — defines afk_bg_npm_discover / afk_bg_npm_run
#   executed — bash gates.sh gate-discover | gate-run <name>
#
# Gate names: ui-lint.

set -u

AFK_BG_NPM_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

AFK_BG_NPM_EXT=('*.js' '*.cjs' '*.mjs' '*.ts' '*.vue')

afk_bg_npm_discover() {
  gate_ctx_any AFK_CTX_LIVE "${AFK_BG_NPM_EXT[@]}" || return 0
  printf 'ui-lint\n'
}

afk_bg_npm_run() {
  case ${1:-} in
    ui-lint)
      # shellcheck source=/dev/null
      . "$AFK_BG_NPM_DIR/ui-lint-gate.sh" || return 4
      gate_ui_lint ;;
    *)
      printf '{"unsupported": true, "verb": "gate-run", "reason": "build-gate/npm has no gate %s"}\n' "${1:-}"
      return 3 ;;
  esac
}

# ---- CLI form
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  _hooks="${AFK_PLUGIN_ROOT:-$(cd "$AFK_BG_NPM_DIR/../../.." && pwd)}/hooks"
  _root=$(git rev-parse --show-toplevel 2>/dev/null) || exit 2
  cd "$_root" || exit 2
  # shellcheck source=/dev/null
  . "$_hooks/lib/config.sh"; afk_config_load
  # shellcheck source=/dev/null
  . "$_hooks/gate-context.sh"; gate_ctx_build
  case ${1:-} in
    gate-discover)
      _names=$(afk_bg_npm_discover | paste -sd, - | sed 's/[^,]*/"&"/g')
      printf '{"gates": [%s]}\n' "$_names"
      exit 0 ;;
    gate-run)
      # shellcheck source=/dev/null
      . "$_hooks/gate-cache.sh"
      # shellcheck source=/dev/null
      . "$_hooks/gate-metrics.sh"
      shift; afk_bg_npm_run "$@"; exit $? ;;
    *)
      printf '{"unsupported": true, "reason": "build-gate/npm verbs: gate-discover, gate-run <name>"}\n'
      exit 3 ;;
  esac
fi
