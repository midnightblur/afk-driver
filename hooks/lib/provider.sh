#!/usr/bin/env bash
# Registry and shared contracts for AFK hook provider adapters.

AFK_PROVIDER_CORE_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
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

afk_hook_input() {
  AFK_HOOK_INPUT=$(cat)
}

afk_hook_field() {
  local path="$1"
  if command -v jq >/dev/null 2>&1; then
    printf '%s' "${AFK_HOOK_INPUT:-}" | jq -r ".${path} // \"\"" 2>/dev/null || printf ''
  else
    local leaf="${path##*.}"
    { printf '%s' "${AFK_HOOK_INPUT:-}" \
      | grep -oE "\"${leaf}\"[[:space:]]*:[[:space:]]*\"([^\"\\\\]|\\\\.)*\"" | head -1 \
      | sed "s/^\"${leaf}\"[[:space:]]*:[[:space:]]*\"//;s/\"\$//" \
      | sed 's/\\"/"/g;s/\\\\/\\/g;s/\\n/ /g;s/\\t/ /g;s/\\r/ /g'; } || true
  fi
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

afk_emit_context() {
  local msg="$1"
  if command -v jq >/dev/null 2>&1; then
    jq -n --arg msg "$msg" \
      '{hookSpecificOutput:{hookEventName:"PreToolUse",additionalContext:$msg}}'
  else
    printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext":"%s"}}\n' "$(afk__json_escape "$msg")"
  fi
}

afk_block_stop() {
  printf '%s\n' "$1" >&2
  exit 2
}
