#!/usr/bin/env bash
# The shell view of the consuming repository's AFK configuration.
#
# One reader owns the configuration file (scripts/afk-config.py). Gates never
# parse it: they source the fixed, shell-quoted names this file exports, so a
# gate can never disagree with the skill it gates.
#
# Names follow the flattened key path: `git.base-branch` -> AFK_CFG_GIT_BASE_BRANCH,
# `build-gates` -> AFK_CFG_BUILD_GATES_COUNT plus AFK_CFG_BUILD_GATES_0...
# AFK_CFG_LOADED is 1 once the export ran, so the whole set costs one Python
# call per gate run no matter how many gates read it.
#
# A missing or unreadable configuration is not a failure: the built-in defaults
# come back, and every gate that needs a value it did not get stays off. When the
# export itself cannot run, AFK_CFG_LOAD_FAILED names why, so a caller can refuse.

afk_config_load() {
  [ "${AFK_CFG_LOADED:-0}" = "1" ] && return 0

  local root script exported py="${AFK_PYTHON:-afk-python}"

  root=${AFK_PLUGIN_ROOT:-}
  if [ -z "$root" ]; then
    root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
  fi
  script="$root/scripts/afk-config.py"
  [ -f "$script" ] || { AFK_CFG_LOADED=1; AFK_CFG_LOAD_FAILED="$script is missing"; return 0; }

  exported=$("$py" "$script" export-shell 2>/dev/null) \
    || { AFK_CFG_LOADED=1; AFK_CFG_LOAD_FAILED="$py could not run $script"; return 0; }
  eval "$exported"
  AFK_CFG_LOADED=1
}

# afk_repo_hooks_manifest — the effective `repo-hooks` path without Python, layers per CONFIG.md "Discovery".
# Accepts one plain top-level `repo-hooks: <path>` line per layer; any other mention is ambiguous (rc 1).
afk_repo_hooks_manifest() {
  local common layer line value found=""
  common=$(git rev-parse --git-common-dir 2>/dev/null) || return 1
  for layer in "${AFK_CONFIG:-}" .afk/config.local.yaml "$common/afk/config.yaml" .afk/config.yaml \
    "${HOME:-/nonexistent}/.afk/config.yaml"; do
    [ -n "$layer" ] || continue
    [ -e "$layer" ] || { [ "$layer" != "${AFK_CONFIG:-}" ] && continue; return 1; }
    [ -r "$layer" ] || return 1
    while IFS= read -r line || [ -n "$line" ]; do
      line=${line%$'\r'}
      case "$line" in *repo-hooks*) ;; *) continue ;; esac
      [[ $line =~ ^[[:space:]]*# ]] && continue
      [ -z "$found" ] || return 1
      if [[ $line =~ ^repo-hooks:[[:space:]]*\"([^\"\\]+)\"[[:space:]]*(#.*)?$ ]] \
        || [[ $line =~ ^repo-hooks:[[:space:]]*\'([^\']+)\'[[:space:]]*(#.*)?$ ]] \
        || [[ $line =~ ^repo-hooks:[[:space:]]*([^[:space:]\"\'\|\>\&\*\!\[\{%@\`#][^[:space:]]*)[[:space:]]*(#.*)?$ ]]; then
        value=${BASH_REMATCH[1]}; found=1
      else
        return 1
      fi
    done <"$layer"
    [ -n "$found" ] && break
  done
  [ -n "$found" ] || value=.afk/hooks.json
  case "$value" in /*|*\\*|[A-Za-z]:*|..|../*|*/..|*/../*) return 1 ;; esac
  printf '%s\n' "$value"
}

# afk_config_get <dotted.key> — one value, for the rare caller that wants a
# structure the flat export cannot carry. Prefer the AFK_CFG_* names.
afk_config_get() {
  local root py="${AFK_PYTHON:-afk-python}"
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
