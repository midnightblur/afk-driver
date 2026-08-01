#!/usr/bin/env bash
# Commit-time gate runner (ships with the afk plugin): the code gates that are
# too expensive to run per conversational turn — maven-compile, java-format,
# ui-lint. Invoked by the `pre-commit` git hook that install-git-hooks.sh
# installs, and only for an AGENT-driven commit (see below); also runnable by hand:
#   bash tools/payable/ai-agents/plugins/workflow/hooks/precommit-gates.sh
#
# Wall-clock matters here in a way it does not on Stop: an agent commits through
# a tool call with its own timeout, and a hook that outlives it kills the commit.
# The maven lock wait is therefore bounded to AFK_MAVEN_LOCK_WAIT (default 240s
# on this path vs 900s for a manual run) rather than parking the commit for 15
# minutes behind a sibling worktree's reactor.
#
# Why here and not on Stop. These three cost 30s-3min each; a Stop hook fires on
# every turn end, so an interactive session paid a reactor build to answer a
# question. Enforcement is not weakened — nothing reaches a branch without
# passing them — it just moves to the boundary where the cost buys something.
#
# AGENT-ONLY, like every other gate in this suite. The hook is installed in the
# SHARED hooks dir, so it fires for every worktree AND the main checkout — but a
# human committing from their terminal or IDE must never wait on a reactor build
# for code they are about to review anyway. Agent runtimes mark the environment
# of every process they spawn (afk_agent_session, hooks/lib/provider.sh); a human
# commit has no marker and returns here immediately.
#
# Scope is the STAGED change set (gate_ctx_build_staged): this repo stages
# explicit paths rather than everything, so judging the working tree would gate
# files the commit does not contain.
#
# Exit 2 blocks the commit. Escape hatches: .claude/hooks/.gate-disabled in the
# repo, AFK_SKIP_PRECOMMIT_GATES=1 for a single commit, or `git commit --no-verify`.

set -u

[ "${AFK_SKIP_PRECOMMIT_GATES:-0}" = "1" ] && exit 0

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

. "$SCRIPT_DIR/lib/provider.sh"
afk_agent_session || exit 0

repo_root=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
cd "$repo_root" || exit 0
[ -f .claude/hooks/.gate-disabled ] && exit 0

. "$SCRIPT_DIR/gate-context.sh"
. "$SCRIPT_DIR/gate-cache.sh"
. "$SCRIPT_DIR/gate-metrics.sh"

gate_ctx_build_staged
[ -z "$AFK_CTX_CHANGED" ] && exit 0

# Bound the maven-lock wait on the commit path (see header).
export AFK_MAVEN_LOCK_WAIT="${AFK_MAVEN_LOCK_WAIT:-240}"

blocked=0
run_gate() {  # $1 = gate name (file <name>-gate.sh, function gate_<name>)
  local name=$1 fn="gate_${1//-/_}" rc=0
  . "$SCRIPT_DIR/$name-gate.sh" || return 0
  "$fn"; rc=$?
  [ "$rc" = "2" ] && blocked=1
  return 0
}

# Scope tests are fork-free; a commit with no .java / no UI files enters neither.
if gate_ctx_any AFK_CTX_LIVE '*.java'; then
  run_gate java-format
  run_gate maven-compile
fi
gate_ctx_any AFK_CTX_LIVE '*.js' '*.cjs' '*.mjs' '*.ts' '*.vue' && run_gate ui-lint

if [ "$blocked" = "1" ]; then
  printf '\n[afk] Commit blocked by a code gate. Fix the findings above, or commit with\n' >&2
  printf '      --no-verify (or AFK_SKIP_PRECOMMIT_GATES=1) if you are deliberately\n' >&2
  printf '      landing a known-red intermediate commit.\n' >&2
  exit 2
fi
exit 0
