#!/usr/bin/env bash
# Release gate: one version, stated in four places, all agreeing.
#
#   bash hooks/release-gate.sh v1.0.0
#
# A release is a tag, and three files claim a version of their own. If any of
# them drifts, an installed plugin reports a version it is not, and the update
# notice compares against a lie. So the gate is an equality check:
#
#   the tag argument (leading `v` optional)
#     == .claude-plugin/plugin.json      "version"
#     == .codex-plugin/plugin.json       "version"
#     == .claude-plugin/marketplace.json plugins[name == the plugin] .version
#     == CHANGELOG.md's FIRST released heading after `## [Unreleased]`
#
# The changelog heading is part of the equality on purpose: a release with no
# entry is a release nobody can read.
#
# Exit 0 all four agree; exit 2 with the disagreement named; exit 1 on usage.
set -uo pipefail

ROOT=${AFK_PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}
PY=python
command -v python >/dev/null 2>&1 || PY=python3

TAG=${1:-}
if [ -z "$TAG" ]; then
  echo "usage: release-gate.sh <tag>   e.g. release-gate.sh v1.0.0" >&2
  exit 1
fi
VERSION=${TAG#v}

if ! printf '%s' "$VERSION" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+([-+][0-9A-Za-z.-]+)?$'; then
  echo "release-gate: '$TAG' is not a SemVer tag (expected vMAJOR.MINOR.PATCH)" >&2
  exit 1
fi

json_version() {   # json_version <file> <jq-ish path: "version" | "marketplace">
  "$PY" - "$1" "$2" <<'PYEOF'
import json, sys
path, mode = sys.argv[1], sys.argv[2]
try:
    doc = json.load(open(path, encoding="utf-8"))
except Exception as exc:                       # a malformed manifest is a finding
    print("", end="")
    sys.exit(0)
if mode == "marketplace":
    for entry in doc.get("plugins", []):
        if entry.get("name") == doc.get("name"):
            print(entry.get("version", ""), end="")
            break
else:
    print(doc.get("version", ""), end="")
PYEOF
}

# The first released heading after `## [Unreleased]`, in keep-a-changelog form
# `## [1.0.0] - 2026-09-03`. Anything before Unreleased is a malformed file.
changelog_version() {
  awk '
    /^## \[Unreleased\]/ { seen = 1; next }
    seen && /^## \[/ {
      line = $0
      sub(/^## \[/, "", line)
      sub(/\].*$/, "", line)
      print line
      exit
    }
  ' "$ROOT/CHANGELOG.md" 2>/dev/null
}

CLAUDE_V=$(json_version "$ROOT/.claude-plugin/plugin.json" version)
CODEX_V=$(json_version "$ROOT/.codex-plugin/plugin.json" version)
MARKET_V=$(json_version "$ROOT/.claude-plugin/marketplace.json" marketplace)
CHANGE_V=$(changelog_version)

fail=""
check() {   # check <label> <found>
  [ "$2" = "$VERSION" ] && return 0
  fail="$fail  $1: ${2:-<none>} (tag says $VERSION)"$'\n'
}

check ".claude-plugin/plugin.json" "$CLAUDE_V"
check ".codex-plugin/plugin.json" "$CODEX_V"
check ".claude-plugin/marketplace.json" "$MARKET_V"
check "CHANGELOG.md first released heading" "$CHANGE_V"

if [ -n "$fail" ]; then
  {
    echo "release-gate: the release version does not agree across the tree."
    printf '%s' "$fail"
    echo "Fix the disagreeing file, then re-run. A tag is never moved to match a file."
  } >&2
  exit 2
fi

echo "release-gate: $TAG — plugin.json (both harnesses), marketplace.json and CHANGELOG.md all say $VERSION"
