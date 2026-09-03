#!/usr/bin/env bash
# forge/github — the GitHub adapter, over the `gh` CLI.
#
#   bash forge.sh <verb> [json-payload]
#
# Same contract as every forge kind: one JSON object on stdout, exit 3 for a
# verb this kind does not implement, exit 4 when `gh` is absent, and the
# four-value exit code on `ci-wait` alone (ADAPTERS.md, CONTRACT.md).
#
# The normalized change object is the same one GitLab answers with — id, url,
# title, state, draft, source, target, pipeline.status — so a skill written
# against one forge runs unchanged on the other. "Pipeline" here is the combined
# status of the head commit's checks.
#
# Authentication is whatever `gh auth login` established.

set -u

FORGE_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PLUGIN_ROOT=${AFK_PLUGIN_ROOT:-$(cd "$FORGE_DIR/../../.." && pwd)}

# The configuration this repository selected. A forge script runs in its own
# process, so the AFK_CFG_* view the caller loaded is not inherited: load it here.
# shellcheck source=/dev/null
. "$PLUGIN_ROOT/hooks/lib/config.sh"
afk_config_load

verb=${1:-}
payload=${2:-'{}'}

PY=python
command -v python >/dev/null 2>&1 || PY=python3

unavailable() {
  printf '{"unavailable":true,"verb":"%s","reason":"%s"}\n' "$verb" "$1"
  exit 4
}

command -v gh >/dev/null 2>&1 || unavailable "forge: github — the \`gh\` CLI is not on PATH"

arg() {
  printf '%s' "$payload" | "$PY" -c '
import json, sys
key, default = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "")
try:
    value = json.load(sys.stdin).get(key, default)
except Exception:
    value = default
if value is None or value is False:
    value = ""
elif value is True:
    value = "true"
elif isinstance(value, (list, tuple)):
    # Both CLIs take a repeated field as one comma-separated argument
    # (`--add-reviewer a,b`). Printing the Python list here is how a caller ends
    # up asking the forge for a user literally named "['a', 'b']".
    value = ",".join(str(v) for v in value)
print(value)
' "$1" "${2:-}"
}


# The project the change lives in. A `repo` in the payload wins. Otherwise
# `github.remote` names a git remote in this checkout and its URL identifies
# the project — the key exists so a repository with several remotes says which
# one is the forge. Neither set means "let the CLI derive it from the checkout",
# which is what it does inside a clone.
resolve_repo() {
  local explicit name url
  explicit=$(arg repo)
  if [ -n "$explicit" ]; then printf '%s\n' "$explicit"; return 0; fi
  name=${AFK_CFG_GITHUB_REMOTE:-}
  [ -n "$name" ] || return 0
  url=$(git remote get-url "$name" 2>/dev/null) || return 0
  [ -n "$url" ] || return 0
  "$PY" "$FORGE_DIR/../project_from_remote.py" "$url"
}

REPO_FLAG=()
_repo=$(resolve_repo)
[ -n "$_repo" ] && REPO_FLAG=(--repo "$_repo")

VIEW_FIELDS=number,url,title,state,isDraft,headRefName,baseRefName,author,statusCheckRollup

view_json() {  # $1 = change ref (branch name, number or URL)
  gh pr view "$1" "${REPO_FLAG[@]}" --json "$VIEW_FIELDS" 2>/dev/null
}

normalize() {
  "$PY" -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    print(json.dumps({"error": True, "reason": "gh returned no readable JSON"}))
    raise SystemExit(0)
# GitHub reports each check separately; the pipeline status is their rollup, in
# the same vocabulary the GitLab adapter answers with, so a caller compares one
# set of words.
checks = d.get("statusCheckRollup") or []
def state(c):
    return (c.get("conclusion") or c.get("state") or c.get("status") or "").upper()
seen = {state(c) for c in checks}
if not checks:
    status = ""
elif seen & {"FAILURE", "TIMED_OUT", "ACTION_REQUIRED", "STARTUP_FAILURE"}:
    status = "failed"
elif seen & {"CANCELLED", "CANCELED"}:
    status = "canceled"
elif seen & {"IN_PROGRESS", "QUEUED", "PENDING", "WAITING", "REQUESTED", ""}:
    status = "running"
else:
    status = "success"
print(json.dumps({
    "id": str(d.get("number") or ""),
    "url": d.get("url") or "",
    "title": d.get("title") or "",
    "draft": bool(d.get("isDraft")),
    "state": (d.get("state") or "").lower(),
    "source": d.get("headRefName") or "",
    "target": d.get("baseRefName") or "",
    "author": (d.get("author") or {}).get("login") or "",
    "pipeline": {"status": status},
}))
'
}

