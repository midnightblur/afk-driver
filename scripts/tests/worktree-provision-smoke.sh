#!/bin/bash
#
# worktree-provision-smoke.sh — seam-test for scripts/worktree-provision and the
# per-kind adapters it dispatches to.
#
# Runs entirely in a disposable temp git repo — never touches a real checkout, a
# real branch, or the developer's own local repository. Asserts:
#   1. payload   — each adapter receives the JSON contract and answers with one
#                  JSON object carrying kind/status/fingerprint
#   2. maven     — an isolated local repository is provisioned, the seed skips
#                  the excluded globs, and both ignore entries land in the
#                  COMMON info/exclude
#   3. npm       — the configured install command runs in the workspace root,
#                  and only when there is a lockfile to install from
#   4. markers   — they live in the git admin dir: `git status` stays clean and
#                  `git worktree remove` needs no --force because of them
#   5. rerun     — a second run repeats no work; a changed lockfile is reported,
#                  not silently redone; --force redoes it
#   6. adoption  — a worktree provisioned before this existed is adopted, not
#                  redone (the migration path)
#   7. skips     — --skip-build-gate, an unselected kind, and `none` settings
#
# Self-contained: no network, no real build tool (a stub `npm` on PATH records
# its invocation). Exit 0 = all green.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROVISION="$SCRIPT_DIR/../worktree-provision"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
export AFK_PLUGIN_ROOT="$PLUGIN_ROOT"

PASS=0
FAIL=0
ok()  { echo "  ok   - $1"; PASS=$((PASS + 1)); }
bad() { echo "  FAIL - $1"; FAIL=$((FAIL + 1)); }

if [[ ! -f "$PROVISION" ]]; then
  echo "FAIL: worktree-provision not found at $PROVISION" >&2
  exit 1
fi

TMP_ROOT="$(mktemp -d 2>/dev/null || mktemp -d -t wtp)"
REPO="$TMP_ROOT/main-repo"
WT_PARENT="$TMP_ROOT/worktrees"
STUBBIN="$TMP_ROOT/stubbin"
NPM_LOG="$TMP_ROOT/npm-invocations.log"

cleanup() {
  git -C "$REPO" worktree prune >/dev/null 2>&1 || true
  rm -rf "$TMP_ROOT" 2>/dev/null || true
}
trap cleanup EXIT

mkdir -p "$REPO" "$WT_PARENT" "$STUBBIN"

# A stub `npm` so the npm adapter's install is observable and instant.
cat > "$STUBBIN/npm" <<STUB
#!/bin/sh
echo "\$PWD \$*" >> "$NPM_LOG"
mkdir -p node_modules
cp package-lock.json node_modules/.package-lock.json
exit 0
STUB
chmod +x "$STUBBIN/npm"
export PATH="$STUBBIN:$PATH"

# The seed source the maven adapter is pointed at — never the real one.
FAKE_M2="$TMP_ROOT/fake-m2"
mkdir -p "$FAKE_M2/com/x/lib/1.0" "$FAKE_M2/com/x/lib/9.9-SNAPSHOT"
echo jar > "$FAKE_M2/com/x/lib/1.0/lib-1.0.jar"
echo jar > "$FAKE_M2/com/x/lib/9.9-SNAPSHOT/lib-9.9-SNAPSHOT.jar"

git -C "$REPO" init -q
git -C "$REPO" config user.email smoke@test.local
git -C "$REPO" config user.name  smoke-tester
git -C "$REPO" config commit.gpgsign false
mkdir -p "$REPO/.afk"
write_config() {   # write_config <build-gates yaml body>
  cat > "$REPO/.afk/config.yaml" <<YAML
schema: 1
build-gates:
$1
YAML
}
cat > "$REPO/package-lock.json" <<'JSON'
{"name":"fixture","lockfileVersion":3}
JSON
echo '{"name":"fixture"}' > "$REPO/package.json"
echo seed > "$REPO/README.md"
write_config "  - maven
  - npm
maven:
  worktree-repo: isolated
  worktree-seed: $FAKE_M2
  worktree-seed-exclude:
    - '*-SNAPSHOT'
npm:
  worktree-install: ci"
git -C "$REPO" add -A
git -C "$REPO" commit -qm seed
BASE="$(git -C "$REPO" rev-parse --abbrev-ref HEAD)"

new_worktree() {   # new_worktree <name> -> path on stdout
  local name="$1" path="$WT_PARENT/$1"
  git -C "$REPO" worktree add -q -b "wt-$name" "$path" "$BASE" >/dev/null 2>&1
  printf '%s' "$path"
}

