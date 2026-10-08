#!/usr/bin/env bash
# Wiring gate (ships with the afk plugin): every new artifact must
# have a consumer or a declared IOU.
#
# Failure class this catches: producer-without-consumer (a file/class/log written
# by one change with no reader anywhere — locally correct, dead at the seam).
#
# Verdict per NEW file (staged adds + commits ahead of the merge-base; an untracked
# file may predate the work, so it is never a candidate):
#   wired   — some other file references its name token           -> pass
#   pending — no referrer, but an open IOU with an anchor exists  -> pass (blocks in final mode)
#   orphan  — no referrer, no IOU                                 -> exit 2 (wire it or add an IOU)
#
# Ledger (per repo, created on first IOU): .claude/wiring-ious.md
#   - [ ] `path/to/artifact` -> anchor: <plan step | ticket | contract "X will call Y">
#   - [x] `path` ...                    # auto-closed by this gate when a referrer appears
#   waive: `path` — <reason>            # permanent silence (build junk etc.)
#
# Referrer search is one bounded scan for ALL candidate tokens, run by
# lib/bounded_scan.py: the changed files first (in-process), then the whole tree
# for only the tokens still unresolved, under a deadline and a repository lock.
# A scan that cannot finish is verdict UNKNOWN (rc 3), never an orphan.
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
    README*|AGENTS.md|CLAUDE.md|GLOSSARY.md|SKILL.md|MEMORY.md|pom.xml|package.json|package-lock.json|\
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
    # Python tests — pytest and unittest discover by the same kind of glob.
    test_*.py|*_test.py) return 0 ;;
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

