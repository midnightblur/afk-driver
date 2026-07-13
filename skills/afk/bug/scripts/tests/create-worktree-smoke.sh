#!/bin/bash
#
# create-worktree-smoke.sh — end-to-end seam-test for the ported create-worktree script.
#
# Runs entirely in a disposable temp git repo — never touches a real checkout, a real
# branch, or the dev's configured worktree base dir. Asserts:
#   1. success  — a conforming branch prints WORKTREE_PATH=<path> as the last line and the
#                 worktree really exists on disk
#   2. config   — .claude/.mcp.json path references are cloned into the worktree and the
#                 main-repo path is rewritten to the worktree path (AC-005 / PRD AC-009)
#   3. bad name — a non-conforming branch prints ERROR=<reason> incl. the gate pattern,
#                 exits non-zero, and creates NO worktree (SDD §9b)
#   4. teardown — the created worktree is removed cleanly
#
# Self-contained: no network, no npm, no IDE. Exit 0 = all green.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CWT="$SCRIPT_DIR/../create-worktree"

PASS=0
FAIL=0
ok()   { echo "  ok   - $1"; PASS=$((PASS + 1)); }
bad()  { echo "  FAIL - $1"; FAIL=$((FAIL + 1)); }

if [[ ! -f "$CWT" ]]; then
  echo "FAIL: create-worktree script not found at $CWT" >&2
  exit 1
fi

# --- disposable sandbox -----------------------------------------------------
TMP_ROOT="$(mktemp -d 2>/dev/null || mktemp -d -t cwt)"
REPO="$TMP_ROOT/main-repo"
WT_PARENT="$TMP_ROOT/worktrees"

cleanup() {
  # Prune/remove any worktree we created, then nuke the whole sandbox.
  git -C "$REPO" worktree prune >/dev/null 2>&1 || true
  rm -rf "$TMP_ROOT" 2>/dev/null || true
}
trap cleanup EXIT

mkdir -p "$REPO" "$WT_PARENT"
git -C "$REPO" init -q
git -C "$REPO" config user.email smoke@test.local
git -C "$REPO" config user.name  smoke-tester
git -C "$REPO" config commit.gpgsign false
# a config file that references the main-repo path, to prove path rewriting
mkdir -p "$REPO/.claude"
REPO_WIN="$(cygpath -m "$REPO" 2>/dev/null || echo "$REPO")"
printf '{"main":"%s/x"}\n' "$REPO_WIN" > "$REPO/.mcp.json"
echo "seed" > "$REPO/README.md"
git -C "$REPO" add -A
git -C "$REPO" commit -qm "seed"
BASE_BRANCH="$(git -C "$REPO" rev-parse --abbrev-ref HEAD)"

run_cwt() { AFK_SKIP_BRANCH_CHECK=1 bash "$CWT" "$@"; }

# --- Test 1 + 2: success + config rewrite -----------------------------------
GOOD_BRANCH="kapteyn/development/tester/smoke-$$"
OUT1="$(run_cwt --branch "$GOOD_BRANCH" --dir good --base "$BASE_BRANCH" \
        --repo "$REPO" --parent "$WT_PARENT" --no-npm --no-open 2>"$TMP_ROOT/err1.log")"
RC1=$?

LAST_LINE="$(printf '%s\n' "$OUT1" | tail -n1)"
if [[ $RC1 -eq 0 ]]; then ok "success exit 0"; else bad "success exit ($RC1); stderr: $(cat "$TMP_ROOT/err1.log")"; fi
if [[ "$LAST_LINE" == WORKTREE_PATH=* ]]; then ok "last line is WORKTREE_PATH="; else bad "last line not WORKTREE_PATH= (got: $LAST_LINE)"; fi

WT_PATH="${LAST_LINE#WORKTREE_PATH=}"
if [[ -n "$WT_PATH" && -d "$WT_PATH" ]]; then ok "worktree dir exists"; else bad "worktree dir missing ($WT_PATH)"; fi

# config cloned + main-repo path rewritten to worktree path
if [[ -f "$WT_PATH/.mcp.json" ]]; then
  ok ".mcp.json cloned into worktree"
  WT_WIN="$(cygpath -m "$WT_PATH" 2>/dev/null || echo "$WT_PATH")"
  if grep -qF "$WT_WIN/x" "$WT_PATH/.mcp.json"; then ok "main-repo path rewritten to worktree path"; else bad "path not rewritten ($(cat "$WT_PATH/.mcp.json"))"; fi
  if grep -qF "$REPO_WIN/x" "$WT_PATH/.mcp.json"; then bad "stale main-repo path still present"; else ok "no stale main-repo path"; fi
else
  bad ".mcp.json not cloned"
fi

# --- Test 4: teardown removes the worktree cleanly --------------------------
# --force because the worktree carries cloned untracked config files (.mcp.json/.claude/...),
# which plain `git worktree remove` refuses — that cloning is the whole point of the script.
if git -C "$REPO" worktree remove --force "$WT_PATH" >/dev/null 2>&1; then ok "worktree removed cleanly"; else bad "worktree remove failed"; fi
if [[ ! -d "$WT_PATH" ]]; then ok "worktree dir gone after remove"; else bad "worktree dir still present after remove"; fi

# --- Test 3: bad branch name -> ERROR=, non-zero, no worktree ---------------
BAD_BRANCH="not-a-valid-branch"
OUT3="$(run_cwt --branch "$BAD_BRANCH" --dir bad --base "$BASE_BRANCH" \
        --repo "$REPO" --parent "$WT_PARENT" --no-npm --no-open 2>"$TMP_ROOT/err3.log")"
RC3=$?
COMBINED3="$OUT3$(cat "$TMP_ROOT/err3.log")"
if [[ $RC3 -ne 0 ]]; then ok "bad branch exits non-zero"; else bad "bad branch exited 0"; fi
if printf '%s' "$COMBINED3" | grep -q '^ERROR='; then ok "bad branch prints ERROR= line"; else bad "no ERROR= line (got: $COMBINED3)"; fi
if printf '%s' "$COMBINED3" | grep -qF 'kapteyn/development'; then ok "ERROR names the gate pattern"; else bad "ERROR omits the pattern"; fi
if [[ ! -d "$WT_PARENT/bad" ]]; then ok "no worktree created for bad branch"; else bad "worktree created despite bad branch"; fi

# --- summary ----------------------------------------------------------------
echo ""
echo "create-worktree smoke: $PASS passed, $FAIL failed"
[[ $FAIL -eq 0 ]] || exit 1
echo "SMOKE_OK"
