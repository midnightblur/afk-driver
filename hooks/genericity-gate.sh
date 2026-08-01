#!/usr/bin/env bash
# Stop gate (ships with the afk plugin): genericity gate — prose added to this
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
# Cost shape: ONE batched diff for every changed file (was one per file), and the
# product-symbol universe (a repo-wide git ls-files, the gate's most expensive
# call) is built only when the added lines actually contain a candidate token —
# ordinary prose edits never pay for it.
#
# Deliberate references (e.g. the plugin's own parent ticket) go in
# hooks/genericity-allow.txt — one exact token per line, comment with reason.
# Disable: GENERICITY_GATE_DISABLE=1, or repo file .claude/hooks/.gate-disabled.

set -u

gate_genericity() {
  [ "${GENERICITY_GATE_DISABLE:-0}" = "1" ] && return 0
  [ -f .claude/hooks/.gate-disabled ] && return 0

  local PLUGIN_DIR="tools/payable/ai-agents/plugins/workflow"
  [ -d "$PLUGIN_DIR/skills" ] || return 0   # not this plugin's checkout
  local ALLOW_FILE="$PLUGIN_DIR/hooks/genericity-allow.txt"

  # ---- scope: plugin .md changed vs the integration base, or untracked.
  local changed_md
  gate_ctx_mergebase
  changed_md=$(
    { git diff --name-only "$AFK_CTX_MERGEBASE" -- "$PLUGIN_DIR/*.md" "$PLUGIN_DIR/**/*.md" 2>/dev/null
      gate_ctx_filter AFK_CTX_NEW "$PLUGIN_DIR/*.md"
    } | sort -u
  )
  [ -z "$changed_md" ] && return 0   # scope no-op

  # Inputs: the plugin's own prose, the allow-list, and the product-symbol
  # inventory (a new product file can turn a previously clean token into a hit).
  local cache_key
  cache_key=$(gate_cache_key genericity "$PLUGIN_DIR/*.md" "$ALLOW_FILE" "11700-payable/*")
  gate_cache_hit genericity "$cache_key" && return 0

  gate_metrics_begin

  local -A allow=()
  local t
  if [ -f "$ALLOW_FILE" ]; then
    while IFS= read -r t; do
      case "$t" in ''|\#*) continue ;; esac
      t=${t%%[[:space:]]*}
      [ -n "$t" ] && allow["$t"]=1
    done < "$ALLOW_FILE"
  fi

  # Internal notation prefixes that are NOT Jira tickets (ADRs, acceptance
  # criteria, user stories, render points, preflight steps, encodings, specs).
  local NOTATION_PREFIXES='ADR|AC|US|RP|PF|UTF|RFC|ISO|JEP|JDK|HHH'

  # ---- added lines per file: ONE diff for every tracked file, plus a fork-free
  # read of each untracked one.
  local -a tracked=() untracked=()
  local f
  while IFS= read -r f; do
    [ -n "$f" ] && [ -f "$f" ] || continue
    if git ls-files --error-unmatch -- "$f" >/dev/null 2>&1; then tracked+=("$f"); else untracked+=("$f"); fi
  done <<<"$changed_md"

  # ---- added lines as one "<path>\t<line>" stream. One diff covers every
  # tracked file; the per-file split is bash string work, untracked files are
  # read whole. Keeping it a single stream is what lets the harvest below be one
  # pass — a per-file (let alone per-line) scan costs a subprocess each, and a
  # long-lived branch has dozens of changed prose files.
  local added_stream="" line cur=""
  if [ "${#tracked[@]}" -gt 0 ]; then
    while IFS= read -r line; do
      case "$line" in
        '+++ b/'*) cur=${line#+++ b/} ;;
        '+++'*|'---'*) ;;
        '+'*) [ -n "$cur" ] && added_stream+="$cur"$'\t'"${line:1}"$'\n' ;;
      esac
    done < <(git diff -U0 "$AFK_CTX_MERGEBASE" -- "${tracked[@]}" 2>/dev/null)
  fi
  for f in ${untracked[@]+"${untracked[@]}"}; do
    while IFS= read -r line; do
      added_stream+="$f"$'\t'"$line"$'\n'
    done < "$f"
  done
  [ -z "$added_stream" ] && { gate_metrics_emit genericity pass; gate_cache_store genericity "$cache_key"; return 0; }

  local violations="" tok file kind pfx
  local -a cand_file=() cand_tok=() cand_kind=()
  local -A seen=()

  # Token harvest: ONE pass over the whole stream, emitting "<file>\t<class>\t<token>".
  # Classes: 1 = ticket ID, 2 = source-file reference, 3 = backticked CamelCase.
  while IFS=$'\t' read -r file kind tok; do
    [ -n "$tok" ] || continue
    [ -n "${seen["$file:$kind:$tok"]:-}" ] && continue
    seen["$file:$kind:$tok"]=1
    [ -n "${allow[$tok]:-}" ] && continue
    case "$kind" in
      1) pfx=${tok%%-*}
         [[ "$pfx" =~ ^($NOTATION_PREFIXES)$ ]] && continue
         violations="$violations$file: ticket ID \`$tok\`"$'\n' ;;
      2) cand_file+=("$file"); cand_tok+=("$tok"); cand_kind+=(file) ;;
      3) cand_file+=("$file"); cand_tok+=("$tok"); cand_kind+=(class) ;;
    esac
  done < <(printf '%s' "$added_stream" | awk -F'\t' '
    {
      file=$1; s=$2
      t=s
      while (match(t, /[A-Z][A-Z0-9]+-[0-9]+/)) {
        if (RSTART==1 || substr(t,RSTART-1,1) !~ /[A-Za-z0-9_-]/)
          print file "\t1\t" substr(t,RSTART,RLENGTH)
        t=substr(t,RSTART+RLENGTH)
      }
      t=s
      while (match(t, /[A-Za-z][A-Za-z0-9_]*\.(vue|java|tsx|ts|mjs|js)/)) {
        if (RSTART==1 || substr(t,RSTART-1,1) !~ /[A-Za-z0-9_.]/)
          print file "\t2\t" substr(t,RSTART,RLENGTH)
        t=substr(t,RSTART+RLENGTH)
      }
      t=s
      while (match(t, /`[A-Z][A-Za-z0-9]*`/)) {
        print file "\t3\t" substr(t,RSTART+1,RLENGTH-2)
        t=substr(t,RSTART+RLENGTH)
      }
    }')

  if [ "${#cand_tok[@]}" -gt 0 ]; then
    local -A prod_file=() prod_class=()
    local n
    local stem
    while IFS= read -r n; do
      n=${n##*/}
      [ -n "$n" ] || continue
      case "$n" in *.vue|*.java|*.ts|*.tsx|*.js|*.mjs) ;; *) continue ;; esac
      stem=${n%.*}
      [ -n "$stem" ] || continue          # dotfile — no class name to resolve
      prod_file["$n"]=1
      prod_class["$stem"]=1
    done < <(git ls-files '11700-payable/*' ':!11700-payable/verification/*' 2>/dev/null)

    local i
    for i in "${!cand_tok[@]}"; do
      tok=${cand_tok[$i]}; file=${cand_file[$i]}
      if [ "${cand_kind[$i]}" = "file" ]; then
        [ -n "${prod_file[$tok]:-}" ] && violations="$violations$file: product source file \`$tok\`"$'\n'
      else
        [ -n "${prod_class[$tok]:-}" ] && violations="$violations$file: product class \`$tok\`"$'\n'
      fi
    done
  fi

  if [ -n "$violations" ]; then
    gate_metrics_emit genericity blocked
    {
      echo "Genericity gate: plugin prose must stay generic — never feature- or incident-specific."
      echo "Added lines reference concrete tickets/product symbols:"
      printf '%s' "$violations" | sort -u
      echo
      echo "Fix: restate the rule in terms of the mechanism/pattern class, not the instance that"
      echo "motivated it. If a reference is deliberate (plugin's own ticket, a format example),"
      echo "add the exact token to $ALLOW_FILE with a reason comment."
    } >&2
    return 2
  fi

  gate_metrics_emit genericity pass
  gate_cache_store genericity "$cache_key"
  return 0
}

# ---- standalone invocation
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  _d=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
  _root=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
  cd "$_root" || exit 0
  . "$_d/gate-context.sh"; gate_ctx_build
  . "$_d/gate-cache.sh"
  . "$_d/gate-metrics.sh"
  gate_genericity; exit $?
fi
