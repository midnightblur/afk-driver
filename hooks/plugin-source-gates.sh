#!/usr/bin/env bash
# Plugin-source gates: this runner's own gates judge one candidate tree, the index (--staged) or a head (--range).
# Usage, trust rule, parity contract and exit codes: hooks/README.md "Plugin-source gates".

set -u

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
JUDGE=$(cd "$SCRIPT_DIR/.." && pwd)
GATES="skill-registry native-contract genericity behavior-registry"

mode="" base_ref="" head_ref=HEAD report=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --staged) mode=staged; shift ;;
    --range)
      mode=range; base_ref=${2:-}; shift 2 || shift
      case "${1:-}" in ''|--*) ;; *) head_ref=$1; shift ;; esac ;;
    --report)
      report=${2:-}; shift 2 || shift
      case "$report" in ''|/*|[A-Za-z]:/*) ;; *) report="$PWD/$report" ;; esac ;;
    *) printf '[afk] plugin-source-gates.sh: unknown argument %s\n' "$1" >&2; exit 2 ;;
  esac
done
if [ -z "$mode" ] || { [ "$mode" = range ] && [ -z "$base_ref" ]; }; then
  echo "usage: plugin-source-gates.sh --staged | --range <base-ref> [<head-ref>] [--report <file>]" >&2
  exit 2
fi

incomplete() {
  printf '[afk] plugin-source gates: %s — the plugin source is NOT verified.\n' "$1" >&2
  exit 2
}

repo_root=$(git rev-parse --show-toplevel 2>/dev/null) || incomplete "not inside a git repository"
cd "$repo_root" || incomplete "cannot enter $repo_root"
[ -f .claude/hooks/.gate-disabled ] && exit 0

empty_tree=$(git hash-object -t tree /dev/null 2>/dev/null) || incomplete "git cannot hash the empty tree"
if [ "$mode" = staged ]; then
  head=$(git rev-parse -q --verify HEAD 2>/dev/null) || head=""
  base=${head:-$empty_tree}
else
  head=$(git rev-parse -q --verify "$head_ref^{commit}" 2>/dev/null) || incomplete "no commit $head_ref"
  base=$(git merge-base "$base_ref" "$head" 2>/dev/null) || incomplete "no merge base of $base_ref and $head_ref"
fi

# The repository is the plugin when its manifest names afk at the base revision or in the candidate.
is_plugin() { git cat-file blob "$1:.claude-plugin/plugin.json" 2>/dev/null | grep -qE '"name": *"afk"'; }
if [ "$mode" = staged ]; then candidate=""; else candidate=$head; fi
is_plugin "$base" || is_plugin "$candidate" || exit 0

tmp=$(mktemp -d "${TMPDIR:-/tmp}/afk-psg.XXXXXX") || incomplete "no temporary folder"
trap 'rm -rf "$tmp"' EXIT
trap 'rm -rf "$tmp"; exit 143' TERM INT HUP

# ---- the path set: every added, changed, deleted or renamed path (both names).
if [ "$mode" = staged ]; then
  git diff --cached --name-status -z -M "$base" >"$tmp/status" 2>/dev/null \
    || incomplete "git cannot list the staged paths"
else
  git diff --name-status -z -M "$base" "$head" >"$tmp/status" 2>/dev/null \
    || incomplete "git cannot list the paths of $base_ref...$head_ref"
fi
changed="" new=""
while IFS= read -r -d '' st; do
  [ -n "$st" ] || continue
  IFS= read -r -d '' path || break
  case "$st" in
    R*|C*) changed+="$path"$'\n'; IFS= read -r -d '' path || break ;;
  esac
  changed+="$path"$'\n'
  case "${st:0:1}" in A|R|C) new+="$path"$'\n' ;; esac
done <"$tmp/status"

[ -n "$changed" ] || exit 0

# ---- the candidate tree, from a private index.
git_dir=$(git rev-parse --absolute-git-dir 2>/dev/null) || incomplete "no git directory"
if [ "$mode" = staged ]; then
  source_index=${GIT_INDEX_FILE:-$(git rev-parse --git-path index)}
  case "$source_index" in /*|[A-Za-z]:/*|[A-Za-z]:\\*) ;; *) source_index="$repo_root/$source_index" ;; esac
  if [ -f "$source_index" ]; then
    cp "$source_index" "$tmp/index" || incomplete "cannot copy the index"
  else
    GIT_INDEX_FILE="$tmp/index" git read-tree --empty || incomplete "cannot build an empty index"
  fi
else
  GIT_INDEX_FILE="$tmp/index" git read-tree "$head" || incomplete "cannot read $head_ref into an index"
fi
mkdir -p "$tmp/tree"
GIT_INDEX_FILE="$tmp/index" git checkout-index -a -f -u --prefix="$tmp/tree/" \
  || incomplete "cannot check the candidate tree out"

export GIT_DIR="$git_dir" GIT_WORK_TREE="$tmp/tree" GIT_INDEX_FILE="$tmp/index"
unset GIT_PREFIX
cd "$tmp/tree" || incomplete "cannot enter the candidate tree"
for control in .claude-plugin/plugin.json hooks/plugin-source-gates.sh BEHAVIORS.md skills \
  $(printf 'hooks/%s-gate.sh ' $GATES); do
  [ -e "$control" ] || incomplete "the candidate deletes $control"
done
hooks="$JUDGE/hooks"
for lib in lib/provider.sh lib/adapter.sh gate-context.sh gate-cache.sh gate-metrics.sh; do
  . "$hooks/$lib" || incomplete "the judging plugin cannot load hooks/$lib"
done

# The candidate tree is the data every gate reads; this runner's tree is the code and rules that judge it.
afk_plugin_dir() { printf '.\n'; }
afk_plugin_scope() { printf '\n'; }
afk_judge_dir() { printf '%s\n' "$JUDGE"; }

export GATE_CACHE_DISABLE=1
AFK_CTX_HEAD=$head AFK_CTX_BASE=$base AFK_CTX_MERGEBASE=$base
AFK_CTX_CHANGED=$changed AFK_CTX_NEW=$new AFK_CTX_LIVE="" AFK_CTX_HASHES=""
AFK_CTX_BRANCH="" AFK_CTX_BRANCH_READY=1 AFK_CTX_TREE="candidate:$mode:$head"
while IFS= read -r path; do
  [ -n "$path" ] && [ -f "$path" ] && AFK_CTX_LIVE+="$path"$'\n'
done <<<"$changed"
AFK_CTX_READY=1
gate_ctx_gitdirs
gate_metrics_begin

# Findings name the temporary folder in both spellings a Windows process can print.
tree_win=$(pwd -W 2>/dev/null) || tree_win=$tmp/tree
unplace() { sed -e "s#$tmp/tree#<tree>#g" -e "s#$tree_win#<tree>#g" "$@"; }

failed=""
[ -n "$report" ] && : >"$report"
for gate in $GATES; do
  # A subshell per gate: an unbound variable or an `exit` in one gate cannot end the runner.
  ( . "$hooks/$gate-gate.sh" >&2 && "gate_${gate//-/_}" >&2 ) 2>"$tmp/$gate.err"
  rc=$?
  case "$rc" in
    0) verdict=pass ;;
    2) verdict=blocked ;;
    *) verdict=crashed
       printf '[afk] %s gate gave no verdict (rc %s).\n' "$gate" "$rc" >>"$tmp/$gate.err" ;;
  esac
  unplace "$tmp/$gate.err" >&2
  [ "$verdict" = pass ] || failed="${failed:+$failed, }$gate"
  if [ -n "$report" ]; then
    printf '%s\t%s\t\n' "$gate" "$verdict" >>"$report"
    [ "$verdict" = pass ] || unplace -e '/^[[:space:]]*$/d' -e "s#^#$gate\t$verdict\t#" \
      "$tmp/$gate.err" >>"$report"
  fi
done

if [ -n "$failed" ]; then
  gate_metrics_emit plugin-source-gates blocked "\"mode\":\"$mode\",\"detail\":\"$failed\""
  printf '[afk] plugin-source gates blocked: %s.\n' "$failed" >&2
  exit 2
fi
gate_metrics_emit plugin-source-gates pass "\"mode\":\"$mode\""
exit 0
