#!/bin/bash
#
# gc-check-smoke.sh — seam-test for gc-check.sh (the /afk:gc guard battery).
#
# Runs entirely in a disposable temp git repo — never touches a real checkout,
# branch, worktree, or glab remote (glab is stubbed where a path needs it).
# Asserts, per the exit-code contract in gc-check.sh's header:
#   0 pass          — shipped header + merged branch + clean tree + interactive +
#                     outside the target => GC_CHECK=pass, verdict safe;
#                     branch inference and explicit-branch arg both work
#   verdicts        — dirty worktree => dirty; committed-ahead worktree (glab
#                     stubbed merged) => unmerged(1) via MERGED_VIA=glab;
#                     removed worktree => absent — all still exit 0
#   1 not_shipped   — non-complete Feature header; merged proof failing
#   2 dirty_tree    — uncommitted change under the spec folder
#   3 hands_off     — AFK_DRIVEN set
#   4 inside_target — invoked from the feature worktree itself
#   5 usage         — no argument / nonexistent spec folder
#   6 unresolved    — no local branch matches the spec-folder basename
#
# Self-contained: no network, no npm. Exit 0 = all green.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GC="$SCRIPT_DIR/../gc-check.sh"

PASS=0
FAIL=0
ok()  { echo "  ok   - $1"; PASS=$((PASS + 1)); }
bad() { echo "  FAIL - $1"; FAIL=$((FAIL + 1)); }

if [[ ! -f "$GC" ]]; then
  echo "FAIL: gc-check.sh not found at $GC" >&2
  exit 1
fi

# --- disposable sandbox -----------------------------------------------------
TMP_ROOT="$(mktemp -d 2>/dev/null || mktemp -d -t gcchk)"
REPO="$TMP_ROOT/main"
WT="$TMP_ROOT/wt-tick-demo"
FBRANCH="kapteyn/development/tester/tick-demo"

cleanup() {
  git -C "$REPO" worktree prune >/dev/null 2>&1 || true
  rm -rf "$TMP_ROOT" 2>/dev/null || true
}
trap cleanup EXIT

mkdir -p "$REPO"
git -C "$REPO" init -q -b master
git -C "$REPO" config user.email smoke@test.local
git -C "$REPO" config user.name  smoke-tester
git -C "$REPO" config commit.gpgsign false

mk_spec() { # <name> <header-body>  — written in PLAN-TEMPLATE.md's blockquote form
  mkdir -p "$REPO/specs/$1/plan"
  printf '> %s   <!-- stamped by the smoke gate -->\n\n## Progress tracker\n' "$2" \
    > "$REPO/specs/$1/plan/PLAN.md"
}
mk_spec tick-demo   'Feature: complete (smoke green 2026-07-01, target=local)'
mk_spec tick-ahead  'Feature: complete (smoke green 2026-07-01, target=local)'
mk_spec tick-orphan 'Feature: complete (smoke green 2026-07-01, target=local)'
mk_spec tick-nope   'Feature: smoke-failing'
git -C "$REPO" add -A
git -C "$REPO" commit -qm seed

# fake origin/master at the seed commit (no real remote; gc-check reads the ref)
git -C "$REPO" update-ref refs/remotes/origin/master refs/heads/master

# merged feature branch (tip == master tip => ancestor proof holds) + its worktree
git -C "$REPO" branch "$FBRANCH" master
git -C "$REPO" worktree add -q "$WT" "$FBRANCH"

# branch ahead of origin/master (ancestor proof must fail)
ahead_commit="$(git -C "$REPO" commit-tree 'HEAD^{tree}' -p HEAD -m ahead)"
git -C "$REPO" branch kapteyn/development/tester/tick-ahead "$ahead_commit"

