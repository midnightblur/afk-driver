#!/usr/bin/env bash
# App-start gate (ships with the afk plugin): boots a service's leaf app module
# and verifies the Spring context actually starts. Proof-of-life for "the app
# still runs" — catches bean-wiring, config, and classpath breakage that
# compile + unit tiers miss.
#
# NOT a Stop hook (boot takes minutes). Invoked on demand by AFK verification
# tiers or manually, from the repo root:
#   bash tools/payable/ai-agents/plugins/workflow/hooks/app-start-gate.sh [service-leaf-module]
# Default module: 11700-payable/payable
#
# Exit codes:
#   0 = context started ("Started *Application" seen); process is then killed —
#       unless APP_START_KEEP=1, which leaves the instance RUNNING (provisioning
#       mode for api/e2e/adversarial verification) and prints its pid + port.
#   2 = code-level startup failure (bean wiring / context refresh error)
#   3 = environment failure (DB/broker unreachable, port in use) — NOT a code bug
#   4 = timeout without a definitive marker
#
# Env: APP_START_TIMEOUT (seconds, default 300)
#      APP_START_PORT    (fixed port; default 0 = ephemeral probe)
#      APP_START_KEEP    (1 = keep the instance running on success)
#      APP_START_SKIP_UI (default true; set false to package the UI into the jar
#                         so the instance serves the rebuilt frontend — adds a
#                         separate UI reactor pass, see "UI pass" below)
#      CI_PROJECT_DIR    (only read when APP_START_SKIP_UI=false; the checkout
#                         path the service's build_ui.sh resolves its workspace
#                         from. Defaults to the repo root — set it only to build
#                         a UI against a different checkout)
#      APP_START_REUSE   (1 = if a kept instance from a prior run is still
#                         alive on APP_START_PORT, reuse it as-is — no rebuild,
#                         no reboot; falls through to a full boot otherwise)
#
# Fixed-port state: a KEPT instance is recorded in the gated repo at
# .claude/hooks/.app-instance-<port> (pid + winpid + module + jar). The next
# fixed-port run kills that recorded instance itself before booting, so
# re-provisioning never trips a port-in-use false env failure.

set -u

mod=${1:-11700-payable/payable}
timeout_s=${APP_START_TIMEOUT:-300}
skip_ui=${APP_START_SKIP_UI:-true}
ui_mod="$mod-ui"

repo_root=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
cd "$repo_root" || exit 3
[ -f all-modules-pom.xml ] || { echo "[app-start-gate] no all-modules-pom.xml at $repo_root — not a core-services checkout" >&2; exit 3; }
[ -f "$mod/pom.xml" ] || { echo "[app-start-gate] no pom at $mod/pom.xml" >&2; exit 3; }

# Fixed-port instance state: reuse or clear a kept instance from a prior run.
port=${APP_START_PORT:-0}
state_file=".claude/hooks/.app-instance-${port}"
if [ "$port" != "0" ] && [ -f "$state_file" ]; then
  prev_pid=$(sed -n 's/^pid=//p' "$state_file" | head -1)
  prev_winpid=$(sed -n 's/^winpid=//p' "$state_file" | head -1)
  if [ -n "$prev_pid" ] && kill -0 "$prev_pid" 2>/dev/null; then
    if [ "${APP_START_REUSE:-0}" = "1" ]; then
      echo "[app-start-gate] REUSED pid=$prev_pid port=$port ($(sed -n 's/^module=//p' "$state_file" | head -1))"
      exit 0
    fi
    echo "[app-start-gate] killing prior kept instance pid=$prev_pid on port $port ..."
    [ -n "$prev_winpid" ] && taskkill //F //T //PID "$prev_winpid" >/dev/null 2>&1
    kill "$prev_pid" >/dev/null 2>&1
    sleep 2
  fi
  rm -f "$state_file"
fi

log=$(mktemp "${TMPDIR:-/tmp}/app-start-gate-XXXXXX.log")

. "$(dirname "${BASH_SOURCE[0]}")/gate-metrics.sh"
gate_metrics_begin

