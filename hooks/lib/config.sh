#!/usr/bin/env bash
# The shell view of the consuming repository's AFK configuration.
#
# One reader owns the configuration file (scripts/afk-config.py). Gates never
# parse it: they source the fixed, shell-quoted names this file exports, so a
# gate can never disagree with the skill it gates.
#
# Names follow the flattened key path: `git.base-branch` -> AFK_CFG_GIT_BASE_BRANCH,
# `build-gates` -> AFK_CFG_BUILD_GATES_COUNT plus AFK_CFG_BUILD_GATES_0...
# AFK_CFG_LOADED is 1 once the export ran, so the whole set costs one python
# call per Stop no matter how many gates read it.
#
# A missing or unreadable configuration is not a failure: the built-in defaults
# come back, and every gate that needs a value it did not get stays off.

afk_config_load() {
  [ "${AFK_CFG_LOADED:-0}" = "1" ] && return 0

  local root script exported py=python
  command -v python >/dev/null 2>&1 || py=python3

  root=${AFK_PLUGIN_ROOT:-}
  if [ -z "$root" ]; then
    root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
  fi
  script="$root/scripts/afk-config.py"
  [ -f "$script" ] || { AFK_CFG_LOADED=1; return 0; }

  exported=$("$py" "$script" export-shell 2>/dev/null) || { AFK_CFG_LOADED=1; return 0; }
  eval "$exported"
  AFK_CFG_LOADED=1
}

# afk_config_get <dotted.key> — one value, for the rare caller that wants a
# structure the flat export cannot carry. Prefer the AFK_CFG_* names.
afk_config_get() {
  local root py=python
  command -v python >/dev/null 2>&1 || py=python3
  root=${AFK_PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}
  "$py" "$root/scripts/afk-config.py" get "$1" 2>/dev/null
}

# afk_config_list <dotted.key> — the elements of a configured list, one per
# line, read from the flat export.
afk_config_list() {
  afk_config_load
  local base count index name
  base="AFK_CFG_$(printf '%s' "$1" | tr '[:lower:].-' '[:upper:]__')"
  count="${base}_COUNT"
  count=${!count:-0}
  index=0
  while [ "$index" -lt "$count" ]; do
    name="${base}_${index}"
    printf '%s\n' "${!name}"
    index=$((index + 1))
  done
}

# afk_config_has <family> <kind> — true when the named build gate is selected.
afk_build_gate_selected() {
  local wanted=$1 gate
  while IFS= read -r gate; do
    [ "$gate" = "$wanted" ] && return 0
  done < <(afk_config_list build-gates)
  return 1
}
