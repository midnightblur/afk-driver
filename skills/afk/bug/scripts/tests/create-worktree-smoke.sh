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
#   2b. m2      — a private per-worktree Maven repo is provisioned: .mvn/maven.config points
#                 at <worktree>/.m2/repository, the seed copies release artifacts but skips
#                 *-SNAPSHOT dirs, maven.config lands in the shared info/exclude; --no-m2
#                 skips all of it
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
# config that references the main-repo path, to prove path rewriting (top-level + a nested
# .claude/ file, so the recursive copy_dir_with_substitution path is exercised too).
mkdir -p "$REPO/.claude/sub"
REPO_WIN="$(cygpath -m "$REPO" 2>/dev/null || echo "$REPO")"
printf '{"main":"%s/x"}\n' "$REPO_WIN" > "$REPO/.mcp.json"
printf 'root=%s/nested\n' "$REPO_WIN" > "$REPO/.claude/sub/settings.local.json"
echo "seed" > "$REPO/README.md"
git -C "$REPO" add -A
git -C "$REPO" commit -qm "seed"
# written AFTER the seed commit: .claude/* is gitignored in the real repo, so TODO.md only
# ever reaches a worktree via the config-clone step — which must skip it (per-worktree state)
echo "- [ ] per-worktree item" > "$REPO/.claude/TODO.md"
BASE_BRANCH="$(git -C "$REPO" rev-parse --abbrev-ref HEAD)"

# fake Maven seed repo — proves .m2 seeding + *-SNAPSHOT exclusion without touching the
# dev's real ~/.m2 (every invocation below passes --m2-seed so the default is never used)
FAKE_M2="$TMP_ROOT/fake-m2"
mkdir -p "$FAKE_M2/com/x/lib/1.0" "$FAKE_M2/com/x/lib/9.9-SNAPSHOT"
echo jar > "$FAKE_M2/com/x/lib/1.0/lib-1.0.jar"
echo jar > "$FAKE_M2/com/x/lib/9.9-SNAPSHOT/lib-9.9-SNAPSHOT.jar"

run_cwt() { bash "$CWT" "$@"; }

# --- Test 1 + 2: success + config rewrite -----------------------------------
GOOD_BRANCH="kapteyn/development/tester/smoke-$$"
OUT1="$(run_cwt --branch "$GOOD_BRANCH" --dir good --base "$BASE_BRANCH" \
        --repo "$REPO" --parent "$WT_PARENT" --no-npm --no-open --m2-seed "$FAKE_M2" 2>"$TMP_ROOT/err1.log")"
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

# nested .claude/ file cloned + rewritten (exercises the recursive copy_dir_with_substitution)
NESTED="$WT_PATH/.claude/sub/settings.local.json"
if [[ -f "$NESTED" ]]; then
  ok "nested .claude/ file cloned recursively"
  WT_WIN2="$(cygpath -m "$WT_PATH" 2>/dev/null || echo "$WT_PATH")"
  if grep -qF "$WT_WIN2/nested" "$NESTED"; then ok "nested file path rewritten"; else bad "nested file path not rewritten ($(cat "$NESTED"))"; fi
else
  bad "nested .claude/ file not cloned"
fi

# per-worktree state must NOT be cloned (.claude/TODO.md is each worktree's own todo list)
if [[ ! -e "$WT_PATH/.claude/TODO.md" ]]; then ok ".claude/TODO.md excluded from clone"; else bad ".claude/TODO.md was cloned into the worktree"; fi

# --- Test 2b: per-worktree Maven repo — maven.config + seed minus snapshots --
MVN_CFG="$WT_PATH/.mvn/maven.config"
if [[ -f "$MVN_CFG" ]]; then
  ok ".mvn/maven.config written"
  WT_WIN3="$(cygpath -m "$WT_PATH" 2>/dev/null || echo "$WT_PATH")"
  if grep -qxF -- "-Dmaven.repo.local=$WT_WIN3/.m2/repository" "$MVN_CFG"; then ok "maven.config points at the worktree's own .m2"; else bad "maven.config wrong (got: $(cat "$MVN_CFG"))"; fi
else
  bad ".mvn/maven.config missing"
fi
if [[ -f "$WT_PATH/.m2/repository/com/x/lib/1.0/lib-1.0.jar" ]]; then ok "release artifact seeded into private .m2"; else bad "release artifact not seeded"; fi
if [[ ! -d "$WT_PATH/.m2/repository/com/x/lib/9.9-SNAPSHOT" ]]; then ok "*-SNAPSHOT dir excluded from seed"; else bad "*-SNAPSHOT dir was seeded"; fi
if grep -qxF '.mvn/maven.config' "$REPO/.git/info/exclude" 2>/dev/null; then ok "maven.config listed in shared info/exclude"; else bad "maven.config not in info/exclude"; fi

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

# --- Test 5: a failure INSIDE a helper function still emits ERROR= (no bare death) ----------
# Regression for the ERR-trap contract: without `set -E` the trap is not inherited into shell
# functions, so a failure inside the perl path-rewrite would exit silently. Shadow perl with a
# failing stub so substitute_paths (called on the repo-path-bearing .mcp.json) fails mid-copy;
# the worktree add succeeds first, then the config copy trips the trap.
STUBBIN="$TMP_ROOT/stubbin"
mkdir -p "$STUBBIN"
printf '#!/bin/sh\nexit 1\n' > "$STUBBIN/perl"
chmod +x "$STUBBIN/perl"
GOOD2="kapteyn/development/tester/smoke2-$$"
OUT5="$( ( export PATH="$STUBBIN:$PATH"; run_cwt --branch "$GOOD2" --dir good2 --base "$BASE_BRANCH" \
        --repo "$REPO" --parent "$WT_PARENT" --no-npm --no-open --no-m2 ) 2>"$TMP_ROOT/err5.log" )"
RC5=$?
COMBINED5="$OUT5$(cat "$TMP_ROOT/err5.log")"
if [[ $RC5 -ne 0 ]]; then ok "helper-internal failure exits non-zero"; else bad "helper-internal failure exited 0"; fi
if printf '%s' "$COMBINED5" | grep -q '^ERROR='; then ok "helper-internal failure emits ERROR= (no bare set-e death)"; else bad "helper-internal failure was a bare death — no ERROR= line"; fi
git -C "$REPO" worktree remove --force "$WT_PARENT/good2" >/dev/null 2>&1 || true

# --- Test 6: --no-m2 skips the private Maven repo ----------------------------
GOOD3="kapteyn/development/tester/smoke3-$$"
OUT6="$(run_cwt --branch "$GOOD3" --dir good3 --base "$BASE_BRANCH" \
        --repo "$REPO" --parent "$WT_PARENT" --no-npm --no-open --no-m2 2>"$TMP_ROOT/err6.log")"
WT6="$(printf '%s\n' "$OUT6" | tail -n1)"; WT6="${WT6#WORKTREE_PATH=}"
if [[ -d "$WT6" && ! -e "$WT6/.mvn/maven.config" && ! -d "$WT6/.m2" ]]; then
  ok "--no-m2 leaves no maven.config / .m2 in the worktree"
else
  bad "--no-m2 still provisioned .m2 or maven.config (wt: $WT6)"
fi
git -C "$REPO" worktree remove --force "$WT6" >/dev/null 2>&1 || true

# --- summary ----------------------------------------------------------------
echo ""
echo "create-worktree smoke: $PASS passed, $FAIL failed"
[[ $FAIL -eq 0 ]] || exit 1
echo "SMOKE_OK"
