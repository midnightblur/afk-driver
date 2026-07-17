#!/usr/bin/env bash
# Shared mutex for gates that run Maven over the reactor. Two concurrent reactors
# rewrite the same target/ dirs (--also-make) and race: one compiles against a
# half-written dependency and fails with bogus "cannot find symbol". Source this
# and wrap every mvnw invocation between acquire_maven_lock / release_maven_lock.
#
# mkdir-based lock; stale locks (>30 min, e.g. a killed process) are stolen.
# The lock lives in the repo being built (target/ dirs are per-checkout), not
# under the plugin.

MAVEN_LOCK_DIR="${MAVEN_LOCK_DIR:-.claude/hooks/.maven.lock}"

acquire_maven_lock() {
  local timeout_s=${1:-900} waited=0
  mkdir -p "$(dirname "$MAVEN_LOCK_DIR")" 2>/dev/null
  while ! mkdir "$MAVEN_LOCK_DIR" 2>/dev/null; do
    # Steal a stale lock: holder died without releasing.
    if [ -d "$MAVEN_LOCK_DIR" ]; then
      local age=$(( $(date +%s) - $(stat -c %Y "$MAVEN_LOCK_DIR" 2>/dev/null || echo 0) ))
      if [ "$age" -gt 1800 ]; then
        rmdir "$MAVEN_LOCK_DIR" 2>/dev/null && continue
      fi
    fi
    if [ "$waited" -ge "$timeout_s" ]; then
      echo "[maven-lock] timed out after ${timeout_s}s waiting for $MAVEN_LOCK_DIR (another gate's build is running)" >&2
      return 1
    fi
    sleep 10
    waited=$((waited + 10))
  done
  return 0
}

release_maven_lock() {
  rmdir "$MAVEN_LOCK_DIR" 2>/dev/null
}
