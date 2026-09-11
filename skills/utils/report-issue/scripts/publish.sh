#!/usr/bin/env bash
# Publish one plugin issue to GitHub, or queue it on disk.
#
#   publish.sh --body FILE --title TEXT --kind bug|feedback --fp HASH
#              [--repo OWNER/NAME|URL] [--approved [--accept-residual]] [--dry-run]
#   publish.sh --from-queue FILE [--approved [--accept-residual]] [--dry-run]
#   publish.sh --list
#
# --approved marks a human's explicit yes. Without it a run is an agent run:
# labels <kind>,agent-filed, and every gate below can queue it. A publish from
# the queue requires --approved. --accept-residual requires --approved.
#
# Order, before any gh call:
#   Config:   `afk-config.py validate`. Unreadable or invalid -> an agent run
#             queues (config-invalid); the target falls back to the manifest.
#   Target:   --repo, else `report-issue.repository`, else the plugin manifest's
#             `repository`.
#   Redact:   redact.py runs on the title and on the body — every field sent to
#             gh or written to the queue. A residual hit, or a redactor failure,
#             queues an agent run and refuses an approved one (exit 4) unless
#             --accept-residual.
#   Complete: the body holds every section ISSUE-TEMPLATE.md requires and the
#             visible Fingerprint row for HASH; otherwise it queues (incomplete).
#   Switch:   an agent run with `report-issue.auto-publish` other than true queues.
#   gh:       absent or logged out queues.
# Then dedup: an issue in the target (any state) whose body holds the visible
# Fingerprint row gets the body as a comment; else a new issue. A missing label
# is created first. The body always ends with `<!-- afk-issue-fp:HASH -->`.
#
# Queue: <main checkout>/.claude/afk-issues/<fp>.md, a meta comment block on
# top, redacted like the published text; the directory ignores itself.
# --from-queue deletes the draft once it lands. --list prints `<path>\t<title>`.
# --dry-run runs no gh and writes nothing: it prints the gh commands, the target,
# the redacted title and body, and the status it would reach.
#
# stdout, last line:
#   ISSUE: created <url> | commented <url> | dry-run <repo>
#        | queued <path> reason=<r> | would-queue reason=<r>
# Exit: 0 created/commented/dry-run/list, 2 usage, 3 queued or would-queue,
#       4 residual refused.

set -u

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
root=$(cd "$here/../../../.." && pwd)
py=python; command -v python >/dev/null 2>&1 || py=python3

usage() { echo "publish: $*" >&2; exit 2; }

body="" title="" kind="" fp="" repo="" approved=0 accept=0 dry=0 from_queue="" list=0
while [ $# -gt 0 ]; do
  case "$1" in
    --body) body=${2-}; shift 2 || usage "--body needs a file" ;;
    --title) title=${2-}; shift 2 || usage "--title needs text" ;;
    --kind) kind=${2-}; shift 2 || usage "--kind needs a value" ;;
    --fp) fp=${2-}; shift 2 || usage "--fp needs a hash" ;;
    --repo) repo=${2-}; shift 2 || usage "--repo needs a value" ;;
    --from-queue) from_queue=${2-}; shift 2 || usage "--from-queue needs a file" ;;
    --approved) approved=1; shift ;;
    --accept-residual) accept=1; shift ;;
    --dry-run) dry=1; shift ;;
    --list) list=1; shift ;;
    *) usage "unknown argument $1" ;;
  esac
done

main_checkout=$(git worktree list --porcelain 2>/dev/null | sed -n '1s/^worktree //p')
[ -n "$main_checkout" ] || main_checkout=$PWD
queue_dir="$main_checkout/.claude/afk-issues"

meta() { sed -n '/^<!-- afk-issue-meta$/,/^-->$/p' "$1" | sed -n "s/^$2: //p" | head -n 1; }

