#!/usr/bin/env bash
# install-git-hooks.sh smoke tests: a failed hook write must not report
# "installed", and the core.hooksPath skip must be distinguishable from a
# success outside --quiet (#121). Self-contained: exercises the real installer
# against throwaway fixture repositories.

set -uo pipefail

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
plugin_root=$(cd "$here/../.." && pwd)
installer="$plugin_root/hooks/install-git-hooks.sh"

fails=0
pass() { echo "  ok: $1"; }
fail() { echo "  FAIL: $1" >&2; fails=$((fails + 1)); }

new_repo() {
  local dir=$1
  rm -rf "$dir"
  mkdir -p "$dir"
  git -C "$dir" init -q
}

# 1. A read-only existing AFK hook (plugin root moved) fails the rewrite.
readonly_hook() {
  local scratch
  scratch=$(mktemp -d)
  new_repo "$scratch/repo"
  local hooks_dir
  hooks_dir=$(git -C "$scratch/repo" rev-parse --path-format=absolute --git-path hooks)
  mkdir -p "$hooks_dir"
  printf '# afk-branch-name-gate (old)\n# afk-plugin-root: /nonexistent/old-root\n' > "$hooks_dir/reference-transaction"
  chmod a-w "$hooks_dir/reference-transaction"

  out=$(cd "$scratch/repo" && bash "$installer" 2>&1)
  rc=$?
  if [ "$rc" -eq 0 ]; then
    fail "read-only hook: installer exits 0 despite the failed write (got: $out)"
  else
    pass "read-only hook: installer exits non-zero ($rc)"
  fi
  if printf '%s' "$out" | grep -q "installed branch-name gate"; then
    fail "read-only hook: output claims the branch-name gate was installed (got: $out)"
  else
    pass "read-only hook: no 'installed branch-name gate' claim"
  fi
  if printf '%s' "$out" | grep -q "NOT installed"; then
    pass "read-only hook: failure is reported"
  else
    fail "read-only hook: failure is not reported (got: $out)"
  fi
  if grep -q "afk-plugin-root: /nonexistent/old-root" "$hooks_dir/reference-transaction"; then
    pass "read-only hook: stale stub left untouched"
  else
    fail "read-only hook: stub was modified or lost"
  fi
  chmod u+w "$hooks_dir/reference-transaction"
  rm -rf "$scratch"
}

# 2. core.hooksPath skip: exit 0 under --quiet, non-zero otherwise.
hooks_path_skip() {
  local scratch rc
  scratch=$(mktemp -d)
  new_repo "$scratch/repo"
  git -C "$scratch/repo" config core.hooksPath .husky

  (cd "$scratch/repo" && bash "$installer" >/dev/null 2>&1)
  rc=$?
  if [ "$rc" -eq 0 ]; then
    fail "hooksPath: manual run exits 0 — a skip is indistinguishable from a success"
  else
    pass "hooksPath: manual run exits non-zero ($rc)"
  fi

  (cd "$scratch/repo" && bash "$installer" --quiet >/dev/null 2>&1)
  rc=$?
  if [ "$rc" -eq 0 ]; then
    pass "hooksPath: --quiet still exits 0 (SessionStart contract)"
  else
    fail "hooksPath: --quiet exits $rc — the SessionStart contract is broken"
  fi
  rm -rf "$scratch"
}

# 3. Happy path still installs both hooks and exits 0.
happy_path() {
  local scratch rc hooks_dir
  scratch=$(mktemp -d)
  new_repo "$scratch/repo"
  hooks_dir=$(git -C "$scratch/repo" rev-parse --path-format=absolute --git-path hooks)

  out=$(cd "$scratch/repo" && bash "$installer" 2>&1)
  rc=$?
  if [ "$rc" -eq 0 ]; then
    pass "happy path: exits 0"
  else
    fail "happy path: exits $rc (got: $out)"
  fi
  if [ -x "$hooks_dir/reference-transaction" ] && grep -q "afk-plugin-root: $plugin_root" "$hooks_dir/reference-transaction"; then
    pass "happy path: branch-name gate installed with the current root"
  else
    fail "happy path: branch-name gate missing or has the wrong root"
  fi
  if [ -x "$hooks_dir/pre-commit" ] && grep -q "afk-precommit-gates" "$hooks_dir/pre-commit"; then
    pass "happy path: pre-commit gate installed"
  else
    fail "happy path: pre-commit gate missing"
  fi
  rm -rf "$scratch"
}

readonly_hook
hooks_path_skip
happy_path

if [ "$fails" -eq 0 ]; then
  echo "install-hooks smoke: all ok"
  exit 0
fi
echo "install-hooks smoke: $fails failure(s)" >&2
exit 1
