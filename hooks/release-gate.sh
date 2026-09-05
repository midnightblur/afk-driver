#!/usr/bin/env bash
# Release gate: one version, stated in four places, all agreeing.
#
#   bash hooks/release-gate.sh v1.0.0
#
# A release is a tag, and four files claim a version of their own. If any of
# them drifts, an installed plugin reports a version it is not, and the update
# notice compares against a lie. So the gate is an equality check:
#
#   the tag argument (leading `v` optional)
#     == .claude-plugin/plugin.json      "version"
#     == .codex-plugin/plugin.json       "version"
#     == .claude-plugin/marketplace.json plugins[name == plugin.json's name] .version
#     == CHANGELOG.md's FIRST released heading after `## [Unreleased]`
#     == .afk/config.yaml                `toolkit-version`
#
# The changelog heading is part of the equality on purpose: a release with no
# entry is a release nobody can read. So is this plugin's own `.afk/config.yaml`:
# it is the reference every consuming repository copies, and a repository reads
# `toolkit-version` as the version it was configured against.
#
# Exit 0 all five agree; exit 2 with the disagreement named; exit 1 on usage.
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

json_version() {   # json_version <file> <mode: "version" | "marketplace"> [plugin name]
  "$PY" - "$1" "$2" "${3:-}" <<'PYEOF'
import json, sys
path, mode, plugin = sys.argv[1], sys.argv[2], sys.argv[3]
try:
    doc = json.load(open(path, encoding="utf-8"))
except Exception:                              # a malformed manifest is a finding
    print("", end="")
    sys.exit(0)
if mode == "marketplace":
    # The plugin's name, not the marketplace's — one marketplace may carry a
    # plugin under a different name, and this one does.
    entries = doc.get("plugins", [])
    match = [e for e in entries if e.get("name") == plugin] or (entries if len(entries) == 1 else [])
    if match:
        print(match[0].get("version", ""), end="")
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
PLUGIN_NAME=$("$PY" -c 'import json,sys;print(json.load(open(sys.argv[1],encoding="utf-8")).get("name",""),end="")' "$ROOT/.claude-plugin/plugin.json" 2>/dev/null)
MARKET_V=$(json_version "$ROOT/.claude-plugin/marketplace.json" marketplace "$PLUGIN_NAME")
CHANGE_V=$(changelog_version)
CONFIG_V=$(awk -F'[:#]' '/^toolkit-version:/ {
    gsub(/^[ \t]+|[ \t]+$/, "", $2); gsub(/^["\047]|["\047]$/, "", $2); print $2; exit
  }' "$ROOT/.afk/config.yaml" 2>/dev/null)

fail=""
check() {   # check <label> <found>
  [ "$2" = "$VERSION" ] && return 0
  fail="$fail  $1: ${2:-<none>} (tag says $VERSION)"$'\n'
}

check ".claude-plugin/plugin.json" "$CLAUDE_V"
check ".codex-plugin/plugin.json" "$CODEX_V"
check ".claude-plugin/marketplace.json" "$MARKET_V"
check "CHANGELOG.md first released heading" "$CHANGE_V"
check ".afk/config.yaml toolkit-version" "$CONFIG_V"

if [ -n "$fail" ]; then
  {
    echo "release-gate: the release version does not agree across the tree."
    printf '%s' "$fail"
    echo "Fix the disagreeing file, then re-run. A tag is never moved to match a file."
  } >&2
  exit 2
fi

echo "release-gate: $TAG — plugin.json (both harnesses), marketplace.json, CHANGELOG.md and .afk/config.yaml all say $VERSION"
