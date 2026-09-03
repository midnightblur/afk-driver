#!/usr/bin/env bash
# build-gate/maven — app-start gate: boots a service's leaf application module
# and verifies the application context actually starts. Proof-of-life for "the
# app still runs" — catches bean-wiring, config, and classpath breakage that
# compile + unit tiers miss.
#
# NOT a Stop hook (boot takes minutes). Invoked on demand by AFK verification
# tiers, by `adapters/build-gate/maven/gates.sh app-start`, or by hand from the
# repository root:
#   bash "$AFK_PLUGIN_ROOT/adapters/build-gate/maven/app-start-gate.sh" [leaf-module]
# The module defaults to `maven.default-module` from .afk/config.yaml.
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
#      APP_START_UI_BUILD (path to the UI build script; default
#                         "<parent of the module>/build_ui.sh")
#      APP_START_REUSE   (1 = if a kept instance from a prior run is still
#                         alive on APP_START_PORT, reuse it as-is — no rebuild,
#                         no reboot; falls through to a full boot otherwise)
#
# Fixed-port state: a KEPT instance is recorded in the gated repo at
# .claude/hooks/.app-instance-<port> (pid + winpid + module + jar). The next
# fixed-port run kills that recorded instance itself before booting, so
# re-provisioning never trips a port-in-use false env failure.

set -u

repo_root=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
cd "$repo_root" || exit 3

. "$(dirname "${BASH_SOURCE[0]}")/maven-lib.sh"
. "$AFK_MAVEN_HOOKS_DIR/lib/config.sh"
afk_config_load

mod=${1:-${AFK_CFG_MAVEN_DEFAULT_MODULE:-}}
timeout_s=${APP_START_TIMEOUT:-300}
skip_ui=${APP_START_SKIP_UI:-true}
ui_mod="$mod-ui"
reactor=$(afk_maven_reactor)
skip_ui_arg=$(afk_maven_skip_ui)

[ -n "$reactor" ] || { echo "[app-start-gate] maven.reactor-pom is not set in .afk/config.yaml" >&2; exit 3; }
[ -f "$reactor" ] || { echo "[app-start-gate] no $reactor at $repo_root — not the checkout .afk/config.yaml describes" >&2; exit 3; }
[ -n "$mod" ] || { echo "[app-start-gate] no module given and maven.default-module is not set in .afk/config.yaml" >&2; exit 3; }
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
    # Confirm it died. A recorded winpid can be wrong (its signature: pid and
    # winpid identical), taskkill then misses silently, and the surviving java
    # process keeps the boot jar locked. The next build dies in
    # spring-boot:repackage on a rename failure, which reads as a code fault.
    for _ in 1 2 3 4 5 6 7 8 9 10; do
      kill -0 "$prev_pid" 2>/dev/null || break
      sleep 1
    done
    if kill -0 "$prev_pid" 2>/dev/null; then
      # Fall back to whoever actually owns the port.
      port_owner=$(netstat -ano 2>/dev/null | grep ":${port} .*LISTENING" | awk '{print $NF}' | head -1)
      [ -n "${port_owner:-}" ] && taskkill //F //T //PID "$port_owner" >/dev/null 2>&1
      sleep 2
    fi
    if kill -0 "$prev_pid" 2>/dev/null; then
      echo "[app-start-gate] pid=$prev_pid survives on port $port and holds the boot jar; kill it by hand" >&2
      exit 3
    fi
  fi
  # Only once nothing holds the port: a state file removed over a live process
  # loses the only record of what to kill.
  rm -f "$state_file"
fi

log=$(mktemp "${TMPDIR:-/tmp}/app-start-gate-XXXXXX.log")

. "$AFK_MAVEN_HOOKS_DIR/gate-metrics.sh"
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
# Why not Maven: a repository that keeps its UI modules behind a profile leaves them
# out of a leaf reactor, so the UI never builds and the jar silently serves no
# frontend — a browser tier would test a page that is not there. Pulling every UI
# module in instead force-rebuilds shared UI libraries whose dist/ is already built.
# The service's own UI is the only one this gate needs; its build script builds
# exactly that.
if [ "$skip_ui" = "false" ]; then
  ui_build=${APP_START_UI_BUILD:-$(dirname "$mod")/build_ui.sh}
  if [ ! -f "$ui_build" ]; then
    release_maven_lock
    echo "[app-start-gate] APP_START_SKIP_UI=false but no UI build script at $ui_build" >&2
    exit 3
  fi
  # Clear the SPA target FIRST. build_ui.sh ends with `cp -Rf dist/spa <public>`,
  # and `cp -R <dir> <dest>` nests into <dest>/spa/ when <dest> already exists
  # (vs. populating <dest> when it doesn't) — so a second gate run on a populated
  # public/ would bury the fresh SPA one level deep and the app would serve the
  # STALE build. Removing it makes every run a clean first-populate.
  spa_root="$mod/src/main/resources/public"
  rm -rf "$spa_root"
  echo "[app-start-gate] building UI via $ui_build — populates $spa_root ..."
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
  if [ ! -f "$spa_root/index.html" ]; then
    release_maven_lock
    gate_metrics_emit app-start code_failure "\"module\":\"$ui_mod\",\"phase\":\"ui\""
    echo "[app-start-gate] UI build reported success but no $spa_root/index.html — refusing to boot a frontend-less instance" >&2
    exit 2
  fi
  echo "[app-start-gate] UI built — SPA in $spa_root."
fi

echo "[app-start-gate] packaging $mod (reactor, --also-make)..."
# The skip-UI flag unconditionally: this pass builds the app leaf only. When a UI
# was requested it was already built by the UI pass above and now sits in the app
# module's resources — rebuilding it here would be a wasted second pass.
pkg_cmd=(./mvnw -f "$reactor" -pl "$mod" --also-make package -DskipTests -q)
[ -n "$skip_ui_arg" ] && pkg_cmd+=("$skip_ui_arg")
if ! "${pkg_cmd[@]}" > "$log" 2>&1; then
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
