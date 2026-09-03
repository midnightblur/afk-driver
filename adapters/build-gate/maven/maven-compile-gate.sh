#!/usr/bin/env bash
# build-gate/maven — compile gate.
# Blocks the commit when any changed Maven module fails to compile.
#
# Runs at COMMIT time (hooks/precommit-gates.sh, installed by
# hooks/install-git-hooks.sh), not on every turn end: a reactor compile is
# minutes of work, and paying it per conversational turn made interactive
# sessions unusable. Correctness is unchanged — nothing reaches a branch without
# passing it.
#
# Scope rules:
#   - Only runs when `maven.reactor-pom` names a POM that exists; silently allows
#     anywhere else, so a repository with no Maven reactor is not gated.
#   - Only runs when .java files are in scope (the shared gate context).
#   - Lists ALL changed modules in a single mvnw invocation so Maven's reactor
#     orders them by their inter-module dependencies.
#   - --also-make: sibling modules build from source. Resolving them from the
#     local repository produces false failures whenever installed artifacts lag
#     HEAD (stale sibling jar -> APT "Expected a DeclaredType, got <error>").
#
# Exit 2 with stderr surfaces the compile error back to the agent/committer.

set -u

gate_maven_compile() {
  [ -f .claude/hooks/.gate-disabled ] && return 0
  . "$(dirname "${BASH_SOURCE[0]}")/maven-lib.sh"
  afk_maven_available || return 0

  local reactor; reactor=$(afk_maven_reactor)

  local changed_java
  changed_java=$(gate_ctx_filter AFK_CTX_LIVE '*.java')
  [ -z "$changed_java" ] && return 0

  local submodules
  submodules=$(afk_maven_modules_of "$changed_java")
  [ -z "$submodules" ] && return 0

  local projects; projects=$(printf '%s\n' "$submodules" | paste -sd, -)

  local cache_key
  cache_key=$(gate_cache_key maven-compile)
  gate_cache_hit maven-compile "$cache_key" && return 0

  gate_metrics_begin

  # Serialize with other Maven-invoking gates — concurrent reactors race on target/.
  . "$(dirname "${BASH_SOURCE[0]}")/maven-lock.sh"
  local lock_t0 lock_wait_ms
  lock_t0=$(gate_metrics_now_ms)
  # Wait bound: the commit path shortens this (hooks/precommit-gates.sh) so a
  # hook can never outlive the tool call driving the commit. On timeout the gate
  # allows — blocking a commit because a sibling worktree is mid-build helps nobody.
  acquire_maven_lock "${AFK_MAVEN_LOCK_WAIT:-900}" || return 0
  lock_wait_ms=$(( $(gate_metrics_now_ms) - lock_t0 ))

  local -a cmd=(./mvnw -f "$reactor" --projects="$projects" --also-make compile -q)
  local skip_ui; skip_ui=$(afk_maven_skip_ui)
  [ -n "$skip_ui" ] && cmd+=("$skip_ui")

  local output rc
  output=$("${cmd[@]}" 2>&1)
  rc=$?
  # Release the moment the reactor is done — explicitly, not via `trap … RETURN`.
  # Gates share one process now, and a RETURN trap fires again as the enclosing
  # dispatcher returns: the second `rmdir` would drop a lock another process had
  # just acquired, re-opening the concurrent-reactor race the lock exists to
  # prevent. One release, one owner, no unwinding.
  release_maven_lock
  if [ "$rc" -ne 0 ]; then
    gate_metrics_emit maven-compile blocked "\"lock_wait_ms\":$lock_wait_ms,\"detail\":\"$projects\""
    # Full log to a file; surface only a triaged digest — an unbounded reactor
    # dump re-enters the agent's context on every failed run.
    local log_file digest
    log_file=$(mktemp -t maven-compile-gate.XXXXXX.log 2>/dev/null || echo /tmp/maven-compile-gate.$$.log)
    printf '%s\n' "$output" > "$log_file"
    digest=$(printf '%s\n' "$output" | grep -E '\[ERROR\]|Caused by:|error:' | head -40)
    [ -z "$digest" ] && digest=$(printf '%s\n' "$output" | tail -40)
    {
      printf '[harness] Maven compile failed for changed modules — cannot commit.\n'
      printf 'Projects: %s\n\n' "$projects"
      printf '%s\n\n' "$digest"
      printf '(digest — full log: %s)\n' "$log_file"
    } >&2
    return 2
  fi

  gate_metrics_emit maven-compile pass "\"lock_wait_ms\":$lock_wait_ms,\"detail\":\"$projects\""
  gate_cache_store maven-compile "$cache_key"
  return 0
}

# ---- standalone invocation (manual run; scope = working tree)
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  _d=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
  _root=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
  cd "$_root" || exit 0
  . "$_d/maven-lib.sh"
  . "$AFK_MAVEN_HOOKS_DIR/lib/config.sh"; afk_config_load
  . "$AFK_MAVEN_HOOKS_DIR/gate-context.sh"; gate_ctx_build
  . "$AFK_MAVEN_HOOKS_DIR/gate-cache.sh"
  . "$AFK_MAVEN_HOOKS_DIR/gate-metrics.sh"
  gate_maven_compile; exit $?
fi
