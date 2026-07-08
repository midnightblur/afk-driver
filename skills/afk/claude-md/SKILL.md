---
name: claude-md
description: Stewards CLAUDE.md, its role sidecars (IMPL.md/TESTING.md/DEBUG.md), .claude/rules, and each service's STAPLES.md registry across a project hierarchy. Use when the user runs /claude-md, asks to create/update/audit/dedup project memory, registers or advances a staple, or when a durable learning (repeated correction, gotcha, established pattern) surfaces mid-session. Writes only after grouped approval.
---

# claude-md — project-memory steward

Steer, don't document. Trust agents to read code; capture only what reading code won't reveal. Always **propose → approve → write**. Never write unasked.

## Modes (auto-detect; user may force via arg)

| Mode | Trigger | Does |
|---|---|---|
| HARVEST | durable signal mid-session, or "remember this / update CLAUDE.md" | propose targeted additions from session learnings |
| AUDIT | "audit / check / dedup / reorganize CLAUDE.md" | scan tree → dup/contradiction/staleness/mechanical/bar checks |
| BOOTSTRAP | dir has no CLAUDE.md, "create CLAUDE.md" | lean scoped exploration → minimal steering file |

Auto-fire: **HARVEST only**, on a durable signal → propose ONE item. AUDIT + BOOTSTRAP manual. Signal = same correction twice · gotcha found · pattern established · review catch code won't reveal. One-off / obvious-from-code / this-session-only → do NOT harvest.

BOOTSTRAP done when: every emitted line passes the 4-gate inclusion bar and the proposal is approved before any write.

## Inclusion bar — every line passes ALL 4
1. **non-obvious** — not quickly derivable from the code
2. **durable** — will recur
3. **steering** — changes what an agent does/decides
4. **non-dup** — not already in an ancestor file

Unsure → **omit silently**. Pointer one-liners > explanations (`X in Y; gotcha: Z`).

## Placement
See [PLACEMENT.md](PLACEMENT.md) — routes each candidate fact by scope + cohesion (place vs kind-of-file vs project-wide), then by **audience** (`CLAUDE.md` for decision-relevant facts everyone auto-loads; role sidecars `IMPL.md`/`TESTING.md`/`DEBUG.md` read on demand via a pointer line). This skill stewards the sidecars alongside CLAUDE.md — same inclusion bar, same proposal protocol.

## STAPLES.md — cross-cutting staples registry (this skill also stewards it)
Beyond CLAUDE.md/rules, this skill is the **sole writer** of each service's `{service}/STAPLES.md` — a registry of **staples**: delivered capabilities that became standing expectations (e.g. deep-linking, Excel import/export). A staple imposes an obligation on any **future** feature whose work matches its **Trigger**; the AFK chain consults it at grill/design/plan/review time, and only this skill writes it. The file self-documents its entry format (`Status / Trigger / Obligation / Reference / Since`); keep new entries to that shape. Inclusion bar for a new staple: it's a **cross-cutting** obligation (applies across features, keyed to a trigger), **durable**, and has a real **Reference** exemplar (or an explicit `TODO` until one ships). One-off feature behaviour is NOT a staple — it goes in the feature's own docs. Writes go through the same **propose → approve → write** protocol (it's a per-directory in-repo steering note like any other). Invoked to register/advance a staple most often by the terminal `NNNN-sync-harness` subtask at feature delivery, or standalone to promote one retroactively.

## Content style
See [STYLE.md](STYLE.md) — compression, verbatim identifiers, generic-over-volatile, precision, leaf-file shape.

## Audit
See [AUDIT.md](AUDIT.md). Surgical by default; full reorg only with `--deep`. Discovery-safety rules (scoping, excludes, CrowdStrike guard) live in AUDIT.md's Discovery section.

## Proposal protocol
Group by target file. Per change: diff · one-line **why** · **placement rationale** (why here, not a level up/down) · moves as `src → dest`. Approval: **apply-all / by-file / by-number**. Write only approved (native Edit; Write for new files). No provenance markers — approval is the gate; treat human-authored lines with equal respect (propose cuts, never auto-cut).

## Safety
- Never write without approval.
- **Write boundary (fail-closed).** Autonomous writes confined to 11xxx turf — `11???*/**`, `tools/payable/**` — and **never** the neutral root `CLAUDE.md` or root `GLOSSARY*`. Any target outside the boundary is **refused before any write**.
- **In-repo per-directory notes, not an out-of-repo `~/.claude/shared` @import layer.** A note lands in the current checkout only; branch isolation is expected — do not attempt to spread it to sibling worktrees.
- Discovery safety per [AUDIT.md](AUDIT.md) Discovery (never scan system roots).
