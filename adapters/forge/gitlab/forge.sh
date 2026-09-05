#!/usr/bin/env bash
# forge/gitlab — the GitLab adapter, over the `glab` CLI.
#
#   bash forge.sh <verb> [json-payload]
#
# Every verb prints ONE JSON object and exits 0. A verb this kind does not
# implement prints {"unsupported": true, ...} and exits 3; a missing `glab`
# prints {"unavailable": true, ...} and exits 4. `ci-wait` is the exception the
# contract names: it carries a four-value exit code a skill routes on.
#
# The normalized change object every forge answers with:
#   id, url, title, state, draft, source, target, pipeline.status
# GitLab's own field names are not passed through — a skill that read `iid` here
# would break the moment the repository moved to GitHub.
#
# Authentication is whatever `glab auth login` established. Nothing here reads a
# token, and no configuration file holds one.

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


unsupported() {
  printf '{"unsupported":true,"verb":"%s","reason":"forge/gitlab has no verb %s"}\n' "$verb" "$verb"
  exit 3
}

unavailable() {
  printf '{"unavailable":true,"verb":"%s","reason":"%s"}\n' "$verb" "$1"
  exit 4
}

command -v glab >/dev/null 2>&1 || unavailable "forge: gitlab — the \`glab\` CLI is not on PATH"

# arg <key> [default] — one value out of the JSON payload, as text.
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
# `gitlab.remote` names a git remote in this checkout and its URL identifies
# the project — the key exists so a repository with several remotes says which
# one is the forge. Neither set means "let the CLI derive it from the checkout",
# which is what it does inside a clone.
resolve_repo() {
  local explicit name url
  explicit=$(arg repo)
  if [ -n "$explicit" ]; then printf '%s\n' "$explicit"; return 0; fi
  name=${AFK_CFG_GITLAB_REMOTE:-}
  [ -n "$name" ] || return 0
  url=$(git remote get-url "$name" 2>/dev/null) || return 0
  [ -n "$url" ] || return 0
  "$PY" "$FORGE_DIR/../project_from_remote.py" "$url"
}

repo_flag() {
  local explicit; explicit=$(resolve_repo)
  [ -n "$explicit" ] && { printf -- '-R\n%s\n' "$explicit"; return 0; }
  return 0
}

mapfile -t REPO_FLAG < <(repo_flag)

# ---------------------------------------------------------------------------
# reads
# ---------------------------------------------------------------------------

# One `glab mr view -F json`, normalized. Prints the normalized object.
normalize() {
  "$PY" -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    print(json.dumps({"error": True, "reason": "glab returned no readable JSON"}))
    raise SystemExit(0)
pipeline = d.get("head_pipeline") or d.get("pipeline") or {}
source = d.get("source_branch") or ""
title = d.get("title") or ""
print(json.dumps({
    "id": str(d.get("iid") or d.get("id") or ""),
    "url": d.get("web_url") or "",
    "title": title,
    # GitLab marks a draft with the title prefix as well as the flag; either is
    # authoritative, and an old server sets only the prefix.
    "draft": bool(d.get("draft") or d.get("work_in_progress")
                  or title.lower().startswith(("draft:", "wip:"))),
    "state": d.get("state") or "",
    "source": source,
    "target": d.get("target_branch") or "",
    "author": (d.get("author") or {}).get("username") or "",
    "pipeline": {"status": pipeline.get("status") or ""},
}))
'
}

view_json() {  # $1 = change ref (branch name or id)
  glab mr view "$1" "${REPO_FLAG[@]}" -F json 2>/dev/null
}

case "$verb" in

change-view)
  view_json "$(arg id)" | normalize
  ;;

