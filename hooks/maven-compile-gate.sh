#!/usr/bin/env bash
# Stop hook (ships with the afk plugin): Maven compile gate.
# Blocks the agent from finishing when any changed Maven module fails to compile.
#
# Scope rules:
#   - Only runs in a core-services-shaped checkout (all-modules-pom.xml at root);
#     silently allows anywhere else.
#   - Only runs when .java files changed in the working tree (tracked/unstaged/untracked).
#   - Lists ALL changed sub-modules in a single mvnw invocation so Maven's reactor
#     orders them by their inter-module dependencies.
#   - --also-make: sibling modules build from source. Resolving them from ~/.m2
#     produces false failures whenever installed artifacts lag HEAD (seen 2026-07-04:
#     stale payable-client jar -> APT "Expected a DeclaredType, got <error>").
#
# Exit 2 with stderr surfaces the compile error back to the agent.

set -u

repo_root=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
cd "$repo_root" || exit 0

# Escape hatch: create .claude/hooks/.gate-disabled to bypass this gate
# (e.g. while all-modules-pom.xml is in a known-broken state). Remove to re-enable.
if [ -f .claude/hooks/.gate-disabled ]; then
  exit 0
fi

# Not a core-services checkout — nothing to gate.
[ -f all-modules-pom.xml ] || exit 0

# Collect changed .java files. awk '{print $NF}' picks the new path for renames too.
changed_java=$(
  git status --porcelain 2>/dev/null \
    | awk '{print $NF}' \
    | grep -E '\.java$' \
    || true
)
[ -z "$changed_java" ] && exit 0

# Derive unique sub-module paths: "<numeric-prefixed-top>/<submodule>"
#   e.g. "11700-payable/payable-entities/src/.../Foo.java" -> "11700-payable/payable-entities"
submodules=$(
  printf '%s\n' "$changed_java" \
    | sed -nE 's|^([0-9]+-[^/]+/[^/]+)/src/.*|\1|p' \
    | sort -u
)
[ -z "$submodules" ] && exit 0

projects=$(printf '%s\n' "$submodules" | paste -sd, -)

# Content-hash pass cache: an unchanged tree that already passed skips the build.
. "$(dirname "${BASH_SOURCE[0]}")/gate-cache.sh"
cache_key=$(gate_cache_key maven-compile)
gate_cache_hit maven-compile "$cache_key" && exit 0

. "$(dirname "${BASH_SOURCE[0]}")/gate-metrics.sh"
gate_metrics_begin

# Serialize with other Maven-invoking gates — concurrent reactors race on target/.
. "$(dirname "${BASH_SOURCE[0]}")/maven-lock.sh"
lock_t0=$(gate_metrics_now_ms)
acquire_maven_lock 900 || exit 0
trap release_maven_lock EXIT
lock_wait_ms=$(( $(gate_metrics_now_ms) - lock_t0 ))

# Single invocation — Maven reactor resolves cross-module dependency order.
output=$(./mvnw -f all-modules-pom.xml --projects="$projects" --also-make compile -DskipUi=true -q 2>&1)
rc=$?
if [ "$rc" -ne 0 ]; then
  gate_metrics_emit maven-compile blocked "\"lock_wait_ms\":$lock_wait_ms,\"detail\":\"$projects\""
  # Full log to a file; surface only a triaged digest — an unbounded reactor
  # dump re-enters the agent's context on every failed Stop.
  log_file=$(mktemp -t maven-compile-gate.XXXXXX.log 2>/dev/null || echo /tmp/maven-compile-gate.$$.log)
  printf '%s\n' "$output" > "$log_file"
  digest=$(printf '%s\n' "$output" | grep -E '\[ERROR\]|Caused by:|error:' | head -40)
  [ -z "$digest" ] && digest=$(printf '%s\n' "$output" | tail -40)
  {
    printf '[harness] Maven compile failed for changed modules — cannot finish.\n'
    printf 'Projects: %s\n\n' "$projects"
    printf '%s\n\n' "$digest"
    printf '(digest — full log: %s)\n' "$log_file"
  } >&2
  exit 2
fi

gate_metrics_emit maven-compile pass "\"lock_wait_ms\":$lock_wait_ms,\"detail\":\"$projects\""
gate_cache_store maven-compile "$cache_key"
exit 0
