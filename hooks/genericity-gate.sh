#!/usr/bin/env bash
# Stop hook (ships with the afk plugin): genericity gate — prose added to this
# plugin's *.md files must stay generic, never feature- or incident-specific.
# The doctrine (plugin CLAUDE.md "generic, never feature-specific") existed and
# was still violated by an agent hardening the harness after an incident —
# instruction alone demonstrably isn't enough, hence enforcement.
#
# Checks ADDED lines of changed/untracked plugin .md files for:
#   1. Jira-shaped ticket IDs   (PREFIX-123) outside the notation allowlist
#   2. source-file references   (`Foo.vue` / `Foo.java` / `Foo.ts` ...) that
#      resolve to a tracked product file under 11700-payable (verification/
#      infra excluded — those are legitimate harness references)
#   3. backticked CamelCase tokens naming a product class (same resolution)
#
# Verdict:
#   no changed plugin .md                      -> silent pass (scope no-op)
#   added lines clean                          -> pass
#   any hit not in hooks/genericity-allow.txt  -> exit 2, listing file:token
#
# Deliberate references (e.g. the plugin's own parent ticket) go in
# hooks/genericity-allow.txt — one exact token per line, comment with reason.
# Disable: GENERICITY_GATE_DISABLE=1, or repo file .claude/hooks/.gate-disabled.

set -u

[ "${GENERICITY_GATE_DISABLE:-0}" = "1" ] && exit 0

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

repo_root=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
cd "$repo_root" || exit 0

[ -f .claude/hooks/.gate-disabled ] && exit 0

PLUGIN_DIR="tools/payable/ai-agents/plugins/workflow"
[ -d "$PLUGIN_DIR/skills" ] || exit 0   # not this plugin's checkout

# ---- scope: plugin .md files changed vs upstream (committed-unpushed + worktree) or untracked
upstream=$(git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null || true)
[ -z "$upstream" ] && git rev-parse --verify -q origin/master >/dev/null 2>&1 && upstream=origin/master
[ -z "$upstream" ] && upstream=HEAD

base=$(git merge-base "$upstream" HEAD 2>/dev/null || echo HEAD)
changed_md=$(
  { git diff --name-only "$base" -- "$PLUGIN_DIR/*.md" "$PLUGIN_DIR/**/*.md" 2>/dev/null
    git ls-files --others --exclude-standard -- "$PLUGIN_DIR" 2>/dev/null | grep -E '\.md$'
  } | sort -u
)
[ -z "$changed_md" ] && exit 0   # scope no-op

. "$SCRIPT_DIR/gate-metrics.sh"
gate_metrics_begin

ALLOW_FILE="$PLUGIN_DIR/hooks/genericity-allow.txt"
allow_tokens=""
[ -f "$ALLOW_FILE" ] && allow_tokens=$(grep -vE '^\s*(#|$)' "$ALLOW_FILE" | awk '{print $1}')

is_allowed() { printf '%s\n' "$allow_tokens" | grep -Fxq -- "$1"; }

# Internal notation prefixes that are NOT Jira tickets (ADRs, acceptance
# criteria, user stories, render points, preflight steps, encodings, specs).
NOTATION_PREFIXES='ADR|AC|US|RP|PF|UTF|RFC|ISO|JEP|JDK|HHH'

# ---- product-symbol universe (tracked source under 11700-payable, minus the
# verification harness the plugin legitimately documents)
prod_files=$(git ls-files '11700-payable/*' ':!11700-payable/verification/*' 2>/dev/null \
  | grep -E '\.(java|vue|ts|tsx|js|mjs)$' | sed 's#.*/##' | sort -u)
prod_classes=$(printf '%s\n' "$prod_files" | sed 's/\.[a-z]*$//' | sort -u)

violations=""

while IFS= read -r f; do
  [ -f "$f" ] || continue
  if git ls-files --error-unmatch -- "$f" >/dev/null 2>&1; then
    added=$(git diff -U0 "$base" -- "$f" 2>/dev/null | grep '^+' | grep -v '^+++' | cut -c2-)
  else
    added=$(cat "$f")
  fi
  [ -z "$added" ] && continue

  # 1. ticket IDs
  while IFS= read -r tok; do
    [ -z "$tok" ] && continue
    prefix=${tok%%-*}
    printf '%s' "$prefix" | grep -qE "^($NOTATION_PREFIXES)$" && continue
    is_allowed "$tok" && continue
    violations="$violations$f: ticket ID \`$tok\`\n"
  done <<EOF
$(printf '%s\n' "$added" | grep -oE '\b[A-Z][A-Z0-9]{1,9}-[0-9]{1,6}\b' | sort -u)
EOF

  # 2. source-file references resolving to product files
  while IFS= read -r tok; do
    [ -z "$tok" ] && continue
    printf '%s\n' "$prod_files" | grep -Fxq -- "$tok" || continue
    is_allowed "$tok" && continue
    violations="$violations$f: product source file \`$tok\`\n"
  done <<EOF
$(printf '%s\n' "$added" | grep -oE '\b[A-Za-z][A-Za-z0-9_]*\.(vue|java|ts|tsx|js|mjs)\b' | sort -u)
EOF

  # 3. backticked CamelCase tokens naming a product class
  while IFS= read -r tok; do
    [ -z "$tok" ] && continue
    printf '%s\n' "$prod_classes" | grep -Fxq -- "$tok" || continue
    is_allowed "$tok" && continue
    violations="$violations$f: product class \`$tok\`\n"
  done <<EOF
$(printf '%s\n' "$added" | grep -oE '`[A-Z][A-Za-z0-9]*`' | tr -d '\`' | sort -u)
EOF
done <<EOF2
$changed_md
EOF2

if [ -n "$violations" ]; then
  gate_metrics_emit genericity blocked
  {
    echo "Genericity gate: plugin prose must stay generic — never feature- or incident-specific."
    echo "Added lines reference concrete tickets/product symbols:"
    printf '%b' "$violations" | sort -u
    echo
    echo "Fix: restate the rule in terms of the mechanism/pattern class, not the instance that"
    echo "motivated it. If a reference is deliberate (plugin's own ticket, a format example),"
    echo "add the exact token to $ALLOW_FILE with a reason comment."
  } >&2
  exit 2
fi

gate_metrics_emit genericity pass
exit 0