# glab stubs
STUB_MERGED="$TMP_ROOT/stub-merged"; mkdir -p "$STUB_MERGED"
printf '#!/bin/sh\necho "{\\"state\\": \\"merged\\"}"\n' > "$STUB_MERGED/glab"
STUB_FAIL="$TMP_ROOT/stub-fail"; mkdir -p "$STUB_FAIL"
printf '#!/bin/sh\nexit 1\n' > "$STUB_FAIL/glab"
chmod +x "$STUB_MERGED/glab" "$STUB_FAIL/glab"

run_gc() { (cd "$REPO" && bash "$GC" "$@"); }

# --- T1: pass, branch inferred from spec-folder basename ---------------------
OUT="$(run_gc specs/tick-demo)"; RC=$?
if [[ $RC -eq 0 ]]; then ok "pass path exits 0"; else bad "pass path exited $RC ($OUT)"; fi
if grep -q '^GC_CHECK=pass$' <<<"$OUT"; then ok "GC_CHECK=pass"; else bad "no GC_CHECK=pass ($OUT)"; fi
if grep -q "^FEATURE_BRANCH=$FBRANCH$" <<<"$OUT"; then ok "branch inferred"; else bad "branch not inferred ($OUT)"; fi
if grep -q '^MERGED_VIA=ancestor$' <<<"$OUT"; then ok "merged via ancestor"; else bad "MERGED_VIA wrong ($OUT)"; fi
if grep -q '^WORKTREE_VERDICT=safe$' <<<"$OUT"; then ok "worktree verdict safe"; else bad "verdict not safe ($OUT)"; fi
if grep -Eq '^ARCHIVE_REF=[0-9a-f]+' <<<"$OUT"; then ok "archive ref present"; else bad "no ARCHIVE_REF ($OUT)"; fi

# --- T2: pass with explicit branch arg ---------------------------------------
run_gc specs/tick-demo "$FBRANCH" >/dev/null; RC=$?
if [[ $RC -eq 0 ]]; then ok "explicit branch arg exits 0"; else bad "explicit branch arg exited $RC"; fi

# --- T3: hands_off (AFK_DRIVEN set) -----------------------------------------
OUT="$( (cd "$REPO" && AFK_DRIVEN=1 bash "$GC" specs/tick-demo) )"; RC=$?
if [[ $RC -eq 3 ]]; then ok "AFK_DRIVEN exits 3"; else bad "AFK_DRIVEN exited $RC"; fi
if grep -q '^GC_CHECK=refused(hands_off)$' <<<"$OUT"; then ok "refused(hands_off)"; else bad "wrong refusal ($OUT)"; fi

# --- T4: inside the target worktree ------------------------------------------
OUT="$( (cd "$WT" && bash "$GC" specs/tick-demo) )"; RC=$?
if [[ $RC -eq 4 ]]; then ok "inside worktree exits 4"; else bad "inside worktree exited $RC ($OUT)"; fi
if grep -q '^GC_CHECK=refused(inside_target_worktree)$' <<<"$OUT"; then ok "refused(inside_target_worktree)"; else bad "wrong refusal ($OUT)"; fi

# --- T5: dirty worktree => verdict dirty, still exit 0 -----------------------
touch "$WT/untracked.txt"
OUT="$(run_gc specs/tick-demo)"; RC=$?
if [[ $RC -eq 0 && "$(grep '^WORKTREE_VERDICT=' <<<"$OUT")" == "WORKTREE_VERDICT=dirty" ]]; then
  ok "dirty worktree => verdict dirty, exit 0"
else
  bad "dirty worktree wrong (rc=$RC, $OUT)"
fi