change-diff)
  ref=$(arg id)
  out=$(glab mr diff "$ref" "${REPO_FLAG[@]}" --color=never 2>&1) || {
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
  # Metadata + raw diff to files, for a reviewer that must read a change it did
  # not create. Accepts a URL as well as a ref: `glab` autodetects from the
  # checkout when given a bare URL, which fails outside one, so the project path
  # and the id are pulled out of the URL and passed explicitly.
  ref=$(arg id)
  out_dir=$(arg out_dir "${CLAUDE_JOB_DIR:-/tmp}")
  mkdir -p "$out_dir"
  fetch_flag=("${REPO_FLAG[@]}")
  case "$ref" in
    http*://*/-/merge_requests/*)
      project=${ref#*://}; project=${project#*/}; project=${project%%/-/merge_requests/*}
      iid=${ref##*/merge_requests/}; iid=${iid%%[!0-9]*}
      fetch_flag=(-R "$project"); ref=$iid ;;
  esac
  err="$out_dir/change.err"
  if ! glab mr view "$ref" "${fetch_flag[@]}" -F json > "$out_dir/mr.json" 2> "$err"; then
    reason=$(head -c 1000 "$err")
    grep -qi auth "$err" && reason="$reason (run \`glab auth login\`)"
    printf '{"error":true,"verb":"change-fetch","reason":%s}\n' \
      "$("$PY" -c 'import json,sys;print(json.dumps(sys.stdin.read()))' <<<"$reason")"
    exit 0
  fi
  if ! glab mr diff "$ref" "${fetch_flag[@]}" --color=never > "$out_dir/mr.diff" 2>>"$err"; then
    printf '{"error":true,"verb":"change-fetch","reason":"glab mr diff failed; see %s"}\n' "$err"
    exit 0
  fi
  normalized=$(normalize < "$out_dir/mr.json")
  printf '%s' "$normalized" | "$PY" -c '
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
  # The one read gc uses: is this branch's change merged? Answers the state and
  # nothing else, so a caller never greps JSON for it.
  view_json "$(arg id)" | "$PY" -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    print(json.dumps({"state": "", "found": False}))
    raise SystemExit(0)
print(json.dumps({"state": d.get("state") or "", "found": True,
                  "id": str(d.get("iid") or ""), "url": d.get("web_url") or ""}))
'
  ;;

ci-status)
  view_json "$(arg id)" | "$PY" -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    print(json.dumps({"status": ""}))
    raise SystemExit(0)
p = d.get("head_pipeline") or d.get("pipeline") or {}
print(json.dumps({"status": p.get("status") or "", "url": p.get("web_url") or ""}))
'
  ;;

auth-status)
  if glab auth status >/dev/null 2>&1; then
    user=$(glab api user 2>/dev/null | "$PY" -c 'import json,sys;print(json.load(sys.stdin).get("username",""))' 2>/dev/null)
    printf '{"authenticated":true,"user":"%s"}\n' "$user"
  else
    printf '{"authenticated":false,"reason":"forge: gitlab — not logged in; run `glab auth login`"}\n'
  fi
  ;;

# ---------------------------------------------------------------------------
# writes
# ---------------------------------------------------------------------------

change-create-draft)
  title=$(arg title); target=$(arg target); source=$(arg source)
  body=$(arg body)
  create=(glab mr create "${REPO_FLAG[@]}" --draft --yes --title "$title" --description "$body")
  [ -n "$target" ] && create+=(--target-branch "$target")
  [ -n "$source" ] && create+=(--source-branch "$source")
  reviewer=$(arg reviewer); [ -n "$reviewer" ] && create+=(--reviewer "$reviewer")
  assignee=$(arg assignee); [ -n "$assignee" ] && create+=(--assignee "$assignee")
  out=$("${create[@]}" 2>&1) || {
    printf '{"error":true,"verb":"change-create-draft","reason":%s}\n' \
      "$("$PY" -c 'import json,sys;print(json.dumps(sys.stdin.read()[:2000]))' <<<"$out")"
    exit 0
  }
  url=$(printf '%s\n' "$out" | grep -oE 'https?://[^ ]+/-/merge_requests/[0-9]+' | tail -1)
  printf '{"url":"%s","id":"%s","draft":true}\n' "$url" "${url##*/}"
  ;;

change-ready)
  out=$(glab mr update "$(arg id)" "${REPO_FLAG[@]}" --ready 2>&1) || {
    printf '{"error":true,"verb":"change-ready","reason":%s}\n' \
      "$("$PY" -c 'import json,sys;print(json.dumps(sys.stdin.read()[:2000]))' <<<"$out")"
    exit 0
  }
  printf '{"ok":true,"id":"%s","draft":false}\n' "$(arg id)"
  ;;

change-reviewers)
  ref=$(arg id); who=$(arg reviewers)
  [ -n "$who" ] || { printf '{"error":true,"reason":"change-reviewers needs `reviewers`"}\n'; exit 0; }
  out=$(glab mr update "$ref" "${REPO_FLAG[@]}" --reviewer "$who" 2>&1) || {
    printf '{"error":true,"verb":"change-reviewers","reason":%s}\n' \
      "$("$PY" -c 'import json,sys;print(json.dumps(sys.stdin.read()[:2000]))' <<<"$out")"
    exit 0
  }
  printf '{"ok":true,"id":"%s","reviewers":"%s"}\n' "$ref" "$who"
  ;;