case "$verb" in

change-view)
  view_json "$(arg id)" | normalize
  ;;

change-diff)
  out=$(gh pr diff "$(arg id)" "${REPO_FLAG[@]}" 2>&1) || {
    printf '{"error":true,"verb":"change-diff","reason":%s}\n' \
      "$("$PY" -c 'import json,sys;print(json.dumps(sys.stdin.read()[:2000]))' <<<"$out")"
    exit 0
  }
  printf '%s' "$out" | "$PY" -c '
import json, sys
diff = sys.stdin.read()
print(json.dumps({"diff": diff, "lines": diff.count(chr(10)), "bytes": len(diff)}))
'
  ;;

change-fetch)
  ref=$(arg id)
  out_dir=$(arg out_dir "${CLAUDE_JOB_DIR:-/tmp}")
  mkdir -p "$out_dir"
  err="$out_dir/change.err"
  if ! gh pr view "$ref" "${REPO_FLAG[@]}" --json "$VIEW_FIELDS,body" > "$out_dir/mr.json" 2> "$err"; then
    reason=$(head -c 1000 "$err")
    grep -qi auth "$err" && reason="$reason (run \`gh auth login\`)"
    printf '{"error":true,"verb":"change-fetch","reason":%s}\n' \
      "$("$PY" -c 'import json,sys;print(json.dumps(sys.stdin.read()))' <<<"$reason")"
    exit 0
  fi
  if ! gh pr diff "$ref" "${REPO_FLAG[@]}" > "$out_dir/mr.diff" 2>>"$err"; then
    printf '{"error":true,"verb":"change-fetch","reason":"gh pr diff failed; see %s"}\n' "$err"
    exit 0
  fi
  normalize < "$out_dir/mr.json" | "$PY" -c '
import json, os, sys
d = json.load(sys.stdin)
out = sys.argv[1]
diff = os.path.join(out, "mr.diff")
d["files"] = {"metadata": os.path.join(out, "mr.json"), "diff": diff}
with open(diff, encoding="utf-8", errors="replace") as fh:
    text = fh.read()
d["diff_lines"] = text.count(chr(10))
d["diff_bytes"] = len(text)
print(json.dumps(d))
' "$out_dir"
  ;;

change-state)
  view_json "$(arg id)" | "$PY" -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    print(json.dumps({"state": "", "found": False}))
    raise SystemExit(0)
# GitHub says MERGED / CLOSED / OPEN; the contract says merged / closed / opened,
# which is what every caller compares against.
mapping = {"MERGED": "merged", "CLOSED": "closed", "OPEN": "opened"}
print(json.dumps({"state": mapping.get(d.get("state") or "", (d.get("state") or "").lower()),
                  "found": True, "id": str(d.get("number") or ""),
                  "url": d.get("url") or ""}))
'
  ;;

ci-status)
  view_json "$(arg id)" | normalize | "$PY" -c '
import json, sys
d = json.load(sys.stdin)
print(json.dumps({"status": (d.get("pipeline") or {}).get("status", ""), "url": d.get("url", "")}))
'
  ;;

auth-status)
  if gh auth status >/dev/null 2>&1; then
    user=$(gh api user --jq .login 2>/dev/null)
    printf '{"authenticated":true,"user":"%s"}\n' "$user"
  else
    printf '{"authenticated":false,"reason":"forge: github — not logged in; run `gh auth login`"}\n'
  fi
  ;;

change-create-draft)
  title=$(arg title); target=$(arg target); source=$(arg source); body=$(arg body)
  create=(gh pr create "${REPO_FLAG[@]}" --draft --title "$title" --body "$body")
  [ -n "$target" ] && create+=(--base "$target")
  [ -n "$source" ] && create+=(--head "$source")
  reviewer=$(arg reviewer); [ -n "$reviewer" ] && create+=(--reviewer "$reviewer")
  assignee=$(arg assignee); [ -n "$assignee" ] && create+=(--assignee "$assignee")
  out=$("${create[@]}" 2>&1) || {
    printf '{"error":true,"verb":"change-create-draft","reason":%s}\n' \
      "$("$PY" -c 'import json,sys;print(json.dumps(sys.stdin.read()[:2000]))' <<<"$out")"
    exit 0
  }
  url=$(printf '%s\n' "$out" | grep -oE 'https?://[^ ]+/pull/[0-9]+' | tail -1)
  printf '{"url":"%s","id":"%s","draft":true}\n' "$url" "${url##*/}"
  ;;