# --- T6: committed-ahead worktree => unmerged(1), merged proof via glab stub --
git -C "$WT" add -A
git -C "$WT" commit -qm stray
OUT="$( (cd "$REPO" && PATH="$STUB_MERGED:$PATH" bash "$GC" specs/tick-demo) )"; RC=$?
if [[ $RC -eq 0 ]]; then ok "ahead worktree still exits 0"; else bad "ahead worktree exited $RC ($OUT)"; fi
if grep -q '^MERGED_VIA=glab$' <<<"$OUT"; then ok "merged proof fell back to glab"; else bad "MERGED_VIA wrong ($OUT)"; fi
if grep -q '^WORKTREE_VERDICT=unmerged(1)$' <<<"$OUT"; then ok "verdict unmerged(1)"; else bad "verdict wrong ($OUT)"; fi
git -C "$WT" reset -q --hard origin/master   # branch back to merged state

# --- T7: dirty spec folder in the main tree => exit 2 ------------------------
echo drift >> "$REPO/specs/tick-demo/plan/PLAN.md"
OUT="$(run_gc specs/tick-demo)"; RC=$?
if [[ $RC -eq 2 ]]; then ok "dirty spec tree exits 2"; else bad "dirty spec tree exited $RC"; fi
if grep -q '^GC_CHECK=refused(dirty_tree)$' <<<"$OUT"; then ok "refused(dirty_tree)"; else bad "wrong refusal ($OUT)"; fi
git -C "$REPO" checkout -q -- specs

# --- T8: non-complete Feature header => exit 1 -------------------------------
OUT="$(run_gc specs/tick-nope)"; RC=$?
if [[ $RC -eq 1 ]]; then ok "smoke-failing header exits 1"; else bad "header refuse exited $RC"; fi
if grep -q '^GC_CHECK=refused(not_shipped)$' <<<"$OUT"; then ok "refused(not_shipped) on header"; else bad "wrong refusal ($OUT)"; fi

# --- T9: unmerged branch, no merged MR => exit 1 -----------------------------
OUT="$( (cd "$REPO" && PATH="$STUB_FAIL:$PATH" bash "$GC" specs/tick-ahead) )"; RC=$?
if [[ $RC -eq 1 ]]; then ok "unmerged branch exits 1"; else bad "unmerged branch exited $RC ($OUT)"; fi
if grep -q 'not an ancestor' <<<"$OUT"; then ok "reason names the failed merge proof"; else bad "reason wrong ($OUT)"; fi

# --- T10: no matching local branch => exit 6 ---------------------------------
OUT="$(run_gc specs/tick-orphan)"; RC=$?
if [[ $RC -eq 6 ]]; then ok "unresolvable branch exits 6"; else bad "unresolvable branch exited $RC ($OUT)"; fi
if grep -q '^GC_CHECK=error(branch_unresolved)$' <<<"$OUT"; then ok "error(branch_unresolved)"; else bad "wrong error ($OUT)"; fi

# --- T11: worktree removed => verdict absent, exit 0 -------------------------
git -C "$REPO" worktree remove "$WT" >/dev/null 2>&1 || git -C "$REPO" worktree remove --force "$WT" >/dev/null 2>&1
OUT="$(run_gc specs/tick-demo)"; RC=$?
if [[ $RC -eq 0 && "$(grep '^WORKTREE_VERDICT=' <<<"$OUT")" == "WORKTREE_VERDICT=absent" ]]; then
  ok "removed worktree => verdict absent, exit 0"
else
  bad "absent worktree wrong (rc=$RC, $OUT)"
fi

# --- T12: usage errors => exit 5 ---------------------------------------------
(cd "$REPO" && bash "$GC" >/dev/null 2>&1); RC=$?
if [[ $RC -eq 5 ]]; then ok "no args exits 5"; else bad "no args exited $RC"; fi
(cd "$REPO" && bash "$GC" specs/no-such-folder >/dev/null 2>&1); RC=$?
if [[ $RC -eq 5 ]]; then ok "missing spec folder exits 5"; else bad "missing folder exited $RC"; fi

# --- summary -----------------------------------------------------------------
echo ""
echo "gc-check smoke: $PASS passed, $FAIL failed"
[[ $FAIL -eq 0 ]] || exit 1
echo "SMOKE_OK"
