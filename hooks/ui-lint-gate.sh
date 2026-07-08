#!/usr/bin/env bash
# Stop hook (ships with the afk plugin): UI lint gate.
# Blocks the agent from finishing when changed UI files (.js/.ts/.vue) fail ESLint.
#
# Scope rules:
#   - Only runs on files changed in the working tree (tracked/unstaged/untracked).
#   - A file is gated only if a .eslintrc.* exists in an ancestor directory
#     (nearest one wins — that directory is treated as the lint workspace).
#   - Deleted files are skipped. Files with no eslint config are skipped.
#   - If eslint cannot be resolved (node_modules not installed), the gate
#     silently allows — lint infra absence is not the agent's failure.
#
# Exit 2 with stderr surfaces lint errors back to the agent.

set -u

repo_root=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
cd "$repo_root" || exit 0

# Shared escape hatch with the other harness gates.
if [ -f .claude/hooks/.gate-disabled ]; then
  exit 0
fi

# Changed candidate files, excluding deletions ($1 == "D" covers staged deletes).
changed_ui=$(
  git status --porcelain 2>/dev/null \
    | awk '$1 != "D" {print $NF}' \
    | grep -E '\.(js|cjs|mjs|ts|vue)$' \
    | grep -vE '(^|/)(node_modules|dist|target)/' \
    || true
)
[ -z "$changed_ui" ] && exit 0

# Map each file to its lint workspace = nearest ancestor holding .eslintrc.*
declare -A ws_files
n_gated=0
while IFS= read -r f; do
  [ -f "$f" ] || continue
  dir=$(dirname "$f")
  ws=""
  while [ "$dir" != "." ] && [ "$dir" != "/" ]; do
    for rc_name in .eslintrc.js .eslintrc.cjs .eslintrc.json .eslintrc.yml .eslintrc.yaml; do
      if [ -f "$dir/$rc_name" ]; then
        ws="$dir"
        break
      fi
    done
    [ -n "$ws" ] && break
    dir=$(dirname "$dir")
  done
  [ -z "$ws" ] && continue
  rel=${f#"$ws"/}
  ws_files["$ws"]+="$rel"$'\n'
  n_gated=$((n_gated + 1))
done <<< "$changed_ui"

[ "$n_gated" -eq 0 ] && exit 0

# Content-hash pass cache: an unchanged tree that already passed skips the lint.
. "$(dirname "${BASH_SOURCE[0]}")/gate-cache.sh"
cache_key=$(gate_cache_key ui-lint)
gate_cache_hit ui-lint "$cache_key" && exit 0

. "$(dirname "${BASH_SOURCE[0]}")/gate-metrics.sh"
gate_metrics_begin

fail=0
linted=0
report=""
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
    report+="Workspace: $ws"$'\n'"$out"$'\n\n'
  fi
done

if [ "$fail" -ne 0 ]; then
  gate_metrics_emit ui-lint blocked "\"files\":$n_gated"
  {
    printf '[harness] ESLint failed for changed UI files — cannot finish.\n\n'
    printf '%s' "$report"
    printf 'Fix the lint errors above (or run the workspace'\''s "npm run lint -- --fix" for auto-fixables).\n'
  } >&2
  exit 2
fi

gate_metrics_emit ui-lint pass "\"files\":$n_gated"
# Store only when eslint actually ran — "eslint unresolvable" is not a pass to remember.
[ "$linted" -eq 1 ] && gate_cache_store ui-lint "$cache_key"
exit 0
