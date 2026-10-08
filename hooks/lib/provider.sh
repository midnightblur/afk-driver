#!/usr/bin/env bash
# Registry and shared contracts for AFK hook provider adapters.

# No dirname and, for an absolute path, no subshell: every hook sources this file.
AFK_PROVIDER_CORE_DIR=${BASH_SOURCE[0]//\\//}
case "$AFK_PROVIDER_CORE_DIR" in
  /*|[A-Za-z]:*) AFK_PROVIDER_CORE_DIR=${AFK_PROVIDER_CORE_DIR%/*} ;;
  */*) AFK_PROVIDER_CORE_DIR=$(cd "${AFK_PROVIDER_CORE_DIR%/*}" && pwd) ;;
  *) AFK_PROVIDER_CORE_DIR=$PWD ;;
esac
AFK_PROVIDER_NAMES=""

for afk_adapter in "$AFK_PROVIDER_CORE_DIR"/providers/*.sh; do
  [ -f "$afk_adapter" ] || continue
  # shellcheck source=/dev/null
  . "$afk_adapter"
  afk_adapter_name=${afk_adapter##*/}
  afk_adapter_name=${afk_adapter_name%.sh}
  AFK_PROVIDER_NAMES="$AFK_PROVIDER_NAMES $afk_adapter_name"
done
unset afk_adapter afk_adapter_name

afk_provider() {
  local name detect priority selected="" selected_priority="" ambiguous=0

  if [ -n "${AFK_PROVIDER:-}" ]; then
    case " $AFK_PROVIDER_NAMES " in
      *" $AFK_PROVIDER "*) printf '%s\n' "$AFK_PROVIDER" ;;
      *) printf 'unknown\n' ;;
    esac
    return 0
  fi

  for name in $AFK_PROVIDER_NAMES; do
    detect="afk_${name}_detect"
    priority="afk_${name}_priority"
    command -v "$detect" >/dev/null 2>&1 || continue
    "$detect" || continue
    if command -v "$priority" >/dev/null 2>&1; then
      priority=$("$priority")
    else
      priority=100
    fi
    if [ -z "$selected_priority" ] || [ "$priority" -lt "$selected_priority" ]; then
      selected=$name
      selected_priority=$priority
      ambiguous=0
    elif [ "$priority" -eq "$selected_priority" ]; then
      ambiguous=1
    fi
  done

  if [ "$ambiguous" -eq 1 ] || [ -z "$selected" ]; then
    printf 'unknown\n'
  else
    printf '%s\n' "$selected"
  fi
}

afk_agent_session() {
  [ "$(afk_provider)" != "unknown" ]
}

afk_plugin_root() {
  local provider function root=""
  provider=$(afk_provider)
  function="afk_${provider}_plugin_root"
  if command -v "$function" >/dev/null 2>&1; then
    root=$("$function")
  fi
  if [ -z "$root" ]; then
    root=$(cd "$AFK_PROVIDER_CORE_DIR/../.." && pwd)
  fi
  printf '%s\n' "$root"
}

afk_user_instruction_file() {
  local provider function file=""
  provider=$(afk_provider)
  function="afk_${provider}_user_instruction_file"
  if command -v "$function" >/dev/null 2>&1; then
    file=$("$function")
  fi
  printf '%s\n' "$file"
}

