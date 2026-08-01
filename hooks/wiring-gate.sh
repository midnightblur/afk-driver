#!/usr/bin/env bash
# Stop gate (ships with the afk plugin): wiring gate — every new artifact must
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
# Referrer search is ONE repo scan for ALL candidate tokens (`git grep -o` over
# the batch), not one scan per candidate — a scan is the gate's dominant cost and
# N of them is what made a many-new-file change unusable.
#
# Mechanical only: zero-referrer detection. Weak-consumer judgment (test-only
# consumers, unreachable flows) belongs to /afk:verify-seams, not this gate.
# Final mode: WIRING_FINAL=1 bash wiring-gate.sh  -> open IOUs block.
# Disable: WIRING_GATE_DISABLE=1, or repo file .claude/hooks/.gate-disabled.

set -u

WIRING_LEDGER=.claude/wiring-ious.md

# Filenames consumed by convention (framework/tooling reads them by name/location).
_wiring_conventional() {
  case "${1##*/}" in
    README*|CLAUDE.md|GLOSSARY.md|SKILL.md|MEMORY.md|pom.xml|package.json|package-lock.json|\
    .gitignore|.gitattributes|Dockerfile|Jenkinsfile|VERSION|*.feature) return 0 ;;
  esac
  case "$1" in
    */src/main/resources/application*|*/src/test/resources/*|*logback*.xml|*log4j*|\
    */db/migration/*|*/target/*|*/node_modules/*|*/dist/*|*/.idea/*|.claude/*|*.iml|\
    */specs/*) return 0 ;;
  esac
  # Design-chain artifacts: read by the skill chain by path/convention, never by
  # textual reference, and authored a stage BEFORE any consumer exists. Gating
  # them makes every interactive design turn report orphans it cannot fix.
  case "$1" in
    */PRD.md|*/SDD.md|*/TICKET.md|*/INDEX.md|*/GRILL-LOG.md|*/STAPLES.md|\
    */DESIGN-BRIEF.md|*/DEMO-PLAN.md|*/VERIFICATION-PLAN.md|*/JOURNAL.md|\
    */PLAN.md|*/TRACE.md|*/PATTERN-DEBT.md|\
    */plan/*.md|*/adr/*/*.md|*/adr/*.md|*/review/*) return 0 ;;
  esac
  case "${1##*/}" in
    *Test.java|*IT.java|*.approved.json|*.approved.txt) return 0 ;;
    # JS/TS tests — every runner (node --test, vitest, jest, cucumber) discovers by glob,
    # so a test file has zero textual referrers by construction.
    *.test.js|*.test.mjs|*.test.ts|*.test.tsx|\
    *.spec.js|*.spec.mjs|*.spec.ts|*.spec.tsx) return 0 ;;
  esac
  return 1
}

# Java classes wired by the framework without a textual reference.
_wiring_framework_wired() {
  case "$1" in
    *.java)
      head -c 8192 "$1" 2>/dev/null | grep -qE '@(RestController|Controller|Configuration|ControllerAdvice|RestControllerAdvice|SpringBootApplication|AutoService|Aspect|WebFilter)\b'
      ;;
    *) return 1 ;;
  esac
}

# Known-text extensions skip the per-file binary probe (a fork each).
_wiring_text_ext() {
  case "${1##*.}" in
    md|java|ts|tsx|js|mjs|cjs|vue|json|xml|yml|yaml|sh|py|txt|sql|html|css|scss|properties|toml|conf) return 0 ;;
  esac
  return 1
}

# Ledger membership is asked once per candidate, so the file is read ONCE and
# matched in-process — a grep per candidate is a fork per candidate.
_WIRING_LEDGER_BODY=""
_wiring_ledger_load()   { [ -f "$WIRING_LEDGER" ] && _WIRING_LEDGER_BODY=$(<"$WIRING_LEDGER"); return 0; }
_wiring_ledger_open()   { [[ "$_WIRING_LEDGER_BODY" == *"- [ ] \`$1\`"* ]]; }
_wiring_ledger_waived() { [[ "$_WIRING_LEDGER_BODY" == *"waive: \`$1\`"* ]]; }
_wiring_ledger_close()  {
  local esc
  esc=$(printf '%s' "$1" | sed 's/[&/\]/\\&/g')
  sed -i "s/- \[ \] \`$esc\`/- [x] \`$esc\`/" "$WIRING_LEDGER" 2>/dev/null
  _wiring_ledger_load
}