_WIRING_SRC=${BASH_SOURCE[0]//\\//}
_WIRING_HELPER="${_WIRING_SRC%/*}/lib/bounded_scan.py"
_WIRING_TMP=""

_wiring_cleanup() {
  [ -n "$_WIRING_TMP" ] && rm -rf "$_WIRING_TMP" 2>/dev/null
  _WIRING_TMP=""
  return 0
}

# Print "<status>\t<detail>\t<metrics-json>" then each wired path, NUL-separated.
# An absent or unreadable result is unknown, so the gate can never read it as "no referrers".
_WIRING_DIGEST='import json, sys
try:
    d = json.load(open(sys.argv[1], encoding="utf-8"))
    head = "%s\t%s\t%s" % (d["status"], d["detail"], ",".join(
        "\"%s\":%d" % (k, d[k]) for k in ("scan_ms", "tokens_local_resolved", "tokens_tree", "restarts", "files_read")))
    sys.stdout.buffer.write(head.encode() + b"\0")
    for p in d["wired"]:
        sys.stdout.buffer.write(p.encode("utf-8", "surrogateescape") + b"\0")
except Exception:
    sys.stdout.buffer.write(b"unknown\tscan_failure\t\0")
'

gate_wiring() {
  _wiring_main "$@"
  local rc=$?
  _wiring_cleanup
  return $rc
}

_wiring_main() {
  [ "${WIRING_GATE_DISABLE:-0}" = "1" ] && return 0
  [ -f .claude/hooks/.gate-disabled ] && return 0

  local FINAL=${WIRING_FINAL:-0}

  # ---- candidates: staged adds plus commits ahead of the integration base. 3-dot keeps
  # a post-merge branch from claiming every file the base added since the divergence.
  local committed_new="" staged_new
  if [ -n "${AFK_CTX_BASE:-}" ] && [ "${AFK_CTX_BASE}" != "HEAD" ]; then
    committed_new=$(git diff --name-only --diff-filter=A "$AFK_CTX_BASE"...HEAD 2>/dev/null || true)
  fi
  staged_new=$(git diff --cached --name-only -z --diff-filter=ACR 2>/dev/null | tr '\0' '\n')

  local new_files
  new_files=$(printf '%s\n%s\n' "$staged_new" "$committed_new" | sort -u | sed '/^$/d')
  [ -z "$new_files" ] && return 0

  local cache_key=""
  if [ "$FINAL" != "1" ]; then
    cache_key=$(gate_cache_key wiring)
    gate_cache_hit wiring "$cache_key" && return 0
  fi

  gate_metrics_begin
  _wiring_ledger_load

  # ---- pass 1 (fork-light): drop everything that cannot be an orphan and
  # collect the surviving name tokens for one bounded scan. Only fork-free tests
  # belong here — anything that spawns runs per CANDIDATE, and a long-lived
  # branch carries hundreds. The costly per-file probes wait for pass 3, where
  # they see only the few files the scan found no referrer for.
  local f tok n_new=0
  local -a cand_files=() cand_toks=()
  while IFS= read -r f; do
    [ -n "$f" ] || continue
    n_new=$((n_new + 1))
    [ -f "$f" ] || continue
    _wiring_conventional "$f" && continue
    _wiring_ledger_waived "$f" && continue
    if ! _wiring_text_ext "$f"; then
      grep -Iq . "$f" 2>/dev/null || continue      # binary
    fi

    tok=${f##*/}; tok=${tok%.*}
    [ "${#tok}" -lt 4 ] && continue                # too generic to grep meaningfully
    cand_files+=("$f")
    cand_toks+=("$tok")
  done <<<"$new_files"

  if [ "${#cand_files[@]}" -eq 0 ]; then
    gate_metrics_emit wiring pass "\"new_files\":$n_new,\"candidates\":0"
    [ "$FINAL" != "1" ] && gate_cache_store wiring "$cache_key"
    return 0
  fi

  # ---- pass 2: the bounded scan. Local universe = everything this change touched.
  local py="${AFK_PYTHON:-afk-python}" scan_rc=0 detail="" scan_metrics="" status="" i
  local -A wired_set=()
  if ! command -v "$py" >/dev/null 2>&1; then
    detail=no_python
  else
    declare -F gate_ctx_branch >/dev/null && gate_ctx_branch
    _WIRING_TMP=$(mktemp -d "${TMPDIR:-/tmp}/afk-wiring.XXXXXX") || _WIRING_TMP=""
    if [ -z "$_WIRING_TMP" ]; then
      detail=scan_failure
    else
      local cfile="$_WIRING_TMP/candidates" lfile="$_WIRING_TMP/local" rfile="$_WIRING_TMP/result.json" p
      for i in "${!cand_files[@]}"; do printf '%s\0%s\0' "${cand_files[$i]}" "${cand_toks[$i]}"; done >"$cfile"
      while IFS= read -r p; do
        [ -n "$p" ] && printf '%s\0' "$p"
      done >"$lfile" <<<"${AFK_CTX_CHANGED:-}"$'\n'"${AFK_CTX_NEW:-}"$'\n'"${AFK_CTX_BRANCH:-}"$'\n'"$committed_new"
      "$py" "$_WIRING_HELPER" --repo "$PWD" --candidates "$cfile" --local "$lfile" --result "$rfile" 2>/dev/null
      scan_rc=$?
      local first=1 item
      while IFS= read -r -d '' item; do
        if [ "$first" = 1 ]; then
          first=0
          status=${item%%$'\t'*}
          item=${item#*$'\t'}
          detail=${item%%$'\t'*}
          scan_metrics=${item#*$'\t'}
        else
          wired_set[$item]=1
        fi
      done < <("$py" -c "$_WIRING_DIGEST" "$rfile")
      if [ "$scan_rc" -ne 0 ] || [ "$status" != complete ]; then
        [ -n "$detail" ] || detail=scan_failure
      fi
    fi
  fi

  if [ -n "$detail" ]; then
    gate_metrics_emit wiring unknown "\"new_files\":$n_new,\"candidates\":${#cand_files[@]},\"detail\":\"$detail\""
    printf '[afk] Wiring gate: verdict unknown (%s) — no orphan check this run.\n' "$detail" >&2
    return 3
  fi
  scan_metrics=${scan_metrics:+,$scan_metrics}

  local orphans="" pending=""
  for i in "${!cand_files[@]}"; do
    f=${cand_files[$i]}
    if [ -n "${wired_set[$f]:-}" ]; then
      _wiring_ledger_open "$f" && _wiring_ledger_close "$f"   # consumer arrived -> auto-close IOU
      continue
    fi
    # Deferred from pass 1: reads the file, so it only runs for the few that the
    # scan could not clear.
    _wiring_framework_wired "$f" && continue
    if _wiring_ledger_open "$f"; then
      pending="$pending$f"$'\n'
      continue
    fi
    orphans="$orphans$f"$'\n'
  done

  if [ -n "$orphans" ]; then
    gate_metrics_emit wiring blocked "\"new_files\":$n_new,\"candidates\":${#cand_files[@]}$scan_metrics"
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
    gate_metrics_emit wiring blocked "\"new_files\":$n_new,\"detail\":\"final: open IOUs\"$scan_metrics"
    {
      printf '[afk] Wiring gate (FINAL): open IOUs remain — consumers never arrived.\n'
      printf '%s' "$pending" | sed 's/^/  - /'
      printf 'Each must be wired, re-anchored with justification, or explicitly waived before shipping.\n'
    } >&2
    return 2
  fi

  gate_metrics_emit wiring pass "\"new_files\":$n_new,\"candidates\":${#cand_files[@]}$scan_metrics"
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
  trap '_wiring_cleanup' EXIT TERM INT HUP
  gate_wiring; exit $?
fi
