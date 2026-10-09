#!/usr/bin/env bash
# Plugin-source gates: this runner's own gates judge one candidate tree, the index (--staged) or a head (--range).
# Usage, trust rule, parity contract and exit codes: hooks/README.md "Plugin-source gates".

set -u

# Builtins only until PATH keeps just absolute, readable folders outside every root git could pick
# (hooks/README.md "Plugin-source gates" names them).
tp_abs() { case "$1" in /*|[A-Za-z]:[/\\]*) return 0 ;; esac; return 1; }
tp_root() {
  local p
  p=$(cd "$1" 2>/dev/null && pwd -P) || { refusal="$2 names no folder"; return 1; }
  roots+=("$p")
  [ "${p##*/}" != .git ] || roots+=("${p%/*}")
}
tp_line() { line=""; IFS= read -r line <"$1" || [ -n "$line" ]; line=${line%$'\r'}; }
# A git directory, or a gitfile naming one, with its commondir and core.worktree.
tp_git_dir() {
  local dir=$1 line common
  if [ -f "$dir" ]; then
    tp_root "${dir%/*}" "$2" || return 1
    tp_line "$dir" && [ "${line#gitdir: }" != "$line" ] || { refusal="$2 is neither a folder nor a gitfile"; return 1; }
    dir=${line#gitdir: }
    tp_abs "$dir" || dir=${1%/*}/$dir
  fi
  tp_root "$dir" "$2" || return 1
  if [ -z "${GIT_COMMON_DIR-}" ] && [ -f "$dir/commondir" ]; then
    tp_line "$dir/commondir" || { refusal="cannot read the commondir of $2"; return 1; }
    common=$line
    tp_abs "$common" || common=$dir/$common
    tp_root "$common" "the commondir of $2" || return 1
  fi
  tp_worktree "$dir/config" "$dir" "$2" && tp_worktree "$dir/config.worktree" "$dir" "$2"
}
# core.worktree from one repository config file, the only source git reads it from.
tp_worktree() {
  local line value section="" status=0
  [ -f "$1" ] || return 0
  shopt -s nocasematch
  while IFS= read -r line || [ -n "$line" ]; do
    line=${line%$'\r'}; line=${line#"${line%%[![:space:]]*}"}
    case "$line" in
      \[core\]*) section=core; case "${line#*]}" in *worktree*) status=1; break ;; esac ;;
      \[*) section=other; case "${line#*]}" in *worktree*) status=1; break ;; esac ;;
      worktree|worktree[[:space:]=]*)
        [ "$section" = core ] || continue
        value=${line#*=}
        [ "$value" != "$line" ] || { status=1; break; }
        value=${value#"${value%%[![:space:]]*}"}; value=${value%"${value##*[![:space:]]}"}
        case "$value" in ''|*[\"\\\;#]*) status=1; break ;; esac
        tp_abs "$value" || value=$2/$value
        tp_root "$value" "core.worktree of $3" || { status=2; break; } ;;
    esac
  done <"$1"
  shopt -u nocasematch
  [ "$status" = 1 ] && refusal="$3 sets core.worktree in a form this runner cannot read"
  [ "$status" = 0 ]
}
trusted_path() {
  local dir phys kept="" fold=false var value root ancestor=""
  local -a dirs roots=()
  case "${OSTYPE:-}" in msys*|cygwin*|win*|darwin*) fold=true ;; esac
  dir=$(pwd -P) || { refusal="cannot read the current folder"; return 1; }
  while [ -n "$dir" ] && [ ! -e "$dir/.git" ]; do dir=${dir%/*}; done
  if [ -n "$dir" ]; then
    ancestor=$dir
    tp_root "$dir" "the enclosing repository" && tp_git_dir "$dir/.git" "$dir/.git" || return 1
  fi
  for var in GIT_WORK_TREE GIT_COMMON_DIR GIT_DIR; do
    value=${!var-}
    [ -n "$value" ] || continue
    tp_abs "$value" || { refusal="$var is relative"; return 1; }
    if [ "$var" = GIT_DIR ]; then tp_git_dir "$value" "$var"; else tp_root "$value" "$var"; fi || return 1
  done
  [ -n "$ancestor" ] || [ -n "${GIT_WORK_TREE-}" ] || { refusal="no repository encloses the current folder"; return 1; }
  IFS=: read -r -a dirs <<<"$PATH"
  "$fold" && shopt -s nocasematch
  for dir in "${dirs[@]}"; do
    case "$dir" in /*) ;; *) continue ;; esac
    [ -r "$dir" ] && phys=$(cd "$dir" 2>/dev/null && pwd -P) || continue
    for root in "${roots[@]}"; do
      case "${phys%/}/" in "${root%/}/"*) continue 2 ;; esac
    done
    kept+="${kept:+:}$dir"
  done
  shopt -u nocasematch
  PATH=$kept
}
refusal=""
trusted_path || { echo "[afk] plugin-source gates: cannot tell which repository git will use ($refusal) — NOT verified." >&2; exit 2; }
# Windows would otherwise search a process's current folder, the candidate, for a bare program name.
export NoDefaultCurrentDirectoryInExePath=1

case "${BASH_SOURCE[0]}" in */*) SCRIPT_DIR=${BASH_SOURCE[0]%/*} ;; *) SCRIPT_DIR=. ;; esac
SCRIPT_DIR=$(cd "$SCRIPT_DIR" && pwd)
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
# The sentinel is candidate data here; the local escape lives in precommit-gates.sh.
export AFK_IGNORE_GATE_SENTINEL=1

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

# Judge Python: an absolute interpreter outside the repository, run with isolated imports.
hooks="$JUDGE/hooks"
. "$hooks/lib/provider.sh" || incomplete "the judging plugin cannot load hooks/lib/provider.sh"
# Physical form: links and junctions resolved, one spelling per Windows mount, no trailing separator.
physical() {
  local p=$1 dir hops=0 target
  while [ -L "$p" ]; do
    hops=$((hops + 1)); [ "$hops" -le 40 ] || return 1
    target=$(readlink "$p") || return 1
    case "$target" in /*) p=$target ;; *) p=${p%/*}/$target ;; esac
  done
  if [ -d "$p" ]; then
    p=$(cd "$p" 2>/dev/null && pwd -P) || return 1
  else
    dir=${p%/*}
    p=$(cd "${dir:-/}" 2>/dev/null && pwd -P)/${p##*/} || return 1
  fi
  p=$(cygpath -m "$p" 2>/dev/null || printf '%s' "$p")
  p=${p//\\//}
  printf '%s\n' "${p%/}"
}
fold=false
PATH=/usr/bin:/bin afk_path_case_fold && fold=true
outside() {
  local p verdict=0
  case "$1" in /*) ;; *) return 1 ;; esac
  p=$(physical "$1") || return 1
  "$fold" && shopt -s nocasematch
  case "$p/" in "$repo_abs/"*|"$tmp_abs/"*) verdict=1 ;; esac
  shopt -u nocasematch
  return "$verdict"
}
repo_abs=$(physical "$repo_root") && tmp_abs=$(physical "$tmp") || incomplete "cannot resolve the repository path"
safe_path=""
IFS=: read -r -a path_dirs <<<"$PATH"
for dir in "${path_dirs[@]}"; do
  outside "$dir" && safe_path+="${safe_path:+:}$dir"
done
judge_py=$(PATH=$safe_path command -v "${AFK_PYTHON:-afk-python}" 2>/dev/null) || judge_py=""
case "$judge_py" in [A-Za-z]:*) judge_py=$(cygpath -u "$judge_py" 2>/dev/null) || judge_py="" ;; esac
outside "$judge_py" || incomplete "no afk-python outside the repository"
mkdir -p "$tmp/bin" && printf '#!/usr/bin/env bash\nexec %q -I "$@"\n' "$judge_py" >"$tmp/bin/afk-python" \
  && chmod +x "$tmp/bin/afk-python" || incomplete "cannot write the judge interpreter"
unset PYTHONPATH PYTHONHOME
export AFK_PYTHON="$tmp/bin/afk-python" PATH="$tmp/bin:$safe_path"
# Judge git: the same containment; Python reads AFK_JUDGE_GIT, shell calls go through git().
AFK_JUDGE_GIT=$(command -v git 2>/dev/null) || AFK_JUDGE_GIT=""
outside "$AFK_JUDGE_GIT" || incomplete "no git outside the repository"
AFK_JUDGE_GIT=$(cygpath -m "$AFK_JUDGE_GIT" 2>/dev/null || printf '%s' "$AFK_JUDGE_GIT")
export AFK_JUDGE_GIT
git() { "$AFK_JUDGE_GIT" "$@"; }
export -f git
for lib in lib/adapter.sh gate-context.sh gate-cache.sh gate-metrics.sh; do
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