gate_wiring() {
  [ "${WIRING_GATE_DISABLE:-0}" = "1" ] && return 0
  [ -f .claude/hooks/.gate-disabled ] && return 0

  local FINAL=${WIRING_FINAL:-0}

  # ---- candidates: working-tree adds/untracked (from the shared context) plus
  # commits ahead of the integration base. 3-dot keeps a post-merge branch from
  # claiming every file master added since the divergence.
  local committed_new=""
  if [ -n "${AFK_CTX_BASE:-}" ] && [ "${AFK_CTX_BASE}" != "HEAD" ]; then
    committed_new=$(git diff --name-only --diff-filter=A "$AFK_CTX_BASE"...HEAD 2>/dev/null || true)
  fi

  local new_files
  new_files=$(printf '%s\n%s\n' "${AFK_CTX_NEW:-}" "$committed_new" | sort -u | sed '/^$/d')
  [ -z "$new_files" ] && return 0

  local cache_key=""
  if [ "$FINAL" != "1" ]; then
    cache_key=$(gate_cache_key wiring)
    gate_cache_hit wiring "$cache_key" && return 0
  fi

  gate_metrics_begin
  _wiring_ledger_load

  # ---- pass 1 (fork-light): drop everything that cannot be an orphan, and
  # collect the surviving name tokens for a single batched scan. Only fork-free
  # tests belong here — anything that spawns runs per CANDIDATE, and a long-lived
  # branch carries hundreds. The costly per-file probes wait for pass 3, where
  # they see only the handful of files the scan found no referrer for.
  local f tok n_new=0
  local -a cand_files=() cand_toks=()
  local -a grep_args=()
  while IFS= read -r f; do
    [ -n "$f" ] || continue
    n_new=$((n_new + 1))
    [ -f "$f" ] || continue
    _wiring_conventional "$f" && continue
    if ! _wiring_text_ext "$f"; then
      grep -Iq . "$f" 2>/dev/null || continue      # binary
    fi

    tok=${f##*/}; tok=${tok%.*}
    [ "${#tok}" -lt 4 ] && continue                # too generic to grep meaningfully
    cand_files+=("$f")
    cand_toks+=("$tok")
    grep_args+=(-e "$tok")
  done <<<"$new_files"

  if [ "${#cand_files[@]}" -eq 0 ]; then
    gate_metrics_emit wiring pass "\"new_files\":$n_new,\"candidates\":0"
    [ "$FINAL" != "1" ] && gate_cache_store wiring "$cache_key"
    return 0
  fi

  # ---- pass 2: ONE scan for every candidate token. -o makes each hit
  # "<path>:<token>", so a single pass tells us which token was seen in which
  # file — a token seen in any file other than its own artifact is wired.
  local hits
  hits=$(git grep -o -I --untracked -F "${grep_args[@]}" -- \
           ":(exclude)$WIRING_LEDGER" ":(exclude).claude/hooks/*" 2>/dev/null | sort -u)

  # Fold the scan output into a token lookup in ONE pass. Re-walking the hit list
  # per candidate is O(candidates x hits) AND re-materialises the here-string
  # every candidate — on a branch with a hundred-odd new files that dominates
  # even the repo scan. Per token we keep the first hit path and whether a second
  # DISTINCT one exists, which is all "referenced by something other than itself"
  # needs, and stays exact when two new files share a basename.
  local -A hit_first=() hit_many=()
  local i line hit_path hit_tok wired
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    hit_tok=${line##*:}
    hit_path=${line%:*}
    if [ -z "${hit_first[$hit_tok]:-}" ]; then
      hit_first[$hit_tok]=$hit_path
    elif [ "${hit_first[$hit_tok]}" != "$hit_path" ]; then
      hit_many[$hit_tok]=1
    fi
  done <<<"$hits"

  local orphans="" pending=""
  for i in "${!cand_files[@]}"; do
    f=${cand_files[$i]}; tok=${cand_toks[$i]}
    wired=0
    if [ -n "${hit_many[$tok]:-}" ]; then
      wired=1                                     # seen in 2+ files: one is not itself
    elif [ -n "${hit_first[$tok]:-}" ] && [ "${hit_first[$tok]}" != "$f" ]; then
      wired=1                                     # sole hit is somewhere other than itself
    fi

    if [ "$wired" = "1" ]; then
      _wiring_ledger_open "$f" && _wiring_ledger_close "$f"   # consumer arrived -> auto-close IOU
      continue
    fi
    # Deferred from pass 1: reads the file, so it only runs for the few that the
    # scan could not clear.
    _wiring_framework_wired "$f" && continue
    _wiring_ledger_waived "$f" && continue
    if _wiring_ledger_open "$f"; then
      pending="$pending$f"$'\n'
      continue
    fi
    orphans="$orphans$f"$'\n'
  done

  if [ -n "$orphans" ]; then
    gate_metrics_emit wiring blocked "\"new_files\":$n_new,\"candidates\":${#cand_files[@]}"
    {
      printf '[afk] Wiring gate: new artifact(s) with NO consumer and NO IOU — cannot finish.\n'
      printf 'Orphans:\n'
      printf '%s' "$orphans" | sed 's/^/  - /'
      printf '\nFor each: either wire a real consumer now, or declare the expected one in %s:\n' "$WIRING_LEDGER"
      printf '  - [ ] `path/to/artifact` -> anchor: <plan step / ticket / contract "X will call Y">\n'
      printf 'The anchor must be concrete (a named step, ticket, or a symbol of yours the consumer will call).\n'
      printf '"Will be used later" with no anchor does not qualify. Junk files: waive: `path` — <reason>\n'
    } >&2
    return 2
  fi

  if [ "$FINAL" = "1" ] && [ -n "$pending" ]; then
    gate_metrics_emit wiring blocked "\"new_files\":$n_new,\"detail\":\"final: open IOUs\""
    {
      printf '[afk] Wiring gate (FINAL): open IOUs remain — consumers never arrived.\n'
      printf '%s' "$pending" | sed 's/^/  - /'
      printf 'Each must be wired, re-anchored with justification, or explicitly waived before shipping.\n'
    } >&2
    return 2
  fi

  gate_metrics_emit wiring pass "\"new_files\":$n_new,\"candidates\":${#cand_files[@]}"
  [ "$FINAL" != "1" ] && gate_cache_store wiring "$cache_key"
  return 0
}

# ---- standalone invocation (final mode, /afk:preflight, manual runs)
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  _d=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
  _root=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
  cd "$_root" || exit 0
  . "$_d/gate-context.sh"; gate_ctx_build
  . "$_d/gate-cache.sh"
  . "$_d/gate-metrics.sh"
  gate_wiring; exit $?
fi
