#!/usr/bin/env bash
# Sourced helper (ships with the afk plugin): the Stop gates' shared change-set
# context — derived ONCE per Stop, consumed by every gate.
#
# Why it exists. Gate latency here is dominated by PROCESS COUNT, not algorithm:
# MSYS fork emulation (Windows git-bash) costs ~0.5-2s per subprocess against
# ~20-40ms for a native Windows spawn, and degrades under load. Each gate used to
# re-derive the same change set and re-hash the same tree — `git status` plus two
# forks per changed file, once per gate — so a 10-file working tree cost ~24
# subprocesses x7 gates before any gate did real work. This derives all of it in
# one place on a fixed, small fork budget (~8 spawns per Stop regardless of tree
# size); every list is parsed with bash string ops, never awk/sed/grep per line.
#
# Variables set (newline-separated lists, no trailing blank line):
#   AFK_CTX_HEAD      HEAD sha ("" in an empty repo)
#   AFK_CTX_BASE      integration base: git.base-branch, else origin/main,
#                     else origin/master, else @{u}, else HEAD
#   AFK_CTX_MERGEBASE merge-base of AFK_CTX_BASE and HEAD (diff base)
#   AFK_CTX_CHANGED   every changed/untracked path (rename -> new path only)
#   AFK_CTX_NEW       added + untracked + rename/copy-target paths
#   AFK_CTX_LIVE      AFK_CTX_CHANGED minus deletions (paths that exist on disk)
#   AFK_CTX_TREE      content digest of HEAD + every working-tree change
#   AFK_CTX_READY     1 once built — re-sourcing/rebuilding is a no-op
#
# Deliberately NOT exported. Every consumer is sourced into the same shell (or a
# subshell, which inherits unexported variables); no exec'd program reads them.
# Exported, the unbounded lists ride the environment of EVERY child — git, mvnw,
# node — and a large change set (generated code, a big merge) can overflow the
# Windows CreateProcess environment block, failing every native spawn the gates
# make, in ways that look nothing like the actual cause.
#
# Per-gate cache keys are "<gate>:$AFK_CTX_TREE" (gate_cache_key, gate-cache.sh):
# a pure string op, so no gate ever pays to derive its own key.
#
# Scope filtering is bash-native and fork-free — see gate_ctx_filter below.
# AFK_GATE_CTX_DISABLE=1 makes gate_ctx_build rebuild on every call (debug only).