# Every registered provider's own (user instruction file, installed root,
# enablement) triple, resolved independently of which provider is the current
# session — 4 NUL-terminated fields per provider that has a target, in
# registration order: name<NUL>target<NUL>root<NUL>enablement<NUL>, with no
# extra separator between records (every 4 fields is one record). ROOT is
# empty when it cannot be independently verified. ENABLEMENT is one of
# enabled|disabled|absent, always a definite value (never empty). TARGET and
# ROOT are filesystem paths, which POSIX allows to contain any byte except
# NUL and `/` — a printable delimiter (tab, the ASCII unit separator, a
# newline) can legally occur inside one, silently shifting a field boundary;
# NUL is the one byte guaranteed never to appear in a path, so it is the
# only safe terminator. A consumer reads exactly 4 NUL-terminated fields per
# record with `IFS= read -r -d '' name && IFS= read -r -d '' target &&
# IFS= read -r -d '' root && IFS= read -r -d '' enablement` — never a single
# `read` with IFS set to a printable delimiter, and never a record-per-line
# format, since a path can itself contain a newline.
#
# A target is never omitted: an install must never write a guessed root, so
# it skips a row with an empty root — but a read like an audit can still
# inspect that target's existing content for a leftover managed marker
# without needing the root at all, and omitting the row outright would hide
# exactly that (a block left behind after a provider is disabled, whose root
# can then no longer resolve, is the case the audit most needs to catch).
# Enablement is a second, independent reason to skip an install: a provider
# whose root still resolves (the plugin is installed, just not currently
# turned on) must not receive a fresh block either, and a read must reject a
# leftover marker there too — root resolving is not the same fact as the
# provider being on.
afk_all_provider_targets() {
  local name target_fn root_fn enablement_fn target root enablement
  for name in $AFK_PROVIDER_NAMES; do
    target_fn="afk_${name}_user_instruction_file"
    root_fn="afk_${name}_installed_root"
    enablement_fn="afk_${name}_enablement"
    command -v "$target_fn" >/dev/null 2>&1 || continue
    target=$("$target_fn")
    [ -n "$target" ] || continue
    root=""
    if command -v "$root_fn" >/dev/null 2>&1; then
      root=$("$root_fn") || root=""
    fi
    enablement="absent"
    if command -v "$enablement_fn" >/dev/null 2>&1; then
      enablement=$("$enablement_fn") || enablement="absent"
      [ -n "$enablement" ] || enablement="absent"
    fi
    printf '%s\0%s\0%s\0%s\0' "$name" "$target" "$root" "$enablement"
  done
}

afk_plugin_data() {
  local provider function dir=""
  provider=$(afk_provider)
  function="afk_${provider}_plugin_data"
  if command -v "$function" >/dev/null 2>&1; then
    dir=$("$function")
  fi
  if [ -z "$dir" ]; then
    dir="$HOME/.afk/data/$(basename "$(afk_plugin_root)")"
  fi
  mkdir -p "$dir" 2>/dev/null || true
  printf '%s\n' "$dir"
}

# Every supported harness's managed plugin directories, one absolute path per
# line, existing ones only. Each adapter declares its own through
# afk_<provider>_managed_plugin_dirs; this reads them ALL, not the detected
# one's, because the answer is a property of the path on disk and holds
# whichever harness (or none) is running.
# Exit: 0 the list is complete, 2 an adapter could not answer (no such
# function, or no home directory to resolve) — the list printed is then partial
# and a miss proves nothing.
afk_managed_plugin_dirs() {
  local name function dir absolute output status=0 asked=0
  for name in $AFK_PROVIDER_NAMES; do
    asked=1
    function="afk_${name}_managed_plugin_dirs"
    if ! command -v "$function" >/dev/null 2>&1; then status=2; continue; fi
    if ! output=$("$function"); then status=2; continue; fi
    while IFS= read -r dir; do
      [ -n "$dir" ] && [ -d "$dir" ] || continue
      absolute=$(cd "$dir" && pwd -P) || continue
      printf '%s\n' "$absolute"
    done <<EOF
$output
EOF
  done
  # No adapter at all is as unanswerable as an adapter that cannot answer.
  [ "$asked" = 1 ] || status=2
  return "$status"
}

# Does this platform's filesystem treat two spellings as one path? Windows and
# macOS do; Linux does not, and folding case there would call a DIFFERENT
# directory a match. AFK_PATH_CASE_FOLD forces the answer (0 or 1).
afk_path_case_fold() {
  case "${AFK_PATH_CASE_FOLD:-}" in
    1) return 0 ;;
    0) return 1 ;;
  esac
  case "$(uname -s 2>/dev/null)" in
    MINGW*|MSYS*|CYGWIN*|Windows*|Darwin) return 0 ;;
    *) return 1 ;;
  esac
}

