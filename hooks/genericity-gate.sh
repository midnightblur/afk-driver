#!/usr/bin/env bash
# Stop gate (ships with the afk plugin): genericity gate — prose added to this
# plugin's *.md files must stay generic, never feature- or incident-specific.
# The doctrine (plugin CLAUDE.md "generic, never feature-specific") existed and
# was still violated by an agent hardening the harness after an incident —
# instruction alone demonstrably isn't enough, hence enforcement.
#
# Checks ADDED lines of changed/untracked plugin .md files for:
#   0. build-system commands in the generic worktree scripts (scripts/*), whose
#      whole design is that every such command lives in a build-gate adapter
#  0b. a person named anywhere in the plugin tree - a tracker account id, an
#      address, or this checkout's own author handles - outside the four paths
#      where authorship is the point (LICENSE, both plugin manifests, CHANGELOG)
#   1. tracker-shaped ticket IDs (PREFIX-123) outside the notation allowlist
#   2. source-file references   (`Foo.vue` / `Foo.java` / `Foo.ts` ...) that
#      resolve to a file the gated repository tracks OUTSIDE the plugin's own
#      tree — that is this gate's definition of "product code"
#   3. backticked CamelCase tokens naming such a file's class (same resolution)
#
# `PROJ` is the reserved placeholder prefix: `PROJ-123` in an example is never
# a real ticket, so it is a notation prefix rather than an allow-list entry.
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

# What the gate's verdict can turn on, as the repo-relative path patterns
# `gate_cache_key` matches: the plugin's own prose, the allow-list, and — only
# where the plugin is not the whole repository — every product path, whose
# symbols checks 2-3 read. A git pathspec exclusion is not a path pattern, and
# an absolute path matches none of them: either one leaves the cache warm while
# the gate's inputs move. The gate's own tests call this, so what they measure
# is what the gate keys on.
genericity_cache_scope() {
  local scope=${1-}
  printf '%s\n' "${scope}*.md" "${scope}hooks/genericity-allow.txt" \
    "${scope}hooks/lib/sensitive-patterns.tsv"
  [ -n "$scope" ] && printf '%s\n' "*"
  return 0
}

