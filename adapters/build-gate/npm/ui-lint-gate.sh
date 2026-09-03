#!/usr/bin/env bash
# build-gate/npm — UI lint gate.
# Blocks the commit when changed UI files (.js/.cjs/.mjs/.ts/.vue) fail the lint
# command the repository named in `npm.lint`.
#
# Runs at COMMIT time (hooks/precommit-gates.sh, installed by
# hooks/install-git-hooks.sh), not on every turn end — see
# adapters/build-gate/maven/maven-compile-gate.sh for the rationale.
#
# Scope rules:
#   - Only files in the shared gate context (staged at commit time).
#   - A file is gated only if a lint configuration exists in an ancestor
#     directory (nearest one wins — that directory is the lint workspace). With
#     none, `npm.workspace-root` is the workspace if it is an ancestor.
#   - Deleted files are skipped. Files with no lint workspace are skipped.
#   - If the lint command cannot be resolved (dependencies not installed), the
#     gate silently allows — lint infra absence is not the committer's failure.
#
# `npm.lint` is a command and its fixed arguments, split on whitespace; the
# changed files are appended. Default: `npx --no-install eslint
# --no-error-on-unmatched-pattern`.
#
# Exit 2 with stderr surfaces lint errors back to the agent/committer.

set -u

AFK_NPM_LINT_CONFIGS=".eslintrc.js .eslintrc.cjs .eslintrc.json .eslintrc.yml .eslintrc.yaml eslint.config.js eslint.config.cjs eslint.config.mjs eslint.config.ts"

gate_ui_lint() {
  [ -f .claude/hooks/.gate-disabled ] && return 0

  local changed_ui
  changed_ui=$(gate_ctx_filter AFK_CTX_LIVE '*.js' '*.cjs' '*.mjs' '*.ts' '*.vue')
  [ -z "$changed_ui" ] && return 0

  local -a lint_cmd=()
  # shellcheck disable=SC2206 — whitespace splitting is the documented contract.
  if [ -n "${AFK_CFG_NPM_LINT:-}" ]; then
    lint_cmd=($AFK_CFG_NPM_LINT)
  else
    lint_cmd=(npx --no-install eslint --no-error-on-unmatched-pattern)
  fi
  local ws_root=${AFK_CFG_NPM_WORKSPACE_ROOT:-}

  # Map each file to its lint workspace = nearest ancestor holding a lint config.
  local -A ws_files=()
  local n_gated=0 f dir ws rc_name rel
  while IFS= read -r f; do
    [ -n "$f" ] || continue
    case "$f" in */node_modules/*|*/dist/*|*/target/*|node_modules/*|dist/*|target/*) continue ;; esac
    [ -f "$f" ] || continue
    dir=${f%/*}; [ "$dir" = "$f" ] && dir="."
    ws=""
    while [ "$dir" != "." ] && [ "$dir" != "/" ]; do
      for rc_name in $AFK_NPM_LINT_CONFIGS; do
        if [ -f "$dir/$rc_name" ]; then ws="$dir"; break; fi
      done
      [ -n "$ws" ] && break
      [ "${dir%/*}" = "$dir" ] && dir="." || dir=${dir%/*}
    done
    # A repository that lints from one hoisted root declares it; use it when the
    # file sits under it and carries no nearer configuration of its own.
    if [ -z "$ws" ] && [ -n "$ws_root" ] && [ -d "$ws_root" ]; then
      case "$f" in "$ws_root"/*) ws="$ws_root" ;; esac
    fi
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
    # Resolve the linter from the workspace (a hoisted root resolves by walk-up).
    if ! (cd "$ws" && "${lint_cmd[@]}" --version >/dev/null 2>&1); then
      continue
    fi
    linted=1
    out=$(cd "$ws" && "${lint_cmd[@]}" "${files[@]}" 2>&1)
    rc=$?
    if [ "$rc" -ne 0 ]; then
      fail=1
      # Cap per-workspace output — an unbounded lint dump re-enters the agent's
      # context on every failed run. Tail keeps the problems-summary line.
      total_lines=$(printf '%s\n' "$out" | wc -l)
      if [ "$total_lines" -gt 40 ]; then
        out=$(printf '%s\n' "$out" | head -35)$'\n'"… ($((total_lines - 35)) more lines — re-run: cd $ws && ${lint_cmd[*]} <files>)"$'\n'$(printf '%s\n' "$out" | tail -2)
      fi
      report+="Workspace: $ws"$'\n'"$out"$'\n\n'
    fi
  done

  if [ "$fail" -ne 0 ]; then
    gate_metrics_emit ui-lint blocked "\"files\":$n_gated"
    {
      printf '[harness] Lint failed for changed UI files — cannot commit.\n\n'
      printf '%s' "$report"
      printf 'Fix the lint errors above (or run the workspace lint script with --fix for auto-fixables).\n'
    } >&2
    return 2
  fi

  gate_metrics_emit ui-lint pass "\"files\":$n_gated"
  # Store only when the linter actually ran — "linter unresolvable" is not a pass
  # to remember.
  [ "$linted" -eq 1 ] && gate_cache_store ui-lint "$cache_key"
  return 0
}

# ---- standalone invocation (manual run; scope = working tree)
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  _d=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
  _hooks="${AFK_PLUGIN_ROOT:-$(cd "$_d/../../.." && pwd)}/hooks"
  _root=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
  cd "$_root" || exit 0
  . "$_hooks/lib/config.sh"; afk_config_load
  . "$_hooks/gate-context.sh"; gate_ctx_build
  . "$_hooks/gate-cache.sh"
  . "$_hooks/gate-metrics.sh"
  gate_ui_lint; exit $?
fi
