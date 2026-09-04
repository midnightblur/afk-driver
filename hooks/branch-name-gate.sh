#!/usr/bin/env bash
# Branch-name gate (ships with the afk plugin) — a GIT `reference-transaction`
# hook, NOT a Stop hook (those live in hooks.json). Opt-in per clone:
#   bash "$AFK_PLUGIN_ROOT/hooks/install-git-hooks.sh"
# (or `/afk:setup`, register entry H5). Uninstall by removing the installed hook.
#
# Blocks creating a NEW local branch whose name does not match
# `git.branch-pattern` from the repository's `.afk/config.yaml`. The key empty or
# absent turns the gate off — a repository with no branch convention is never
# told it broke one.
#
# Deliberately narrow — ONLY new-branch creation is gated. Everything else is
# left alone, so day-to-day git is never in the way:
#   - checking out / committing on / updating an existing branch  -> not a creation, allowed
#   - `git checkout <name>` that DWIM-tracks a branch already on a remote
#     (e.g. `git checkout master-4`, another team's `orion/development/...`)   -> allowed,
#     regardless of name (the "already exists on a remote" escape below)
#   - tags, stash, notes, remote-tracking refs, HEAD moves, deletions          -> not gated
#
# Bypass a single command:  AFK_SKIP_BRANCH_CHECK=1 git <cmd>
# Disable in this clone:     git config afk.branchNameGate false
# Remove entirely:           rm "$(git rev-parse --git-path hooks)/reference-transaction"

set -u

# AGENT-ONLY. Keep this detection order aligned with hooks/lib/provider.sh.
# This installed git hook cannot source the plugin file.
afk_git_provider=unknown
if [ -n "${AFK_PROVIDER:-}" ]; then
  afk_git_provider=$AFK_PROVIDER
elif [ -n "${PLUGIN_ROOT:-}" ]; then
  afk_git_provider=codex
elif [ -n "${CLAUDE_PLUGIN_ROOT:-}" ] || [ -n "${CLAUDECODE:-}" ]; then
  afk_git_provider=claude
fi
[ "$afk_git_provider" != unknown ] || exit 0

# Only the "prepared" phase of a ref transaction can veto it; "committed" and
# "aborted" are informational (a non-zero exit there does nothing useful).
[ "${1:-}" = "prepared" ] || exit 0

# Escape hatches.
[ "${AFK_SKIP_BRANCH_CHECK:-}" = "1" ] && exit 0
[ "$(git config --bool afk.branchNameGate 2>/dev/null)" = "false" ] && exit 0

# The pattern comes from the repository, and reading it costs a python call, so
# it is read LAZILY: a `git fetch` transaction moving a hundred refs must not pay
# for a configuration read it will never use. Empty pattern = gate off.
pattern=""
pattern_loaded=0
load_pattern() {
  [ "$pattern_loaded" = 1 ] && return 0
  pattern_loaded=1
  local here
  here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
  # shellcheck source=/dev/null
  . "$here/lib/config.sh" 2>/dev/null || return 0
  afk_config_load
  pattern=${AFK_CFG_GIT_BRANCH_PATTERN:-}
}

block=""
# git feeds one "<old-value> <new-value> <ref-name>" line per ref on stdin.
while read -r old new ref; do
  case "$ref" in refs/heads/*) ;; *) continue ;; esac   # branch refs only
  # Creations only: old-value is all-zeros (40 hex for sha1, 64 for sha256).
  # Any non-'0' character means old points at a real commit -> update, not create.
  case "$old" in *[!0]*) continue ;; esac

  branch="${ref#refs/heads/}"

  # Allow checking out a branch that already exists on any remote (DWIM tracking).
  tracked=""
  for r in $(git remote 2>/dev/null); do
    if git show-ref --verify --quiet "refs/remotes/$r/$branch"; then tracked=1; break; fi
  done
  [ -n "$tracked" ] && continue

  # A genuinely new branch: enforce the convention, if the repository has one.
  load_pattern
  [ -z "$pattern" ] && continue
  printf '%s\n' "$branch" | grep -Eq "$pattern" && continue
  block="$branch"
done

[ -z "$block" ] && exit 0

# Suggest a conforming name from the repository's own template (best-effort).
user=$(git config user.name 2>/dev/null | tr '[:upper:] ' '[:lower:]--' | tr -cd 'a-z0-9-')
example=${AFK_CFG_GIT_BRANCH_TEMPLATE:-}
example=${example//\{user\}/${user:-username}}
example=${example//\{ticket_lower\}/ticket-123-short-slug}
example=${example//\{ticket\}/TICKET-123}
{
  echo "afk: refusing to CREATE branch '$block' — the name breaks this repository's convention."
  echo "afk:   required:  git.branch-pattern in .afk/config.yaml"
  echo "afk:              $pattern"
  [ -n "$example" ] && echo "afk:   example:   $example"
  echo "afk:"
  echo "afk: only NEW-branch creation is blocked; checking out existing or remote"
  echo "afk: branches is unaffected. Bypass once: AFK_SKIP_BRANCH_CHECK=1 <git cmd>."
} >&2
exit 1
