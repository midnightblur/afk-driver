#!/usr/bin/env bash
# Commit gate (ships with the afk plugin): Java format gate (STRICT).
# Blocks the commit when any changed .java file does not conform to the repo's
# canonical Eclipse formatter profile (eclipse-code-formatter.xml).
#
# Runs at COMMIT time (precommit-gates.sh, installed by install-git-hooks.sh),
# not on every turn end — see maven-compile-gate.sh for the rationale.
#
# Policy (owner-approved): strict on ALL changed files — touching a legacy file
# means bringing the whole file into conformance. Fix by running the format goal
# printed in the failure message, then re-verify.
#
# Scope rules:
#   - Only runs in a core-services-shaped checkout (all-modules-pom.xml +
#     eclipse-code-formatter.xml at root); silently allows anywhere else.
#   - Only changed (non-deleted) .java files, grouped by Maven submodule.
#   - One validate invocation per submodule, restricted to the changed files
#     via -Dformatter.includes (paths relative to the module's source roots).
#
# Exit 2 with stderr surfaces the violation back to the agent/committer.

set -u

FORMATTER_PLUGIN="net.revelc.code.formatter:formatter-maven-plugin:2.28.0"

gate_java_format() {
  [ -f .claude/hooks/.gate-disabled ] && return 0
  [ -f all-modules-pom.xml ] && [ -f eclipse-code-formatter.xml ] || return 0

  local repo_root=$PWD

  local changed_java
  changed_java=$(gate_ctx_filter AFK_CTX_LIVE '*.java')
  [ -z "$changed_java" ] && return 0

  # Unique submodules, same derivation as maven-compile-gate.sh.
  local submodules
  submodules=$(printf '%s\n' "$changed_java" \
    | sed -nE 's|^([0-9]+-[^/]+/[^/]+)/src/.*|\1|p' | sort -u)
  [ -z "$submodules" ] && return 0

  local cache_key
  cache_key=$(gate_cache_key java-format)
  gate_cache_hit java-format "$cache_key" && return 0

  gate_metrics_begin
  local mods_csv; mods_csv=$(printf '%s\n' "$submodules" | paste -sd, -)

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

    out=$(./mvnw -f all-modules-pom.xml -pl "$mod" "$FORMATTER_PLUGIN:validate" \
      -Dconfigfile="$repo_root/eclipse-code-formatter.xml" \
      -Dformatter.includes="$includes" -q 2>&1)
    rc=$?
    if [ "$rc" -ne 0 ]; then
      fail=1
      report+="Module: $mod  (files: $includes)"$'\n'
      report+="$(printf '%s\n' "$out" | grep -E '\[ERROR\]|has not been previously formatted' | head -10)"$'\n'
      report+="Fix: ./mvnw -f all-modules-pom.xml -pl $mod $FORMATTER_PLUGIN:format -Dconfigfile=$repo_root/eclipse-code-formatter.xml -Dformatter.includes=$includes"$'\n\n'
    fi
  done <<<"$submodules"

  if [ "$fail" -ne 0 ]; then
    gate_metrics_emit java-format blocked "\"detail\":\"$mods_csv\""
    {
      printf '[harness] Java format gate failed — changed files must conform to eclipse-code-formatter.xml.\n'
      printf 'Policy is strict: a touched legacy file gets fully reformatted (owner-approved churn).\n'
      printf 'Run the Fix command(s) below, review the diff, then commit.\n\n'
      printf '%s' "$report"
    } >&2
    return 2
  fi

  gate_metrics_emit java-format pass "\"detail\":\"$mods_csv\""
  gate_cache_store java-format "$cache_key"
  return 0
}

# ---- standalone invocation (manual run; scope = working tree)
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  _d=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
  _root=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
  cd "$_root" || exit 0
  . "$_d/gate-context.sh"; gate_ctx_build
  . "$_d/gate-cache.sh"
  . "$_d/gate-metrics.sh"
  gate_java_format; exit $?
fi
