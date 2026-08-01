#!/usr/bin/env bash
# Sourced helper (ships with the afk plugin): content-hash pass cache for the
# Stop gates (maven-compile, ui-lint, java-format, wiring, skill-registry,
# codex-drift, genericity).
#
# A Stop hook fires on every turn end; the gated tree often hasn't changed since
# the last green run. The cache remembers the last PASS per gate as a hash over
# HEAD + every working-tree change (path + blob hash, deletions included) — an
# identical tree skips the gate's real work entirely.
#
# The hash itself is NOT computed here: it is the shared per-Stop tree digest
# built once by gate-context.sh (AFK_CTX_TREE) and reused by every gate, so a
# key costs a string concat rather than `git status` + two forks per changed
# file. Every operation below is fork-free ($(<file), printf, [[ ]]).
#
# Contract for gates:
#   key=$(gate_cache_key <gate>)              # after scope checks, before work
#   gate_cache_hit <gate> "$key" && return 0  # cache hit = silent allow,
#                                             #   no metrics line (it's a no-op)
#   gate_cache_store <gate> "$key"            # only on PASS
#
# A failed run stores nothing — the stored key stays the last passing tree,
# which by construction differs from any tree that can fail.
#
# Cache lives in the GATED repo at .claude/hooks/.gate-cache/<gate>.
# GATE_CACHE_DISABLE=1 bypasses (every run does real work).
# Assumes cwd = repo root (all gates cd there first).

gate_cache_key() {
  # $1 = gate name. Remaining args (optional) are globs bounding the gate's
  # INPUTS, e.g. gate_cache_key genericity 'plugin/*.md' '11700-payable/*'.
  #
  # With no globs the key covers the whole change set — correct for a gate whose
  # verdict can turn on any sibling edit (compile/format depend on poms and
  # resources). With globs the key covers only the matching changes, so an edit
  # the gate could not possibly care about no longer busts its cache. That is the
  # difference between a gate running once per session and once per turn while a
  # human works in the same checkout.
  if [ "${AFK_CTX_READY:-0}" != "1" ]; then
    . "$(dirname "${BASH_SOURCE[0]}")/gate-context.sh"
    gate_ctx_build
  fi
  local gate=$1; shift
  if [ "$#" -eq 0 ]; then
    printf '%s:%s' "$gate" "$AFK_CTX_TREE"
    return 0
  fi
  # Scoped key: HEAD + the in-scope (path, content-hash) pairs + in-scope
  # deletions. Built with fork-free list matching; stored verbatim as the key.
  local line path pat scoped=""
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    path=${line%%$'\t'*}
    for pat in "$@"; do
      # shellcheck disable=SC2254
      case "$path" in
        $pat) scoped+="$line"$'\n'; break ;;
      esac
    done
  done <<<"${AFK_CTX_HASHES:-}"
  while IFS= read -r path; do
    [ -n "$path" ] || continue
    [ -f "$path" ] && continue           # live files are covered by the hash list
    for pat in "$@"; do
      # shellcheck disable=SC2254
      case "$path" in
        $pat) scoped+="$path"$'\t'"deleted"$'\n'; break ;;
      esac
    done
  done <<<"${AFK_CTX_CHANGED:-}"
  printf '%s:%s\n%s' "$gate" "$AFK_CTX_HEAD" "$scoped"
}

gate_cache_hit() {
  # $1 = gate name, $2 = key. True only when the stored last-pass key matches.
  [ "${GATE_CACHE_DISABLE:-0}" = "1" ] && return 1
  [ -n "${2:-}" ] || return 1
  local f=".claude/hooks/.gate-cache/$1"
  [ -f "$f" ] || return 1
  [ "$(<"$f")" = "$2" ]
}

gate_cache_store() {
  # $1 = gate name, $2 = key. Call only on PASS.
  [ "${GATE_CACHE_DISABLE:-0}" = "1" ] && return 0
  [ -n "${2:-}" ] || return 0
  mkdir -p .claude/hooks/.gate-cache 2>/dev/null || return 0
  printf '%s\n' "$2" > ".claude/hooks/.gate-cache/$1" 2>/dev/null
  return 0
}
