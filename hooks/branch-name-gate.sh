#!/usr/bin/env bash
# Branch-name gate (ships with the afk plugin) — a GIT `reference-transaction`
# hook, NOT a Claude Code Stop hook (those live in hooks.json). Opt-in per clone:
#   bash tools/payable/ai-agents/plugins/workflow/hooks/install-git-hooks.sh
# (or `/afk:setup`, register entry H5). Uninstall by removing the installed hook.
#
# Blocks creating a NEW local branch whose name doesn't match the AFK convention:
#   kapteyn/development/<username>/<slug>
# which is the pattern `/afk:execute`'s push depends on (workflow/CLAUDE.md).
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

# AGENT-ONLY. This gate keeps *agent*-created branches on-convention; it must
# never get in a human's way. Claude sets CLAUDECODE in the environment of every
# process it spawns, so an agent's `git checkout -b` / `git worktree add` /
# create-worktree run carries it (and so does the reference-transaction hook git
# invokes). Branch creation from your own terminal or IDE has no such marker —
# not gated; name branches however you like.
[ -n "${CLAUDECODE:-}" ] || exit 0

# Only the "prepared" phase of a ref transaction can veto it; "committed" and
# "aborted" are informational (a non-zero exit there does nothing useful).
[ "${1:-}" = "prepared" ] || exit 0

# Escape hatches.
[ "${AFK_SKIP_BRANCH_CHECK:-}" = "1" ] && exit 0
[ "$(git config --bool afk.branchNameGate 2>/dev/null)" = "false" ] && exit 0

# Required shape: kapteyn/development/<username>/<slug> (slug may contain slashes).
pattern='^kapteyn/development/[a-z0-9][a-z0-9._-]*/.+$'

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

  # A genuinely new branch: enforce the convention.
  printf '%s\n' "$branch" | grep -Eq "$pattern" && continue
  block="$branch"
done

[ -z "$block" ] && exit 0

# Suggest a conforming name using the configured git user (best-effort).
user=$(git config user.name 2>/dev/null | tr '[:upper:] ' '[:lower:]--' | tr -cd 'a-z0-9-')
{
  echo "afk: refusing to CREATE branch '$block' — name breaks the AFK convention."
  echo "afk:   required:  kapteyn/development/<username>/<slug>"
  echo "afk:   example:   kapteyn/development/${user:-<username>}/p2p-1234-short-slug"
  echo "afk:"
  echo "afk: only NEW-branch creation is blocked; checking out existing or remote"
  echo "afk: branches is unaffected. Bypass once: AFK_SKIP_BRANCH_CHECK=1 <git cmd>."
} >&2
exit 1
