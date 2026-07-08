#!/usr/bin/env bash
# Stop hook (ships with the afk plugin): wiring gate — every new artifact must
# have a consumer or a declared IOU.
#
# Failure class this catches: producer-without-consumer (a file/class/log written
# by one change with no reader anywhere — locally correct, dead at the seam).
#
# Verdict per NEW file (working tree + commits not yet on upstream):
#   wired   — some other file references its name token           -> pass
#   pending — no referrer, but an open IOU with an anchor exists  -> pass (blocks in final mode)
#   orphan  — no referrer, no IOU                                 -> exit 2 (wire it or add an IOU)
#
# Ledger (per repo, created on first IOU): .claude/wiring-ious.md
#   - [ ] `path/to/artifact` -> anchor: <plan step | ticket | contract "X will call Y">
#   - [x] `path` ...                    # auto-closed by this gate when a referrer appears
#   waive: `path` — <reason>            # permanent silence (build junk etc.)
#
# Mechanical only: zero-referrer detection. Weak-consumer judgment (test-only
# consumers, unreachable flows) belongs to /afk:verify-seams, not this gate.
# Final mode: WIRING_FINAL=1 bash wiring-gate.sh  -> open IOUs block.
# Disable: WIRING_GATE_DISABLE=1, or repo file .claude/hooks/.gate-disabled.

set -u

[ "${WIRING_GATE_DISABLE:-0}" = "1" ] && exit 0

repo_root=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
cd "$repo_root" || exit 0

if [ -f .claude/hooks/.gate-disabled ]; then
  exit 0
fi

LEDGER=.claude/wiring-ious.md
FINAL=${WIRING_FINAL:-0}

# ---- collect NEW files: working tree adds/untracked + commits ahead of upstream
worktree_new=$(
  git status --porcelain -uall 2>/dev/null \
    | awk '/^(A[ MD]|\?\?)/ {print $NF}'
)
upstream=$(git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null || true)
[ -z "$upstream" ] && git rev-parse --verify -q origin/master >/dev/null 2>&1 && upstream=origin/master
committed_new=""
if [ -n "$upstream" ]; then
  committed_new=$(git diff --name-only --diff-filter=A "$upstream"...HEAD 2>/dev/null || true)
fi

new_files=$(printf '%s\n%s\n' "$worktree_new" "$committed_new" | sed '/^$/d' | sort -u)
[ -z "$new_files" ] && exit 0

. "$(dirname "${BASH_SOURCE[0]}")/gate-metrics.sh"
gate_metrics_begin
n_new=$(printf '%s\n' "$new_files" | wc -l | tr -d '[:space:]')

# ---- ledger helpers
ledger_open() {   # 0 if an open IOU exists for $1
  [ -f "$LEDGER" ] && grep -qF -- "- [ ] \`$1\`" "$LEDGER"
}
ledger_waived() { # 0 if $1 is waived
  [ -f "$LEDGER" ] && grep -qF -- "waive: \`$1\`" "$LEDGER"
}
ledger_close() {  # flip open IOU for $1 to closed
  local esc
  esc=$(printf '%s' "$1" | sed 's/[&/\]/\\&/g')
  sed -i "s/- \[ \] \`$esc\`/- [x] \`$esc\`/" "$LEDGER" 2>/dev/null
}

# Filenames consumed by convention (framework/tooling reads them by name/location).
conventional() {
  case "$(basename "$1")" in
    README*|CLAUDE.md|GLOSSARY.md|SKILL.md|MEMORY.md|pom.xml|package.json|package-lock.json|\
    .gitignore|.gitattributes|Dockerfile|Jenkinsfile|VERSION|*.feature) return 0 ;;
  esac
  case "$1" in
    */src/main/resources/application*|*/src/test/resources/*|*logback*.xml|*log4j*|\
    */db/migration/*|*/target/*|*/node_modules/*|*/dist/*|*/.idea/*|.claude/*|*.iml|\
    */specs/*) return 0 ;;
  esac
  case "$(basename "$1")" in
    *Test.java|*IT.java|*.approved.json|*.approved.txt) return 0 ;;
  esac
  return 1
}

# Java classes wired by the framework without a textual reference.
framework_wired() {
  case "$1" in
    *.java)
      head -c 8192 "$1" 2>/dev/null | grep -qE '@(RestController|Controller|Configuration|ControllerAdvice|RestControllerAdvice|SpringBootApplication|AutoService|Aspect|WebFilter)\b'
      ;;
    *) return 1 ;;
  esac
}

orphans=""
pending=""
while IFS= read -r f; do
  [ -f "$f" ] || continue
  conventional "$f" && continue
  grep -Iq . "$f" 2>/dev/null || continue          # skip binaries
  framework_wired "$f" && continue

  base=$(basename "$f")
  token="${base%.*}"
  [ "${#token}" -lt 4 ] && continue                # too generic to grep meaningfully

  refs=$(git grep -l --untracked -F "$token" -- ":(exclude)$f" ":(exclude)$LEDGER" ":(exclude).claude/hooks/*" 2>/dev/null | head -1)
  if [ -n "$refs" ]; then
    ledger_open "$f" && ledger_close "$f"          # consumer arrived -> auto-close IOU
    continue
  fi

  ledger_waived "$f" && continue
  if ledger_open "$f"; then
    pending="$pending$f"$'\n'
    continue
  fi
  orphans="$orphans$f"$'\n'
done <<EOF
$new_files
EOF

if [ -n "$orphans" ]; then
  gate_metrics_emit wiring blocked "\"new_files\":$n_new"
  {
    printf '[afk] Wiring gate: new artifact(s) with NO consumer and NO IOU — cannot finish.\n'
    printf 'Orphans:\n'
    printf '%s' "$orphans" | sed 's/^/  - /'
    printf '\nFor each: either wire a real consumer now, or declare the expected one in %s:\n' "$LEDGER"
    printf '  - [ ] `path/to/artifact` -> anchor: <plan step / ticket / contract "X will call Y">\n'
    printf 'The anchor must be concrete (a named step, ticket, or a symbol of yours the consumer will call).\n'
    printf '"Will be used later" with no anchor does not qualify. Junk files: waive: `path` — <reason>\n'
  } >&2
  exit 2
fi

if [ "$FINAL" = "1" ] && [ -n "$pending" ]; then
  gate_metrics_emit wiring blocked "\"new_files\":$n_new,\"detail\":\"final: open IOUs\""
  {
    printf '[afk] Wiring gate (FINAL): open IOUs remain — consumers never arrived.\n'
    printf '%s' "$pending" | sed 's/^/  - /'
    printf 'Each must be wired, re-anchored with justification, or explicitly waived before shipping.\n'
  } >&2
  exit 2
fi

gate_metrics_emit wiring pass "\"new_files\":$n_new"
exit 0