# gate_ctx_build — idempotent; assumes cwd = repo root.
gate_ctx_build() {
  [ "${AFK_CTX_READY:-0}" = "1" ] && [ "${AFK_GATE_CTX_DISABLE:-0}" != "1" ] && return 0

  AFK_CTX_HEAD=$(git rev-parse HEAD 2>/dev/null || true)

  # Integration base. The consuming repository names it (`git.base-branch` in
  # .afk/config.yaml); `auto` and an unset value fall back to origin/main, then
  # origin/master, then the branch's own upstream, then HEAD. The named base
  # comes first because merging the base into a feature branch puts the base's
  # commits ahead of that branch's upstream, so basing on @{u} would attribute
  # every file the base added since the divergence to this change.
  AFK_CTX_BASE=""
  if [ -n "${AFK_CFG_GIT_BASE_BRANCH:-}" ] && [ "${AFK_CFG_GIT_BASE_BRANCH}" != "auto" ]; then
    git rev-parse --verify -q "$AFK_CFG_GIT_BASE_BRANCH" >/dev/null 2>&1       && AFK_CTX_BASE=$AFK_CFG_GIT_BASE_BRANCH
  fi
  [ -z "$AFK_CTX_BASE" ] && git rev-parse --verify -q origin/main >/dev/null 2>&1 && AFK_CTX_BASE=origin/main
  [ -z "$AFK_CTX_BASE" ] && git rev-parse --verify -q origin/master >/dev/null 2>&1 && AFK_CTX_BASE=origin/master
  [ -z "$AFK_CTX_BASE" ] && AFK_CTX_BASE=$(git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null || true)
  [ -z "$AFK_CTX_BASE" ] && AFK_CTX_BASE=HEAD
  AFK_CTX_MERGEBASE=""     # lazy — only the diff-based gates need it (see below)

  # -z (NUL-delimited) avoids git's quoting of unusual paths. Bash variables
  # cannot hold NUL, so status goes to a file and is read back with read -d ''.
  # $$-suffixed: two sessions' Stop hooks in one checkout must not truncate each
  # other's scratch mid-read (a torn read = a wrong change set for that Stop).
  local statfile=".claude/hooks/.gate-cache/.status.$$"
  mkdir -p .claude/hooks/.gate-cache 2>/dev/null
  git status --porcelain -z -uall >"$statfile" 2>/dev/null || : >"$statfile"

  AFK_CTX_CHANGED=""; AFK_CTX_NEW=""; AFK_CTX_LIVE=""
  local entry st path _src
  while IFS= read -r -d '' entry; do
    [ -n "$entry" ] || continue
    st=${entry:0:2}
    path=${entry:3}
    # Rename/copy entries are "XY <new>\0<orig>\0" — consume and drop the source.
    case "$st" in
      R*|C*) IFS= read -r -d '' _src || true ;;
    esac
    AFK_CTX_CHANGED+="$path"$'\n'
    # Rename/copy targets count as NEW: the path is new under this name, and the
    # wiring gate must ask whether anything references the NEW name — a rename
    # whose referrers still say the old name is exactly an orphan.
    case "$st" in
      'A '|'AM'|'AD'|'??'|R?|C?) AFK_CTX_NEW+="$path"$'\n' ;;
    esac
    [ -f "$path" ] && AFK_CTX_LIVE+="$path"$'\n'
  done <"$statfile"
  rm -f "$statfile" 2>/dev/null

  # Tree digest: HEAD + (path, content-hash) for every live change + a marker per
  # deletion. --stdin-paths hashes ALL of them in a single call (was one fork per
  # file). Deletions are covered because they appear in CHANGED but not LIVE.
  local hashes digest
  if [ -n "$AFK_CTX_LIVE" ]; then
    hashes=$(printf '%s' "$AFK_CTX_LIVE" | git hash-object --stdin-paths 2>/dev/null || true)
  else
    hashes=""
  fi

  # Zip paths with hashes into "<path>\t<hash>" lines. This is what lets a gate
  # key its pass cache on ITS OWN scope (gate_cache_key with patterns) instead of
  # on the whole tree — otherwise any unrelated edit busts every gate's cache,
  # which is exactly what an interactive session does on every turn.
  AFK_CTX_HASHES=""
  local -a _paths=() _hashes=()
  while IFS= read -r entry; do [ -n "$entry" ] && _paths+=("$entry"); done <<<"$AFK_CTX_LIVE"
  while IFS= read -r entry; do [ -n "$entry" ] && _hashes+=("$entry"); done <<<"$hashes"
  local _i
  for _i in "${!_paths[@]}"; do
    AFK_CTX_HASHES+="${_paths[$_i]}"$'\t'"${_hashes[$_i]:-?}"$'\n'
  done

  # The wiring IOU ledger is gitignored, so `git status` never lists it — yet
  # its content flips wiring verdicts (deleting a waive/IOU line must bust both
  # the Stop stamp and wiring's pass cache). Fold it into the digest directly.
  local ledger_body=""
  [ -f .claude/wiring-ious.md ] && ledger_body=$(<.claude/wiring-ious.md)

  digest=$(printf '%s\n---\n%s\n---\n%s\n---\n%s' \
    "$AFK_CTX_HEAD" "$AFK_CTX_CHANGED" "$AFK_CTX_HASHES" "$ledger_body" \
    | git hash-object --stdin 2>/dev/null || true)
  AFK_CTX_TREE="${digest:-nodigest-$AFK_CTX_HEAD}"

  AFK_CTX_READY=1
  return 0
}

# gate_ctx_mergebase — populate AFK_CTX_MERGEBASE (merge-base of the integration
# base and HEAD) on first use, then reuse. Only the diff-based gates (genericity,
# native-contract) need it, and only after their scope check passes, so a turn that
# touches no prose never spawns it. Sets the variable rather than echoing it:
# a $(...) call would compute it in a subshell and throw the memo away.
gate_ctx_mergebase() {
  [ -n "${AFK_CTX_MERGEBASE:-}" ] && return 0
  AFK_CTX_MERGEBASE=$(git merge-base "$AFK_CTX_BASE" HEAD 2>/dev/null || echo HEAD)
  return 0
}

