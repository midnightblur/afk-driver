#!/usr/bin/env bash
# gc-check.sh — mechanical guard battery for /afk-toolkit:gc, bundled with the skill.
# Encodes SKILL.md's refusal guards and worktree verify-safe checks; the skill
# routes on this script's exit code (see SKILL.md "Guards & verify-safe" — a
# lockstep pair, keep both in sync). Judgment (propose → approve → retire →
# delete) stays with the skill; this script only checks and reports.
#
# Usage (from the MAIN checkout root, the integration base freshly fetched):
#   bash skills/afk/gc/scripts/gc-check.sh <spec-folder> [feature-branch]
#
#   <spec-folder>     the ticket's spec directory (holds plan/PLAN.md) — never guessed
#   [feature-branch]  the feature's local branch; omitted → inferred as the one
#                     local branch whose name contains the spec folder's
#                     basename, lowercased (exactly one match required)
#
# The integration base is `git.base-branch` from .afk/config.yaml, and the
# merged-state read goes through the configured forge adapter — this script
# names neither a branch nor a forge CLI.
#
# Guards, in SKILL.md order (first failure wins, nothing later runs):
#   1. shipped only  — plan/PLAN.md `Feature:` header reads `complete (…)` AND the
#                      feature branch is proven merged: its tip is an ancestor of
#                      the integration base, or the forge reports its change merged
#   2. clean tree    — no uncommitted changes under <spec-folder>
#   3. interactive   — env AFK_DRIVEN unset/empty; a driven/autopilot invoker exports
#                      AFK_DRIVEN=1, so a hands-off run can never pass this guard
#   4. not inside    — the cwd checkout's branch is not the feature branch (a worktree
#                      can't remove itself)
#
# Exit codes (`EXIT_BRANCH_UNRESOLVED` is this script's `## Produces` anchor):
#   EXIT_OK=0                 all guards pass; stdout carries the worktree verdict
#   EXIT_NOT_SHIPPED=1        guard 1 failed -> refused(not_shipped)
#   EXIT_DIRTY_TREE=2         guard 2 failed -> refused(dirty_tree)
#   EXIT_HANDS_OFF=3          guard 3 failed -> refused(hands_off)
#   EXIT_INSIDE_TARGET=4      guard 4 failed -> refused(inside_target_worktree)
#   EXIT_USAGE=5              bad invocation / not a git checkout / no integration base
#   EXIT_BRANCH_UNRESOLVED=6  feature branch neither given nor inferable (zero or
#                             several matches) — pass it explicitly and re-run
#
# Stdout on exit 0 (structured, one KEY=value per line):
#   GC_CHECK=pass
#   SPEC_FOLDER=<path>            FEATURE_HEADER=<the Feature: line>
#   FEATURE_BRANCH=<branch>       MERGED_VIA=ancestor|forge
#   ARCHIVE_REF=<HEAD short hash — the ref INDEX.md records>
#   WORKTREE=<path>|absent        WORKTREE_SIZE=<du -sh>|-
#   WORKTREE_VERDICT=safe|absent|dirty|unmerged(<n>)
# Verify-safe misses (dirty / unmerged) are a VERDICT, not an exit code — per
# SKILL.md they skip the retirement item, never block the spec compaction.
# On refusal: GC_CHECK=refused(<reason>) + REASON=<detail>, matching exit code.
set -u

EXIT_OK=0
EXIT_NOT_SHIPPED=1
EXIT_DIRTY_TREE=2
EXIT_HANDS_OFF=3
EXIT_INSIDE_TARGET=4
EXIT_USAGE=5
EXIT_BRANCH_UNRESOLVED=6

refuse() { # <tag> <detail> <exit-code>
  echo "GC_CHECK=refused($1)"
  echo "REASON=$2"
  exit "$3"
}

fail() { # <tag> <detail> <exit-code>  — mechanical error, not a SKILL refusal
  echo "GC_CHECK=error($1)"
  echo "REASON=$2"
  exit "$3"
}

if [ "$#" -lt 1 ]; then
  echo "usage: gc-check.sh <spec-folder> [feature-branch]" >&2
  fail usage "spec-folder argument required" "$EXIT_USAGE"
fi

SPEC="${1%/}"
BRANCH="${2:-}"

[ -d "$SPEC" ] || fail usage "spec folder not found: $SPEC" "$EXIT_USAGE"
git rev-parse --is-inside-work-tree >/dev/null 2>&1 \
  || fail usage "cwd is not a git checkout" "$EXIT_USAGE"
# The integration base and the forge both come from the repository's
# configuration; this script sources the same reader every gate uses.
AFK_ROOT=${AFK_PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)}
. "$AFK_ROOT/hooks/lib/config.sh"
. "$AFK_ROOT/hooks/lib/adapter.sh"
afk_config_load
BASE=${AFK_CFG_GIT_BASE_BRANCH:-auto}
if [ "$BASE" = "auto" ] || [ -z "$BASE" ]; then
  for candidate in origin/main origin/master; do
    git rev-parse --verify -q "$candidate" >/dev/null 2>&1 && { BASE=$candidate; break; }
  done
