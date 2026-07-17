#!/usr/bin/env bash
# Mutation probe (ships with the afk plugin): runs PIT (pitest) scoped to the
# classes a slice changed and reports which mutants its tests failed to kill.
# A green test suite that kills no mutants proves nothing — this probe is the
# oracle for test STRENGTH, consumed as an advisory signal by the review gate's
# test-veracity concern. NOT a Stop hook; on demand only:
#
#   bash tools/payable/ai-agents/plugins/workflow/hooks/mutation-probe.sh \
#     <module> <targetClasses-csv> [targetTests-csv]
#   e.g. … 11700-payable/payable com.nakisa.payable.service.FooService com.nakisa.payable.service.FooServiceTest
#
# Exit codes:
#   0 = probe ran; summary + surviving mutants printed to stdout
#   3 = unavailable (infra/compat: pitest can't run here) or timeout — NEVER a
#       code/test verdict; callers treat it as "no signal", not a failure
#
# Env: PITEST_VERSION   (default 1.25.3 — override to track upstream)
#      MUTATION_TIMEOUT (seconds, default 900)
#
# JUnit 5 caveat (verified against pitest docs 2026-07): pitest discovers
# JUnit 5 tests only when `org.pitest:pitest-junit5-plugin` is on the pitest
# MAVEN PLUGIN's classpath — that cannot be injected from the CLI. One-time
# enablement per service parent POM (<pluginManagement>):
#
#   <plugin>
#     <groupId>org.pitest</groupId><artifactId>pitest-maven</artifactId>
#     <version>1.25.3</version>
#     <dependencies>
#       <dependency>
#         <groupId>org.pitest</groupId><artifactId>pitest-junit5-plugin</artifactId>
#         <version>1.2.3</version>
#       </dependency>
#     </dependencies>
#   </plugin>
#
# Until a module's parent carries that, this probe exits 3 (unavailable) there.

set -u

mod=${1:-}
target_classes=${2:-}
target_tests=${3:-}
[ -n "$mod" ] && [ -n "$target_classes" ] || {
  echo "usage: mutation-probe.sh <module> <targetClasses-csv> [targetTests-csv]" >&2
  exit 3
}

PITEST_VERSION=${PITEST_VERSION:-1.25.3}
timeout_s=${MUTATION_TIMEOUT:-900}

repo_root=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
cd "$repo_root" || exit 3
[ -f all-modules-pom.xml ] || { echo "MUTATION: unavailable — not a core-services checkout" ; exit 3; }
[ -f "$mod/pom.xml" ] || { echo "MUTATION: unavailable — no pom at $mod/pom.xml"; exit 3; }

. "$(dirname "${BASH_SOURCE[0]}")/gate-metrics.sh"
gate_metrics_begin

# pitest rewrites target/ — serialize with the other Maven-invoking gates.
. "$(dirname "${BASH_SOURCE[0]}")/maven-lock.sh"
acquire_maven_lock 900 || { echo "MUTATION: unavailable — maven lock timeout"; exit 3; }
trap release_maven_lock EXIT

log=$(mktemp "${TMPDIR:-/tmp}/mutation-probe-XXXXXX.log")
rm -rf "$mod/target/pit-reports"

mvn_cmd=(./mvnw -f all-modules-pom.xml -pl "$mod" --also-make test-compile
  "org.pitest:pitest-maven:${PITEST_VERSION}:mutationCoverage"
  -DtargetClasses="$target_classes"
  -DoutputFormats=CSV -DtimestampedReports=false -DskipUi=true -q)
[ -n "$target_tests" ] && mvn_cmd+=(-DtargetTests="$target_tests")

if command -v timeout >/dev/null 2>&1; then
  timeout "$timeout_s" "${mvn_cmd[@]}" > "$log" 2>&1
else
  "${mvn_cmd[@]}" > "$log" 2>&1
fi
rc=$?

if [ "$rc" -eq 124 ]; then
  gate_metrics_emit mutation-probe timeout "\"module\":\"$mod\""
  echo "MUTATION: unavailable — timed out after ${timeout_s}s (raise MUTATION_TIMEOUT or narrow targetClasses)"
  exit 3
fi

csv="$mod/target/pit-reports/mutations.csv"
if [ "$rc" -ne 0 ] || [ ! -f "$csv" ]; then
  gate_metrics_emit mutation-probe unavailable "\"module\":\"$mod\""
  {
    echo "MUTATION: unavailable — pitest did not produce a report (infra/compat, not a test verdict)."
    echo "Common cause: the module's parent POM lacks the pitest-junit5-plugin pluginManagement entry (see this script's header)."
    grep -E '\[ERROR\]|Exception' "$log" | head -8
    echo "Full log: $log"
  }
  exit 3
fi

# CSV columns: fileName,className,mutator,method,lineNumber,status[,killingTest]
awk -F, '
  { total++ }
  $6 == "KILLED" || $6 == "TIMED_OUT" || $6 == "MEMORY_ERROR" || $6 == "RUN_ERROR" { killed++ }
  $6 == "SURVIVED"    { survived++;  surv_list = surv_list sprintf("  %s:%s %s (%s)\n", $2, $5, $3, $4) }
  $6 == "NO_COVERAGE" { uncovered++; ncov_list = ncov_list sprintf("  %s:%s %s (%s)\n", $2, $5, $3, $4) }
  END {
    score = total ? int(100 * killed / total) : 0
    printf "MUTATION: ok — total=%d killed=%d survived=%d no_coverage=%d score=%d%%\n", total, killed, survived, uncovered, score
    if (survived)  printf "survived (test exists but does not catch the change):\n%s", surv_list
    if (uncovered) printf "no coverage (mutated line exercised by no test):\n%s", ncov_list
  }
' "$csv"

gate_metrics_emit mutation-probe ok "\"module\":\"$mod\""
exit 0