# gate_ctx_branch — populate AFK_CTX_BRANCH (every path this branch's COMMITS
# changed vs the integration base) on first use, then reuse.
#
# Why a second list. The lists above are derived from `git status`, so they empty
# out the moment work is committed — but a gate that judges a whole change
# (plugin prose stays generic, the generated Codex layer matches its sources, a
# registry matches disk) scopes itself on the branch, not the worktree. Dispatch
# from the worktree alone therefore stops gating a change at exactly the point it
# becomes permanent. Dispatching on CHANGED plus BRANCH keeps the two in step.
#
# One diff, memoized, and only reached on a turn that already busted the Stop
# short-circuit — a talk-only turn never pays it.
gate_ctx_branch() {
  [ "${AFK_CTX_BRANCH_READY:-0}" = "1" ] && return 0
  AFK_CTX_BRANCH=""
  gate_ctx_mergebase
  # Equal shas mean the branch carries no commits of its own -> nothing to add.
  if [ -n "${AFK_CTX_HEAD:-}" ] && [ "$AFK_CTX_MERGEBASE" != "$AFK_CTX_HEAD" ]; then
    AFK_CTX_BRANCH=$(git diff --name-only "$AFK_CTX_MERGEBASE" HEAD 2>/dev/null || true)
    [ -n "$AFK_CTX_BRANCH" ] && AFK_CTX_BRANCH+=$'\n'
  fi
  AFK_CTX_BRANCH_READY=1
  return 0
}

# gate_ctx_build_staged — same exports, scoped to what is STAGED rather than to
# the working tree. Used by precommit-gates.sh: this repo stages explicit paths
# rather than everything, so a commit-time gate must judge the commit's content,
# not whatever else happens to be dirty.
#
# Content is read from the WORKING TREE (the gates shell out to Maven/ESLint,
# which cannot see a staged-only version of a file); the staged list decides
# WHICH files are judged. When a gated file's staged copy differs from its
# worktree copy the verdict would be about bytes the commit does not contain —
# precommit-gates.sh refuses that commit up front rather than judging either.
gate_ctx_build_staged() {
  [ "${AFK_CTX_READY:-0}" = "1" ] && return 0

  AFK_CTX_HEAD=$(git rev-parse HEAD 2>/dev/null || true)
  AFK_CTX_BASE=HEAD
  AFK_CTX_MERGEBASE=HEAD

  AFK_CTX_CHANGED=""; AFK_CTX_NEW=""; AFK_CTX_LIVE=""
  local entry st path
  local statfile=".claude/hooks/.gate-cache/.staged.$$"
  mkdir -p .claude/hooks/.gate-cache 2>/dev/null
  git diff --cached --name-status -z --diff-filter=ACMRT >"$statfile" 2>/dev/null || : >"$statfile"
  while IFS= read -r -d '' st; do
    [ -n "$st" ] || continue
    IFS= read -r -d '' path || break
    case "$st" in
      R*|C*) IFS= read -r -d '' path || break ;;   # rename/copy: second field is the new path
    esac
    AFK_CTX_CHANGED+="$path"$'\n'
    case "${st:0:1}" in A|R|C) AFK_CTX_NEW+="$path"$'\n' ;; esac
    [ -f "$path" ] && AFK_CTX_LIVE+="$path"$'\n'
  done <"$statfile"
  rm -f "$statfile" 2>/dev/null

  # Digest straight from the staged blob shas — no per-file hashing needed.
  AFK_CTX_TREE=$(git diff --cached --raw 2>/dev/null | git hash-object --stdin 2>/dev/null || true)
  AFK_CTX_TREE="staged:${AFK_CTX_TREE:-none}"

  AFK_CTX_READY=1
  return 0
}

# gate_ctx_filter <list-var-name> <pattern> [<pattern>...]
# Echoes the lines of the named context list matching ANY glob pattern (bash
# case globs, e.g. '*.java' '11700-payable/*'). Fork-free — this is what a gate
# uses instead of `git status | grep`.
gate_ctx_filter() {
  local __list=${!1:-} line pat
  shift
  [ -n "$__list" ] || return 0
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    for pat in "$@"; do
      # shellcheck disable=SC2254
      case "$line" in
        $pat) printf '%s\n' "$line"; break ;;
      esac
    done
  done <<<"$__list"
}

# gate_ctx_any <list-var-name> <pattern>... — true if any line matches. Fork-free.
gate_ctx_any() {
  local __list=${!1:-} line pat
  shift
  [ -n "$__list" ] || return 1
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    for pat in "$@"; do
      # shellcheck disable=SC2254
      case "$line" in
        $pat) return 0 ;;
      esac
    done
  done <<<"$__list"
  return 1
}
