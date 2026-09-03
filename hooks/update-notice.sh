#!/usr/bin/env bash
# SessionStart notice: a newer release exists, and here is what is in it.
#
# Run with `--soft`: it must never block, never slow a session start, and never
# need a dependency the toolkit does not already require. Every failure path —
# no network, no remote, no `git`, a slow server, a malformed answer — exits 0
# in silence. A session that starts a beat later is worse than a missed notice.
#
# Two steps, each budgeted 2 seconds and each cached 24 hours in the plugin data
# directory:
#
#   1. the highest SemVer tag the origin repository has
#      (`git ls-remote --tags`), compared with the installed plugin.json version
#   2. only when step 1 says a newer version exists: that tag's CHANGELOG.md,
#      fetched WITHOUT cloning — `git archive --remote`, falling back to a raw
#      HTTPS read — of which only the sections newer than the installed version
#      are printed
#
# The cache holds the tag result and the fetched changelog, so a session inside
# the 24-hour window costs one file read.
set -uo pipefail

ROOT=${AFK_PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}
PY=python
command -v python >/dev/null 2>&1 || PY=python3
command -v git >/dev/null 2>&1 || exit 0

# shellcheck source=/dev/null
. "$ROOT/hooks/lib/provider.sh" 2>/dev/null || exit 0

CACHE_DIR="$(afk_plugin_data 2>/dev/null)"
[ -n "$CACHE_DIR" ] || exit 0
mkdir -p "$CACHE_DIR/update-notice" 2>/dev/null || exit 0
TAG_CACHE="$CACHE_DIR/update-notice/latest-tag"
LOG_CACHE="$CACHE_DIR/update-notice/changelog"

fresh() {   # fresh <file> — modified inside the last 24 hours
  [ -f "$1" ] || return 1
  local now age
  now=$(date +%s 2>/dev/null) || return 1
  age=$("$PY" -c 'import os,sys; print(int(os.path.getmtime(sys.argv[1])))' "$1" 2>/dev/null) || return 1
  [ $((now - age)) -lt 86400 ]
}

INSTALLED=$("$PY" -c 'import json,sys; print(json.load(open(sys.argv[1],encoding="utf-8")).get("version",""))' \
  "$ROOT/.claude-plugin/plugin.json" 2>/dev/null) || exit 0
[ -n "$INSTALLED" ] || exit 0

REMOTE=$(git -C "$ROOT" remote get-url origin 2>/dev/null) || exit 0
[ -n "$REMOTE" ] || exit 0

# ---- step 1: the highest SemVer tag on the origin -------------------------
if fresh "$TAG_CACHE"; then
  LATEST=$(cat "$TAG_CACHE" 2>/dev/null)
else
  LATEST=$(timeout 2 git ls-remote --tags "$REMOTE" 2>/dev/null \
    | sed -n 's|.*refs/tags/v\([0-9][0-9.]*\)$|\1|p' \
    | "$PY" -c '
import sys
def key(v):
    try:
        return tuple(int(p) for p in v.strip().split("."))
    except ValueError:
        return ()
vs = [v.strip() for v in sys.stdin if v.strip() and key(v)]
print(max(vs, key=key) if vs else "", end="")
' 2>/dev/null) || LATEST=""
  printf '%s' "$LATEST" >"$TAG_CACHE" 2>/dev/null || true
fi
[ -n "$LATEST" ] || exit 0

newer=$("$PY" -c '
import sys
def key(v):
    try:
        return tuple(int(p) for p in v.split("."))
    except ValueError:
        return ()
a, b = key(sys.argv[1]), key(sys.argv[2])
print("1" if a and b and a > b else "0", end="")
' "$LATEST" "$INSTALLED" 2>/dev/null) || exit 0
[ "$newer" = "1" ] || exit 0

# ---- step 2: that tag's changelog, without cloning -------------------------
if fresh "$LOG_CACHE"; then
  BODY=$(cat "$LOG_CACHE" 2>/dev/null)
else
  BODY=$(timeout 2 git archive --remote="$REMOTE" "v$LATEST" CHANGELOG.md 2>/dev/null | tar -xO 2>/dev/null) || BODY=""
  if [ -z "$BODY" ]; then
    case "$REMOTE" in
      *github.com*)
        RAW=$(printf '%s' "$REMOTE" \
          | sed -e 's|git@github.com:|https://raw.githubusercontent.com/|' \
                -e 's|https://github.com/|https://raw.githubusercontent.com/|' \
                -e 's|\.git$||')
        BODY=$(curl -fsS -m 2 "$RAW/v$LATEST/CHANGELOG.md" 2>/dev/null) || BODY="" ;;
    esac
  fi
  [ -n "$BODY" ] && printf '%s' "$BODY" >"$LOG_CACHE" 2>/dev/null
fi

SECTIONS=$(printf '%s' "$BODY" | "$PY" -c '
import re, sys
installed = sys.argv[1]
def key(v):
    try:
        return tuple(int(p) for p in v.split("."))
    except ValueError:
        return ()
base = key(installed)
out, keep = [], False
for line in sys.stdin.read().splitlines():
    m = re.match(r"^## \[([0-9][0-9.]*)\]", line)
    if m:
        keep = bool(base) and key(m.group(1)) > base
    elif line.startswith("## "):
        keep = False
    if keep:
        out.append(line)
print("\n".join(out).strip(), end="")
' "$INSTALLED" 2>/dev/null) || SECTIONS=""

printf 'afk-toolkit %s is out (you have %s).\n' "$LATEST" "$INSTALLED"
[ -n "$SECTIONS" ] && printf '%s\n' "$SECTIONS"
exit 0
