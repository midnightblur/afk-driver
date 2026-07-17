#!/usr/bin/env bash
# Installer for the afk plugin's git hooks (currently just the branch-name gate).
#
# Runs automatically on every session start (wired in hooks.json → SessionStart),
# so enabling the plugin is the only opt-in a dev needs — the first session in a
# core-services checkout installs the hook and it then persists in .git/hooks.
# Also runnable by hand (and by `/afk:setup`, register H5) for non-session / CI:
#   bash tools/payable/ai-agents/plugins/workflow/hooks/install-git-hooks.sh
#
# Behaviour:
#   - Idempotent: if our hook is already installed, it's a silent no-op.
#   - Self-scoping: installs ONLY in a checkout that actually ships the gate
#     script (i.e. core-services); no-ops in any other repo, so a globally
#     enabled plugin never drops a reference-transaction hook into a foreign repo.
#   - Worktree-safe: installs into the shared (common) hooks dir — one install
#     covers every worktree of the checkout.
#   - Non-destructive: refuses to clobber a pre-existing, non-AFK
#     reference-transaction hook (silently skips it in --quiet mode).
#
# --quiet: suppress info output and never exit non-zero (used by SessionStart).
set -uo pipefail

QUIET=0
[ "${1:-}" = "--quiet" ] && QUIET=1
say() { [ "$QUIET" = 1 ] || echo "$@"; }

marker="afk-branch-name-gate"

# Must be inside a git repo.
top=$(git rev-parse --show-toplevel 2>/dev/null) || { say "afk: not inside a git repo — nothing to do."; exit 0; }

# Only install where the gate actually ships (a core-services checkout); never
# drop a reference-transaction hook into an unrelated repo.
gate="$top/tools/payable/ai-agents/plugins/workflow/hooks/branch-name-gate.sh"
if [ ! -f "$gate" ]; then
  say "afk: branch-name gate not present in this repo ($top) — skipping."
  exit 0
fi

# Absolute path to the resolved (common) hooks dir — correct from any subdir/worktree.
hooks_dir=$(git rev-parse --path-format=absolute --git-path hooks 2>/dev/null) \
  || hooks_dir=$(git rev-parse --git-path hooks)
mkdir -p "$hooks_dir"
target="$hooks_dir/reference-transaction"

# Already ours? no-op (keeps SessionStart cheap, avoids mtime churn).
if [ -e "$target" ] && grep -q "$marker" "$target" 2>/dev/null; then
  say "afk: branch-name gate already installed -> $target"
  exit 0
fi

# Present but not ours: never clobber.
if [ -e "$target" ]; then
  [ "$QUIET" = 1 ] && exit 0
  echo "afk: refusing to overwrite an existing non-AFK hook:" >&2
  echo "     $target" >&2
  echo "afk: inspect it and merge the delegation stub by hand, or remove it first." >&2
  exit 1
fi

cat > "$target" <<'HOOK'
#!/usr/bin/env bash
# afk-branch-name-gate (installed by the afk plugin's install-git-hooks.sh).
# Delegates to the plugin gate in the acting checkout; never breaks git.
top=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
gate="$top/tools/payable/ai-agents/plugins/workflow/hooks/branch-name-gate.sh"
[ -f "$gate" ] || exit 0
exec bash "$gate" "$@"
HOOK
chmod +x "$target"

say "afk: installed branch-name gate -> $target"
say "afk: new branches must match kapteyn/development/<username>/<slug>."
say "afk: checkouts of existing/remote branches are unaffected."
say "afk: disable -> git config afk.branchNameGate false   |   remove -> rm \"$target\""
