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
if [ "$#" -ge 2 ]; then
  payload=$2
else
  payload=$(cat)
  [ -n "$payload" ] || payload='{}'
fi

PY=python
command -v python >/dev/null 2>&1 || PY=python3

# Text going to or from the forge is UTF-8, and a console encoding is not: on a
# Windows terminal the default is cp1252, where an emoji in a change body raises
# UnicodeEncodeError inside every helper below and the field arrives EMPTY. The
# forge is the authority on what its text may contain, so pin the interpreter to
# UTF-8 rather than trimming what a body may say.
export PYTHONIOENCODING=utf-8

# A paginated read prints one JSON document per page, not one document holding
# every page, so a reader that calls json.load sees page 2 as trailing data and
# reports the whole answer unreadable. This prelude decodes the documents one
# after another and joins the arrays into the single list a caller expects.
PAGES='
import json

def _documents(text):
    decoder = json.JSONDecoder()
    index, out = 0, []
    while True:
        while index < len(text) and text[index].isspace():
            index += 1
        if index >= len(text):
            return out
        value, index = decoder.raw_decode(text, index)
        out.append(value)

def pages(text):
    documents = _documents(text)
    if not documents:
        raise ValueError("no JSON document in the answer")
    items = []
    for document in documents:
        if isinstance(document, list):
            items.extend(document)
        else:
            items.append(document)
    return items
'


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

