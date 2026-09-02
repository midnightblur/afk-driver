#!/usr/bin/env bash
# Stop hook (ships with the afk plugin): the single entry point for the plugin's
# Stop-time gates. Replaces one hooks.json entry per gate.
#
# Why one process. Gate cost on Windows/git-bash is subprocess COUNT (MSYS fork
# emulation ~0.5-2s per spawn vs ~20-40ms native), so N hook entries meant N bash
# startups plus N independent re-derivations of the same change set. This builds
# the change set once (gate-context.sh) and runs each gate as a sourced function
# in this one process.
#
# Two dispatch rules keep an interactive turn near zero cost:
#   1. Stop-level short-circuit — if the tree digest is identical to the last
#      Stop that passed everything, no gate runs at all. A turn that only talked
#      (the common case while grilling) costs the context build and nothing else.
#   2. Scope-driven dispatch — a gate is only entered when the change set holds
#      a path it could possibly gate. Scope tests are fork-free list matches, so
#      "no .java changed" costs a string compare, not a bash startup + git call.
#
# Heavy code gates (maven-compile, java-format, ui-lint) are NOT here: they run
# at commit/push time via precommit-gates.sh (installed by install-git-hooks.sh),
# where the cost is paid once per commit instead of once per turn.
#
# A block is emitted once, at the end, through the provider shim: the findings
# go to stderr AND to a stdout decision object, and the adapter picks the exit
# code its harness reads a block from. Every gate is run first (a block in one
# does not hide findings in another). Escape hatch, per-gate disable vars,
# and the pass cache are unchanged — see hooks/README.md.
# Disable the whole set: .claude/hooks/.gate-disabled in the gated repo.

set -u

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

repo_root=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
cd "$repo_root" || exit 0
[ -f .claude/hooks/.gate-disabled ] && exit 0

. "$SCRIPT_DIR/lib/provider.sh"
. "$SCRIPT_DIR/gate-context.sh"
. "$SCRIPT_DIR/gate-cache.sh"
. "$SCRIPT_DIR/gate-metrics.sh"

gate_metrics_begin
gate_ctx_build
# Fork-free line count of the change set (metrics detail only).
n_changed=0
while IFS= read -r _l; do [ -n "$_l" ] && n_changed=$((n_changed + 1)); done <<<"$AFK_CTX_CHANGED"
gate_metrics_emit context pass "\"changed\":$n_changed"

# ---- rule 1: nothing changed since the last all-green Stop -> no gate runs.
# Only a PASS verdict may short-circuit: an unchanged tree that BLOCKED last time
# must block again, or the agent could finish simply by trying twice.
STOP_STAMP=".claude/hooks/.gate-cache/.last-stop"
if [ "${GATE_CACHE_DISABLE:-0}" != "1" ] && [ -f "$STOP_STAMP" ]; then
  if [ "$(<"$STOP_STAMP")" = "pass:$AFK_CTX_TREE" ]; then
    exit 0
  fi
fi

PLUGIN_DIR="tools/payable/ai-agents/plugins/workflow"

# ---- rule 2: scope-driven dispatch. Each entry is "<gate>:<scope-test>", where
# the scope test is fork-free and answers "could this gate have anything to say?"
blocked=0
crashed=0

# Gate findings are the block reason, and a reason has to be a value, not a
# stream: collect stderr here and replay it once the verdict is known.
GATE_ERR=$(mktemp "${TMPDIR:-/tmp}/afk-stop.XXXXXX") || GATE_ERR=
if [ -n "$GATE_ERR" ]; then
  exec 3>&2 2>"$GATE_ERR"
fi

release_stderr() {
  [ -n "$GATE_ERR" ] || return 0
  exec 2>&3 3>&-
}

run_gate() {  # $1 = gate name (file <name>-gate.sh, function gate_<name>)
  local name=$1 fn="gate_${1//-/_}" rc=0
  # A gate that cannot load or exits with anything but 0/2 has an UNKNOWN
  # verdict. It must not block (old per-hook semantics: only exit 2 blocks) but
  # it must not be silent either, and this Stop must not stamp all-green.
  if ! . "$SCRIPT_DIR/$name-gate.sh"; then
    printf '[afk] %s-gate.sh failed to load — gate skipped, verdict unknown.\n' "$name" >&2
    crashed=1
    return 0
  fi
  "$fn"; rc=$?
  case "$rc" in
    0) ;;
    2) blocked=1 ;;
    *) printf '[afk] gate %s crashed (rc %s) — verdict unknown.\n' "$name" "$rc" >&2
       crashed=1 ;;
  esac
  return 0
}

# wiring — no scope test. Its candidate set is working-tree adds PLUS every file
# the branch's commits added, and the shared context only knows the former, so
# gating on AFK_CTX_NEW would skip a branch whose new files are all committed.
# The gate self-exits on an empty candidate set (one git diff).
run_gate wiring

# The three gates below judge the branch's whole change, not just its worktree
# (a registry vs disk, the generated Codex layer vs its sources, added prose vs
# the integration base) — so each scope test spans the working-tree list AND the
# committed list. Testing only the former would silently stop gating a change the
# moment it was committed, which is when it matters most.
gate_ctx_branch

# ctx_scoped <pattern>... — true if the working tree OR this branch's commits
# touched a matching path.
ctx_scoped() {
  gate_ctx_any AFK_CTX_CHANGED "$@" || gate_ctx_any AFK_CTX_BRANCH "$@"
}

# skill-registry — only when something under the plugin moved. Registries cannot
# drift from disk if nothing on disk moved.
ctx_scoped "$PLUGIN_DIR/*" && run_gate skill-registry

# native-contract — plugin prose, both native manifests, provider adapters and
# local activation paths form one contract. A change to any member can make the
# otherwise-shared plugin surface harness-specific.
ctx_scoped "$PLUGIN_DIR/*" ".agents/*" ".codex/*" && run_gate native-contract

# genericity — only when plugin prose moved.
ctx_scoped "$PLUGIN_DIR/*.md" && run_gate genericity

# Stamp writes are write-to-temp + rename: a concurrent session's Stop reading
# the stamp mid-truncate would otherwise see a torn value (worst case an empty
# "pass:" matching an empty digest).
write_stamp() {
  printf '%s\n' "$1" > "$STOP_STAMP.$$" 2>/dev/null \
    && mv -f "$STOP_STAMP.$$" "$STOP_STAMP" 2>/dev/null
  rm -f "$STOP_STAMP.$$" 2>/dev/null
}

release_stderr

if [ "$blocked" = "1" ]; then
  write_stamp "blocked:$AFK_CTX_TREE"
  reason=$(cat "$GATE_ERR" 2>/dev/null)
  rm -f "$GATE_ERR" 2>/dev/null
  afk_block_stop "$reason"
fi

# Not blocking: a crashed gate or an advisory line still has to be seen.
if [ -n "$GATE_ERR" ]; then
  cat "$GATE_ERR" >&2 2>/dev/null
  rm -f "$GATE_ERR" 2>/dev/null
fi

# A crashed gate means this Stop verified less than the full suite — leave the
# old stamp in place so the next Stop re-runs everything.
[ "$crashed" = "1" ] && exit 0

write_stamp "pass:$AFK_CTX_TREE"
exit 0