gate_genericity() {
  [ "${GENERICITY_GATE_DISABLE:-0}" = "1" ] && return 0
  [ -f .claude/hooks/.gate-disabled ] && return 0

  local PLUGIN_DIR PLUGIN_SCOPE; PLUGIN_DIR=$(afk_plugin_dir); PLUGIN_SCOPE=$(afk_plugin_scope)
  [ -d "$PLUGIN_DIR/skills" ] || return 0   # not this plugin's checkout
  local ALLOW_FILE="$PLUGIN_DIR/hooks/genericity-allow.txt"

  # The shapes this gate blocks are shared with the outgoing-issue redactor, so
  # they live in one file. A missing file blocks: an empty pattern set passes all.
  local PATTERNS_FILE="$PLUGIN_DIR/hooks/lib/sensitive-patterns.tsv" pk pv
  local -A PAT=()
  if [ -f "$PATTERNS_FILE" ]; then
    while IFS=$'\t' read -r pk pv || [ -n "$pk" ]; do
      case "$pk" in ''|\#*) continue ;; esac
      PAT["$pk"]=${pv%$'\r'}
    done < "$PATTERNS_FILE"
  fi
  for pk in ticket-id notation-prefixes account-id email source-file; do
    [ -n "${PAT[$pk]:-}" ] || { echo "Genericity gate: $PATTERNS_FILE has no \`$pk\` pattern." >&2; return 2; }
  done
  # A pattern that does not compile matches nothing, and a check that matches
  # nothing passes. Both engines that run the patterns must compile every one:
  # one grep -E and one awk, whatever the change set holds.
  printf '' | grep -E -e "${PAT[ticket-id]}" -e "${PAT[account-id]}" -e "${PAT[email]}" \
    -e "${PAT[source-file]}" -e "^(${PAT[notation-prefixes]})$" >/dev/null 2>&1
  [ $? -le 1 ] || { echo "Genericity gate: $PATTERNS_FILE holds a pattern grep -E cannot compile." >&2; return 2; }
  GEN_TICKET_RE="${PAT[ticket-id]}" GEN_FILE_RE="${PAT[source-file]}" \
    awk 'BEGIN { match("", ENVIRON["GEN_TICKET_RE"]); match("", ENVIRON["GEN_FILE_RE"]) }' >/dev/null 2>&1 \
    || { echo "Genericity gate: $PATTERNS_FILE holds a pattern awk cannot compile." >&2; return 2; }

  # ---- check 0: the generic scripts stay generic.
  # scripts/ holds the harness-side scripts every consuming repository runs,
  # whatever it builds with. A build command here would make one build system the
  # built-in one, which is exactly what the build-gate adapters exist to prevent.
  local script_hits="" sf sline
  for sf in "$PLUGIN_DIR"/scripts/create-worktree "$PLUGIN_DIR"/scripts/worktree-provision "$PLUGIN_DIR"/scripts/*.sh; do
    [ -f "$sf" ] || continue
    while IFS= read -r sline; do
      [ -n "$sline" ] || continue
      script_hits+="${sf#"$PLUGIN_DIR/"}:$sline"$'\n'
    done < <(grep -nvE '^[[:space:]]*#' "$sf" 2>/dev/null | grep -E 'mvnw?[[:space:]]|maven\.config|\.m2/|npm (ci|install)|robocopy' 2>/dev/null)
  done
  if [ -n "$script_hits" ]; then
    {
      echo "Genericity gate: the generic scripts must name no build system."
      printf '%s' "$script_hits" | sort -u
      echo
      echo "Fix: move the command into adapters/build-gate/<kind>/, and let the script"
      echo "dispatch to whichever build gates the repository selected."
    } >&2
    return 2
  fi

  # ---- check 0b: nothing this plugin ships names a person.
  # A committed file naming one developer makes every other developer read
  # around it, and an account id or address shipped in a plugin publishes
  # someone's identity. Three shapes, over the whole tree rather than only added
  # lines: a tracker account id (24 lowercase hex), an address, and this
  # checkout's own author handles — so the check catches a name without one
  # being written into it.
  if git -C "$PLUGIN_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    local handles="" tok name_cfg mail_cfg ident_hits
    name_cfg=$(git -C "$PLUGIN_DIR" config user.name 2>/dev/null || true)
    mail_cfg=$(git -C "$PLUGIN_DIR" config user.email 2>/dev/null || true)
    for tok in $(printf '%s %s' "$name_cfg" "${mail_cfg%%@*}" | tr -cs 'A-Za-z0-9' ' '); do
      tok=$(printf '%s' "$tok" | tr 'A-Z' 'a-z')
      [ "${#tok}" -ge 3 ] || continue
      handles="$handles${handles:+|}$tok"
    done

    # Excluded BY PATH, because in these four a name is the point: the licence
    # and the two plugin manifests state authorship, and the changelog records
    # what was already published and may not be rewritten.
    ident_hits=$(
      git -C "$PLUGIN_DIR" grep -nIEi --untracked \
        -e "${PAT[account-id]}" \
        -e "${PAT[email]}" \
        ${handles:+-e "\b($handles)\b"} \
        -- . ':(exclude)LICENSE' ':(exclude)CHANGELOG.md' \
             ':(exclude).claude-plugin/*' ':(exclude).codex-plugin/*' 2>/dev/null \
        | grep -vEi '(^|[^A-Za-z0-9._%+-])(git|noreply)@' \
        | grep -vEi '@([A-Za-z0-9-]+\.)*(example\.(com|org|net)|[A-Za-z0-9-]+\.(test|local|invalid))\b' \
        | head -20
    )
    if [ -n "$ident_hits" ]; then
      {
        echo "Genericity gate: this plugin must name no person."
        printf '%s\n' "$ident_hits"
        echo
        echo "Fix: replace the account id, address or handle with a placeholder"
        echo "({user}, dev@example.com), or move the value into a developer's own"
        echo "~/.afk/config.yaml - a committed file never names a person."
      } >&2
      return 2
    fi
  fi

  # ---- scope: plugin .md changed vs the integration base, or untracked.
  local changed_md
  gate_ctx_mergebase
  changed_md=$(
    { git diff --name-only "$AFK_CTX_MERGEBASE" -- "$PLUGIN_SCOPE*.md" "$PLUGIN_SCOPE**/*.md" 2>/dev/null
      gate_ctx_filter AFK_CTX_NEW "$PLUGIN_SCOPE*.md"
    } | sort -u
  )
  [ -z "$changed_md" ] && return 0   # scope no-op

  local cache_key
  # The product-symbol universe is every tracked path OUTSIDE the plugin tree.
  # When the plugin IS the repository there is none and checks 2-3 are inert.
  local PRODUCT_SCOPE=""
  [ -n "$PLUGIN_SCOPE" ] && PRODUCT_SCOPE=":!$PLUGIN_SCOPE*"
  local cache_scope=() pat
  while IFS= read -r pat; do cache_scope+=("$pat"); done \
    < <(genericity_cache_scope "$PLUGIN_SCOPE")
  cache_key=$(gate_cache_key genericity "${cache_scope[@]}")
  gate_cache_hit genericity "$cache_key" && return 0

  gate_metrics_begin

  local -A allow=()
  local t
  if [ -f "$ALLOW_FILE" ]; then
    # `|| [ -n "$t" ]`: an unterminated final line must still register — a
    # silently dropped token re-blocks something deliberately allowed.
    while IFS= read -r t || [ -n "$t" ]; do
      t=${t#"${t%%[![:space:]]*}"}    # leading whitespace would otherwise void the whole line
      case "$t" in ''|\#*) continue ;; esac
      t=${t%%[[:space:]]*}
      [ -n "$t" ] && allow["$t"]=1
    done < "$ALLOW_FILE"
  fi

  # Internal notation prefixes that are NOT Jira tickets (ADRs, acceptance
  # criteria, user stories, render points, preflight steps, encodings, specs).
  local NOTATION_PREFIXES="${PAT[notation-prefixes]}"

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
        # A path containing a blank gets a trailing TAB in the +++ header —
        # left in place it empties the awk content field for the whole file.
        '+++ b/'*) cur=${line#+++ b/}; cur=${cur%$'\t'} ;;
        # quotePath-escaped header (non-ASCII path): decoding the escapes is not
        # worth it — drop attribution rather than crediting lines to the
        # PREVIOUS file.
        '+++ "b/'*) cur="" ;;
        '+++'*|'---'*) ;;
        '+'*) [ -n "$cur" ] && added_stream+="$cur"$'\t'"${line:1}"$'\n' ;;
      esac
    done < <(git diff -U0 "$AFK_CTX_MERGEBASE" -- "${tracked[@]}" 2>/dev/null)
  fi
  for f in ${untracked[@]+"${untracked[@]}"}; do
    while IFS= read -r line || [ -n "$line" ]; do
      added_stream+="$f"$'\t'"$line"$'\n'
    done < "$f"
  done
  [ -z "$added_stream" ] && { gate_metrics_emit genericity pass; gate_cache_store genericity "$cache_key"; return 0; }

  local violations="" tok file kind pfx
  local -a cand_file=() cand_tok=() cand_kind=()
  local -A seen=()

  # Token harvest: ONE pass over the whole stream, emitting "<file>\t<class>\t<token>".
  # Classes: 1 = ticket ID, 2 = source-file reference, 3 = backticked CamelCase.
  # The harvest ends on an END sentinel: an awk that dies part-way (a runtime
  # regex error, a crash) leaves none, and that blocks rather than passing the
  # lines it never read.
  local harvest_done=0
  while IFS=$'\t' read -r file kind tok; do
    [ "$kind" = END ] && { harvest_done=1; continue; }
    [ -n "$tok" ] || continue
    [ -n "${seen["$file:$kind:$tok"]:-}" ] && continue
    seen["$file:$kind:$tok"]=1
    [ -n "${allow[$tok]:-}" ] && continue
    case "$kind" in
      1) pfx=${tok%%-*}
         [[ "$pfx" =~ ^($NOTATION_PREFIXES)$ ]] && continue
         # The changelog is dated history: an entry may name the ticket that
         # motivated the change. Product files and classes still block there.
         [ "${file##*/}" = "CHANGELOG.md" ] && continue
         violations="$violations$file: ticket ID \`$tok\`"$'\n' ;;
      2) cand_file+=("$file"); cand_tok+=("$tok"); cand_kind+=(file) ;;
      3) cand_file+=("$file"); cand_tok+=("$tok"); cand_kind+=(class) ;;
    esac
  done < <(printf '%s' "$added_stream" | GEN_TICKET_RE="${PAT[ticket-id]}" GEN_FILE_RE="${PAT[source-file]}" awk '
    # Boundaries are checked against ABSOLUTE positions in the full line (pre/
    # post computed from s, not the consumed remainder) — checking the remainder
    # makes every post-consumption match look line-initial and defeats the left
    # boundary. Both ends are word boundaries, matching the old per-line \b greps.
    {
      idx = index($0, "\t")
      if (idx == 0) next
      file = substr($0, 1, idx-1)
      s = substr($0, idx+1)          # NOT $2: added lines may contain tabs

      # class 1: Jira-shaped ticket IDs (prefix 2-10 chars, 1-6 digits)
      rest = s
      while (match(rest, ENVIRON["GEN_TICKET_RE"])) {
        pos = length(s) - length(rest) + RSTART
        pre = (pos == 1) ? "" : substr(s, pos-1, 1)
        post = substr(s, pos+RLENGTH, 1)
        if (pre !~ /[A-Za-z0-9_]/ && post !~ /[A-Za-z0-9_]/)
          print file "\t1\t" substr(rest, RSTART, RLENGTH)
        rest = substr(rest, RSTART+RLENGTH)
      }

      # class 2: source-file references
      rest = s
      while (match(rest, ENVIRON["GEN_FILE_RE"])) {
        pos = length(s) - length(rest) + RSTART
        pre = (pos == 1) ? "" : substr(s, pos-1, 1)
        post = substr(s, pos+RLENGTH, 1)
        if (pre !~ /[A-Za-z0-9_]/ && post !~ /[A-Za-z0-9_]/)
          print file "\t2\t" substr(rest, RSTART, RLENGTH)
        rest = substr(rest, RSTART+RLENGTH)
      }

      # class 3: backticked CamelCase (backticks are the boundaries)
      rest = s
      while (match(rest, /`[A-Z][A-Za-z0-9]*`/)) {
        print file "\t3\t" substr(rest, RSTART+1, RLENGTH-2)
        rest = substr(rest, RSTART+RLENGTH)
      }
    }
    END { print "-\tEND\t-" }')
  [ "$harvest_done" = 1 ] || { echo "Genericity gate: the token harvest failed; nothing was checked." >&2; return 2; }

  if [ "${#cand_tok[@]}" -gt 0 ]; then
    local -A prod_file=() prod_class=()
    local n
    local stem
    while IFS= read -r n; do
      n=${n##*/}
      [ -n "$n" ] || continue
      [[ "$n" =~ ^${PAT[source-file]}$ ]] || continue
      stem=${n%.*}
      [ -n "$stem" ] || continue          # dotfile — no class name to resolve
      prod_file["$n"]=1
      prod_class["$stem"]=1
    done < <(if [ -n "$PRODUCT_SCOPE" ]; then git ls-files -- . "$PRODUCT_SCOPE" 2>/dev/null; fi)

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
  # provider.sh first: this gate resolves the plugin's own directory through
  # afk_plugin_dir, and without it a manual run would scope to nothing and
  # report a silent pass.
  . "$_d/lib/provider.sh"
  . "$_d/lib/config.sh"; afk_config_load
  . "$_d/gate-context.sh"; gate_ctx_build
  . "$_d/gate-cache.sh"
  . "$_d/gate-metrics.sh"
  gate_genericity; exit $?
fi
