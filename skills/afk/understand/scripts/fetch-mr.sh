#!/usr/bin/env bash
# Fetch a GitLab MR's metadata + diff into $CLAUDE_JOB_DIR.
# Usage: fetch-mr.sh <MR_URL>
# Outputs: $CLAUDE_JOB_DIR/mr.json, $CLAUDE_JOB_DIR/mr.diff
# Exits non-zero with a clear message on failure.

set -euo pipefail

URL="${1:-}"
if [[ -z "$URL" ]]; then
  echo "usage: $0 <MR_URL>" >&2
  exit 2
fi

if ! command -v glab >/dev/null 2>&1; then
  echo "glab not found on PATH. Install: https://gitlab.com/gitlab-org/cli" >&2
  exit 3
fi

OUT="${CLAUDE_JOB_DIR:-/tmp}"
mkdir -p "$OUT"

# Parse GitLab URL -> repo path + iid so glab works outside a git repo
# (glab 1.89 falls back to git autodetect when given a URL only — fails w/
# "not a git repository". Passing -R <repo> + <iid> bypasses autodetect.)
REPO_ARG=()
REF="$URL"
if [[ "$URL" =~ ^https?://[^/]+/(.+)/-/merge_requests/([0-9]+) ]]; then
  REPO="${BASH_REMATCH[1]}"
  IID="${BASH_REMATCH[2]}"
  REPO_ARG=(-R "$REPO")
  REF="$IID"
fi

if ! glab mr view "$REF" "${REPO_ARG[@]}" -F json > "$OUT/mr.json" 2> "$OUT/mr.err"; then
  echo "glab mr view failed:" >&2
  cat "$OUT/mr.err" >&2
  if grep -qi "auth" "$OUT/mr.err"; then
    echo "Hint: run 'glab auth login' (or 'glab auth status' to check)." >&2
  fi
  exit 4
fi

glab mr diff "$REF" "${REPO_ARG[@]}" --color=never > "$OUT/mr.diff" 2>> "$OUT/mr.err" || {
  echo "glab mr diff failed (see $OUT/mr.err)" >&2
  exit 5
}

LINES=$(wc -l < "$OUT/mr.diff")
SIZE=$(wc -c < "$OUT/mr.diff")
echo "OK: mr.json + mr.diff written to $OUT (${LINES} diff lines, ${SIZE} bytes)"
