#!/usr/bin/env bash
# build-gate/maven — the `worktree-provision` operation.
#
# Concurrent worktree builds must never share a writable local repository:
# parallel installs of the same snapshot and in-place metadata rewrites corrupt
# each other. Maven has no read-only tail repository, so isolation means a
# private repository per worktree, activated by `.mvn/maven.config`, which every
# wrapper run and every IDE that reads maven.config picks up with no caller
# change.
#
#   bash worktree-provision.sh '<json>'
#
# JSON: {"source":…,"worktree":…,"worktree_native":…,"dry_run":false}
# Answer: one JSON object on stdout; progress on stderr.
# Exit: 0 provisioned/adopted/skipped, 2 invalid input or unsafe, 4 recoverable.

set -u

AFK_BG_MAVEN_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

json_field() {   # json_field <json> <name> — a string or boolean field, unescaped
  printf '%s' "$1" | "${AFK_PY:-python}" -c '
import json, sys
doc = json.loads(sys.stdin.read())
value = doc.get(sys.argv[1])
if isinstance(value, bool):
    print("true" if value else "false", end="")
elif value is not None:
    print(value, end="")
' "$2" 2>/dev/null
}

json_array() {   # json_array <name of AFK_CFG list> — one entry per line
  local base="$1" count i
  eval "count=\${${base}_COUNT:-}"
  [ -n "$count" ] || return 0
  i=0
  while [ "$i" -lt "$count" ]; do
    eval "printf '%s\n' \"\${${base}_$i}\""
    i=$((i + 1))
  done
}

fail() { printf '%s\n' "afk: build-gate/maven worktree-provision: $1" >&2; exit 2; }

PAYLOAD=${1:-}
[ -n "$PAYLOAD" ] || fail "no JSON payload on argv[1]"
SOURCE=$(json_field "$PAYLOAD" source)
WORKTREE=$(json_field "$PAYLOAD" worktree)
WORKTREE_NATIVE=$(json_field "$PAYLOAD" worktree_native)
DRY_RUN=$(json_field "$PAYLOAD" dry_run)
[ -n "$SOURCE" ] && [ -n "$WORKTREE" ] || fail "payload needs source and worktree"
[ -d "$WORKTREE" ] || fail "worktree does not exist: $WORKTREE"
git -C "$WORKTREE" rev-parse --git-dir >/dev/null 2>&1 \
  || fail "not a git worktree: $WORKTREE"
[ -n "$WORKTREE_NATIVE" ] || WORKTREE_NATIVE=$(cygpath -m "$WORKTREE" 2>/dev/null || printf '%s' "$WORKTREE")

# ---- configuration (flat maven.* keys, exported by hooks/lib/config.sh)
REPO_MODE=${AFK_CFG_MAVEN_WORKTREE_REPO:-isolated}
SEED=${AFK_CFG_MAVEN_WORKTREE_SEED:-auto}
EXCLUDES=$(json_array AFK_CFG_MAVEN_WORKTREE_SEED_EXCLUDE)
[ -n "$EXCLUDES" ] || EXCLUDES='*-SNAPSHOT'

# The fingerprint answers one question: would provisioning today do something
# different from what it did when the marker was written? Only the inputs that
# change the outcome belong in it.
FINGERPRINT=$(printf '%s\n%s\n%s\n' "$REPO_MODE" "$SEED" "$EXCLUDES" \
  | "${AFK_PY:-python}" -c 'import hashlib,sys; print(hashlib.sha256(sys.stdin.buffer.read()).hexdigest(), end="")')

DONE=""; SKIPPED=""; WARNINGS=""; STATUS=provisioned
add() { local var=$1 item=$2; eval "$var=\"\${$var}\${$var:+,}\$item\""; }
quoted() { printf '%s' "$1" | sed 's/"/\\"/g'; }

answer() {
  printf '{"kind":"maven","status":"%s","fingerprint":"%s","done":[%s],"skipped":[%s],"warnings":[%s]}\n' \
    "$STATUS" "$FINGERPRINT" "$DONE" "$SKIPPED" "$WARNINGS"
}

MAVEN_CONFIG="$WORKTREE/.mvn/maven.config"
REPO_LINE="-Dmaven.repo.local=$WORKTREE_NATIVE/.m2/repository"

# ---- the two reasons not to provision at all
if [ "$REPO_MODE" = shared ]; then
  STATUS=skipped
  add SKIPPED "{\"step\":\"maven.config\",\"reason\":\"maven.worktree-repo is shared\"}"
  answer; exit 0
fi
if [ "${WORKTREE_NATIVE}" != "${WORKTREE_NATIVE% *}" ]; then
  # maven.config cannot quote a path containing a space, so an isolated repo
  # here would produce builds that fail in a way nobody would connect to this.
  STATUS=degraded
  add SKIPPED "{\"step\":\"maven.config\",\"reason\":\"worktree path contains a space; builds share the default repository\"}"
  add WARNINGS "\"worktree path contains a space — Maven cannot quote it in maven.config; the worktree shares the default local repository\""
  answer; exit 0
fi

