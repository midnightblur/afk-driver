#!/usr/bin/env bash
# Stop hook (ships with the afk plugin): Java format gate (STRICT).
# Blocks the agent from finishing when any changed .java file does not conform
# to the repo's canonical Eclipse formatter profile (eclipse-code-formatter.xml).
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
# Exit 2 with stderr surfaces the violation back to the agent.

set -u

FORMATTER_PLUGIN="net.revelc.code.formatter:formatter-maven-plugin:2.28.0"

repo_root=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
cd "$repo_root" || exit 0

# Shared escape hatch with the other harness gates.
if [ -f .claude/hooks/.gate-disabled ]; then
  exit 0
fi

# Not a core-services checkout — nothing to gate.
[ -f all-modules-pom.xml ] && [ -f eclipse-code-formatter.xml ] || exit 0

changed_java=$(
  git status --porcelain 2>/dev/null \
    | awk '$1 != "D" {print $NF}' \
    | grep -E '\.java$' \
    || true
)
[ -z "$changed_java" ] && exit 0

# Unique submodules, same derivation as maven-compile-gate.sh.
submodules=$(
  printf '%s\n' "$changed_java" \
    | sed -nE 's|^([0-9]+-[^/]+/[^/]+)/src/.*|\1|p' \
    | sort -u
)
[ -z "$submodules" ] && exit 0

# Content-hash pass cache: an unchanged tree that already passed skips the validate.
. "$(dirname "${BASH_SOURCE[0]}")/gate-cache.sh"
cache_key=$(gate_cache_key java-format)
gate_cache_hit java-format "$cache_key" && exit 0

. "$(dirname "${BASH_SOURCE[0]}")/gate-metrics.sh"
gate_metrics_begin
mods_csv=$(printf '%s\n' "$submodules" | paste -sd, -)

fail=0
report=""
while IFS= read -r mod; do
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
done <<< "$submodules"

if [ "$fail" -ne 0 ]; then
  gate_metrics_emit java-format blocked "\"detail\":\"$mods_csv\""
  {
    printf '[harness] Java format gate failed — changed files must conform to eclipse-code-formatter.xml.\n'
    printf 'Policy is strict: a touched legacy file gets fully reformatted (owner-approved churn).\n'
    printf 'Run the Fix command(s) below, review the diff, then finish.\n\n'
    printf '%s' "$report"
  } >&2
  exit 2
fi

gate_metrics_emit java-format pass "\"detail\":\"$mods_csv\""
gate_cache_store java-format "$cache_key"
exit 0