# Two-step boot, both reactor-based so parents/siblings resolve from source
# (a stale ~/.m2 sibling jar misclassifies env problems as code failures):
#   1. package the leaf with --also-make -> self-contained boot jar
#   2. java -jar the boot jar -> runtime classpath is exactly what was built
# Package under the shared maven lock — concurrent gate reactors race on target/.
. "$(dirname "${BASH_SOURCE[0]}")/maven-lock.sh"
acquire_maven_lock 900 || exit 3

# UI pass (APP_START_SKIP_UI=false only) — runs the service's build_ui.sh directly,
# BEFORE the leaf is packaged, because build_ui.sh copies the built SPA into the app
# module's src/main/resources/public and the jar only picks it up if it's already there.
#
# Why not Maven: -DskipUi=false on the leaf reactor is a NO-OP (the default profile is
# active on !pipelineBuild and leaves *-ui out of the reactor, so the UI never builds
# and the jar silently serves no frontend — a browser tier would test a page that isn't
# there). Adding -DpipelineBuild=true to pull *-ui in trades that for a worse bug:
# skipUi is a GLOBAL property every in-house UI lib gates its own npm build on, so
# -DskipUi=false force-rebuilds all of them — they build with vite/rollup, whose native
# binary is not pinned for every dev platform, and their dist/ is already built anyway.
# The service's own UI is the only one this gate needs; build_ui.sh builds exactly that.
if [ "$skip_ui" = "false" ]; then
  ui_build="$(dirname "$mod")/build_ui.sh"
  if [ ! -f "$ui_build" ]; then
    release_maven_lock
    echo "[app-start-gate] APP_START_SKIP_UI=false but no UI build script at $ui_build" >&2
    exit 3
  fi
  echo "[app-start-gate] building UI via $ui_build — populates $mod/src/main/resources/public ..."
  # build_ui.sh runs the UI unit suite under `set -e`: a red suite fails the UI build
  # (and CI's), so it is a code failure here too, not an environment one.
  if ! bash "$ui_build" -c "${CI_PROJECT_DIR:-$repo_root}" > "$log" 2>&1; then
    release_maven_lock
    gate_metrics_emit app-start code_failure "\"module\":\"$ui_mod\",\"phase\":\"ui\""
    {
      printf '[app-start-gate] UI BUILD FAILURE for %s — the instance would serve no frontend:\n' "$ui_mod"
      grep -E '✕|FAIL |Tests:|error|ERROR' "$log" | head -15
      printf 'Full log: %s\n' "$log"
    } >&2
    exit 2
  fi
  spa_root="$mod/src/main/resources/public"
  if [ ! -f "$spa_root/index.html" ]; then
    release_maven_lock
    gate_metrics_emit app-start code_failure "\"module\":\"$ui_mod\",\"phase\":\"ui\""
    echo "[app-start-gate] UI build reported success but no $spa_root/index.html — refusing to boot a frontend-less instance" >&2
    exit 2
  fi
  echo "[app-start-gate] UI built — SPA in $spa_root."
fi

echo "[app-start-gate] packaging $mod (reactor, --also-make)..."
# -DskipUi=true unconditionally: this pass builds the app leaf only. When a UI was
# requested it was already built by the UI pass above and now sits in public/ —
# rebuilding it here would be a wasted (or, without the UI profile, silently
# skipped) second pass.
if ! ./mvnw -f all-modules-pom.xml -pl "$mod" --also-make package \
    -DskipTests -DskipUi=true -q > "$log" 2>&1; then
  release_maven_lock
  gate_metrics_emit app-start code_failure "\"module\":\"$mod\",\"phase\":\"package\""
  {
    printf '[app-start-gate] BUILD FAILURE packaging %s:\n' "$mod"
    grep -E '\[ERROR\]' "$log" | head -15
    printf 'Full log: %s\n' "$log"
  } >&2
  exit 2
fi
release_maven_lock
package_ms=$(( $(gate_metrics_now_ms) - GATE_METRICS_T0 ))

