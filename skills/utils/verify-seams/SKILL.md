---
name: verify-seams
description: Independent orphan hunt over a change — verify everything produced is actually consumed. Use before declaring a multi-artifact task done, before pushing/shipping (`final` mode), or when asked whether a change is fully wired.
user-invocable: false
---

> **Language:** read `LANGUAGE.md` (plugin root) first. It binds every reply, question, and artifact this skill produces — Simplified Technical English, glossary terms verbatim.

Catch the producer-without-consumer failure: work that is locally correct but dead at the seam — a file nothing reads, an endpoint nothing calls, an event nothing subscribes to, a config key nothing loads, a DTO field never mapped. Compilers and unit tests are blind to it; this skill isn't.

The mechanical zero-referrer tier already ran (`hooks/wiring-gate.sh` at this plugin's root — three levels up from this skill's directory — fires on every Stop). This skill is the judgment tier: referrers that exist but aren't real consumption.

## Steps

1. **Scope the change.** `git status --porcelain -uall` plus `git diff --name-only @{u}...HEAD` (fall back to `origin/master...HEAD`). This file list — not the conversation — defines what gets audited.

2. **Spawn the verifier blind.** One fresh-context subagent (`afk-reader`). Give it: the change goal (one sentence), the file list, the repo path. Do **not** give it your own account of what you wired — the author's narrative is what it exists to distrust. Its brief, verbatim:

   > For each artifact this change adds or reshapes (files, endpoints, events, config keys, public methods, emitted files/logs), find its consumer and classify:
   > - **wired** — a consumer exists AND lies on a path that actually executes (cite file:line of the consuming site);
   > - **weak** — only referenced by its own tests, dead code, docs, or a consumer that never runs;
   > - **orphan** — no consumer found.
   > Default to orphan when you cannot prove reachability. Return a table: artifact | verdict | evidence (cited) — nothing else.

3. **Resolve every non-wired row.** For each `weak`/`orphan`: wire a real consumer now, or add an IOU to the repo's `.claude/wiring-ious.md` anchored to a plan step, ticket, or contract naming *your* symbol the future consumer will call (never a guessed future filename — implementers choose their own names). An anchor-less "used later" is not a resolution.

4. **Final mode only** (`verify-seams final` — run before push/ship):
   - Run `WIRING_FINAL=1 bash <plugin-root>/hooks/wiring-gate.sh` — open IOUs now block.
   - Hand still-open IOUs to the step-2 subagent with one extra question: "Is this anchor real (the step/ticket exists and still plans to consume it), or a hand-wave?" Hand-waves get wired or waived-with-reason before shipping — never carried across the ship line.

Done when: every artifact in the verifier's table is `wired`, or `pending` behind an anchored IOU (non-final), and in final mode the IOU list is empty or all-waived-with-reason.