change-ready)
  out=$(gh pr ready "$(arg id)" "${REPO_FLAG[@]}" 2>&1) || {
    printf '{"error":true,"verb":"change-ready","reason":%s}\n' \
      "$("$PY" -c 'import json,sys;print(json.dumps(sys.stdin.read()[:2000]))' <<<"$out")"
    exit 0
  }
  printf '{"ok":true,"id":"%s","draft":false}\n' "$(arg id)"
  ;;

change-reviewers)
  ref=$(arg id); who=$(arg reviewers)
  [ -n "$who" ] || { printf '{"error":true,"reason":"change-reviewers needs `reviewers`"}\n'; exit 0; }
  out=$(gh pr edit "$ref" "${REPO_FLAG[@]}" --add-reviewer "$who" 2>&1) || {
    printf '{"error":true,"verb":"change-reviewers","reason":%s}\n' \
      "$("$PY" -c 'import json,sys;print(json.dumps(sys.stdin.read()[:2000]))' <<<"$out")"
    exit 0
  }
  printf '{"ok":true,"id":"%s","reviewers":"%s"}\n' "$ref" "$who"
  ;;

change-update-body)
  ref=$(arg id); body=$(arg body)
  out=$(gh pr edit "$ref" "${REPO_FLAG[@]}" --body "$body" 2>&1) || {
    printf '{"error":true,"verb":"change-update-body","reason":%s}\n' \
      "$("$PY" -c 'import json,sys;print(json.dumps(sys.stdin.read()[:2000]))' <<<"$out")"
    exit 0
  }
  printf '{"ok":true,"id":"%s"}\n' "$ref"
  ;;

change-comment)
  ref=$(arg id); text=$(arg text); file=$(arg file); line=$(arg line)
  if [ -z "$file" ]; then
    out=$(gh pr comment "$ref" "${REPO_FLAG[@]}" --body "$text" 2>&1) || {
      printf '{"error":true,"verb":"change-comment","reason":%s}\n' \
        "$("$PY" -c 'import json,sys;print(json.dumps(sys.stdin.read()[:2000]))' <<<"$out")"
      exit 0
    }
    printf '{"ok":true,"id":"%s","inline":false}\n' "$ref"
    exit 0
  fi
  # An inline comment is a review comment on the head commit; `gh pr comment`
  # cannot place one, so it goes through the API with the commit id.
  meta=$(gh pr view "$ref" "${REPO_FLAG[@]}" --json number,headRefOid 2>/dev/null)
  repo=$_repo
  [ -n "$repo" ] || repo=$(gh repo view --json nameWithOwner --jq .nameWithOwner 2>/dev/null)
  # `gh` prints its field errors on stderr and nothing on stdout, so read the
  # answer defensively: a traceback here would leave the caller with neither a
  # comment nor a JSON object it can read. Take each field through its own
  # command substitution, which strips the line ending; `read` would keep the
  # carriage return of a CRLF line and send it to the API inside the value.
  meta_field() {
    printf '%s' "$meta" | "$PY" -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    d = {}
sys.stdout.write(str(d.get(sys.argv[1], "")))
' "$1"
  }
  number=$(meta_field number)
  commit=$(meta_field headRefOid)
  if [ -z "$number" ] || [ -z "$commit" ] || [ -z "$repo" ]; then
    printf '{"error":true,"verb":"change-comment","reason":"could not resolve the change number, head commit and project needed for an inline comment on %s"}\n' "$ref"
    exit 0
  fi
  out=$(gh api -X POST "repos/$repo/pulls/$number/comments" \
        -f body="$text" -f commit_id="$commit" -f path="$file" \
        -F line="$line" -f side=RIGHT 2>&1) || {
    printf '{"error":true,"verb":"change-comment","reason":%s}\n' \
      "$("$PY" -c 'import json,sys;print(json.dumps(sys.stdin.read()[:2000]))' <<<"$out")"
    exit 0
  }
  printf '%s' "$out" | "$PY" -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    print(json.dumps({"ok": False, "reason": "no readable response"}))
    raise SystemExit(0)
print(json.dumps({"ok": bool(d.get("id")), "inline": True, "type": "ReviewComment",
                  "url": d.get("html_url", "")}))
'
  ;;

thread-list)
  # GitHub has no discussion object: a thread is a root review comment plus the
  # comments whose `in_reply_to_id` points at it, so the grouping is done here
  # rather than left to the caller.
  ref=$(arg id)
  repo=$_repo
  [ -n "$repo" ] || repo=$(gh repo view --json nameWithOwner --jq .nameWithOwner 2>/dev/null)
  number=$(gh pr view "$ref" "${REPO_FLAG[@]}" --json number --jq .number 2>/dev/null)
  gh api --paginate "repos/$repo/pulls/$number/comments?per_page=100" 2>/dev/null   | "$PY" -c '