if [ "$list" = 1 ]; then
  for f in "$queue_dir"/*.md; do
    [ -f "$f" ] && printf '%s\t%s\n' "$f" "$(meta "$f" title)"
  done
  exit 0
fi

[ "$accept" = 0 ] || [ "$approved" = 1 ] || usage "--accept-residual needs --approved (a human's explicit yes)"

tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
labels=""
if [ -n "$from_queue" ]; then
  [ -f "$from_queue" ] || usage "no queued draft at $from_queue"
  [ "$approved" = 1 ] || [ "$dry" = 1 ] || usage "--from-queue needs --approved (a human's explicit yes)"
  title=$(meta "$from_queue" title); kind=$(meta "$from_queue" kind)
  fp=$(meta "$from_queue" fp); repo=$(meta "$from_queue" repo); labels=$(meta "$from_queue" labels)
  sed '/^<!-- afk-issue-meta$/,/^-->$/d' "$from_queue" > "$tmp/body.md"
  body="$tmp/body.md"
fi

[ -f "$body" ] || usage "--body must name a file"
[ -n "$title" ] || usage "--title is required"
case "$kind" in bug|feedback) ;; *) usage "--kind must be bug or feedback" ;; esac
case "$fp" in ''|*[!0-9a-f]*) usage "--fp must be the hex hash fingerprint.py printed" ;; esac
if [ -z "$labels" ]; then
  labels="$kind"; [ "$approved" = 1 ] || labels="$kind,agent-filed"
fi

# ---- config: fail closed. A value is trusted only from a configuration that
# validates; `get` exit 1 means absent, anything else means unreadable.
cfg_ok=1
"$py" "$root/scripts/afk-config.py" validate >/dev/null 2>"$tmp/config.err" || cfg_ok=0
cfg() {
  [ "$cfg_ok" = 1 ] || return 0
  local value rc
  value=$("$py" "$root/scripts/afk-config.py" get "$1" 2>>"$tmp/config.err"); rc=$?
  case "$rc" in 0) printf '%s' "$value" ;; 1) ;; *) cfg_ok=0 ;; esac
}
if [ -z "$repo" ]; then
  repo=$(cfg report-issue.repository)
  [ "$cfg_ok" = 1 ] || repo=""
fi
[ -n "$repo" ] || repo=$("$py" -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8")).get("repository", ""))' "$root/.claude-plugin/plugin.json" 2>/dev/null)
repo=$(printf '%s' "$repo" | sed -E 's#^(https?://|git@)?(www\.)?github\.com[/:]##; s#\.git$##; s#/+$##')
case "$repo" in */*) ;; *) usage "no target repository resolves (got '$repo')" ;; esac
auto=$(cfg report-issue.auto-publish)

# ---- redact every outgoing field. The queue stores only redacted text.
redact() { "$py" "$here/redact.py" --plugin-root "$root" --repo-root "$main_checkout" --keep-repo "$repo" "$@"; }
residual=0
printf '%s\n' "$title" | tr '\r\n' '  ' > "$tmp/title.raw"
redact -o "$tmp/title.txt" "$tmp/title.raw" 2>>"$tmp/residual" || residual=1
[ -s "$tmp/title.txt" ] || printf 'unredactable title\n' > "$tmp/title.txt"
title=$(sed 's/[[:space:]]*$//' "$tmp/title.txt" | head -n 1)
redact -o "$tmp/issue.md" "$body" 2>>"$tmp/residual" || residual=1
[ -f "$tmp/issue.md" ] || { : > "$tmp/issue.md"; residual=1; }
marker="<!-- afk-issue-fp:$fp -->"
grep -qF "$marker" "$tmp/issue.md" || printf '\n%s\n' "$marker" >> "$tmp/issue.md"
fp_row="| Fingerprint | \`$fp\` |"

queue() {
  if [ "$dry" = 1 ]; then echo "ISSUE: would-queue reason=$1"; exit 3; fi
  mkdir -p "$queue_dir"
  [ -f "$queue_dir/.gitignore" ] || printf '*\n' > "$queue_dir/.gitignore"
  local target="$queue_dir/$fp.md"
  {
    printf '<!-- afk-issue-meta\ntitle: %s\nkind: %s\nfp: %s\nrepo: %s\nlabels: %s\nreason: %s\n-->\n' \
      "$title" "$kind" "$fp" "$repo" "$labels" "$1"
    cat "$tmp/issue.md"
  } > "$target"
  echo "ISSUE: queued $target reason=$1"
  echo "publish after a human's yes: bash \"\$AFK_PLUGIN_ROOT/skills/utils/report-issue/scripts/publish.sh\" --from-queue \"$target\" --approved"
  exit 3
}

