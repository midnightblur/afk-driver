#!/usr/bin/env bash
# build-gate/npm — the `worktree-provision` operation.
#
# A fresh worktree has no `node_modules`, so every UI command in it fails until
# something restores the dependencies. This runs the repository's own install
# command in its workspace root, and only when there is a lockfile there to
# install from.
#
#   bash worktree-provision.sh '<json>'
#
# JSON: {"source":…,"worktree":…,"worktree_native":…,"dry_run":false}
# Answer: one JSON object on stdout; progress on stderr.
# Exit: 0 provisioned/adopted/skipped, 2 invalid input, 4 the install failed.

set -u

json_field() {
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

fail() { printf '%s\n' "afk: build-gate/npm worktree-provision: $1" >&2; exit 2; }

PAYLOAD=${1:-}
[ -n "$PAYLOAD" ] || fail "no JSON payload on argv[1]"
SOURCE=$(json_field "$PAYLOAD" source)
WORKTREE=$(json_field "$PAYLOAD" worktree)
DRY_RUN=$(json_field "$PAYLOAD" dry_run)
[ -n "$SOURCE" ] && [ -n "$WORKTREE" ] || fail "payload needs source and worktree"
[ -d "$WORKTREE" ] || fail "worktree does not exist: $WORKTREE"
git -C "$WORKTREE" rev-parse --git-dir >/dev/null 2>&1 \
  || fail "not a git worktree: $WORKTREE"

INSTALL=${AFK_CFG_NPM_WORKTREE_INSTALL:-ci}
WORKSPACE_ROOT=${AFK_CFG_NPM_WORKSPACE_ROOT:-.}
COMMAND=""
count=${AFK_CFG_NPM_WORKTREE_COMMAND_COUNT:-}
if [ -n "$count" ]; then
  i=0
  while [ "$i" -lt "$count" ]; do
    eval "word=\${AFK_CFG_NPM_WORKTREE_COMMAND_$i}"
    COMMAND="$COMMAND${COMMAND:+ }$word"
    i=$((i + 1))
  done
fi
[ -n "$COMMAND" ] || COMMAND="npm ci"

ROOT="$WORKTREE/$WORKSPACE_ROOT"
LOCK="$ROOT/package-lock.json"
SENTINEL="$ROOT/node_modules/.package-lock.json"

# The fingerprint covers the command, where it runs, and the lockfile it
# installs from — a change to any of them makes the existing node_modules stale.
LOCK_HASH=none
[ -f "$LOCK" ] && LOCK_HASH=$("${AFK_PY:-python}" -c '
import hashlib, sys
print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest(), end="")' "$LOCK" 2>/dev/null)
FINGERPRINT=$(printf '%s\n%s\n%s\n%s\n' "$INSTALL" "$COMMAND" "$WORKSPACE_ROOT" "$LOCK_HASH" \
  | "${AFK_PY:-python}" -c 'import hashlib,sys; print(hashlib.sha256(sys.stdin.buffer.read()).hexdigest(), end="")')

DONE=""; SKIPPED=""; WARNINGS=""; STATUS=provisioned
add() { local var=$1 item=$2; eval "$var=\"\${$var}\${$var:+,}\$item\""; }
# A Windows path carries backslashes, and an unescaped one makes the answer
# invalid JSON — the caller then reads no status at all. Backslash first.
quoted() { printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g'; }
answer() {
  printf '{"kind":"npm","status":"%s","fingerprint":"%s","done":[%s],"skipped":[%s],"warnings":[%s]}\n' \
    "$STATUS" "$FINGERPRINT" "$DONE" "$SKIPPED" "$WARNINGS"
}

if [ "$INSTALL" = none ]; then
  STATUS=skipped
  add SKIPPED '{"step":"install","reason":"npm.worktree-install is none"}'
  answer; exit 0
fi
if [ ! -f "$LOCK" ]; then
  STATUS=skipped
  add SKIPPED "{\"step\":\"install\",\"reason\":\"no package-lock.json at $(quoted "$WORKSPACE_ROOT")\"}"
  answer; exit 0
fi

# Adoption: npm writes .package-lock.json into node_modules after an install, so
# a copy of it newer than the lockfile is npm's own statement that the tree is
# current. Documented in CONTRACT.md because it is npm's sentinel, not ours.
if [ -f "$SENTINEL" ] && [ ! "$SENTINEL" -ot "$LOCK" ]; then
  STATUS=adopted
  add DONE '"adopted existing node_modules"'
  printf '%s\n' "afk: node_modules at $ROOT is current for its lockfile — adopting" >&2
  answer; exit 0
fi

if [ "$DRY_RUN" = true ]; then
  add DONE '"fingerprint"'
  answer; exit 0
fi

printf '%s\n' "afk: running '$COMMAND' in $ROOT" >&2
install_rc=0
( cd "$ROOT" && $COMMAND ) >&2 || install_rc=$?
if [ "$install_rc" -eq 0 ]; then
  add DONE '"install"'
  answer; exit 0
fi
# The worktree is usable without dependencies; the human runs the install again.
add WARNINGS "\"$(quoted "$COMMAND") failed in $(quoted "$WORKSPACE_ROOT"); run it by hand\""
answer; exit 4
