#!/usr/bin/env bash
# Installer for the afk plugin's git hooks:
#   reference-transaction -> branch-name-gate.sh  (agent-only branch naming)
#   pre-commit            -> precommit-gates.sh   (maven-compile, java-format, ui-lint)
#
# The pre-commit hook is where the expensive code gates live. They used to run on
# every turn end, which made interactive sessions pay a reactor build per
# question; at commit time the same enforcement costs once per commit.
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
#     covers every worktree of the checkout. Both hooks are AGENT-ONLY at run
#     time (they return immediately without an agent-runtime marker), so the
#     shared install never puts a gate in a human's commit or branch creation.
#   - Non-destructive: refuses to clobber a pre-existing, non-AFK
#     reference-transaction hook (silently skips it in --quiet mode).
#
# --quiet: suppress info output and never exit non-zero (used by SessionStart).
set -uo pipefail

QUIET=0
[ "${1:-}" = "--quiet" ] && QUIET=1
say() { [ "$QUIET" = 1 ] || echo "$@"; }

# Must be inside a git repo.
top=$(git rev-parse --show-toplevel 2>/dev/null) || { say "afk: not inside a git repo — nothing to do."; exit 0; }

# Absolute path to the resolved (common) hooks dir — correct from any subdir/worktree.
hooks_dir=$(git rev-parse --path-format=absolute --git-path hooks 2>/dev/null) \
  || hooks_dir=$(git rev-parse --git-path hooks)
mkdir -p "$hooks_dir"

rc=0

# install_hook <git-hook-name> <marker> <plugin-script> <description>
# Idempotent, self-scoping (only where the plugin script ships) and
# non-destructive (never clobbers a pre-existing non-AFK hook).
install_hook() {
  local hook=$1 marker=$2 script=$3 desc=$4
  local gate="$top/tools/payable/ai-agents/plugins/workflow/hooks/$script"
  if [ ! -f "$gate" ]; then
    say "afk: $desc not present in this repo ($top) — skipping."
    return 0
  fi

  local target="$hooks_dir/$hook"

  # Already ours? no-op (keeps SessionStart cheap, avoids mtime churn).
  if [ -e "$target" ] && grep -q "$marker" "$target" 2>/dev/null; then
    say "afk: $desc already installed -> $target"
    return 0
  fi

  # Present but not ours: never clobber.
  if [ -e "$target" ]; then
    [ "$QUIET" = 1 ] && return 0
    echo "afk: refusing to overwrite an existing non-AFK hook:" >&2
    echo "     $target" >&2
    echo "afk: inspect it and merge the delegation stub by hand, or remove it first." >&2
    rc=1
    return 0
  fi

  cat > "$target" <<HOOK
#!/usr/bin/env bash
# $marker (installed by the afk plugin's install-git-hooks.sh).
# Delegates to the plugin gate in the acting checkout; never breaks git.
top=\$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
gate="\$top/tools/payable/ai-agents/plugins/workflow/hooks/$script"
[ -f "\$gate" ] || exit 0
exec bash "\$gate" "\$@"
HOOK
  chmod +x "$target"
  say "afk: installed $desc -> $target"
}

install_hook reference-transaction afk-branch-name-gate branch-name-gate.sh "branch-name gate"
install_hook pre-commit           afk-precommit-gates  precommit-gates.sh  "pre-commit code gates"

if [ "$QUIET" != 1 ]; then
  say "afk: new branches must match kapteyn/development/<username>/<slug>."
  say "afk: checkouts of existing/remote branches are unaffected."
  say "afk: disable branch gate -> git config afk.branchNameGate false"
  say "afk: pre-commit runs maven-compile / java-format / ui-lint on STAGED files,"
  say "afk: for AGENT-driven commits only — your own commits are never gated."
  say "afk: skip once -> AFK_SKIP_PRECOMMIT_GATES=1 git commit …   (or --no-verify)"
fi
exit $rc
