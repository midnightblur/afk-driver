#!/bin/bash
#
# verify-contract-smoke.sh — seam-test for verify-contract.sh. Runs entirely in
# a disposable temp dir; asserts:
#   1. produces all-pass — exit 0, one pass line per bullet, [materialized] reported
#   2. consumes all-pass — exit 0, producer ids in the pass lines
#   3. anchor miss      — exit 1, FAIL line names bullet + producer id
#   4. file miss        — exit 1, FAIL line says file missing
#   5. usage errors     — missing/bad --direction exit 2
#   6. no ## Consumes   — exit 0, "nothing to verify"
#   7. no ## Produces   — exit 2 (mandatory section)
#   8. unparseable bullet (no '#') — exit 2
#
# Self-contained: no network, no maven. Exit 0 = all green.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VC="$SCRIPT_DIR/../verify-contract.sh"

PASS=0
FAIL=0
ok()  { echo "  ok   - $1"; PASS=$((PASS + 1)); }
bad() { echo "  FAIL - $1"; FAIL=$((FAIL + 1)); }

if [[ ! -f "$VC" ]]; then
  echo "FAIL: verify-contract.sh not found at $VC" >&2
  exit 1
fi

TMP_ROOT="$(mktemp -d 2>/dev/null || mktemp -d -t vcs)"
trap 'rm -rf "$TMP_ROOT" 2>/dev/null || true' EXIT

ROOT="$TMP_ROOT/worktree"
mkdir -p "$ROOT/src"
printf 'class Foo { void registerExporter() {} }\n' > "$ROOT/src/Foo.java"
printf 'class Bar { void exportSchema() {} }\n'     > "$ROOT/src/Bar.java"
printf 'class Base { static String baseAnchor; }\n' > "$ROOT/src/Base.java"
printf 'interface Seam { void seamMethod(); }\n'    > "$ROOT/src/Seam.java"

CONTRACT="$TMP_ROOT/0003-consumer.md"
cat > "$CONTRACT" <<'EOF'
# 0003-consumer

## Goal
Fixture.

## Produces
- src/Foo.java#registerExporter — exposes the registry hook
- src/Bar.java#exportSchema — schema surface [materialized]

## Consumes
- 0001-base src/Base.java#baseAnchor — base symbol
- 0002-seam src/Seam.java#seamMethod — seam contract [materialized]

## Blocked by
(none)
EOF

run_vc() { bash "$VC" "$@"; }

# --- Test 1: produces all-pass ----------------------------------------------
OUT1="$(run_vc "$CONTRACT" --direction produces --root "$ROOT" 2>&1)"; RC1=$?
if [[ $RC1 -eq 0 ]]; then ok "produces all-pass exits 0"; else bad "produces all-pass exit ($RC1): $OUT1"; fi
if [[ "$(printf '%s\n' "$OUT1" | grep -c '^pass - ')" == 2 ]]; then ok "one pass line per produces bullet"; else bad "pass-line count wrong: $OUT1"; fi
if printf '%s' "$OUT1" | grep -q 'exportSchema \[materialized\]'; then ok "[materialized] tag reported on its bullet"; else bad "[materialized] tag not reported: $OUT1"; fi
if printf '%s' "$OUT1" | grep -q 'compile check'; then ok "summary demands the compile check for [materialized]"; else bad "no compile-check summary line: $OUT1"; fi

# --- Test 2: consumes all-pass ----------------------------------------------
OUT2="$(run_vc "$CONTRACT" --direction consumes --root "$ROOT" 2>&1)"; RC2=$?
if [[ $RC2 -eq 0 ]]; then ok "consumes all-pass exits 0"; else bad "consumes all-pass exit ($RC2): $OUT2"; fi
if printf '%s' "$OUT2" | grep -q '^pass - \[0001-base\] src/Base.java#baseAnchor'; then ok "producer id in pass line"; else bad "producer id missing: $OUT2"; fi

