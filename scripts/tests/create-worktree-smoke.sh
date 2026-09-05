#!/bin/bash
#
# create-worktree-smoke.sh — end-to-end seam-test for scripts/create-worktree.
#
# Runs entirely in a disposable temp git repo — never touches a real checkout, a real
# branch, or the dev's configured worktree base dir. Asserts:
#   1. success  — a conforming branch prints WORKTREE_PATH=<path> as the last line and the
#                 worktree really exists on disk
#   2. config   — .claude/.mcp.json path references are cloned into the worktree and the
#                 main-repo path is rewritten to the worktree path (AC-005 / PRD AC-009)
#   3. copy     — the copy list comes from configuration: a repository naming its own
#                 entries gets those, and `copy-personal: false` gets none
#   4. gates    — the worktree is handed to the build gates, and --skip-build-gate and
#                 the deprecated aliases reach them
#   5. bad name — a non-conforming branch prints ERROR=<reason> incl. the gate pattern,
#                 exits non-zero, and creates NO worktree (SDD §9b)
#   6. trap     — a failure inside a helper still emits one ERROR= line
#   7. teardown — the created worktree is removed cleanly
#
# What each build gate then does to the worktree is scripts/tests/worktree-provision-smoke.sh.
# Self-contained: no network, no real build tool, no IDE. Exit 0 = all green.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CWT="$SCRIPT_DIR/../create-worktree"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
export AFK_PLUGIN_ROOT="$PLUGIN_ROOT"

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
STUBBIN="$TMP_ROOT/stubbin"
NPM_LOG="$TMP_ROOT/npm-invocations.log"

cleanup() {
  # Prune/remove any worktree we created, then nuke the whole sandbox.
  git -C "$REPO" worktree prune >/dev/null 2>&1 || true
  rm -rf "$TMP_ROOT" 2>/dev/null || true
}
trap cleanup EXIT

mkdir -p "$REPO" "$WT_PARENT" "$STUBBIN"

# A stub `npm` so a build gate's install is observable and instant.
cat > "$STUBBIN/npm" <<STUB
#!/bin/sh
echo "\$PWD \$*" >> "$NPM_LOG"
mkdir -p node_modules
exit 0
STUB
chmod +x "$STUBBIN/npm"
export PATH="$STUBBIN:$PATH"

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
# These are the untracked, personal files a plain `git worktree add` would leave behind —
# gitignored here exactly as they are in a real checkout, so the copy step is what puts
# them in the worktree, and nothing else can.
printf '.mcp.json
.claude/
tooling/
' > "$REPO/.gitignore"
echo '{"name":"fixture"}' > "$REPO/package.json"
echo '{"name":"fixture","lockfileVersion":3}' > "$REPO/package-lock.json"
# The branch gate reads the repository's own convention, so the fixture declares one.
mkdir -p "$REPO/.afk"
BRANCH_YAML="git:
  branch-pattern: '^team/development/[a-z0-9][a-z0-9._-]*/.+\$'
  branch-template: 'team/development/{user}/{ticket_lower}'"
write_config() {   # write_config <extra yaml>
  {
    echo "schema: 1"
    echo "$BRANCH_YAML"
    [[ -n "${1:-}" ]] && echo "$1"
  } > "$REPO/.afk/config.yaml"
}
write_config "build-gates:
  - npm
npm:
  worktree-install: ci"
git -C "$REPO" add -A
git -C "$REPO" commit -qm "seed"
# written AFTER the seed commit: .claude/* is gitignored in the real repo, so TODO.md only
# ever reaches a worktree via the config-clone step — which must skip it (per-worktree state)
echo "- [ ] per-worktree item" > "$REPO/.claude/TODO.md"
BASE_BRANCH="$(git -C "$REPO" rev-parse --abbrev-ref HEAD)"

run_cwt() { bash "$CWT" "$@"; }
drop_worktree() { git -C "$REPO" worktree remove --force "$1" >/dev/null 2>&1 || true; }

# --- Test 1 + 2: success + config rewrite -----------------------------------
GOOD_BRANCH="team/development/tester/smoke-$$"
OUT1="$(run_cwt --branch "$GOOD_BRANCH" --dir good --base "$BASE_BRANCH" \
        --repo "$REPO" --parent "$WT_PARENT" --no-open 2>"$TMP_ROOT/err1.log")"
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

# --- Test 4: the worktree reached the build gates ---------------------------
if [[ -s "$NPM_LOG" ]]; then ok "the selected build gate provisioned the worktree"; else bad "no build gate ran"; fi
MARKER="$(git -C "$WT_PATH" rev-parse --git-path afk/provisioned/npm 2>/dev/null)"
if [[ -f "$MARKER" ]]; then ok "provisioning marker written"; else bad "no provisioning marker at $MARKER"; fi

# --- Test 7: teardown removes the worktree cleanly --------------------------
# --force because the worktree carries cloned untracked config files (.mcp.json/.claude/...),
# which plain `git worktree remove` refuses — that cloning is the whole point of the script.
if git -C "$REPO" worktree remove --force "$WT_PATH" >/dev/null 2>&1; then ok "worktree removed cleanly"; else bad "worktree remove failed"; fi
if [[ ! -d "$WT_PATH" ]]; then ok "worktree dir gone after remove"; else bad "worktree dir still present after remove"; fi

# --- Test 5: bad branch name -> ERROR=, non-zero, no worktree ---------------
BAD_BRANCH="not-a-valid-branch"
OUT3="$(run_cwt --branch "$BAD_BRANCH" --dir bad --base "$BASE_BRANCH" \
        --repo "$REPO" --parent "$WT_PARENT" --no-open 2>"$TMP_ROOT/err3.log")"