import json, sys
try:
    data = json.load(sys.stdin)
except Exception:
    print(json.dumps({"error": True, "reason": "gh returned no readable JSON"}))
    raise SystemExit(0)
roots, order = {}, []
for c in data if isinstance(data, list) else []:
    root = c.get("in_reply_to_id") or c.get("id")
    if root not in roots:
        roots[root] = []
        order.append(root)
    roots[root].append(c)
threads = []
for root in order:
    notes = roots[root]
    threads.append({
        "id": str(root),
        # GitHub resolution lives on a GraphQL review thread, not on these
        # comments, so it is reported as unknown rather than guessed as false.
        "resolved": None,
        "file": notes[0].get("path"),
        "notes": [{"id": n.get("id"),
                   "author": (n.get("user") or {}).get("login"),
                   "type": "ReviewComment",
                   "body": n.get("body") or ""} for n in notes],
    })
print(json.dumps({"threads": threads, "count": len(threads)}))
'
  ;;

thread-reply)
  ref=$(arg id); thread=$(arg thread); text=$(arg text)
  repo=$_repo
  [ -n "$repo" ] || repo=$(gh repo view --json nameWithOwner --jq .nameWithOwner 2>/dev/null)
  number=$(gh pr view "$ref" "${REPO_FLAG[@]}" --json number --jq .number 2>/dev/null)
  out=$(gh api -X POST "repos/$repo/pulls/$number/comments/$thread/replies"         -f body="$text" 2>&1) || {
    printf '{"error":true,"verb":"thread-reply","reason":%s}
'       "$("$PY" -c 'import json,sys;print(json.dumps(sys.stdin.read()[:2000]))' <<<"$out")"
    exit 0
  }
  printf '{"ok":true,"thread":"%s"}
' "$thread"
  ;;

thread-resolve)
  # Resolving needs the GraphQL review-thread node id, which the REST comment
  # ids above are not. Rather than resolve the wrong thread, this answers
  # unsupported: a referee that cannot resolve leaves the thread open, which is
  # visible, where resolving the wrong one silently hides a finding.
  printf '{"unsupported":true,"verb":"thread-resolve","reason":"forge: github — resolving a review thread needs its GraphQL node id, which this adapter does not carry; leave the thread open and say so"}
'
  exit 3
  ;;

change-close)
  out=$(gh pr close "$(arg id)" "${REPO_FLAG[@]}" 2>&1) || {
    printf '{"error":true,"verb":"change-close","reason":%s}\n' \
      "$("$PY" -c 'import json,sys;print(json.dumps(sys.stdin.read()[:2000]))' <<<"$out")"
    exit 0
  }
  printf '{"ok":true,"id":"%s","state":"closed"}\n' "$(arg id)"
  ;;

ci-wait)
  # Same exit-code contract as forge/gitlab: 0 success, 1 failed/canceled,
  # 2 budget exhausted (the run keeps going), 3 unreadable after 3 tries.
  ref=$(arg id)
  budget=$(arg budget 5400)
  interval=$(arg interval 180)
  errors=0
  elapsed=0
  while [ "$elapsed" -lt "$budget" ]; do
    status=$(view_json "$ref" | normalize | "$PY" -c '
import json, sys
try:
    print((json.load(sys.stdin).get("pipeline") or {}).get("status") or "")
except Exception:
    print("")
')
    if [ -z "$status" ]; then
      errors=$((errors + 1))
      if [ "$errors" -ge 3 ]; then
        printf '{"status":"unreadable","elapsed":%s,"reason":"3 consecutive read errors on %s — auth or network, not a check verdict"}\n' "$elapsed" "$ref" >&2
        exit 3
      fi
    else
      errors=0
      case "$status" in
        success)
          printf '{"status":"success","elapsed":%s,"id":"%s"}\n' "$elapsed" "$ref"; exit 0 ;;
        failed|canceled)
          printf '{"status":"%s","elapsed":%s,"id":"%s"}\n' "$status" "$elapsed" "$ref"; exit 1 ;;
      esac
    fi
    sleep "$interval"
    elapsed=$((elapsed + interval))
  done
  printf '{"status":"running","elapsed":%s,"id":"%s","reason":"budget exhausted; the checks keep running"}\n' "$elapsed" "$ref" >&2
  exit 2
  ;;

*)
  printf '{"unsupported":true,"verb":"%s","reason":"forge/github has no verb %s"}\n' "$verb" "$verb"
  exit 3
  ;;
esac
