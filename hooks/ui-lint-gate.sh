#!/usr/bin/env bash
# Commit gate (ships with the afk plugin): UI lint gate.
# Blocks the commit when changed UI files (.js/.ts/.vue) fail ESLint.
#
# Runs at COMMIT time (precommit-gates.sh, installed by install-git-hooks.sh),
# not on every turn end — see maven-compile-gate.sh for the rationale.
#
# Scope rules:
#   - Only files in the shared gate context (staged at commit time).
#   - A file is gated only if a .eslintrc.* exists in an ancestor directory
#     (nearest one wins — that directory is treated as the lint workspace).
#   - Deleted files are skipped. Files with no eslint config are skipped.
#   - If eslint cannot be resolved (node_modules not installed), the gate
#     silently allows — lint infra absence is not the committer's failure.
#
# Exit 2 with stderr surfaces lint errors back to the agent/committer.

set -u

gate_ui_lint() {
  [ -f .claude/hooks/.gate-disabled ] && return 0

  local changed_ui
  changed_ui=$(gate_ctx_filter AFK_CTX_LIVE '*.js' '*.cjs' '*.mjs' '*.ts' '*.vue')
  [ -z "$changed_ui" ] && return 0

  # Map each file to its lint workspace = nearest ancestor holding .eslintrc.*
  local -A ws_files=()
  local n_gated=0 f dir ws rc_name rel
  while IFS= read -r f; do
    [ -n "$f" ] || continue
    case "$f" in */node_modules/*|*/dist/*|*/target/*|node_modules/*|dist/*|target/*) continue ;; esac
    [ -f "$f" ] || continue
    dir=${f%/*}; [ "$dir" = "$f" ] && dir="."
    ws=""
    while [ "$dir" != "." ] && [ "$dir" != "/" ]; do
      for rc_name in .eslintrc.js .eslintrc.cjs .eslintrc.json .eslintrc.yml .eslintrc.yaml; do
        if [ -f "$dir/$rc_name" ]; then ws="$dir"; break; fi
      done
      [ -n "$ws" ] && break
      [ "${dir%/*}" = "$dir" ] && dir="." || dir=${dir%/*}
    done
    [ -z "$ws" ] && continue
    rel=${f#"$ws"/}
    ws_files["$ws"]+="$rel"$'\n'
    n_gated=$((n_gated + 1))
  done <<<"$changed_ui"

  [ "$n_gated" -eq 0 ] && return 0

  local cache_key
  cache_key=$(gate_cache_key ui-lint)
  gate_cache_hit ui-lint "$cache_key" && return 0

  gate_metrics_begin

  local fail=0 linted=0 report="" out rc total_lines
  local -a files
  for ws in "${!ws_files[@]}"; do
    mapfile -t files < <(printf '%s' "${ws_files[$ws]}")
    # Resolve eslint from the workspace (hoisted root node_modules via npx walk-up).
    if ! (cd "$ws" && npx --no-install eslint --version >/dev/null 2>&1); then
      continue
    fi
    linted=1
    out=$(cd "$ws" && npx --no-install eslint --no-error-on-unmatched-pattern "${files[@]}" 2>&1)
    rc=$?
    if [ "$rc" -ne 0 ]; then
      fail=1
      # Cap per-workspace output — an unbounded eslint dump re-enters the agent's
      # context on every failed run. Tail keeps the problems-summary line.
      total_lines=$(printf '%s\n' "$out" | wc -l)
      if [ "$total_lines" -gt 40 ]; then
        out=$(printf '%s\n' "$out" | head -35)$'\n'"… ($((total_lines - 35)) more lines — re-run: cd $ws && npx eslint <files>)"$'\n'$(printf '%s\n' "$out" | tail -2)
      fi
      report+="Workspace: $ws"$'\n'"$out"$'\n\n'
    fi
  done

  if [ "$fail" -ne 0 ]; then
    gate_metrics_emit ui-lint blocked "\"files\":$n_gated"
    {
      printf '[harness] ESLint failed for changed UI files — cannot commit.\n\n'
      printf '%s' "$report"
      printf 'Fix the lint errors above (or run the workspace'\''s "npm run lint -- --fix" for auto-fixables).\n'
    } >&2
    return 2
  fi

  gate_metrics_emit ui-lint pass "\"files\":$n_gated"
  # Store only when eslint actually ran — "eslint unresolvable" is not a pass to remember.
  [ "$linted" -eq 1 ] && gate_cache_store ui-lint "$cache_key"
  return 0
}

# ---- standalone invocation (manual run; scope = working tree)
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  _d=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
  _root=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
  cd "$_root" || exit 0
  . "$_d/gate-context.sh"; gate_ctx_build
  . "$_d/gate-cache.sh"
  . "$_d/gate-metrics.sh"
  gate_ui_lint; exit $?
fi