boot_jar=$(ls -t "$mod"/target/*.jar 2>/dev/null | grep -v '\.original$' | head -1)
[ -z "$boot_jar" ] && { echo "[app-start-gate] no boot jar under $mod/target" >&2; exit 2; }

echo "[app-start-gate] booting $boot_jar ..."
# server.port=0 (ephemeral) by default: the probe only checks context-up and must
# not collide with a developer-run instance of the same service. Override with
# APP_START_PORT when a fixed port is needed (e.g. smoke suites probing HTTP).
"${JAVA_HOME:+$JAVA_HOME/bin/}java" -jar "$boot_jar" \
  --server.port="${APP_START_PORT:-0}" > "$log" 2>&1 &
mvn_pid=$!

kill_tree() {
  # Git Bash: map MSYS pid -> Windows pid, kill the whole tree (mvnw -> java).
  winpid=$(ps -p "$mvn_pid" 2>/dev/null | awk 'NR==2{print $4}')
  if [ -n "${winpid:-}" ]; then
    taskkill //F //T //PID "$winpid" >/dev/null 2>&1
  fi
  kill "$mvn_pid" >/dev/null 2>&1
}
trap kill_tree EXIT

env_pat='Communications link failure|Connection refused|Could not connect to|Address already in use|Port [0-9]+ was already in use|UnknownHostException|broker is unavailable'
code_pat='APPLICATION FAILED TO START|Error creating bean|BeanCreationException|UnsatisfiedDependencyException|BeanDefinitionStoreException|ApplicationContextException|Caused by: java\.lang\.NoClassDefFoundError'
ok_pat='Started [A-Za-z0-9]+Application in'

elapsed=0
while [ "$elapsed" -lt "$timeout_s" ]; do
  if grep -qE "$ok_pat" "$log"; then
    gate_metrics_emit app-start ok "\"module\":\"$mod\",\"package_ms\":$package_ms"
    echo "[app-start-gate] OK — $(grep -oE "$ok_pat"' [0-9.]+ seconds' "$log" | tail -1)"
    if [ "${APP_START_KEEP:-0}" = "1" ]; then
      trap - EXIT
      echo "[app-start-gate] KEPT RUNNING pid=$mvn_pid port=${APP_START_PORT:-0} log=$log"
      echo "[app-start-gate] stop it with: taskkill //F //T //PID \$(ps -p $mvn_pid | awk 'NR==2{print \$4}')"
      if [ "$port" != "0" ]; then
        mkdir -p .claude/hooks 2>/dev/null
        {
          printf 'pid=%s\n' "$mvn_pid"
          printf 'winpid=%s\n' "$(ps -p "$mvn_pid" 2>/dev/null | awk 'NR==2{print $4}')"
          printf 'module=%s\n' "$mod"
          printf 'jar=%s\n' "$boot_jar"
        } > "$state_file" 2>/dev/null
      fi
    fi
    exit 0
  fi
  if grep -qE "$env_pat" "$log"; then
    gate_metrics_emit app-start env_failure "\"module\":\"$mod\",\"package_ms\":$package_ms"
    {
      printf '[app-start-gate] ENVIRONMENT failure booting %s — local infra, not code:\n' "$mod"
      grep -E "$env_pat" "$log" | head -5
      printf 'Start the local infra (docker-compose) or free the port, then re-run.\n'
    } >&2
    exit 3
  fi
  if grep -qE "$code_pat" "$log"; then
    gate_metrics_emit app-start code_failure "\"module\":\"$mod\",\"phase\":\"boot\",\"package_ms\":$package_ms"
    # Give the log a moment to flush the full stacktrace before excerpting.
    sleep 3
    {
      printf '[app-start-gate] STARTUP FAILURE for %s — the app no longer boots:\n\n' "$mod"
      grep -B2 -A15 -E 'APPLICATION FAILED TO START' "$log" | head -40
      grep -E "$code_pat" "$log" | head -10
      printf '\nFull log: %s\n' "$log"
    } >&2
    exit 2
  fi
  if ! kill -0 "$mvn_pid" 2>/dev/null; then
    gate_metrics_emit app-start code_failure "\"module\":\"$mod\",\"phase\":\"boot\",\"package_ms\":$package_ms"
    {
      printf '[app-start-gate] process exited before a definitive marker; log tail:\n'
      tail -30 "$log"
    } >&2
    exit 2
  fi
  sleep 5
  elapsed=$((elapsed + 5))
done

gate_metrics_emit app-start timeout "\"module\":\"$mod\",\"package_ms\":$package_ms"
{
  printf '[app-start-gate] TIMEOUT after %ss without startup marker; log tail:\n' "$timeout_s"
  tail -20 "$log"
} >&2
exit 4
