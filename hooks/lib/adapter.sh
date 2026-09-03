#!/usr/bin/env bash
# Adapter dispatch: family + verb in, the selected kind's implementation out.
#
# A skill or a gate never names a binary and never names a kind. It asks for a
# verb of a family; the configuration decides which directory under adapters/
# answers. That is the whole reason the toolkit can move between a Jira/GitLab
# repository and a GitHub one without a single skill edit.
#
#   afk_adapter_dir  <family>            -> adapters/<family>/<kind>
#   afk_adapter_kind <family>            -> the configured kind
#   afk_adapter      <family> <verb> [json…]
#
# Exit codes from a verb are the adapter's own contract (see each
# adapters/<family>/<kind>/CONTRACT.md). Dispatch itself exits 2 with a message
# naming the configuration path when the family or kind cannot be resolved.

if [ -z "${AFK_ADAPTER_LIB_DIR:-}" ]; then
  AFK_ADAPTER_LIB_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
fi
# shellcheck source=/dev/null
. "$AFK_ADAPTER_LIB_DIR/config.sh"

afk_adapter_root() {
  local root=${AFK_PLUGIN_ROOT:-}
  [ -n "$root" ] || root=$(cd "$AFK_ADAPTER_LIB_DIR/../.." && pwd)
  printf '%s\n' "$root"
}

afk_adapter_kind() {
  local family=$1 name value
  afk_config_load
  name="AFK_CFG_$(printf '%s' "$family" | tr '[:lower:]-' '[:upper:]_')"
  value=${!name:-}
  printf '%s\n' "$value"
}

afk_adapter_dir() {
  local family=$1 kind dir
  kind=$(afk_adapter_kind "$family")
  if [ -z "$kind" ]; then
    printf 'afk: no kind configured for family %s — set `%s:` in .afk/config.yaml\n' \
      "$family" "$family" >&2
    return 2
  fi
  dir="$(afk_adapter_root)/adapters/$family/$kind"
  if [ ! -d "$dir" ]; then
    printf 'afk: unknown %s adapter `%s` (set by `%s:` in .afk/config.yaml); no directory %s\n' \
      "$family" "$kind" "$family" "adapters/$family/$kind" >&2
    return 2
  fi
  printf '%s\n' "$dir"
}

# The executable each family dispatches through, relative to its adapter dir.
afk_adapter_entry() {
  local family=$1 dir=$2 entry py=python
  command -v python >/dev/null 2>&1 || py=python3
  if [ -f "$dir/adapter.json" ]; then
    entry=$("$py" -c 'import json,sys; print(json.load(open(sys.argv[1],encoding="utf-8")).get("runner",{}).get("entry",""))' \
      "$dir/adapter.json" 2>/dev/null)
  fi
  printf '%s\n' "$entry"
}

afk_adapter() {
  local family=$1 dir entry
  shift || return 2
  dir=$(afk_adapter_dir "$family") || return 2
  entry=$(afk_adapter_entry "$family" "$dir")
  if [ -z "$entry" ] || [ ! -f "$dir/$entry" ]; then
    printf 'afk: %s adapter at %s declares no runnable entry in adapter.json\n' \
      "$family" "$dir" >&2
    return 2
  fi
  case "$entry" in
    *.py)
      local py=python
      command -v python >/dev/null 2>&1 || py=python3
      "$py" "$dir/$entry" "$@" ;;
    *) bash "$dir/$entry" "$@" ;;
  esac
}