# ---- completeness. Synchronized copy of the section set ISSUE-TEMPLATE.md owns.
for section in "## Summary" "## Goal" "## Expected" "## Actual" "## Steps to reproduce" \
               "## Evidence" "## Environment" "## Suspected owner"; do
  grep -qx "$section" "$tmp/issue.md" || queue "incomplete:${section#\#\# }"
done
grep -qF "$fp_row" "$tmp/issue.md" || queue "incomplete:Fingerprint row"

if [ "$residual" = 1 ]; then
  cat "$tmp/residual" >&2
  [ "$approved" = 1 ] || queue residual
  [ "$accept" = 1 ] || { echo "ISSUE: refused residual (after the human accepts each hit, re-run with --approved --accept-residual)"; exit 4; }
fi
if [ "$approved" = 0 ]; then
  [ "$cfg_ok" = 1 ] || { cat "$tmp/config.err" >&2; queue config-invalid; }
  case "$auto" in ''|true) ;; *) queue auto-publish-off ;; esac
fi

if [ "$dry" = 1 ]; then
  printf 'DRY-RUN: gh issue list -R %q --state all --search %q --json number,url,body --limit 20\n' "$repo" "$fp in:body"
  printf 'DRY-RUN: gh label list -R %q --json name --limit 200\n' "$repo"
  printf 'DRY-RUN: gh issue create -R %q --title %q --body-file <body below>' "$repo" "$title"
  for label in ${labels//,/ }; do printf ' --label %q' "$label"; done
  printf '\n--- target: %s\n--- title: %s\n--- body:\n' "$repo" "$title"
  cat "$tmp/issue.md"
  echo "ISSUE: dry-run $repo"
  exit 0
fi

command -v gh >/dev/null 2>&1 || queue no-gh
gh auth status >/dev/null 2>&1 || queue no-gh-auth

gh issue list -R "$repo" --state all --search "$fp in:body" --json number,url,body --limit 20 > "$tmp/found.json" 2>/dev/null \
  || queue gh-search-failed
existing=$("$py" -c '
import json, sys
row = sys.argv[2]
for issue in json.load(open(sys.argv[1], encoding="utf-8")):
    if row in (issue.get("body") or ""):
        print(issue["number"], issue["url"]); break
' "$tmp/found.json" "$fp_row" 2>/dev/null)

if [ -n "$existing" ]; then
  number=${existing%% *}
  { printf 'Seen again. New evidence:\n\n'; cat "$tmp/issue.md"; } > "$tmp/comment.md"
  gh issue comment "$number" -R "$repo" --body-file "$tmp/comment.md" >/dev/null 2>&1 || queue gh-comment-failed
  [ -n "$from_queue" ] && rm -f "$from_queue"
  echo "ISSUE: commented ${existing#* }"
  exit 0
fi

have=$(gh label list -R "$repo" --json name --limit 200 2>/dev/null) || queue gh-label-failed
label_args=()
for label in ${labels//,/ }; do
  if ! printf '%s' "$have" | grep -q "\"name\":\"$label\""; then
    case "$label" in
      bug) color=d73a4a desc="A plugin defect" ;;
      feedback) color=0e8a16 desc="A feature request or usability opinion" ;;
      *) color=ededed desc="Filed by an agent through /afk:report-issue" ;;
    esac
    gh label create "$label" -R "$repo" --color "$color" --description "$desc" >/dev/null 2>&1 || queue gh-label-failed
  fi
  label_args+=(--label "$label")
done

url=$(gh issue create -R "$repo" --title "$title" --body-file "$tmp/issue.md" "${label_args[@]}" 2>/dev/null) || queue gh-create-failed
[ -n "$from_queue" ] && rm -f "$from_queue"
echo "ISSUE: created $url"
exit 0