RC3=$?
COMBINED3="$OUT3$(cat "$TMP_ROOT/err3.log")"
if [[ $RC3 -ne 0 ]]; then ok "bad branch exits non-zero"; else bad "bad branch exited 0"; fi
if printf '%s' "$COMBINED3" | grep -q '^ERROR='; then ok "bad branch prints ERROR= line"; else bad "no ERROR= line (got: $COMBINED3)"; fi
if printf '%s' "$COMBINED3" | grep -qF 'team/development'; then ok "ERROR names the gate pattern"; else bad "ERROR omits the pattern"; fi
if [[ ! -d "$WT_PARENT/bad" ]]; then ok "no worktree created for bad branch"; else bad "worktree created despite bad branch"; fi

# --- Test 6: a failure INSIDE a helper function still emits ERROR= ----------
# Regression for the ERR-trap contract: without `set -E` the trap is not inherited into shell
# functions, so a failure inside the perl path-rewrite would exit silently. Shadow perl with a
# failing stub so substitute_paths (called on the repo-path-bearing .mcp.json) fails mid-copy;
# the worktree add succeeds first, then the config copy trips the trap.
printf '#!/bin/sh\nexit 1\n' > "$STUBBIN/perl"
chmod +x "$STUBBIN/perl"
GOOD2="team/development/tester/smoke2-$$"
OUT5="$(run_cwt --branch "$GOOD2" --dir good2 --base "$BASE_BRANCH" \
        --repo "$REPO" --parent "$WT_PARENT" --no-open 2>"$TMP_ROOT/err5.log")"
RC5=$?
COMBINED5="$OUT5$(cat "$TMP_ROOT/err5.log")"
if [[ $RC5 -ne 0 ]]; then ok "helper-internal failure exits non-zero"; else bad "helper-internal failure exited 0"; fi
if printf '%s' "$COMBINED5" | grep -q '^ERROR='; then ok "helper-internal failure emits ERROR= (no bare set-e death)"; else bad "helper-internal failure was a bare death — no ERROR= line"; fi
rm -f "$STUBBIN/perl"
drop_worktree "$WT_PARENT/good2"

# --- Test 4b: --skip-build-gate and the deprecated aliases ------------------
: > "$NPM_LOG"
GOOD3="team/development/tester/smoke3-$$"
OUT6="$(run_cwt --branch "$GOOD3" --dir good3 --base "$BASE_BRANCH" \
        --repo "$REPO" --parent "$WT_PARENT" --no-open --skip-build-gate npm 2>"$TMP_ROOT/err6.log")"
WT6="$(printf '%s\n' "$OUT6" | tail -n1)"; WT6="${WT6#WORKTREE_PATH=}"
[[ ! -s "$NPM_LOG" ]] && ok "--skip-build-gate reaches the provisioner" || bad "--skip-build-gate did not skip"
drop_worktree "$WT6"

: > "$NPM_LOG"
GOOD4="team/development/tester/smoke4-$$"
OUT7="$(run_cwt --branch "$GOOD4" --dir good4 --base "$BASE_BRANCH" \
        --repo "$REPO" --parent "$WT_PARENT" --no-open --no-npm --no-m2 --m2-seed "$TMP_ROOT/nowhere" 2>"$TMP_ROOT/err7.log")"
WT7="$(printf '%s\n' "$OUT7" | tail -n1)"; WT7="${WT7#WORKTREE_PATH=}"
[[ -d "$WT7" ]] && ok "deprecated flags still produce a worktree" || bad "deprecated flags broke the run"
[[ ! -s "$NPM_LOG" ]] && ok "--no-npm still skips its build gate" || bad "--no-npm no longer skips"
grep -q 'deprecated' "$TMP_ROOT/err7.log" && ok "deprecated flags print a notice" || bad "no deprecation notice"
drop_worktree "$WT7"

# --- Test 3: the copy list comes from configuration -------------------------
mkdir -p "$REPO/tooling"
echo "personal" > "$REPO/tooling/notes.txt"
write_config "worktree:
  copy:
    - tooling
  copy-ignored-claude-md: false"
GOOD5="team/development/tester/smoke5-$$"
OUT8="$(run_cwt --branch "$GOOD5" --dir good5 --base "$BASE_BRANCH" \
        --repo "$REPO" --parent "$WT_PARENT" --no-open 2>"$TMP_ROOT/err8.log")"
WT8="$(printf '%s\n' "$OUT8" | tail -n1)"; WT8="${WT8#WORKTREE_PATH=}"
[[ -f "$WT8/tooling/notes.txt" ]] && ok "a configured copy entry is copied" || bad "configured copy entry missing"
[[ ! -e "$WT8/.mcp.json" ]] && ok "an entry not in the list is not copied" || bad ".mcp.json copied though the list omits it"
drop_worktree "$WT8"

write_config "worktree:
  copy-personal: false"
GOOD6="team/development/tester/smoke6-$$"
OUT9="$(run_cwt --branch "$GOOD6" --dir good6 --base "$BASE_BRANCH" \
        --repo "$REPO" --parent "$WT_PARENT" --no-open 2>"$TMP_ROOT/err9.log")"
WT9="$(printf '%s\n' "$OUT9" | tail -n1)"; WT9="${WT9#WORKTREE_PATH=}"
if [[ -d "$WT9" && ! -e "$WT9/.mcp.json" && ! -e "$WT9/.claude" ]]; then
  ok "copy-personal: false copies nothing"
else
  bad "copy-personal: false still copied files (wt: $WT9)"
fi
drop_worktree "$WT9"

# --- summary ----------------------------------------------------------------
echo ""
echo "create-worktree smoke: $PASS passed, $FAIL failed"
[[ $FAIL -eq 0 ]] || exit 1
echo "SMOKE_OK"
