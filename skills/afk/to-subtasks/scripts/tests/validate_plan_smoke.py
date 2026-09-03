#!/usr/bin/env python3
"""validate_plan_smoke.py — end-to-end smoke test for validate_plan.py.

Builds disposable fixture plans in a temp dir (never touches a real checkout):
  1. clean cited plan + full gate + VERIFICATION-PLAN.md      -> exit 0
  2. seeded-violation plan                                    -> exit 1, every expected rule id present
  3. plan dir without PLAN.md                                 -> exit 2
  4. clean uncited plan, minimal gate, no VERIFICATION-PLAN   -> exit 0
Exit 0 = all green (prints SMOKE_OK).
"""
import os
import shutil
import subprocess
import sys
import tempfile

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "validate_plan.py")
PASS = FAIL = 0


def ok(msg):
    global PASS
    print(f"  ok   - {msg}")
    PASS += 1


def bad(msg):
    global FAIL
    print(f"  FAIL - {msg}")
    FAIL += 1


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def run(plan_dir):
    p = subprocess.run([sys.executable, SCRIPT, plan_dir],
                       capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def subtask(goal, scope, verification, produces=None, consumes=None, blocked="(none)", review=None):
    parts = [f"## Goal\n{goal}\n", "## Complexity\nstandard\n"]
    if review:
        parts.append(f"## Review\n{review}\n")
    parts.append(f"## Scope\n{scope}\n")
    if produces:
        parts.append(f"## Produces\n{produces}\n")
    if consumes:
        parts.append(f"## Consumes\n{consumes}\n")
    parts.append("## Verification\n| Tier | Check (command or method) | Proves |\n"
                 "|------|---------------------------|--------|\n" + verification + "\n")
    parts.append(f"## Blocked by\n{blocked}\n")
    return "\n".join(parts)


STATIC = "| static | `compile` + grep anchors | builds |"
VP_FULL = """# Verification Plan — Fixture

## UI Journeys

| # | Journey (plain business language) | Actor | Traces to | Env-limited? | Requires target |
|---|-----------------------------------|-------|-----------|--------------|-----------------|
| 1 | journey one | clerk | PRD User Story 1 | no | any |
| 2 | journey two | clerk | PRD User Story 2 | no | any |

## API Scenarios

| # | Scenario (call → asserted contract) | Surface (method + path) | Traces to | Env-limited? |
|---|-------------------------------------|-------------------------|-----------|--------------|
| 1 | call → envelope | GET /api/x | SDD §3 row "x" | no |
"""


def gate_table(ui_rows, api_rows):
    rows = ""
    n = 0
    for i in range(ui_rows):
        n += 1
        rows += f"| {n} | journey {n} | ui-e2e | PRD User Story {n} | ui-e2e/features/f.feature ▸ \"s{n}\" | any | pending |\n"
    for i in range(api_rows):
        n += 1
        rows += f"| {n} | call {n} | api | SDD §3 row \"x\" | api/f.test.mjs ▸ \"t{n}\" | any | pending |\n"
    return ("## Feature smoke gate\n\n"
            "> Gate: /afk-toolkit:smoke-test\n> Last run: —\n\n"
            "| # | Scenario (integrated) | Modality | Traces to | Spec | Requires target | Status |\n"
            "|---|-----------------------|----------|-----------|------|-----------------|--------|\n"
            + rows)


def plan_md(gate_section, policy=""):
    return ("# Execution Plan — Fixture\n\n> Parent ticket: T-1   Mode: cited\n" + policy + "\n"
            "## Progress tracker\n\n| # | Subtask | Title | Status |\n|---|---|---|---|\n\n"
            + gate_section)


def build_clean(root):
    plan = os.path.join(root, "repo", "tasks", "T-1", "plan")
    os.makedirs(os.path.join(root, "repo", ".git"), exist_ok=True)
    write(os.path.join(root, "repo", "tasks", "T-1", "VERIFICATION-PLAN.md"), VP_FULL)
    write(os.path.join(plan, "PLAN.md"),
          plan_md(gate_table(2, 1), policy="> Review policy: lean   <!-- lean | full -->\n"))
    write(os.path.join(plan, "0001-core.md"), subtask(
        "Core service.", "- 11700-payable/payable/src/**",
        STATIC + "\n| unit | `mvn test` | behavior |",
        produces="- 11700-payable/src/Foo.java#FooServiceContractV1 — the service contract"))
    write(os.path.join(plan, "0002-consumer.md"), subtask(
        "Consumer.", "- 11700-payable/payable/src/**",
        STATIC,
        consumes="- 0001-core 11700-payable/src/Foo.java#FooServiceContractV1 — the contract",
        blocked="0001-core",
        review="policy: full\nopt-in: code-quality, resilience"))
    write(os.path.join(plan, "0003-smoke-e2e.md"), subtask(
        "UI smoke specs.", "- 11700-payable/verification/ui-e2e/features/*.feature",
        STATIC + "\n| e2e/browser | `npm run smoke` | scenarios green |",
        blocked="0001-core, 0002-consumer"))
    write(os.path.join(plan, "0004-smoke-api.md"), subtask(
        "API smoke specs.", "- 11700-payable/verification/api/*.test.mjs",
        STATIC + "\n| api | `node --test` | scenarios green |",
        blocked="0001-core, 0002-consumer"))
    write(os.path.join(plan, "0005-sync-harness.md"), subtask(
        "Harness sync.", "- 11700-payable/**/CLAUDE.md", STATIC,
        blocked="0001-core, 0002-consumer, 0003-smoke-e2e, 0004-smoke-api"))
    return plan


def build_dirty(root):
    plan = os.path.join(root, "repo", "tasks", "T-2", "plan")
    os.makedirs(os.path.join(root, "repo", ".git"), exist_ok=True)
    write(os.path.join(root, "repo", "tasks", "T-2", "VERIFICATION-PLAN.md"), VP_FULL)
    # gate has 1 ui-e2e row but the plan has 2 -> G-PARITY-UI; bogus policy -> H-POLICY
    write(os.path.join(plan, "PLAN.md"),
          plan_md(gate_table(1, 1), policy="> Review policy: strict\n"))
    # ambiguous anchor target: file exists, anchor greps twice
    write(os.path.join(root, "repo", "svc", "Dup.java"),
          "AmbiguousAnchorHere x\nAmbiguousAnchorHere y\n")
    # 0001: consumes forward from 0002 (A-FORWARD) + unknown producer; generic + short anchors;
    # materialized bullet with missing file; entities scope without integration row
    write(os.path.join(plan, "0001-alpha.md"), subtask(
        "Alpha.", "- 11700-payable/foo-entities/src/**",
        STATIC,
        produces=("- svc/A.java#class — bad anchor\n"
                  "- svc/B.java#shortA — bad anchor\n"
                  "- svc/Gone.java#MaterializedButMissingStub — stub [materialized]\n"
                  "- svc/Dup.java#AmbiguousAnchorHere — ambiguous"),
        consumes=("- 0002-beta svc/C.java#SomeLaterProducedThing — forward\n"
                  "- 0099-ghost svc/D.java#GhostProducedArtifact — orphan"),
        blocked="(none)",
        # H-POLICY-VALUE + H-OPT-IN-UNKNOWN (spec-fidelity is core, not deferrable) + H-REVIEW-LINE
        review="policy: bogus\nopt-in: spec-fidelity\nstray prose line"))
    # 0002: produces the thing 0001 forward-consumes, marked materialized while the
    # consumer line isn't (A-MAT-DISAGREE on 0003's consume below is cleaner; here
    # collision partner) ; ui scope without e2e row (E-TIER-E2E); no static row (E-STATIC)
    write(os.path.join(root, "repo", "svc", "C.java"), "SomeLaterProducedThing once\n")
    write(os.path.join(plan, "0002-beta.md"), subtask(
        "Beta.", "- 11700-payable/payable-ui/src/**",
        "| unit | `mvn test` | behavior |",
        produces="- svc/C.java#SomeLaterProducedThing — the thing [materialized]"))
    # 0003: collides with 0002 on the same file#anchor (A-COLLISION); consumes it
    # without the [materialized] marker (A-MAT-DISAGREE); consumes an anchor 0002
    # never produced (A-NOT-PRODUCED); controller scope without api row (E-TIER-API)
    write(os.path.join(plan, "0003-gamma.md"), subtask(
        "Gamma.", "- 11700-payable/src/controller/**",
        STATIC,
        produces="- svc/C.java#SomeLaterProducedThing — collides",
        consumes=("- 0002-beta svc/C.java#SomeLaterProducedThing — no marker\n"
                  "- 0002-beta svc/C.java#NeverDeclaredAnywhere — missing"),
        blocked="0002-beta"))
    # smoke-e2e present but Blocked-by misses 0002/0003 (G-BLOCKEDBY); no smoke-api
    # subtask while VP has real API scenarios (G-BUILD-MISSING)
    write(os.path.join(plan, "0004-smoke-e2e.md"), subtask(
        "UI smoke specs.", "- 11700-payable/verification/ui-e2e/features/*.feature",
        STATIC + "\n| e2e/browser | `npm run smoke` | green |",
        blocked="0001-alpha"))
    return plan


def build_minimal(root):
    plan = os.path.join(root, "repo2", "tasks", "T-3", "plan")
    os.makedirs(os.path.join(root, "repo2", ".git"), exist_ok=True)
    write(os.path.join(plan, "PLAN.md"), plan_md(
        "## Feature smoke gate (minimal)\n\n"
        "| # | Check | Command | Status |\n|---|-------|---------|--------|\n"
        "| 1 | compile | ./mvnw compile | |\n\nLast run: —\n"))
    write(os.path.join(plan, "0001-fix.md"), subtask(
        "Small fix.", "- 11700-payable/payable/src/**", STATIC))
    return plan


def main():
    tmp = tempfile.mkdtemp(prefix="vp-smoke-")
    try:
        # --- 1: clean cited plan ------------------------------------------
        rc, out = run(build_clean(tmp))
        (ok if rc == 0 else bad)(f"clean plan exits 0 (got {rc})" + ("" if rc == 0 else f"\n{out}"))
        (ok if "clean" in out else bad)("clean plan reports clean")

        # --- 2: dirty plan -------------------------------------------------
        rc, out = run(build_dirty(tmp))
        (ok if rc == 1 else bad)(f"dirty plan exits 1 (got {rc})")
        for rule in ["A-FORWARD", "A-UNKNOWN-PRODUCER", "A-NOT-PRODUCED", "A-COLLISION",
                     "A-MAT-DISAGREE", "B-GENERIC", "B-SHORT", "B-AMBIGUOUS",
                     "B-MAT-UNRESOLVED", "E-STATIC", "E-TIER-E2E", "E-TIER-API",
                     "E-TIER-INTEGRATION", "G-PARITY-UI", "G-BUILD-MISSING", "G-BLOCKEDBY",
                     "H-POLICY", "H-POLICY-VALUE", "H-OPT-IN-UNKNOWN", "H-REVIEW-LINE"]:
            (ok if rule + ":" in out else bad)(f"dirty plan flags {rule}")
        for absent in ["G-NO-GATE", "G-PHANTOM-BUILD", "G-FULL-WITHOUT-PLAN", "SYNTAX"]:
            (ok if absent + ":" not in out else bad)(f"dirty plan does not flag {absent}")

        # --- 3: parse error ------------------------------------------------
        empty = os.path.join(tmp, "empty-plan")
        os.makedirs(empty, exist_ok=True)
        rc, out = run(empty)
        (ok if rc == 2 else bad)(f"missing PLAN.md exits 2 (got {rc})")

        # --- 4: clean minimal-gate plan ------------------------------------
        rc, out = run(build_minimal(tmp))
        (ok if rc == 0 else bad)(f"minimal-gate plan exits 0 (got {rc})" + ("" if rc == 0 else f"\n{out}"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print(f"\nvalidate_plan smoke: {PASS} passed, {FAIL} failed")
    if FAIL:
        sys.exit(1)
    print("SMOKE_OK")


if __name__ == "__main__":
    main()
