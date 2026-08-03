#!/usr/bin/env bash
# Shared mutex for gates that run Maven over the reactor. Two concurrent reactors
# rewrite the same target/ dirs (--also-make) and race: one compiles against a
# half-written dependency and fails with bogus "cannot find symbol". Source this
# and wrap every mvnw invocation between acquire_maven_lock / release_maven_lock.
#
# mkdir-based lock; stale locks (>30 min, e.g. a killed process) are stolen.
# The lock lives in the repo being built (target/ dirs are per-checkout), not
# under the plugin.
#
# Safety properties:
#   - Steal is ATOMIC: the stale dir is renamed to a per-PID grave first, so of
#     two contenders that both judged it stale only one wins the rename — the
#     loser can never rmdir a fresh lock the winner just re-created.
#   - Release is guarded by a held flag: releasing without holding (double
#     release, trap after explicit release) is a no-op, never a theft.
#   - An owner file ($$ + timestamp) inside the dir is forensic only.
#   - Sourcing installs an EXIT/TERM/INT trap so a dying holder releases instead
#     of stranding the lock for the 30-min steal window (a hard kill still
#     strands; the steal covers that).

MAVEN_LOCK_DIR="${MAVEN_LOCK_DIR:-.claude/hooks/.maven.lock}"
_MAVEN_LOCK_HELD=0

acquire_maven_lock() {
  local timeout_s=${1:-900} waited=0
  mkdir -p "$(dirname "$MAVEN_LOCK_DIR")" 2>/dev/null
  while ! mkdir "$MAVEN_LOCK_DIR" 2>/dev/null; do
    # Steal a stale lock: holder died without releasing.
    if [ -d "$MAVEN_LOCK_DIR" ]; then
      local age=$(( $(date +%s) - $(stat -c %Y "$MAVEN_LOCK_DIR" 2>/dev/null || echo 0) ))
      if [ "$age" -gt 1800 ]; then
        local grave="$MAVEN_LOCK_DIR.stale.$$"
        if mv "$MAVEN_LOCK_DIR" "$grave" 2>/dev/null; then
          rm -rf "$grave" 2>/dev/null
        fi
        continue
      fi
    fi
    if [ "$waited" -ge "$timeout_s" ]; then
      echo "[maven-lock] timed out after ${timeout_s}s waiting for $MAVEN_LOCK_DIR (another gate's build is running) — proceeding WITHOUT the gate that wanted it" >&2
      return 1
    fi
    sleep 10
    waited=$((waited + 10))
  done
  printf '%s %s\n' "$$" "$(date +%s)" > "$MAVEN_LOCK_DIR/owner" 2>/dev/null
  _MAVEN_LOCK_HELD=1
  return 0
}

release_maven_lock() {
  [ "${_MAVEN_LOCK_HELD:-0}" = "1" ] || return 0
  _MAVEN_LOCK_HELD=0
  rm -rf "$MAVEN_LOCK_DIR" 2>/dev/null
  return 0
}

# Held-flag guard makes this safe even when the gate already released explicitly.
trap 'release_maven_lock' EXIT
trap 'release_maven_lock; exit 143' TERM
trap 'release_maven_lock; exit 130' INT
