#!/usr/bin/env bash
# build-gate/maven — Java format gate (STRICT).
# Blocks the commit when any changed .java file does not conform to the
# formatter profile the repository named in `maven.formatter-config`.
#
# Runs at COMMIT time (hooks/precommit-gates.sh, installed by
# hooks/install-git-hooks.sh), not on every turn end — see maven-compile-gate.sh
# for the rationale.
#
# Policy: strict on ALL changed files — touching a legacy file means bringing the
# whole file into conformance. Fix by running the format goal printed in the
# failure message, then re-verify.
#
# Scope rules:
#   - Only runs when `maven.reactor-pom`, `maven.formatter-plugin` and
#     `maven.formatter-config` are all set and the two files exist; silently
#     allows anywhere else.
#   - Only changed (non-deleted) .java files, grouped by Maven module.
#   - One validate invocation per module, restricted to the changed files via
#     -Dformatter.includes (paths relative to the module's source roots).
#
# Exit 2 with stderr surfaces the violation back to the agent/committer.

set -u

gate_java_format() {
  [ -f .claude/hooks/.gate-disabled ] && return 0
  . "$(dirname "${BASH_SOURCE[0]}")/maven-lib.sh"
  afk_maven_available || return 0

  local reactor plugin cfg
  reactor=$(afk_maven_reactor)
  plugin=${AFK_CFG_MAVEN_FORMATTER_PLUGIN:-}
  cfg=${AFK_CFG_MAVEN_FORMATTER_CONFIG:-}
  [ -n "$plugin" ] && [ -n "$cfg" ] && [ -f "$cfg" ] || return 0

  local repo_root=$PWD

  local changed_java
  changed_java=$(gate_ctx_filter AFK_CTX_LIVE '*.java')
  [ -z "$changed_java" ] && return 0

  local submodules
  submodules=$(afk_maven_modules_of "$changed_java")
  [ -z "$submodules" ] && return 0

  local cache_key
  cache_key=$(gate_cache_key java-format)
  gate_cache_hit java-format "$cache_key" && return 0

  gate_metrics_begin
  local mods_csv; mods_csv=$(printf '%s\n' "$submodules" | paste -sd, -)

  # Serialize with other Maven-invoking gates — concurrent mvnw runs in one
  # checkout race on target/ and the local-repo metadata. Same policy as
  # maven-compile-gate.sh: on timeout, allow rather than block the commit.
  . "$(dirname "${BASH_SOURCE[0]}")/maven-lock.sh"
  local lock_t0 lock_wait_ms
  lock_t0=$(gate_metrics_now_ms)
  acquire_maven_lock "${AFK_MAVEN_LOCK_WAIT:-900}" || return 0
  lock_wait_ms=$(( $(gate_metrics_now_ms) - lock_t0 ))

  local fail=0 report="" mod includes out rc
  while IFS= read -r mod; do
    [ -n "$mod" ] || continue
    # Includes: file paths relative to the module's java source roots.
    includes=$(
      printf '%s\n' "$changed_java" \
        | grep -F "$mod/src/" \
        | sed -E 's#^.*/src/(main|test)/java/##' \
        | { while IFS= read -r p; do [ -f "$repo_root/$mod/src/main/java/$p" ] || [ -f "$repo_root/$mod/src/test/java/$p" ] && printf '%s\n' "$p"; done; } \
        | paste -sd, -
    )
    [ -z "$includes" ] && continue

    out=$(./mvnw -f "$reactor" -pl "$mod" "$plugin:validate" \
      -Dconfigfile="$repo_root/$cfg" \
      -Dformatter.includes="$includes" -q 2>&1)
    rc=$?
    if [ "$rc" -ne 0 ]; then
      fail=1
      report+="Module: $mod  (files: $includes)"$'\n'
      report+="$(printf '%s\n' "$out" | grep -E '\[ERROR\]|has not been previously formatted' | head -10)"$'\n'
      report+="Fix: ./mvnw -f $reactor -pl $mod $plugin:format -Dconfigfile=$repo_root/$cfg -Dformatter.includes=$includes"$'\n\n'
    fi
  done <<<"$submodules"

  # One release, one owner — explicit, not `trap … RETURN` (see maven-compile-gate.sh).
  release_maven_lock

  if [ "$fail" -ne 0 ]; then
    gate_metrics_emit java-format blocked "\"lock_wait_ms\":$lock_wait_ms,\"detail\":\"$mods_csv\""
    {
      printf '[harness] Java format gate failed — changed files must conform to %s.\n' "$cfg"
      printf 'Policy is strict: a touched legacy file gets fully reformatted.\n'
      printf 'Run the Fix command(s) below, review the diff, then commit.\n\n'
      printf '%s' "$report"
    } >&2
    return 2
  fi

  gate_metrics_emit java-format pass "\"lock_wait_ms\":$lock_wait_ms,\"detail\":\"$mods_csv\""
  gate_cache_store java-format "$cache_key"
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
  gate_java_format; exit $?
fi
