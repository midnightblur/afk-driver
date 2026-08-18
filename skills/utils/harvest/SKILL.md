---
name: harvest
description: Sweep this session for the lessons it taught and apply them before it ends.
disable-model-invocation: true
---

> **Language:** read `LANGUAGE.md` (plugin root) first — it binds every word this skill produces.

# harvest — this session's lessons, applied before it ends

The **manual** detection point: a deliberate whole-session sweep that captures
lessons *and* applies them, while the context that earned them is still live.

Scope is **this session**. Drafts of any age or origin belong to `/afk:lessons`
— that skill for "what has the workflow learned and not absorbed?", this one for
"what did the last hour teach, and can it bind before I lose it?".

**Interactive only.** Invoked hands-off, refuse — every route ends in a human
approving a write.

## 1. Sweep

Walk the session start to now. Qualify each candidate against the capture bar in
[CAPTURE.md](../../afk/lessons/CAPTURE.md). Unsure → drop it.

Then subtract what is already handled: run
`bash <main-checkout>/tools/payable/ai-agents/plugins/workflow/hooks/lesson-digest.sh --all`
from the repo root (`<main-checkout>` = first entry of `git worktree list` —
`GLOSSARY.md` "Main checkout") and drop any candidate whose `target` and substance already
appear on an `applied` line — a detection point wrote that edit this run.

Done when every correction, gotcha, and established pattern in the session is
carried forward or consciously dropped.

## 2. Draft

Per survivor, follow CAPTURE.md's "Conclude it now": classify, name the target
file, draft the concrete edit self-contained.

Done when every survivor carries a class, a target path, and an edit its steward
could apply without asking what you meant.

## 3. Propose

**One round**, grouped by target file. Per item: the edit · one-line **why** ·
its route. Approval granularity per `/afk:claude-md`'s proposal protocol.
**Never write unapproved.**

Done when every drafted item is approved, declined, or deferred — none left
unheard.

## 4. Apply

Route each approved item per CAPTURE.md's route table, which owns the
target → steward map and the self-contained bar gating a mid-task plugin edit.
A steward's own propose → approve → write protocol governs once delegated;
this skill writes no durable edit itself.

Done when every approved item has been routed and its steward has returned — no
item silently skipped.

## 5. Record and bind

Append each outcome per CAPTURE.md's "The append", then close per
[`/afk:lessons`](../../afk/lessons/SKILL.md)'s Bind table — it owns what a
written edit needs before it is in force.

Anything left `opened` — a defer, or a plugin edit too entangled to apply
mid-task — is the ledger's now. Say so and name `/afk:lessons apply`.

Report per [REPORTING.md](../../../REPORTING.md), citing captured ids as
`[lesson: L-NNNN]`.

Done when every item's outcome is on the ledger and the human knows what to
reload.
