---
name: glossary
description: >
  Maintain and fix the repo's multi-context domain glossary — a
  vocabulary-only steward. Audits an existing
  GLOSSARY.md for ambiguity, synonyms, vague/overloaded terms, and drift
  from the code; or grills new terminology one question at a time when
  building vocabulary in conversation. Writes to the GLOSSARY-MAP.md +
  per-service GLOSSARY.md setup after approval. Use when user invokes
  `/afk:glossary`, asks to define/fix/audit/dedup domain terms, harden
  terminology, build a glossary, sharpen the ubiquitous language, or
  mentions "domain model" / "DDD" terminology hygiene. Does NOT grill
  requirements, emit ADRs, or touch the tracker.
---

# glossary — domain-vocabulary steward

A **vocabulary-only steward**: it tends terminology and nothing else. No requirements grilling, no
scope decisions, no PRD, no decision records. Reach for it when the *only* concern is the words. Always **propose → approve →
write**; never write unasked.

## The glossary setup (shared, not redefined here)

This repo uses a **multi-context glossary**: a root `GLOSSARY-MAP.md` indexes one `GLOSSARY.md` per
service (one level below root, never nested deeper); an optional root `GLOSSARY.md` holds system-wide
terms. **Read `GLOSSARY-MAP.md` first** — it routes you to the right service glossary; load only the
glossaries the current work touches.

Format, rules, and the full multi-context layout are **canonical** in
[`GLOSSARY-FORMAT.md`](./GLOSSARY-FORMAT.md) — this skill owns it. Follow it exactly; do **not** restate
its rules.

**Routing:** route by the **known target service** (ticket / spec path), not by guessing from the topic.
Infer or ask only when the target is ambiguous or the work spans services. Create lazily what's missing —
a new `{service}/GLOSSARY.md` gets its `GLOSSARY-MAP.md` row **in the same move** (an unlisted glossary
is invisible to the next session); a genuinely system-wide term goes in the root `GLOSSARY.md` with a
Relationships note in the map.

## Two modes (auto-detect)

| Mode | Fires when | Does |
|---|---|---|
| **AUDIT** (default) | pointed at an existing glossary to fix/check/dedup/reconcile | scan glossary vs. conversation + code → diagnose → propose grouped fixes |
| **GRILL** | building or extending vocabulary mid-conversation | ask one vocabulary question at a time, recommend a canonical term, update the owning glossary inline as each resolves |

Detect from intent: "fix / audit / dedup / reconcile the glossary" → AUDIT; "define / build / sharpen these
terms" while terms are still fluid → GRILL. When both apply, audit what exists first, then grill the gaps.

### AUDIT

1. Read `GLOSSARY-MAP.md` → locate the target service `GLOSSARY.md`. Read it inline; delegate the
   code side of the scan to an `afk-reader` subagent that checks the relevant code against the
   glossary's terms and returns cited drift findings, per `DELEGATION.md` (plugin root).
2. Diagnose vocabulary problems only:
   - **Ambiguity** — one word used for several concepts.
   - **Synonyms** — several words for one concept (pick a canonical, list the rest under `_Avoid_`).
   - **Vague / overloaded** terms that need a precise canonical replacement.
   - **Code drift** — glossary definition contradicts how the code actually behaves; surface it
     ("glossary says cancellation = X, but the code cancels Y — which is right?").
   - **Missing** — a domain term used in the conversation/code with no entry, or a **stale** definition.
3. Propose fixes grouped per file, **cherry-pickable** — each change: the diff + a one-line *why*. For a
   moved/retired term, show `term → owner`.
4. On approval, write inline per the shared format; update the `GLOSSARY-MAP.md` row when a glossary is
   created or term ownership shifts.

### GRILL

Ask vocabulary questions **one at a time**, waiting for each answer; for every question give your
recommended answer. When a term resolves, update the owning glossary **right there** — don't batch.
If a question is answerable from the code, read the code instead of asking. Challenge conflicts against
the existing glossary immediately; sharpen fuzzy language to a canonical term; stress-test boundaries
between related concepts with concrete scenarios.

## Boundaries (don't cross)

- **Glossary is glossary only** — totally devoid of implementation details. Not a spec, not a scratchpad,
  not a home for decisions. Skip generic programming concepts (timeout, array, endpoint) unless they carry
  domain-specific meaning.
- **Emit no decision records.** A requirement/solution decision that surfaces is for `/afk:to-prd` /
  `/afk:to-sdd` — note it in the conversation, don't record it here.
- **One owner per term** — never let the same term carry two definitions across glossaries.
- **Never write without approval.** Group changes; approval is **apply-all / by-file / by-term**.

## Safety

Discovery is scoped to the git-repo root (or cwd) — **never** recurse from system roots (CrowdStrike
guard). Skip vendor/build/.git.

## Next

- Terminology is sound but the *requirements* need stress-testing → [`/afk:grill-requirements`](../../afk/grill-requirements/SKILL.md).
- Ready to synthesize settled requirements into a PRD → `/afk:to-prd`.

Glossary maintenance is **standalone** — it does not require running the AFK chain.