# ---- what the worktree already says. maven.config is a file a developer may own:
# it can carry other flags, or point the local repository somewhere deliberate (a
# second repository for another toolchain, say). Overwriting either would break a
# build in a way nobody would connect to cutting a worktree.
ADOPT=false
FOREIGN_REPO=""
if [ -f "$MAVEN_CONFIG" ]; then
  if grep -qxF -- "$REPO_LINE" "$MAVEN_CONFIG" 2>/dev/null; then
    ADOPT=true
    STATUS=adopted
  else
    FOREIGN_REPO=$(grep -o -- '-Dmaven\.repo\.local=[^[:space:]]*' "$MAVEN_CONFIG" 2>/dev/null | head -1)
  fi
fi

if [ -n "$FOREIGN_REPO" ]; then
  STATUS=degraded
  add SKIPPED "{\"step\":\"maven.config\",\"reason\":\"the worktree already points its local repository elsewhere\"}"
  add WARNINGS "\"$(quoted "$MAVEN_CONFIG") already sets $(quoted "$FOREIGN_REPO"); left as it is — delete that line and re-run with --force for a private repository\""
  printf '%s\n' "afk: $MAVEN_CONFIG already sets $FOREIGN_REPO — leaving it alone" >&2
  answer; exit 0
fi

if [ "$DRY_RUN" = true ]; then
  [ "$ADOPT" = true ] || STATUS=provisioned
  add DONE '"fingerprint"'
  answer; exit 0
fi

# ---- the git-ignore entries. Both are needed and neither is guaranteed: a
# generic repository has no reason to ignore `.m2/`, and none ignores
# `.mvn/maven.config`. info/ lives in the COMMON git dir, so one entry covers
# the main checkout and every worktree.
COMMON_INFO="$(git -C "$SOURCE" rev-parse --path-format=absolute --git-common-dir 2>/dev/null || printf '%s' "$SOURCE/.git")/info"
mkdir -p "$COMMON_INFO" 2>/dev/null || true
for entry in '.mvn/maven.config' '.m2/'; do
  grep -qxF "$entry" "$COMMON_INFO/exclude" 2>/dev/null \
    || printf '%s\n' "$entry" >> "$COMMON_INFO/exclude" 2>/dev/null || true
done
add DONE '"info/exclude"'

if [ "$ADOPT" = true ]; then
  mkdir -p "$WORKTREE/.m2/repository" 2>/dev/null || true
  printf '%s\n' "afk: adopting the Maven repository already at $WORKTREE/.m2/repository" >&2
  answer; exit 0
fi

mkdir -p "$WORKTREE/.m2/repository" "$WORKTREE/.mvn" || fail "cannot create $WORKTREE/.mvn"
# Append, never truncate: any other flag already in the file is the developer's.
printf -- '%s\n' "$REPO_LINE" >> "$MAVEN_CONFIG" || fail "cannot write $MAVEN_CONFIG"
add DONE '"maven.config"'
printf '%s\n' "afk: private Maven repository at $WORKTREE_NATIVE/.m2/repository" >&2

# ---- seed
if [ "$SEED" = none ]; then
  add SKIPPED '{"step":"seed","reason":"maven.worktree-seed is none"}'
  answer; exit 0
fi

SEED_SRC="$SEED"
if [ "$SEED" = auto ]; then
  SEED_SRC="$HOME/.m2/repository"
  if [ -f "$HOME/.m2/settings.xml" ]; then
    CUSTOM=$(sed -n 's/.*<localRepository>[[:space:]]*\(.*[^[:space:]]\)[[:space:]]*<\/localRepository>.*/\1/p' \
      "$HOME/.m2/settings.xml" 2>/dev/null | head -1)
    [ -n "${CUSTOM:-}" ] && SEED_SRC="$CUSTOM"
  fi
fi
if [ ! -d "$SEED_SRC" ]; then
  add SKIPPED "{\"step\":\"seed\",\"reason\":\"no repository at $(quoted "$SEED_SRC"); the private one starts empty\"}"
  answer; exit 0
fi

printf '%s\n' "afk: seeding from $SEED_SRC (excluding $EXCLUDES)" >&2
seed_rc=0
if command -v robocopy >/dev/null 2>&1; then
  # Git-Bash rewrites /E-style switches into paths without these; robocopy
  # exit codes below 8 all mean success.
  # shellcheck disable=SC2086
  set -- "$(cygpath -w "$SEED_SRC")" "$(cygpath -w "$WORKTREE/.m2/repository")" /E
  for glob in $(printf '%s' "$EXCLUDES" | tr ',' ' '); do set -- "$@" /XD "$glob"; done
  set -- "$@" /MT:16 /R:0 /W:0 /NFL /NDL /NJH /NJS /NP
  MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*' robocopy "$@" >/dev/null 2>&1 || seed_rc=$?
  [ "$seed_rc" -lt 8 ] && seed_rc=0
else
  cp -a "$SEED_SRC/." "$WORKTREE/.m2/repository/" 2>/dev/null || seed_rc=1
  if [ "$seed_rc" -eq 0 ]; then
    for glob in $(printf '%s' "$EXCLUDES" | tr ',' ' '); do
      find "$WORKTREE/.m2/repository" -type d -name "$glob" -prune -exec rm -rf {} + 2>/dev/null || true
    done
  fi
fi

if [ "$seed_rc" -eq 0 ]; then
  add DONE '"seed"'
  answer; exit 0
fi
# A failed seed is not a failed provision: the worktree is isolated either way
# and Maven downloads what it needs.
add WARNINGS '"seed copy failed; the private repository is empty and Maven will download on demand"'
answer; exit 4