change-update-body)
  ref=$(arg id); body=$(arg body)
  # Editing a body is not a decision to publish, but `glab mr update` clears the
  # draft flag as a side effect: the title comes back without its prefix and the
  # change becomes reviewable. Read the flag first, restore it after, and say in
  # the answer whether it had to be put back.
  was_draft=$(glab mr view "$ref" "${REPO_FLAG[@]}" --output json 2>/dev/null \
    | "$PY" -c 'import json,sys
try:
    print("true" if json.load(sys.stdin).get("draft") else "false", end="")
except Exception:
    print("unknown", end="")')
  out=$(glab mr update "$ref" "${REPO_FLAG[@]}" --description "$body" 2>&1) || {
    printf '{"error":true,"verb":"change-update-body","reason":%s}\n' \
      "$("$PY" -c 'import json,sys;print(json.dumps(sys.stdin.read()[:2000]))' <<<"$out")"
    exit 0
  }
  restored=false
  if [ "$was_draft" = true ]; then
    now=$(glab mr view "$ref" "${REPO_FLAG[@]}" --output json 2>/dev/null \
      | "$PY" -c 'import json,sys
try:
    print("true" if json.load(sys.stdin).get("draft") else "false", end="")
except Exception:
    print("unknown", end="")')
    if [ "$now" != true ]; then
      glab mr update "$ref" "${REPO_FLAG[@]}" --draft >/dev/null 2>&1 && restored=true
    fi
  fi
  printf '{"ok":true,"id":"%s","was_draft":"%s","draft_restored":%s}\n' \
    "$ref" "$was_draft" "$restored"
  ;;

change-comment)
  # A plain note, or an INLINE note when `file` and `line` are given. An inline
  # note is a DiffNote and needs the change's four diff refs: `glab mr note` has
  # no flag for that, and passing -f position[...] posts a plain note instead —
  # silently, which is why this builds the JSON body and posts it through the API.
  ref=$(arg id); text=$(arg text); file=$(arg file); line=$(arg line)
  if [ -z "$file" ]; then
    out=$(glab mr note "$ref" "${REPO_FLAG[@]}" --message "$text" 2>&1) || {
      printf '{"error":true,"verb":"change-comment","reason":%s}\n' \
        "$("$PY" -c 'import json,sys;print(json.dumps(sys.stdin.read()[:2000]))' <<<"$out")"
      exit 0
    }
    printf '{"ok":true,"id":"%s","inline":false}\n' "$ref"
    exit 0
  fi
  meta=$(view_json "$ref")
  body_file=$(mktemp -t afk-forge-note.XXXXXX.json)
  printf '%s' "$meta" | "$PY" -c '
import json, sys
d = json.load(sys.stdin)
refs = d.get("diff_refs") or {}
text, path, line = sys.argv[1], sys.argv[2], sys.argv[3]
print(json.dumps({
    "body": text,
    "position": {
        "position_type": "text",
        "new_path": path, "old_path": path,
        "new_line": int(line),
        "base_sha": refs.get("base_sha"),
        "start_sha": refs.get("start_sha"),
        "head_sha": refs.get("head_sha"),
    },
}))
' "$text" "$file" "$line" > "$body_file"
  iid=$(printf '%s' "$meta" | "$PY" -c 'import json,sys;print(json.load(sys.stdin).get("iid",""))')
  out=$(glab api -X POST -H "Content-Type: application/json" \
        "projects/:id/merge_requests/$iid/discussions" --input "$body_file" 2>&1) || {
    printf '{"error":true,"verb":"change-comment","reason":%s}\n' \
      "$("$PY" -c 'import json,sys;print(json.dumps(sys.stdin.read()[:2000]))' <<<"$out")"
    rm -f "$body_file"; exit 0
  }
  rm -f "$body_file"
  # Verify the note actually landed as a DiffNote: a rejected position degrades
  # to a plain note, and a review that believes it commented on a line did not.
  printf '%s' "$out" | "$PY" -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    print(json.dumps({"ok": False, "reason": "no readable response"}))
    raise SystemExit(0)
notes = d.get("notes") or []
kind = notes[0].get("type") if notes else None
print(json.dumps({"ok": kind == "DiffNote", "inline": True, "type": kind,
                  "discussion": d.get("id"),
                  **({} if kind == "DiffNote" else
                     {"reason": "the position was rejected; this landed as a plain note"})}))
'
  ;;

thread-list)
  # Every discussion on the change, flattened to the shape a review referee
  # needs: id, resolved, and each note's author, body and type. Paginated to the
  # end — a round that read only the first page would re-open findings it had
  # already settled.
  iid=$(view_json "$(arg id)" | "$PY" -c 'import json,sys;print(json.load(sys.stdin).get("iid",""))')
  glab api --paginate "projects/:id/merge_requests/$iid/discussions?per_page=100" 2>/dev/null   | "$PY" -c "$PAGES"'