# --- 1/2/3: a plain run provisions both kinds --------------------------------
WT1="$(new_worktree one)"
OUT1="$(bash "$PROVISION" --source "$REPO" --worktree "$WT1" 2>"$TMP_ROOT/err1.log")"
RC1=$?
[[ $RC1 -eq 0 ]] && ok "exit 0" || bad "exit $RC1; stderr: $(cat "$TMP_ROOT/err1.log")"
printf '%s' "$OUT1" | grep -q '"kind":"maven"' && ok "maven adapter answered with JSON" || bad "no maven JSON (got: $OUT1)"
printf '%s' "$OUT1" | grep -q '"kind":"npm"'   && ok "npm adapter answered with JSON"   || bad "no npm JSON (got: $OUT1)"

WT1_WIN="$(cygpath -m "$WT1" 2>/dev/null || echo "$WT1")"
if grep -qxF -- "-Dmaven.repo.local=$WT1_WIN/.m2/repository" "$WT1/.mvn/maven.config" 2>/dev/null; then
  ok "maven.config points at the worktree's own local repository"
else
  bad "maven.config wrong or missing"
fi
[[ -f "$WT1/.m2/repository/com/x/lib/1.0/lib-1.0.jar" ]] && ok "release artifact seeded" || bad "release artifact not seeded"
[[ -d "$WT1/.m2/repository/com/x/lib/9.9-SNAPSHOT" ]] && bad "excluded glob was seeded" || ok "excluded glob skipped"
EXCLUDE="$REPO/.git/info/exclude"
grep -qxF '.mvn/maven.config' "$EXCLUDE" 2>/dev/null && ok "maven.config in the common info/exclude" || bad "maven.config not excluded"
grep -qxF '.m2/' "$EXCLUDE" 2>/dev/null && ok ".m2/ in the common info/exclude" || bad ".m2/ not excluded"
if grep -qF " ci" "$NPM_LOG" 2>/dev/null && grep -qF "$(cd "$WT1" && pwd) " "$NPM_LOG"; then
  ok "the configured install command ran in the workspace root"
else
  bad "install not recorded for $WT1 (log: $(cat "$NPM_LOG" 2>/dev/null))"
fi
[[ -d "$WT1/node_modules" ]] && ok "node_modules restored" || bad "node_modules missing"

# --- 4: markers are invisible to git ----------------------------------------
MARKER="$(git -C "$WT1" rev-parse --git-path afk/provisioned/maven)"
[[ -f "$MARKER" ]] && ok "marker written in the git admin dir" || bad "no marker at $MARKER"
grep -q '^fingerprint=' "$MARKER" 2>/dev/null && ok "marker carries a fingerprint" || bad "marker has no fingerprint"
grep -q '^toolkit=' "$MARKER" 2>/dev/null && ok "marker records the toolkit version" || bad "marker has no toolkit version"
if [[ -z "$(git -C "$WT1" status --porcelain -- .mvn .m2 2>/dev/null)" ]]; then
  ok "git status clean after provisioning"
else
  bad "provisioning left files in git status: $(git -C "$WT1" status --porcelain | head -3)"
fi

# --- 5: rerun repeats no work ------------------------------------------------
: > "$NPM_LOG"
PREV_JAR_TIME="$(stat -c %Y "$WT1/.m2/repository/com/x/lib/1.0/lib-1.0.jar" 2>/dev/null || echo 0)"
bash "$PROVISION" --source "$REPO" --worktree "$WT1" >/dev/null 2>"$TMP_ROOT/err2.log"
if grep -q 'unchanged' "$TMP_ROOT/err2.log"; then ok "rerun reports unchanged"; else bad "rerun did not report unchanged: $(cat "$TMP_ROOT/err2.log")"; fi
[[ ! -s "$NPM_LOG" ]] && ok "rerun ran no install" || bad "rerun ran the install again"
NOW_JAR_TIME="$(stat -c %Y "$WT1/.m2/repository/com/x/lib/1.0/lib-1.0.jar" 2>/dev/null || echo 1)"
[[ "$PREV_JAR_TIME" == "$NOW_JAR_TIME" ]] && ok "rerun re-seeded nothing" || bad "rerun re-seeded the repository"

# a changed lockfile is reported, not silently redone
echo '{"name":"fixture","lockfileVersion":3,"changed":true}' > "$WT1/package-lock.json"
bash "$PROVISION" --source "$REPO" --worktree "$WT1" >/dev/null 2>"$TMP_ROOT/err3.log"
grep -q 'changed since provisioning' "$TMP_ROOT/err3.log" && ok "changed lockfile is reported" || bad "changed lockfile not reported: $(cat "$TMP_ROOT/err3.log")"
[[ ! -s "$NPM_LOG" ]] && ok "changed lockfile ran no install without --force" || bad "changed lockfile installed anyway"

