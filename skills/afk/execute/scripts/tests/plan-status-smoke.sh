#!/bin/bash
#
# plan-status-smoke.sh — seam-test for plan-status.sh. Runs entirely in a
# disposable temp dir; asserts:
#   1. valid flip  — exit 0, target row's Status cell set, header `> Last
#                    updated:` stamped today, everything else byte-identical
#                    (other tracker rows, seam register, smoke-gate Status cells)
#   2. blocked(…)  — status with spaces/parens accepted
#   3. row miss    — exit 1, file untouched
#   4. table miss  — exit 2, file untouched
#   5. bad status  — exit 3, file untouched
#
# Self-contained. Exit 0 = all green.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PS="$SCRIPT_DIR/../plan-status.sh"

PASS=0
FAIL=0
ok()  { echo "  ok   - $1"; PASS=$((PASS + 1)); }
bad() { echo "  FAIL - $1"; FAIL=$((FAIL + 1)); }

if [[ ! -f "$PS" ]]; then
  echo "FAIL: plan-status.sh not found at $PS" >&2
  exit 1
fi

TMP_ROOT="$(mktemp -d 2>/dev/null || mktemp -d -t pss)"
trap 'rm -rf "$TMP_ROOT" 2>/dev/null || true' EXIT

PLAN_DIR="$TMP_ROOT/plan"
mkdir -p "$PLAN_DIR"
TODAY="$(date +%F)"

write_fixture() {
  cat > "$PLAN_DIR/PLAN.md" <<'EOF'
# Execution Plan — Fixture

> Parent ticket: TCK-1   Mode: cited
> Branch (for /afk:execute): dev/afk/tck-1
> Last updated: 2026-01-01 (status column maintained by /afk:execute)
> Feature: in-progress

## Seam register

| § | Seam (SDD §9b row) | Implemented by | Used by |
|---|--------------------|----------------|---------|
| 1 | "boundary" | 0002-beta | 0003-gamma |

## Progress tracker

| # | Subtask | Title | Status | Blocked by | Tiers | Seams |
|---|---------|-------|--------|------------|-------|-------|
| 1 | 0001-alpha | First | pending | — | static, unit | — |
| 2 | 0002-beta | Second | pending | — | static, unit | impl §1 |

Status values: `pending` → … or `blocked(<reason>)`.

## Feature smoke gate (minimal)

> Last run: — (maintained by /afk:smoke-test)

| # | Scenario (integrated) | Modality | Traces to | Spec | Status |
|---|-----------------------|----------|-----------|------|--------|
| 1 | app boots | ui-e2e | PRD | x.feature | pending |
EOF
}

run_ps() { bash "$PS" "$@"; }

# --- Test 1: valid flip ------------------------------------------------------
write_fixture
cp "$PLAN_DIR/PLAN.md" "$TMP_ROOT/before.md"
OUT1="$(run_ps "$PLAN_DIR" 0001-alpha designing 2>&1)"; RC1=$?
if [[ $RC1 -eq 0 ]]; then ok "valid flip exits 0"; else bad "valid flip exit ($RC1): $OUT1"; fi
if grep -q '^| 1 | 0001-alpha | First | designing | — | static, unit | — |$' "$PLAN_DIR/PLAN.md"; then ok "Status cell set, row otherwise intact"; else bad "row wrong: $(grep 0001-alpha "$PLAN_DIR/PLAN.md")"; fi
if grep -q "^> Last updated: $TODAY (status column maintained by /afk:execute)\$" "$PLAN_DIR/PLAN.md"; then ok "Last updated stamped today, tail preserved"; else bad "Last updated wrong: $(grep 'Last updated' "$PLAN_DIR/PLAN.md")"; fi
CHANGED="$(diff "$TMP_ROOT/before.md" "$PLAN_DIR/PLAN.md" | grep -c '^<')"
if [[ "$CHANGED" == 2 ]]; then ok "exactly 2 lines changed (row + date)"; else bad "changed-line count $CHANGED"; fi
if grep -q '^| 2 | 0002-beta | Second | pending |' "$PLAN_DIR/PLAN.md"; then ok "other tracker row untouched"; else bad "other tracker row disturbed"; fi
if grep -q '^| 1 | app boots | ui-e2e | PRD | x.feature | pending |$' "$PLAN_DIR/PLAN.md"; then ok "smoke-gate Status cell untouched"; else bad "smoke-gate table disturbed"; fi

# --- Test 2: blocked(<reason>) with spaces accepted --------------------------
OUT2="$(run_ps "$PLAN_DIR" 0002-beta 'blocked(contract_mismatch: 0001-alpha drifted)' 2>&1)"; RC2=$?
if [[ $RC2 -eq 0 ]]; then ok "blocked(<reason>) exits 0"; else bad "blocked(<reason>) exit ($RC2): $OUT2"; fi
if grep -q '^| 2 | 0002-beta | Second | blocked(contract_mismatch: 0001-alpha drifted) | — | static, unit | impl §1 |$' "$PLAN_DIR/PLAN.md"; then ok "blocked cell written verbatim"; else bad "blocked cell wrong: $(grep 0002-beta "$PLAN_DIR/PLAN.md" | head -n1)"; fi

# --- Test 3: row miss -> exit 1, file untouched ------------------------------
write_fixture
cp "$PLAN_DIR/PLAN.md" "$TMP_ROOT/before3.md"
run_ps "$PLAN_DIR" 0009-ghost designing >/dev/null 2>&1
[[ $? -eq 1 ]] && ok "row miss exits 1" || bad "row miss did not exit 1"
cmp -s "$TMP_ROOT/before3.md" "$PLAN_DIR/PLAN.md" && ok "file untouched on row miss" || bad "file changed on row miss"

# --- Test 4: table miss -> exit 2, file untouched ----------------------------
printf '# Plan without tracker\n\n> Last updated: 2026-01-01\n\nNo table here.\n' > "$PLAN_DIR/PLAN.md"
cp "$PLAN_DIR/PLAN.md" "$TMP_ROOT/before4.md"
run_ps "$PLAN_DIR" 0001-alpha designing >/dev/null 2>&1
[[ $? -eq 2 ]] && ok "table miss exits 2" || bad "table miss did not exit 2"
cmp -s "$TMP_ROOT/before4.md" "$PLAN_DIR/PLAN.md" && ok "file untouched on table miss" || bad "file changed on table miss"
run_ps "$TMP_ROOT/no-such-dir" 0001-alpha designing >/dev/null 2>&1
[[ $? -eq 2 ]] && ok "missing PLAN.md exits 2" || bad "missing PLAN.md did not exit 2"

# --- Test 5: bad status -> exit 3, file untouched ----------------------------
write_fixture
cp "$PLAN_DIR/PLAN.md" "$TMP_ROOT/before5.md"
run_ps "$PLAN_DIR" 0001-alpha flying >/dev/null 2>&1
[[ $? -eq 3 ]] && ok "bad status exits 3" || bad "bad status did not exit 3"
run_ps "$PLAN_DIR" 0001-alpha 'blocked()' >/dev/null 2>&1
[[ $? -eq 3 ]] && ok "empty blocked() reason exits 3" || bad "empty blocked() did not exit 3"
cmp -s "$TMP_ROOT/before5.md" "$PLAN_DIR/PLAN.md" && ok "file untouched on bad status" || bad "file changed on bad status"

# --- summary -----------------------------------------------------------------
echo ""
echo "plan-status smoke: $PASS passed, $FAIL failed"
[[ $FAIL -eq 0 ]] || exit 1
echo "SMOKE_OK"