# --- Test 3: anchor miss -> exit 1, names bullet + producer id ---------------
printf 'class Base { }\n' > "$ROOT/src/Base.java"
OUT3="$(run_vc "$CONTRACT" --direction consumes --root "$ROOT" 2>&1)"; RC3=$?
if [[ $RC3 -eq 1 ]]; then ok "anchor miss exits 1"; else bad "anchor miss exit ($RC3)"; fi
if printf '%s' "$OUT3" | grep -q '^FAIL - \[0001-base\] src/Base.java#baseAnchor.*anchor not found'; then ok "FAIL line names bullet + producer id"; else bad "FAIL line wrong: $OUT3"; fi
printf 'class Base { static String baseAnchor; }\n' > "$ROOT/src/Base.java"

# --- Test 4: file miss -> exit 1 ---------------------------------------------
rm "$ROOT/src/Seam.java"
OUT4="$(run_vc "$CONTRACT" --direction consumes --root "$ROOT" 2>&1)"; RC4=$?
if [[ $RC4 -eq 1 ]]; then ok "file miss exits 1"; else bad "file miss exit ($RC4)"; fi
if printf '%s' "$OUT4" | grep -q '^FAIL - \[0002-seam\] src/Seam.java#seamMethod.*file missing'; then ok "FAIL line says file missing"; else bad "file-missing line wrong: $OUT4"; fi
printf 'interface Seam { void seamMethod(); }\n' > "$ROOT/src/Seam.java"

# --- Test 5: usage errors ----------------------------------------------------
run_vc "$CONTRACT" --root "$ROOT" >/dev/null 2>&1
[[ $? -eq 2 ]] && ok "missing --direction exits 2" || bad "missing --direction did not exit 2"
run_vc "$CONTRACT" --direction sideways --root "$ROOT" >/dev/null 2>&1
[[ $? -eq 2 ]] && ok "bad direction exits 2" || bad "bad direction did not exit 2"
run_vc "$TMP_ROOT/absent.md" --direction produces >/dev/null 2>&1
[[ $? -eq 2 ]] && ok "missing contract file exits 2" || bad "missing contract file did not exit 2"

# --- Test 6: no ## Consumes section -> exit 0, nothing to verify -------------
LEAF="$TMP_ROOT/0001-leaf.md"
printf '# 0001-leaf\n\n## Produces\n- src/Foo.java#registerExporter — hook\n' > "$LEAF"
OUT6="$(run_vc "$LEAF" --direction consumes --root "$ROOT" 2>&1)"; RC6=$?
if [[ $RC6 -eq 0 ]] && printf '%s' "$OUT6" | grep -q 'nothing to verify'; then ok "absent ## Consumes exits 0 with note"; else bad "absent ## Consumes wrong ($RC6): $OUT6"; fi

# --- Test 7: no ## Produces section -> exit 2 --------------------------------
BARE="$TMP_ROOT/0002-bare.md"
printf '# 0002-bare\n\n## Goal\nFixture.\n' > "$BARE"
run_vc "$BARE" --direction produces --root "$ROOT" >/dev/null 2>&1
[[ $? -eq 2 ]] && ok "absent ## Produces exits 2" || bad "absent ## Produces did not exit 2"

# --- Test 8: unparseable bullet (no '#') -> exit 2 ---------------------------
BROKEN="$TMP_ROOT/0004-broken.md"
printf '# 0004-broken\n\n## Produces\n- src/Foo.java no anchor here — oops\n' > "$BROKEN"
run_vc "$BROKEN" --direction produces --root "$ROOT" >/dev/null 2>&1
[[ $? -eq 2 ]] && ok "unparseable bullet exits 2" || bad "unparseable bullet did not exit 2"

# --- summary -----------------------------------------------------------------
echo ""
echo "verify-contract smoke: $PASS passed, $FAIL failed"
[[ $FAIL -eq 0 ]] || exit 1
echo "SMOKE_OK"
