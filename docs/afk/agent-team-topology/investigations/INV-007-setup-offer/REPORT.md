C:\Users\mvu\PersonalProjects\afk-driver-agent-teams@7e9c87a · closed-with-frontier · boundaries 13/14 · unverified 1 (load-bearing 0) · ledger: docs/afk/agent-team-topology/investigations/INV-007-setup-offer/COVERAGE.json

Published partial and acknowledged by the human (R-31, ACK-1); rebuilt after, now closed with frontier.

## Answer

A new optional multiplexer row in the dependency register joins the setup election on every run, deselected by default, with no code change, provided it is an `[opt-in]` row carrying no "(only when" gate and sits outside sections O and X. No uninstall path exists today; the settled design (S-98) puts the one-line uninstall command in the row's install note. Paths are under skills/afk/setup/ unless given. Every site is unguarded: no test reaches any register reader.

## Sites that change or break

- SKILL.md:76-83 (step 3) — unchanged. The election is built from the register at run time.
- SKILL.md:85-86 (step 4) — breaks ENV4 in a run with no human: a global install is confirmed only in an interactive session. Settled by S-108: with no human present, the multiplexer is skipped.
- hooks/native-contract-gate.sh:119 (rule A) — breaks if the row names a harness ("Claude Code", "Codex"); hooks/native-contract-allow.txt:25 matches only the O5 heading. Found by the blind counter-search.
- AUDIT.md:38 (audit check 2) — breaks if the row lands before any skill or script invokes the multiplexer; the check reports an unreferenced entry. Agent-judged.
- hooks/skill-registry-gate.sh:175 (check C) — unchanged; a hook reading a new environment variable needs that name in the register.
- hooks/lib/adapter_registry_check.py:113-114 (check E) — unchanged; checks headings only for row ids an adapter manifest names.
- scripts/install_block.py:27-29 — no remove mode; no row, field or script gives a one-command undo today.
- docs/afk/agent-team-topology/GRILL-LOG.md:191, :270 and grill-solution.round.json:1221 (card S-47) — break: an added effect voids the signed seven-effect HL-5 packet (skills/afk/grill-solution/HUMAN-SIGNOFF.md:57-60).

## For the design

- FRESHNESS.md:13-15: the row lands in the same commit as the first skill or script that invokes the multiplexer.
- No conflict with the opt-in boundary (CLAUDE.md:23) or the distribution law (PROVIDERS.md:39-40), inferred: setup runs only where the plugin is enabled, and the install runs only after the human accepts.
- PRD.md carries ENV1 as AC-028 but drops ENV4's undo clause (claim c-1b9e99ea); routed to the requirements skill (S-109).
- GRILL-LOG.md:239 (L9-5) contradicts ENV1 (claim c-cd7c9b27).

## Frontier

B14: installed plugin copies and machines where the multiplexer is already installed.

## Unverified

- c-e00426cf: the hit set holds every reference over the name forms searched. Not load-bearing.

## Run notes

- c-20f9dd63 is now a fact: skills/afk/setup/SKILL.md:68-83 (step 3) has no rule for a run with no human; the only interactivity rule is step 4 (:85-86). S-108 designs the answer.
- c-caf822be was partly false and is replaced by c-4537cc84: hooks/tests/hook-smoke.sh covers provider detection, envelopes, the hook launcher, native twins, the genericity gate and lavish navigation; no test pins check C, check E, adapter_registry_check.py, the native-contract prose rules or install_block.py.
- Staging nodes GRILL-LOG.md:279 and :286 carry stale line hashes from working-tree edits; :286 (the HL-5 re-sign decision) is relevant but marked irrelevant.
- Run shape: the first counter-search (P5) was not blind and is left out with its dependent delta (P6); the blind rerun (P7, re-emitted as P7b) and a new delta (P8) replace them. P2 is re-emitted as P2b. The previous ledger is kept in scratch as COVERAGE-r31.json.
