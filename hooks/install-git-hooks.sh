#!/usr/bin/env bash
# Installer for the afk-toolkit git hooks:
#   reference-transaction -> branch-name-gate.sh  (agent-only branch naming)
#   pre-commit            -> precommit-gates.sh   (build-gate adapters)
#
# The pre-commit hook is where the expensive code gates live. They used to run on
# every turn end, which made interactive sessions pay a reactor build per
# question; at commit time the same enforcement costs once per commit.
#
# Runs automatically on every session start (wired in hooks.json / hooks.codex.json
# -> SessionStart), so enabling the plugin is the only opt-in a dev needs.
# Also runnable by hand (and by `/afk-toolkit:setup`, register H5) for non-session / CI:
#   bash "$AFK_PLUGIN_ROOT/hooks/install-git-hooks.sh"
#
# Behaviour:
#   - Opt-in per repository: installs ONLY where the repository root carries an
#     `.afk/` directory. The toolkit is installed globally on a harness, so a
#     repository that never opted in never receives a git hook.
#   - Root-aware: the installed stub carries the ABSOLUTE plugin root resolved at
#     install time, on an `# afk-plugin-root:` line. A session whose plugin root
#     differs (a version upgrade moves the install cache) rewrites the stub.
#   - Idempotent: same root, same stub -> silent no-op.
#   - Worktree-safe: installs into the shared (common) hooks dir — one install
#     covers every worktree of the checkout. Both hooks are AGENT-ONLY at run
#     time (they return immediately without an agent-runtime marker), so the
#     shared install never puts a gate in a human's commit or branch creation.
#   - Non-destructive: refuses to clobber a pre-existing, non-AFK hook.
#
# --quiet: suppress info output and never exit non-zero (used by SessionStart).
set -uo pipefail

QUIET=0
[ "${1:-}" = "--quiet" ] && QUIET=1
say() { [ "$QUIET" = 1 ] || echo "$@"; }

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
. "$SCRIPT_DIR/lib/provider.sh"

# The plugin root as an absolute path, resolved once at install time.
plugin_root=$(afk_plugin_root)
plugin_root=$(cd "$plugin_root" 2>/dev/null && pwd) || {
  say "afk: cannot resolve the plugin root — nothing to do."; exit 0; }

# Must be inside a git repo.
top=$(git rev-parse --show-toplevel 2>/dev/null) || { say "afk: not inside a git repo — nothing to do."; exit 0; }

# Opt-in marker: this repository asked for AFK.
if [ ! -d "$top/.afk" ]; then
  say "afk: $top has no .afk/ — repository has not opted in, skipping git hooks."
  exit 0
fi

# Absolute path to the resolved (common) hooks dir — correct from any subdir/worktree.
hooks_dir=$(git rev-parse --path-format=absolute --git-path hooks 2>/dev/null) \
  || hooks_dir=$(git rev-parse --git-path hooks)
mkdir -p "$hooks_dir"

rc=0

# install_hook <git-hook-name> <marker> <plugin-script> <description>
install_hook() {
  local hook=$1 marker=$2 script=$3 desc=$4
  local gate="$plugin_root/hooks/$script"
  if [ ! -f "$gate" ]; then
    say "afk: $desc missing from the plugin root ($plugin_root) — skipping."
    return 0
  fi

  local target="$hooks_dir/$hook"
  local root_line="# afk-plugin-root: $plugin_root"

  if [ -e "$target" ] && grep -q "$marker" "$target" 2>/dev/null; then
    # Ours already. Rewrite only when the recorded plugin root moved.
    if grep -qF "$root_line" "$target" 2>/dev/null; then
      say "afk: $desc already installed -> $target"
      return 0
    fi
    say "afk: $desc plugin root changed — reinstalling -> $target"
  elif [ -e "$target" ]; then
    # Present but not ours: never clobber. Say so even in --quiet mode — a silent
    # skip leaves a machine permanently ungated with zero signal anywhere.
    echo "afk: pre-existing non-AFK $hook hook — $desc NOT installed ($target)." >&2
    [ "$QUIET" = 1 ] && return 0
    echo "afk: inspect it and merge the delegation stub by hand, or remove it first." >&2
    rc=1
    return 0
  fi

  cat > "$target" <<HOOK
#!/usr/bin/env bash
# $marker (installed by afk-toolkit install-git-hooks.sh).
$root_line
# Delegates to the plugin gate at the recorded root; never breaks git.
gate="$plugin_root/hooks/$script"
[ -f "\$gate" ] || exit 0
exec bash "\$gate" "\$@"
HOOK
  chmod +x "$target"
  say "afk: installed $desc -> $target"
}

install_hook reference-transaction afk-branch-name-gate branch-name-gate.sh "branch-name gate"
install_hook pre-commit           afk-precommit-gates  precommit-gates.sh  "pre-commit code gates"

if [ "$QUIET" != 1 ]; then
  say "afk: new branches must match git.branch-pattern from .afk/config.yaml (empty = gate off)."
  say "afk: checkouts of existing/remote branches are unaffected."
  say "afk: disable branch gate -> git config afk.branchNameGate false"
  say "afk: pre-commit runs the configured build-gate adapters on STAGED files,"
  say "afk: for AGENT-driven commits only — your own commits are never gated."
  say "afk: skip once -> AFK_SKIP_PRECOMMIT_GATES=1 git commit …   (or --no-verify)"
fi
exit $rc
