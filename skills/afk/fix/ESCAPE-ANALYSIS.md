# Phase 2.5 — Escape analysis (why did the existing tests miss it?)

A bug that reached the verification phase means a guard that *should* have stopped
it didn't — or was never there. Phase 2 added the missing guard; this step
interrogates the **existing** one that whiffed — a sibling next to a weak assertion
just grows the suite without closing the hole.

Run only for **standing-suite tier** bugs — a user-visible flow (`e2e/browser`)
or a backend contract (`api`). Skip a pure unit/logic bug that never had a
higher-tier scenario (Phase 2 already homed it).

1. **Find the scenario that *should* have caught it.** Grep the catalogs for the
   flow/endpoint the bug lives on — `11700-payable/verification/ui-e2e`
   (`*.feature` + steps) for a user-visible flow, `11700-payable/verification/api`
   (`*.test.mjs`) for a contract. Either a scenario exercises this path, or you
   confirm none does.

2. **Name the miss class** (exactly one):

   | Miss class | What it means | Right response |
   |-----------|---------------|----------------|
   | `no-scenario` | No existing test exercised this path at all | Keep the Phase 2 sibling — it's the right add. This is a **gate gap** → Phase 3 + 3.5 |
   | `weak-assertion` | A scenario walks the path but asserts too little (happy-path only, missing field/negative/edge) | **Strengthen that scenario** — don't add a sibling that repeats the weak check |
   | `wrong-path` | A scenario exercises a *near* path, not the one that broke (wrong fixture, wrong branch, mocked-away seam) | Fix the fixture/branch so the real path is covered |
   | `excluded` | A scenario exists but is `@sap`/env-tagged out of the green gate, so it never ran | Note for Phase 3.5 — the gate's exclusion let a real regression through |
   | `disabled/flaky` | Skipped, quarantined, or silently green on a swallowed error | Re-enable + de-flake; a skipped guard is no guard |

3. **Act on the class — and revise Phase 2 if needed.** For `weak-assertion` /
   `wrong-path` / `disabled`, prefer **fixing the existing scenario in place** over
   the new Phase 2 sibling (a redundant sibling asserting the same weak thing is
   gold-plating — drop it). Re-run that scenario **red-then-green** to prove it now
   catches this exact bug.

4. **Record the miss class.** The lesson — names which guard failed and,
   in Phase 3.5, which AFK stage under-specified it. Carry into Phase 4's report.
