#!/usr/bin/env bash
# Sourced helper (ships with the afk plugin): content-hash pass cache for the
# code Stop gates (maven-compile, ui-lint, java-format).
#
# A Stop hook fires on every turn end; the gated tree often hasn't changed
# since the last green run. The cache remembers the last PASS per gate as a
# hash over HEAD + every working-tree change (path + blob hash, deletions
# included) — an identical tree skips the gate's real work entirely.
#
# Contract for gates:
#   key=$(gate_cache_key <gate>)              # after scope checks, before work
#   gate_cache_hit <gate> "$key" && exit 0    # cache hit = silent allow,
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
  # $1 = gate name. Key covers the full change set, not just the gate's file
  # type — compile/format outcomes can depend on sibling edits (poms, resources).
  {
    printf '%s\n' "$1"
    git rev-parse HEAD 2>/dev/null
    git status --porcelain -uall 2>/dev/null | while IFS= read -r line; do
      f=$(printf '%s' "$line" | awk '{print $NF}')
      if [ -f "$f" ]; then
        printf '%s %s\n' "$f" "$(git hash-object "$f" 2>/dev/null)"
      else
        printf '%s deleted\n' "$f"
      fi
    done
  } | git hash-object --stdin 2>/dev/null
}

gate_cache_hit() {
  # $1 = gate name, $2 = key. True only when the stored last-pass key matches.
  [ "${GATE_CACHE_DISABLE:-0}" = "1" ] && return 1
  [ -n "${2:-}" ] || return 1
  [ -f ".claude/hooks/.gate-cache/$1" ] || return 1
  [ "$(cat ".claude/hooks/.gate-cache/$1" 2>/dev/null)" = "$2" ]
}

gate_cache_store() {
  # $1 = gate name, $2 = key. Call only on PASS.
  [ "${GATE_CACHE_DISABLE:-0}" = "1" ] && return 0
  [ -n "${2:-}" ] || return 0
  mkdir -p .claude/hooks/.gate-cache 2>/dev/null || return 0
  printf '%s\n' "$2" > ".claude/hooks/.gate-cache/$1" 2>/dev/null
  return 0
}
