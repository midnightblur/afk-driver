C:\Users\mvu\PersonalProjects\afk-driver-worktrees\afkv2@22ab4de0ff03d9b3b79425494df03938b56d0899 · closed-with-frontier · boundaries 12/14 · unverified 1 (load-bearing 0) · ledger: C:/Users/mvu/AppData/Local/Temp/claude/C--Users-mvu-PersonalProjects-afk-driver/23e372bc-cde6-4631-9ea7-43a4a91d8684/scratchpad/investigations/INV-20261029T1630-lavish-round-document/COVERAGE.json

## Answer
- Validator: `scripts/lavish/schema.py:476` `load()`; `schema` must == 1 (:480); document keys closed (:86); exactly one `current` round (:494); round/item/current-header/group keys closed (:504, :260, :458, :317).
- Components (:22): round_header (header only), decided_card (6-field contract, degrades to confirm_row :182, hard exit on empty decision :184), debate_card, confirm_row, signoff_packet, settled_card. state settled <=> settled_card (:244). Ids unique across artifact incl. `R-n` (:515).
- Render: `scripts/lavish_render.py:116` load -> page.build -> validate_input_page; exit 0/1/2. Inject (tooltips) runs at show time, `scripts/lavish_show.py:278`.
- Response: emitted only by `scripts/lavish/assets/runtime.js:137` compose(); no parser in the repo (agent folds by prose, `skills/afk/grill-requirements/ROUND.md:321`).
- Drafts: key `afk-answers:`+pathname in window.name envelope and localStorage (`runtime.js:27`, :41, :61); frame copy wins whenever present (:75).
- Drift: 17 doc-vs-code items (facts-t2.md §3); key ones: nested objects not closed, settled headers unchecked, R-3 "tie" vs always-wins, `page —` and `[btw]` lines not page-emitted, ROUND.md fallback parser absent, send warns-then-sends vs ROUND.md:152 "refuses".

## Sites
scripts/lavish/schema.py · scripts/lavish_render.py · scripts/lavish/page.py · scripts/lavish/components.py · scripts/lavish/assets/runtime.js · scripts/lavish/inject.py · scripts/lavish_show.py · LAVISH-KIT.md · LAVISH.md · skills/afk/grill-requirements/ROUND.md · scripts/tests/test_lavish_render.py · scripts/tests/samples/lavish-round.json

## Frontier
- B6: round HTML is a per-session build product; none tracked.
- B14: lavish-axi host (window.lavish bridge, poll output framing), browser storage semantics.

## Unverified
- Poll output framing of the queued text (host outside repo).
- Served page vs file-opened page keep separate drafts (inferred from pathname).
- Test suite not run at head.