fi
git rev-parse --verify -q "$BASE" >/dev/null 2>&1 \
  || fail usage "no $BASE ref — fetch it first, or set git.base-branch in .afk/config.yaml" "$EXIT_USAGE"

# --- Guard 1: shipped only --------------------------------------------------
PLAN="$SPEC/plan/PLAN.md"
[ -f "$PLAN" ] \
  || refuse not_shipped "no $PLAN — nothing proves the feature shipped" "$EXIT_NOT_SHIPPED"

# The header is a blockquote line in PLAN-TEMPLATE.md (`> Feature: …`); accept the
# bare form too, and strip the marker before matching.
header="$(grep -m1 -E '^> ?Feature:' "$PLAN" || grep -m1 -E '^Feature:' "$PLAN" || true)"
header="${header#> }"
case "$header" in
  "Feature: complete ("*) : ;;
  *) refuse not_shipped "Feature header is '${header:-<missing>}', not 'complete (…)'" "$EXIT_NOT_SHIPPED" ;;
esac

# Resolve the feature branch (arg 2, else infer from the spec-folder basename).
if [ -z "$BRANCH" ]; then
  ticket="$(basename "$SPEC" | tr '[:upper:]' '[:lower:]')"
  # Any local branch whose name carries the ticket; the repository's branch
  # convention is `git.branch-pattern`, not something to hard-code here.
  matches="$(git for-each-ref 'refs/heads' --format='%(refname:short)' \
    | grep -F -- "$ticket" || true)"
  count="$(printf '%s' "$matches" | grep -c . || true)"
  if [ "$count" -ne 1 ]; then
    fail branch_unresolved \
      "expected exactly 1 local branch whose name contains '$ticket', found $count — pass the feature branch explicitly" \
      "$EXIT_BRANCH_UNRESOLVED"
  fi
  BRANCH="$matches"
fi

# Merged proof: branch tip ancestor of the integration base, else the forge
# reports the branch's change merged. `forge: none` answers unsupported, which
# leaves the ancestor test as the only proof — never a false "merged".
tip="$(git rev-parse --verify -q "refs/heads/$BRANCH" \
  || git rev-parse --verify -q "refs/remotes/origin/$BRANCH" || true)"
MERGED_VIA=""
if [ -n "$tip" ] && git merge-base --is-ancestor "$tip" "$BASE" 2>/dev/null; then
  MERGED_VIA=ancestor
elif afk_adapter forge change-state "{\"id\":\"$BRANCH\"}" 2>/dev/null \
     | grep -Eq '"state": ?"merged"'; then
  MERGED_VIA=forge
else
  refuse not_shipped \
    "branch '$BRANCH' is not an ancestor of $BASE and the forge reports no merged change for it" \
    "$EXIT_NOT_SHIPPED"
fi

# --- Guard 2: clean tree under the spec folder ------------------------------
dirty="$(git status --porcelain -- "$SPEC")"
[ -z "$dirty" ] \
  || refuse dirty_tree "uncommitted changes under $SPEC: $(printf '%s' "$dirty" | head -n3 | tr '\n' ';')" "$EXIT_DIRTY_TREE"

# --- Guard 3: interactive only ----------------------------------------------
[ -z "${AFK_DRIVEN:-}" ] \
  || refuse hands_off "AFK_DRIVEN is set — hands-off invocation; deletion always gets a human eye" "$EXIT_HANDS_OFF"

# --- Guard 4: not standing in the target ------------------------------------
current="$(git rev-parse --abbrev-ref HEAD)"
[ "$current" != "$BRANCH" ] \
  || refuse inside_target_worktree "cwd checkout is on '$BRANCH' — re-run from the main checkout" "$EXIT_INSIDE_TARGET"

# --- Worktree verify-safe (verdict, never an exit code) ---------------------
wt=""
cur_wt=""
while IFS= read -r line; do
  case "$line" in
    "worktree "*) cur_wt="${line#worktree }" ;;
    "branch refs/heads/$BRANCH") wt="$cur_wt" ;;
  esac
done <<EOF_WT
$(git worktree list --porcelain)
EOF_WT

if [ -z "$wt" ]; then
  verdict=absent
  size="-"
else
  size="$(du -sh "$wt" 2>/dev/null | cut -f1)"
  size="${size:--}"
  if [ -n "$(git -C "$wt" status --porcelain)" ]; then
    verdict=dirty
  else
    ahead="$(git -C "$wt" rev-list --count "$BASE"..HEAD 2>/dev/null || echo '?')"
    if [ "$ahead" = "0" ]; then
      verdict=safe
    else
      verdict="unmerged($ahead)"
    fi
  fi
fi

echo "GC_CHECK=pass"
echo "SPEC_FOLDER=$SPEC"
echo "FEATURE_HEADER=$header"
echo "FEATURE_BRANCH=$BRANCH"
echo "MERGED_VIA=$MERGED_VIA"
echo "ARCHIVE_REF=$(git rev-parse --short HEAD)"
echo "WORKTREE=${wt:-absent}"
echo "WORKTREE_SIZE=$size"
echo "WORKTREE_VERDICT=$verdict"
exit "$EXIT_OK"
