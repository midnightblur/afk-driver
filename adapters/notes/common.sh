#!/usr/bin/env bash
# notes — the file-backed implementation the `repo-files` and `obsidian` kinds
# share.
#
# Both kinds store the same Markdown tree; they differ in exactly two things,
# so each kind's notes.sh defines those two and sources this file:
#
#   notes_root        the absolute directory the tree is rooted at
#   notes_link_form   how a link to a note is written: `md` or `wikilink`
#
# Every verb takes one JSON object — on the command line or on stdin — and
# answers with one JSON object on stdout. The exit codes are the family's:
#
#   0  the verb ran
#   2  the verb could not resolve what it needed (the message names the key)
#   3  the verb is not one this family has
#
set -uo pipefail

AFK_NOTES_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
AFK_NOTES_ROOT=${AFK_PLUGIN_ROOT:-$(cd "$AFK_NOTES_DIR/../.." && pwd)}
# shellcheck source=/dev/null
. "$AFK_NOTES_ROOT/hooks/lib/config.sh"

AFK_NOTES_PY=python
command -v python >/dev/null 2>&1 || AFK_NOTES_PY=python3

notes_die() {                                   # notes_die <exit> <reason>
  local code=$1; shift
  "$AFK_NOTES_PY" -c 'import json,sys; print(json.dumps({"error": sys.argv[1]}))' "$*"
  exit "$code"
}

notes_unsupported() {
  "$AFK_NOTES_PY" -c 'import json,sys; print(json.dumps({"unsupported": True, "verb": sys.argv[1], "reason": sys.argv[2]}))' \
    "$1" "$2"
  exit 3
}

# notes_field <json> <name> — one string field, empty when absent.
notes_field() {
  printf '%s' "$1" | "$AFK_NOTES_PY" -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    d = {}
v = d.get(sys.argv[1], "") if isinstance(d, dict) else ""
sys.stdout.write("" if v is None else str(v))
' "$2"
}

# notes_expand <template> <json> — the fixed placeholder set, CONFIG.md
# "Path templates". An unknown placeholder is left alone rather than guessed.
notes_expand() {
  printf '%s' "$2" | "$AFK_NOTES_PY" -c '
import json, os, re, sys
tpl = sys.argv[1]
try:
    d = json.load(sys.stdin)
except Exception:
    d = {}
if not isinstance(d, dict):
    d = {}
work = str(d.get("workId") or d.get("ticket") or "")
ticket = str(d.get("ticket") or work)
vals = {
    "workId": work,
    "ticket": ticket,
    "ticket_lower": ticket.lower(),
    "service": str(d.get("service") or ""),
    "release": str(d.get("release") or ""),
    "user": str(d.get("user") or os.environ.get("USER") or os.environ.get("USERNAME") or ""),
}
sys.stdout.write(re.sub(r"\{([A-Za-z_]+)\}",
                        lambda m: vals[m.group(1)] if m.group(1) in vals else m.group(0),
                        tpl))
' "$1"
}

# notes_emit <key=value…> — one JSON object, values treated as strings unless
# the key ends in `?`, which marks a bare JSON literal (true / false / null).
notes_emit() {
  "$AFK_NOTES_PY" -c '
import json, sys
out = {}
for pair in sys.argv[1:]:
    k, _, v = pair.partition("=")
    if k.endswith("?"):
        out[k[:-1]] = json.loads(v)
    else:
        out[k] = v
print(json.dumps(out))
' "$@"
}

# notes_check_name <name> — the payload's `name` is taken relative to the work
# item's directory and must stay inside it. Called directly, never inside a
# command substitution: a refusal is JSON on stdout, and a substitution would
# swallow it.
notes_check_name() {
  local name=$1
  [ -n "$name" ] || notes_die 2 "no \`name\` in the payload — name the note file relative to the work item's directory"
  case "$name" in
    /*|*..*) notes_die 2 "\`name\` must be relative and must not climb out of the work item's directory: $name" ;;
  esac
}

notes_main() {
  local verb=${1:-} payload=${2:-}
  [ -n "$verb" ] || notes_die 2 "no verb — see this adapter's CONTRACT.md"
  [ -n "$payload" ] || { [ -t 0 ] || payload=$(cat); }
  [ -n "$payload" ] || payload='{}'

  afk_config_load
  local template dir root name target
  template=${AFK_CFG_REPO_FILES_SPEC_DIR:-}
  [ -n "$template" ] || notes_die 2 "no \`repo-files.spec-dir\` in .afk/config.yaml — it is the template every notes kind renders"
  # A kind that cannot resolve its root answers with the JSON itself, so the
  # caller sees the reason rather than an empty stdout.
  local rc=0
  root=$(notes_root) || rc=$?
  if [ "$rc" != 0 ]; then printf '%s\n' "$root"; exit "$rc"; fi
  dir="$root/$(notes_expand "$template" "$payload")"

  case "$verb" in
    resolve)
      notes_emit "kind=$(notes_kind)" "dir=$dir" "template=$template" \
        "exists?=$([ -d "$dir" ] && echo true || echo false)"
      ;;
    note-create)
      name=$(notes_field "$payload" name)
      notes_check_name "$name"
      target="$dir/$name"
      mkdir -p "$(dirname "$target")" || notes_die 2 "could not create $(dirname "$target")"
      notes_field "$payload" content >"$target" || notes_die 2 "could not write $target"
      notes_emit "path=$target" "created?=true"
      ;;
    note-read)
      name=$(notes_field "$payload" name)
      notes_check_name "$name"
      target="$dir/$name"
      [ -f "$target" ] || notes_die 2 "no note at $target"
      "$AFK_NOTES_PY" -c 'import json,sys; p=sys.argv[1]; print(json.dumps({"path": p, "content": open(p, encoding="utf-8").read()}))' \
        "$target"
      ;;
    note-update)
      name=$(notes_field "$payload" name)
      notes_check_name "$name"
      target="$dir/$name"
      [ -f "$target" ] || notes_die 2 "no note at $target — use note-create"
      if [ "$(notes_field "$payload" mode)" = "append" ]; then
        notes_field "$payload" content >>"$target"
      else
        notes_field "$payload" content >"$target"
      fi
      notes_emit "path=$target" "updated?=true"
      ;;
    note-delete)
      name=$(notes_field "$payload" name)
      notes_check_name "$name"
      target="$dir/$name"
      [ -f "$target" ] || notes_die 2 "no note at $target"
      rm -f "$target" || notes_die 2 "could not delete $target"
      notes_emit "path=$target" "deleted?=true"
      ;;
    note-link)
      name=$(notes_field "$payload" name)
      notes_check_name "$name"
      target="$dir/$name"
      local text
      text=$(notes_field "$payload" text)
      [ -n "$text" ] || text=$(basename "$name" .md)
      if [ "$(notes_link_form)" = "wikilink" ]; then
        notes_emit "path=$target" "link=[[$(basename "$name" .md)|$text]]"
      else
        notes_emit "path=$target" "link=[$text]($name)"
      fi
      ;;
    *)
      notes_unsupported "$verb" "notes has note-create, note-read, note-update, note-delete, note-link and resolve"
      ;;
  esac
}