# Does the harness own this plugin copy? An edit under a managed directory is
# lost on the next harness update, so the tree is installed however it looks.
# The comparison folds case and separators: Windows hands the same directory
# back under either spelling, and a missed match would hand a harness-owned
# tree to an editor.
# Exit: 0 managed, 1 not managed, 2 UNDECIDABLE — the caller must not read 2 as
# "not managed"; the safe reading is managed.
afk_harness_managed_path() {
  local target dir dirs status previous verdict=1
  dirs=$(afk_managed_plugin_dirs); status=$?
  target=$(cd "$1" 2>/dev/null && pwd -P) || return 2
  target=${target//\\//}
  previous=$(shopt -p nocasematch)
  afk_path_case_fold && shopt -s nocasematch
  while IFS= read -r dir; do
    [ -n "$dir" ] || continue
    dir=${dir//\\//}
    case "$target/" in "$dir"/*) verdict=0; break ;; esac
  done <<EOF
$dirs
EOF
  $previous
  [ "$verdict" -eq 0 ] && return 0
  [ "$status" -eq 0 ] || return 2
  return 1
}

afk_hook_input() {
  AFK_HOOK_INPUT=$(cat)
}

afk_hook_field() {
  local path="$1"
  if command -v jq >/dev/null 2>&1; then
    printf '%s' "${AFK_HOOK_INPUT:-}" | jq -r ".${path} // \"\"" 2>/dev/null || printf ''
  else
    # Builtins only: every hook reads fields, and a process start can cost 0.1-0.7 s.
    afk__json_field "$path"
  fi
}

# Print the string or number at dotted object path $1 of AFK_HOOK_INPUT, like
# `jq -r ".$1 // \"\""`; an object, an array, false and null print nothing.
afk__json_field() {
  local glob=+f
  case $- in *f*) glob=-f ;; esac
  set -f; afk__json_find "$1"; set "$glob"
}

# Split once at every ": bash's own pattern replace is quadratic on a large envelope.
# A part ending in an odd run of \ continues the string; any other " toggles it.
afk__json_find() {
  local IFS='"' p t v i n k=-1 d=0 L=0 in=0 open=-2
  local -a parts segs o c
  parts=(${AFK_HOOK_INPUT:-}); n=${#parts[@]}
  IFS=.; segs=($1); IFS='"'
  # Forward, tracking how much of the path the open objects match. A one-key search
  # finishes from the end after 64 parts, so a key behind a large value stays cheap.
  for ((i = 0; i < n; i++)); do
    ((${#segs[@]} == 1 && i == 64)) && break
    p=${parts[i]}
    if ((in)); then
      if [[ $p == *\\ ]]; then t=${p##*[!\\]}; ((${#t} % 2)) && continue; fi
      in=0; continue
    fi
    if [[ $p == *:* ]] && ((d == L + 1 && open == i - 1)) && [ "${parts[i-1]}" = "${segs[L]}" ]; then
      ((L + 1 == ${#segs[@]})) && { k=$i; break; }
      v=${p#*:}; v=${v#"${v%%[![:space:]]*}"}
      [[ $v == \{* ]] || return 0
      L=$((L + 1))
    fi
    if [[ $p == *[\{\}\[\]]* ]]; then
      IFS='{['; o=(.$p.); IFS='}]'; c=(.$p.); IFS='"'
      d=$((d + ${#o[@]} - ${#c[@]}))
      ((d <= L)) && L=$((d > 0 ? d - 1 : 0))
    fi
    in=1; open=$((i + 1))
  done
  # Backward, where the depth of a key is the closers after it less the openers.
  if ((k < 0 && i < n)); then
    local stop=$i
    d=0 in=0
    for ((i = n - 1; i >= stop; i--)); do
      p=${parts[i]}
      if ((in)); then
        t=${parts[i-1]} in=0
        if [[ $t == *\\ ]]; then t=${t##*[!\\]}; ((${#t} % 2)) && in=1; fi
        continue
      fi
      if [[ $p == *[\{\}\[\]]* ]]; then
        IFS='{['; o=(.$p.); IFS='}]'; c=(.$p.); IFS='"'
        d=$((d + ${#c[@]} - ${#o[@]}))
      fi
      if [[ $p == *:* ]] && ((d == 1 && i >= 2)) && [ "${parts[i-1]}" = "$1" ]; then
        t=${parts[i-2]}
        [[ $t == *\\ ]] && t=${t##*[!\\]}
        [[ $t == *\\ ]] && ((${#t} % 2)) || { k=$i; break; }
      fi
      in=1
    done
  fi
  ((k < 0)) && return 0
  v=${parts[k]#*:}; v=${v#"${v%%[![:space:]]*}"}
  if [ -z "$v" ] && ((k + 1 < n)); then
    for ((i = k + 1; i < n; i++)); do
      p=${parts[i]}
      [[ $p == *\\ ]] || break
      t=${p##*[!\\]}; ((${#t} % 2)) || break
    done
    afk__json_unescape "${parts[*]:k+1:i-k}"
  elif [[ ${v:0:64} =~ ^(-?[0-9][-+.eE0-9]*|true)[[:space:]]*([],}]|$) ]]; then
    printf '%s' "${BASH_REMATCH[1]}"
  fi
}

# Decode one JSON string body, each escape once. Runs with globbing off.
afk__json_unescape() {
  local IFS='\' p c cp lo bytes i n
  local -a f
  f=($1.); n=${#f[@]}  # the "." keeps a trailing empty part
  for ((i = 1; i < n; i++)); do
    p=${f[i]}
    if [ -z "$p" ]; then f[i]='\'; i=$((i + 1)); continue; fi  # \\: the next part is plain
    c=${p:0:1} p=${p:1}
    case $c in
      b) c=$'\b' ;; f) c=$'\f' ;; n) c=$'\n' ;; r) c=$'\r' ;; t) c=$'\t' ;;
      '"'|/) ;;
      u)
        if [[ $p != [0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F]* ]]; then c='\u'
        else
          cp=$((16#${p:0:4})) p=${p:4}
          if ((cp >= 0xD800 && cp < 0xDC00)) && [ -z "$p" ] \
            && [[ ${f[i+1]} == u[dD][c-fC-F][0-9a-fA-F][0-9a-fA-F]* ]]; then
            lo=$((16#${f[i+1]:1:4})) f[i]= i=$((i + 1))
            cp=$(((cp - 0xD800) * 0x400 + lo - 0xDC00 + 0x10000)) p=${f[i]:5}
          fi
          # UTF-8 by hand: printf's own \u follows the locale, and hooks run in C.
          if ((cp < 0x80)); then printf -v bytes '\\x%02x' "$cp"
          elif ((cp < 0x800)); then printf -v bytes '\\x%02x' $((0xC0 | cp >> 6)) $((0x80 | cp & 63))
          elif ((cp < 0x10000)); then
            printf -v bytes '\\x%02x' $((0xE0 | cp >> 12)) $((0x80 | cp >> 6 & 63)) $((0x80 | cp & 63))
          else
            printf -v bytes '\\x%02x' $((0xF0 | cp >> 18)) $((0x80 | cp >> 12 & 63)) \
              $((0x80 | cp >> 6 & 63)) $((0x80 | cp & 63))
          fi
          printf -v c '%b' "$bytes"
        fi ;;
      *) c='\'$c ;;
    esac
    f[i]=$c$p
  done
  IFS=; p="${f[*]}"; printf '%s' "${p%.}"
}

afk__json_escape() {
  printf '%s' "$1" | sed 's/\\/\\\\/g;s/"/\\"/g' | awk 'NR>1{printf "\\n"}{printf "%s",$0}' | sed 's/\t/\\t/g'
}

afk_emit_deny() {
  local reason="$1"
  if command -v jq >/dev/null 2>&1; then
    jq -n --arg r "$reason" \
      '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$r}}'
  else
    printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"%s"}}\n' "$(afk__json_escape "$reason")"
  fi
}

# Emit an additional-context injection for one hook event. The event name is the
# caller's, not a constant — a PostToolUse handler must name PostToolUse. Both a
# nested `hookSpecificOutput.additionalContext` and a top-level `additional_context`
# carry the same text, so one shape satisfies either harness's reader.
afk_emit_context() {
  local event="$1" msg="$2"
  if command -v jq >/dev/null 2>&1; then
    jq -n --arg e "$event" --arg msg "$msg" \
      '{hookSpecificOutput:{hookEventName:$e,additionalContext:$msg},additional_context:$msg}'
  else
    local esc; esc=$(afk__json_escape "$msg")
    printf '{"hookSpecificOutput":{"hookEventName":"%s","additionalContext":"%s"},"additional_context":"%s"}\n' "$event" "$esc" "$esc"
  fi
}

# One top-level scalar of hooks/lib/providers/<provider>.json, quotes dropped; empty when
# absent. Reads the file's `  "key": value` lines with builtins only (no fork, no jq).
afk_provider_fact() {
  local file line value
  file="$AFK_PROVIDER_CORE_DIR/providers/$(afk_provider).json"
  [ -f "$file" ] || return 0
  while IFS= read -r line; do
    line=${line%$'\r'}
    case "$line" in
      "  \"$1\": "*)
        value=${line#*\": }; value=${value%,}; value=${value#\"}; value=${value%\"}
        printf '%s\n' "$value"; return 0 ;;
    esac
  done <"$file"
}

# Nested-steering policy from providers/<name>.json (values: PROVIDERS.md). An unknown
# provider gets the no-op defaults, so nothing loads twice.
afk_nested_inject_mode() {
  local mode; mode=$(afk_provider_fact nested_inject_mode)
  printf '%s\n' "${mode:-never}"
}

afk_nested_inject_rules() {
  local rules; rules=$(afk_provider_fact nested_inject_rules)
  printf '%s\n' "${rules:-0}"
}

# A Stop verdict has to reach the session, and harnesses read it differently:
# one takes stderr with exit 2, another only honours a decision object on
# stdout. Emit both, and let the adapter say which exit code its harness
# reads a block from (`stop_block_code` in its provider declaration, default 0).
afk_emit_stop_block() {
  # A gate that prints through a Windows text stream can leave CR bytes in the
  # middle of the findings; they corrupt the decision value, not just the view.
  local reason=${1//$'\r'/}
  printf '%s\n' "$reason" >&2
  if command -v jq >/dev/null 2>&1; then
    jq -n --arg r "$reason" '{decision:"block",reason:$r}'
  else
    printf '{"decision":"block","reason":"%s"}\n' "$(afk__json_escape "$reason")"
  fi
}

afk_stop_block_code() {
  local code; code=$(afk_provider_fact stop_block_code)
  printf '%s\n' "${code:-0}"
}

# The plugin tree's path RELATIVE to the current repository root, or the empty
# string when the plugin is installed outside this repository. Standalone the
# plugin repo IS the plugin root, so this prints ".". Gates that only judge the
# toolkit's own tree treat "" as "not this plugin's checkout" and exit 0.
afk_plugin_dir() {
  local root plugin_top repo_top prefix
  root=$(afk_plugin_root)
  # Ask git for both roots: a bash `pwd` can render the same directory under a
  # different mount alias (/tmp vs /c/Users/.../Temp on Windows), and two
  # spellings of one path would compare unequal.
  plugin_top=$(git -C "$root" rev-parse --show-toplevel 2>/dev/null) || { printf '
'; return 0; }
  repo_top=$(git rev-parse --show-toplevel 2>/dev/null) || { printf '
'; return 0; }
  [ "$plugin_top" = "$repo_top" ] || { printf '
'; return 0; }
  prefix=$(git -C "$root" rev-parse --show-prefix 2>/dev/null)
  prefix=${prefix%/}
  if [ -z "$prefix" ]; then printf '.
'; else printf '%s
' "$prefix"; fi
}

# The plugin tree as a PATH-GLOB PREFIX for change-scope tests and git
# pathspecs: empty when the plugin repo is the repository being gated (every
# path is already plugin-relative), "<rel>/" when the plugin sits inside a
# larger repository.
afk_plugin_scope() {
  local dir
  dir=$(afk_plugin_dir)
  case "$dir" in
    ""|".") printf '\n' ;;
    *) printf '%s/\n' "$dir" ;;
  esac
}