import json, sys
try:
    data = pages(sys.stdin.read())
except Exception:
    print(json.dumps({"error": True, "reason": "glab returned no readable JSON"}))
    raise SystemExit(0)
threads = []
for d in data if isinstance(data, list) else []:
    notes = d.get("notes") or []
    threads.append({
        "id": d.get("id"),
        "resolved": any(n.get("resolved") for n in notes),
        "file": ((notes[0].get("position") or {}).get("new_path") if notes else None),
        "notes": [{"id": n.get("id"),
                   "author": (n.get("author") or {}).get("username"),
                   "type": n.get("type"),
                   "body": n.get("body") or ""} for n in notes],
    })
print(json.dumps({"threads": threads, "count": len(threads)}))
'
  ;;

thread-reply)
  iid=$(view_json "$(arg id)" | "$PY" -c 'import json,sys;print(json.load(sys.stdin).get("iid",""))')
  thread=$(arg thread); text=$(arg text)
  out=$(glab api -X POST "projects/:id/merge_requests/$iid/discussions/$thread/notes"         -f body="$text" 2>&1) || {
    printf '{"error":true,"verb":"thread-reply","reason":%s}
'       "$("$PY" -c 'import json,sys;print(json.dumps(sys.stdin.read()[:2000]))' <<<"$out")"
    exit 0
  }
  printf '{"ok":true,"thread":"%s"}
' "$thread"
  ;;

thread-resolve)
  iid=$(view_json "$(arg id)" | "$PY" -c 'import json,sys;print(json.load(sys.stdin).get("iid",""))')
  thread=$(arg thread); state=$(arg resolved true)
  out=$(glab api -X PUT "projects/:id/merge_requests/$iid/discussions/$thread?resolved=$state" 2>&1) || {
    printf '{"error":true,"verb":"thread-resolve","reason":%s}
'       "$("$PY" -c 'import json,sys;print(json.dumps(sys.stdin.read()[:2000]))' <<<"$out")"
    exit 0
  }
  printf '{"ok":true,"thread":"%s","resolved":%s}
' "$thread" "$state"
  ;;

change-close)
  # `glab mr close` refuses on a project that requires a passing pipeline before
  # merging: it reports the MERGE precondition even though closing is not
  # merging. Close through the API, which has no such precondition.
  iid=$(arg id)
  out=$(glab api -X PUT "projects/:id/merge_requests/$iid?state_event=close" 2>&1) || {
    printf '{"error":true,"verb":"change-close","reason":%s}\n' \
      "$("$PY" -c 'import json,sys;print(json.dumps(sys.stdin.read()[:2000]))' <<<"$out")"
    exit 0
  }
  printf '{"ok":true,"id":"%s","state":"closed"}\n' "$(arg id)"
  ;;

# ---------------------------------------------------------------------------
# ci-wait — the one verb with an exit-code contract
# ---------------------------------------------------------------------------
ci-wait)
  # Poll until the pipeline reaches a terminal state or the budget runs out.
  #   0 success   1 failed/canceled   2 budget exhausted (still running)
  #   3 unreadable — 3 consecutive read errors (auth/network fault, never a
  #     verdict on the change)
  # Parking is not cancelling: the pipeline keeps running, and a resume re-reads
  # the live status first.
  ref=$(arg id)
  budget=$(arg budget 5400)
  interval=$(arg interval 180)
  # A poll that never advances the clock never ends: an interval of 0
  # would spin against the forge until the caller is killed.
  [ "$interval" -gt 0 ] 2>/dev/null || interval=1
  errors=0
  elapsed=0
  while [ "$elapsed" -lt "$budget" ]; do
    status=$(view_json "$ref" | "$PY" -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    print("")
    raise SystemExit(0)
print(((d.get("head_pipeline") or d.get("pipeline") or {}).get("status")) or "")
')
    if [ -z "$status" ]; then
      errors=$((errors + 1))
      if [ "$errors" -ge 3 ]; then
        printf 'forge: %s could not be read 3 times running — auth or network, not a pipeline verdict\n' "$ref" >&2
        printf '{"status":"unreadable","elapsed":%s,"reason":"3 consecutive read errors on %s — auth or network, not a pipeline verdict"}\n' "$elapsed" "$ref"
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
  printf 'forge: budget of %ss is spent on %s; the pipeline keeps running\n' "$elapsed" "$ref" >&2
  printf '{"status":"running","elapsed":%s,"id":"%s","reason":"budget exhausted; the pipeline keeps running"}\n' "$elapsed" "$ref"
  exit 2
  ;;

*)
  unsupported
  ;;
esac