bool_arg() {
  printf '%s' "$payload" | "$PY" -c '
import json, sys
key, default = sys.argv[1], sys.argv[2] == "true"
try:
    value = json.load(sys.stdin).get(key, default)
except Exception:
    value = default
print("true" if value is True else "false")
' "$1" "${2:-false}"
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

VIEW_FIELDS=number,url,title,state,isDraft,headRefName,baseRefName,headRefOid,baseRefOid,isCrossRepository,headRepository,author,statusCheckRollup

view_json() {  # $1 = change ref (branch name, number or URL)
  gh pr view "$1" "${REPO_FLAG[@]}" --json "$VIEW_FIELDS" 2>/dev/null
}

review_threads_json() {  # $1 repo, $2 pull request number
  local owner=${1%%/*} name=${1#*/}
  gh api graphql --paginate -F owner="$owner" -F name="$name" -F number="$2" -f query='
query($owner:String!,$name:String!,$number:Int!,$endCursor:String) {
  repository(owner:$owner,name:$name) {
    pullRequest(number:$number) {
      reviewThreads(first:100,after:$endCursor) {
        nodes { id isResolved comments(first:100) { nodes { databaseId } } }
        pageInfo { hasNextPage endCursor }
      }
    }
  }
}' 2>/dev/null | "$PY" -c '
import json, sys
decoder=json.JSONDecoder(); text=sys.stdin.read(); i=0; out={}
while True:
    while i < len(text) and text[i].isspace(): i += 1
    if i >= len(text): break
    doc, i = decoder.raw_decode(text, i)
    threads=((((doc.get("data") or {}).get("repository") or {}).get("pullRequest") or {}).get("reviewThreads") or {}).get("nodes") or []
    for thread in threads:
        comments=(thread.get("comments") or {}).get("nodes") or []
        if comments and comments[0].get("databaseId") is not None:
            out[str(comments[0]["databaseId"])]={"node":thread.get("id") or "", "resolved":bool(thread.get("isResolved"))}
print(json.dumps(out))
'
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
    "head_sha": d.get("headRefOid") or "",
    "base_sha": d.get("baseRefOid") or "",
    "head_ref": "pull/{}/head".format(d.get("number") or ""),
    "cross_fork": bool(d.get("isCrossRepository")),
    "blob_base": ((d.get("headRepository") or {}).get("url") or
                  ("https://github.com/" + (d.get("headRepository") or {}).get("nameWithOwner", "")
                   if (d.get("headRepository") or {}).get("nameWithOwner") else "")) +
                 ("/blob" if d.get("headRepository") else ""),
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
  ref=$(arg id); text=$(arg text); file=$(arg file)
  old_path=$(arg old_path "$file"); new_path=$(arg new_path "$file")
  side=$(arg side new); line=$(arg line); old_line=$(arg old_line)
  repo=$_repo
  [ -n "$repo" ] || repo=$(gh repo view --json nameWithOwner --jq .nameWithOwner 2>/dev/null)
  if [ -z "$file" ] && [ -z "$old_path" ] && [ -z "$new_path" ]; then
    number=$(gh pr view "$ref" "${REPO_FLAG[@]}" --json number --jq .number 2>/dev/null)
    out=$(gh api -X POST "repos/$repo/issues/$number/comments" -f body="$text" 2>&1) || {
      printf '{"error":true,"verb":"change-comment","reason":%s}\n' \
        "$("$PY" -c 'import json,sys;print(json.dumps(sys.stdin.read()[:2000]))' <<<"$out")"
      exit 0
    }
    printf '%s' "$out" | "$PY" -c '
import json, sys
try: d = json.load(sys.stdin)
except Exception: d = {}
ident = str(d.get("id") or "")
print(json.dumps({"ok": bool(ident), "inline": False, "thread": "", "comment": ident,
                  "url": d.get("html_url") or "",
                  **({} if ident else {"reason": "no readable response"})}))
'
    exit 0
  fi
  # An inline comment is a review comment on the head commit; `gh pr comment`
  # cannot place one, so it goes through the API with the commit id.
  meta=$(gh pr view "$ref" "${REPO_FLAG[@]}" --json number,headRefOid 2>/dev/null)
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
  api_side=RIGHT; api_path=$new_path; api_line=$line
  if [ "$side" = old ]; then api_side=LEFT; api_path=$old_path; api_line=$old_line; fi
  [ -n "$api_path" ] && [ -n "$api_line" ] || {
    printf '{"ok":false,"inline":false,"thread":"","comment":"","url":"","reason":"inline comment needs a path and line for its side"}\n'
    exit 0
  }
  out=$(gh api -X POST "repos/$repo/pulls/$number/comments" \
        -f body="$text" -f commit_id="$commit" -f path="$api_path" \
        -F line="$api_line" -f side="$api_side" 2>&1) || {
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
ident = str(d.get("id") or "")
print(json.dumps({"ok": bool(ident), "inline": True, "thread": ident, "comment": ident,
                  "url": d.get("html_url", ""),
                  **({} if ident else {"reason": "no comment id in response"})}))
'
  ;;

note-list)
  ref=$(arg id)
  repo=$_repo
  [ -n "$repo" ] || repo=$(gh repo view --json nameWithOwner --jq .nameWithOwner 2>/dev/null)
  number=$(gh pr view "$ref" "${REPO_FLAG[@]}" --json number --jq .number 2>/dev/null)
  gh api --paginate "repos/$repo/issues/$number/comments?per_page=100" 2>/dev/null \
    | "$PY" -c "$PAGES"'
import json, sys
try:
    data = pages(sys.stdin.read())
except Exception:
    print(json.dumps({"error": True, "reason": "gh returned no readable JSON"}))
    raise SystemExit(0)
notes = [{"id": str(n.get("id") or ""),
          "author": (n.get("user") or {}).get("login") or "",
          "body": n.get("body") or "",
          "created_at": n.get("created_at") or "",
          "updated_at": n.get("updated_at") or ""} for n in data]
notes.sort(key=lambda n: (n["created_at"], n["id"]))
print(json.dumps({"notes": notes, "count": len(notes)}))
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
  graph=$(review_threads_json "$repo" "$number")
  gh api --paginate "repos/$repo/pulls/$number/comments?per_page=100" 2>/dev/null   | "$PY" -c "$PAGES"'
import json, sys
graph=json.loads(sys.argv[1])
try:
    data = pages(sys.stdin.read())
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
missing = [str(root) for root in order if str(root) not in graph]
if missing:
    print(json.dumps({"error": True, "reason": "GraphQL review thread missing for REST roots: " + ", ".join(missing)}))
    raise SystemExit(0)
threads = []
for root in order:
    notes = sorted(roots[root], key=lambda n: (n.get("created_at") or "", str(n.get("id") or "")))
    first = notes[0]
    api_side = first.get("side") or "RIGHT"
    side = "old" if api_side == "LEFT" else "new"
    line = first.get("line") if side == "new" else None
    old_line = ((first.get("line") if first.get("line") is not None else first.get("original_line"))
                if side == "old" else None)
    threads.append({
        "id": str(root),
        "resolved": bool((graph.get(str(root)) or {}).get("resolved")),
        "file": first.get("path"),
        "side": side, "line": line, "old_line": old_line,
        "old_path": first.get("old_path") or first.get("path"),
        "new_path": first.get("new_path") or first.get("path"),
        "url": first.get("html_url") or "",
        "notes": [{"id": n.get("id"),
                   "author": (n.get("user") or {}).get("login"),
                   "type": "ReviewComment",
                   "body": n.get("body") or "",
                   "created_at": n.get("created_at") or "",
                   "updated_at": n.get("updated_at") or ""} for n in notes],
    })
threads.sort(key=lambda t: ((t["notes"][0]["created_at"] if t["notes"] else ""), t["id"]))
print(json.dumps({"threads": threads, "count": len(threads)}))
' "$graph"
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
  ref=$(arg id); thread=$(arg thread); state=$(bool_arg resolved true)
  repo=$_repo
  [ -n "$repo" ] || repo=$(gh repo view --json nameWithOwner --jq .nameWithOwner 2>/dev/null)
  number=$(gh pr view "$ref" "${REPO_FLAG[@]}" --json number --jq .number 2>/dev/null)
  graph=$(review_threads_json "$repo" "$number")
  node=$(printf '%s' "$graph" | "$PY" -c 'import json,sys;print((json.load(sys.stdin).get(sys.argv[1]) or {}).get("node", ""))' "$thread")
  current=$(printf '%s' "$graph" | "$PY" -c 'import json,sys;print("true" if (json.load(sys.stdin).get(sys.argv[1]) or {}).get("resolved") else "false")' "$thread")
  if [ -z "$node" ]; then
    printf '{"error":true,"verb":"thread-resolve","reason":"could not map REST root %s to a GraphQL review thread"}\n' "$thread"
    exit 0
  fi
  if [ "$current" = "$state" ]; then
    printf '{"ok":true,"thread":"%s","resolved":%s}\n' "$thread" "$state"
    exit 0
  fi
  mutation=resolveReviewThread
  [ "$state" = true ] || mutation=unresolveReviewThread
  out=$(gh api graphql -F threadId="$node" -f query="mutation(\$threadId:ID!){$mutation(input:{threadId:\$threadId}){thread{id isResolved}}}" 2>&1) || {
    printf '{"error":true,"verb":"thread-resolve","reason":%s}\n' \
      "$("$PY" -c 'import json,sys;print(json.dumps(sys.stdin.read()[:2000]))' <<<"$out")"
    exit 0
  }
  printf '{"ok":true,"thread":"%s","resolved":%s}\n' "$thread" "$state"
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
  # A poll that never advances the clock never ends: an interval of 0
  # would spin against the forge until the caller is killed.
  [ "$interval" -gt 0 ] 2>/dev/null || interval=1
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
        printf 'forge: %s could not be read 3 times running — auth or network, not a check verdict\n' "$ref" >&2
        printf '{"status":"unreadable","elapsed":%s,"reason":"3 consecutive read errors on %s — auth or network, not a check verdict"}\n' "$elapsed" "$ref"
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
  printf 'forge: budget of %ss is spent on %s; the checks keep running\n' "$elapsed" "$ref" >&2
  printf '{"status":"running","elapsed":%s,"id":"%s","reason":"budget exhausted; the checks keep running"}\n' "$elapsed" "$ref"
  exit 2
  ;;

*)
  printf '{"unsupported":true,"verb":"%s","reason":"forge/github has no verb %s"}\n' "$verb" "$verb"
  exit 3
  ;;
esac