bash "$PROVISION" --source "$REPO" --worktree "$WT1" --force >/dev/null 2>&1
[[ -s "$NPM_LOG" ]] && ok "--force redoes the install" || bad "--force did not redo the install"

# `git worktree remove` must not need --force because of anything we wrote.
# The worktree still carries the local repository we provisioned, so remove it first —
# that directory is the point of the feature, not an accident of the markers.
rm -rf "$WT1/.m2" "$WT1/.mvn" "$WT1/node_modules" "$WT1/package-lock.json"
git -C "$WT1" checkout -- package-lock.json 2>/dev/null || true
if git -C "$REPO" worktree remove "$WT1" >/dev/null 2>&1; then
  ok "git worktree remove needs no --force for the markers"
else
  bad "markers blocked git worktree remove: $(git -C "$REPO" worktree remove "$WT1" 2>&1 | head -1)"
  git -C "$REPO" worktree remove --force "$WT1" >/dev/null 2>&1 || true
fi

# --- 6: adoption of a worktree provisioned before this existed ---------------
WT2="$(new_worktree two)"
WT2_WIN="$(cygpath -m "$WT2" 2>/dev/null || echo "$WT2")"
mkdir -p "$WT2/.mvn" "$WT2/.m2/repository/legacy"
printf -- '-Dmaven.repo.local=%s/.m2/repository\n' "$WT2_WIN" > "$WT2/.mvn/maven.config"
echo legacy > "$WT2/.m2/repository/legacy/marker.txt"
: > "$NPM_LOG"
mkdir -p "$WT2/node_modules"
cp "$WT2/package-lock.json" "$WT2/node_modules/.package-lock.json"
OUT6="$(bash "$PROVISION" --source "$REPO" --worktree "$WT2" 2>"$TMP_ROOT/err6.log")"
printf '%s' "$OUT6" | grep -q '"status":"adopted"' && ok "existing state is adopted" || bad "not adopted (got: $OUT6)"
[[ -f "$WT2/.m2/repository/legacy/marker.txt" ]] && ok "adoption kept the existing repository" || bad "adoption destroyed the existing repository"
[[ ! -f "$WT2/.m2/repository/com/x/lib/1.0/lib-1.0.jar" ]] && ok "adoption did not re-seed" || bad "adoption re-seeded"
[[ ! -s "$NPM_LOG" ]] && ok "adoption ran no install" || bad "adoption ran an install"
git -C "$REPO" worktree remove --force "$WT2" >/dev/null 2>&1 || true

# --- 7: the ways to opt out --------------------------------------------------
WT3="$(new_worktree three)"
: > "$NPM_LOG"
bash "$PROVISION" --source "$REPO" --worktree "$WT3" --skip-build-gate npm >/dev/null 2>"$TMP_ROOT/err7.log"
[[ ! -s "$NPM_LOG" ]] && ok "--skip-build-gate npm skips the install" || bad "--skip-build-gate npm still installed"
[[ -f "$WT3/.mvn/maven.config" ]] && ok "--skip-build-gate npm still provisions maven" || bad "--skip-build-gate npm skipped maven too"
git -C "$REPO" worktree remove --force "$WT3" >/dev/null 2>&1 || true

write_config "  - maven
maven:
  worktree-repo: shared"
WT4="$(new_worktree four)"
: > "$NPM_LOG"
OUT8="$(bash "$PROVISION" --source "$REPO" --worktree "$WT4" 2>"$TMP_ROOT/err8.log")"
printf '%s' "$OUT8" | grep -q '"status":"skipped"' && ok "a shared local repository provisions nothing" || bad "shared mode still provisioned (got: $OUT8)"
[[ ! -e "$WT4/.mvn/maven.config" ]] && ok "shared mode wrote no maven.config" || bad "shared mode wrote maven.config"
[[ ! -s "$NPM_LOG" ]] && ok "an unselected kind is never run" || bad "an unselected kind ran"
git -C "$REPO" worktree remove --force "$WT4" >/dev/null 2>&1 || true

write_config "  - npm
npm:
  worktree-install: none"
WT5="$(new_worktree five)"
: > "$NPM_LOG"
bash "$PROVISION" --source "$REPO" --worktree "$WT5" >/dev/null 2>&1
[[ ! -s "$NPM_LOG" ]] && ok "worktree-install none runs no install" || bad "worktree-install none installed anyway"
git -C "$REPO" worktree remove --force "$WT5" >/dev/null 2>&1 || true

# --- summary ----------------------------------------------------------------
echo ""
echo "worktree-provision smoke: $PASS passed, $FAIL failed"
[[ $FAIL -eq 0 ]] || exit 1
echo "SMOKE_OK"
