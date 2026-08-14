---
name: glossary
description: >
  Vocabulary-only steward of the multi-context domain glossary
  (GLOSSARY-MAP.md + per-service GLOSSARY.md) — distinct from the plugin-root
  workflow GLOSSARY.md. Use when the user invokes /afk:glossary, asks to
  define/audit/dedup/harden domain terms, or mentions "domain model"/"DDD"
  terminology hygiene. Writes only after approval; never grills requirements,
  emits ADRs, or touches the tracker.
---

> **Language:** read `LANGUAGE.md` (plugin root) first. It binds every reply, question, and artifact this skill produces — Simplified Technical English, glossary terms verbatim.

# glossary — domain-vocabulary steward

A **vocabulary-only steward**: tends terminology and nothing else. No requirements grilling, no
scope decisions, no PRD, no decision records. Reach for it when the *only* concern is words. Always **propose → approve →
write**; never write unasked.

## The glossary setup (shared, not redefined here)

Layout/format/rules canonical in [`GLOSSARY-FORMAT.md`](./GLOSSARY-FORMAT.md)
(this skill owns it) — follow exactly. Load only the glossaries the current
work touches.

## Two modes (auto-detect)

| Mode | Fires when | Does |
|---|---|---|
| **AUDIT** (default) | pointed at an existing glossary to fix/check/dedup/reconcile | scan glossary vs. conversation + code → diagnose → propose grouped fixes |
| **GRILL** | building or extending vocabulary mid-conversation | ask one vocabulary question at a time, recommend a canonical term, update the owning glossary inline as each resolves |

Detect from intent: "fix / audit / dedup / reconcile the glossary" → AUDIT; "define / build / sharpen these
terms" while terms still fluid → GRILL. When both apply, audit what exists first, then grill the gaps.

### AUDIT

1. Read `GLOSSARY-MAP.md` → locate target service `GLOSSARY.md`. Read it inline; delegate the
   code side of the scan to an `afk-reader` subagent that checks relevant code against the
   glossary's terms and returns cited drift findings, per `DELEGATION.md` (plugin root).
2. Diagnose vocabulary problems only:
   - **Ambiguity** — one word for several concepts.
   - **Synonyms** — several words for one concept (pick a canonical, list rest under `_Avoid_`).
   - **Vague / overloaded** terms needing a precise canonical replacement.
   - **Code drift** — glossary definition contradicts how code actually behaves; surface it
     ("glossary says cancellation = X, but code cancels Y — which is right?").
   - **Missing** — a domain term used in conversation/code with no entry, or a **stale** definition.
3. Propose fixes grouped per file, **cherry-pickable** — each change: diff + one-line *why*. For a
   moved/retired term, show `term → owner`.
4. On approval, write inline per the shared format; update the `GLOSSARY-MAP.md` row when a glossary is
   created or term ownership shifts.

### GRILL

Ask vocabulary questions **one at a time**, waiting for each answer; for every question give your
recommended answer. When a term resolves, update the owning glossary **right there** — don't batch.
If a question is answerable from code, read the code instead of asking. Challenge conflicts against
the existing glossary immediately; sharpen fuzzy language to a canonical term; stress-test boundaries
between related concepts with concrete scenarios.

Done when every term surfaced in the conversation has an owning glossary entry or an explicit park.

A resolved term that **corrects a misunderstanding a human had to clarify** is a `wrong-term` workflow lesson — record it per `skills/afk/lessons/CAPTURE.md` (`opened` then `applied` once the glossary write ships; `opened` alone otherwise).

## Boundaries (don't cross)

- **Glossary is glossary only** — devoid of implementation details. Not a spec, not a scratchpad,
  not a home for decisions. Skip generic programming concepts (timeout, array, endpoint) unless they carry
  domain-specific meaning.
- **Emit no decision records.** A requirement/solution decision that surfaces is for `/afk:to-prd` /
  `/afk:to-sdd` — note it in the conversation, don't record it here.
- **One owner per term** — per [`GLOSSARY-FORMAT.md`](./GLOSSARY-FORMAT.md) Rules.
- **Never write without approval.** Group changes; approval is **apply-all / by-file / by-term**.

## Safety

Discovery-safety rules (repo-root scoping, vendor/build/.git skips, CrowdStrike guard) per
[`claude-md/AUDIT.md`](../../afk/claude-md/AUDIT.md), Discovery section.

## Next

- Terminology sound but *requirements* need stress-testing → [`/afk:grill-requirements`](../../afk/grill-requirements/SKILL.md).
- Ready to synthesize settled requirements into a PRD → `/afk:to-prd`.

Glossary maintenance is **standalone** — does not require running the AFK chain.
