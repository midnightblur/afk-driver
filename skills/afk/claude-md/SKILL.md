---
name: claude-md
description: Stewards CLAUDE.md, .claude/rules, and each service's STAPLES.md registry across a project hierarchy. Use when the user runs /claude-md, asks to create/update/audit/dedup project memory, registers or advances a staple, or when a durable learning (repeated correction, gotcha, established pattern) surfaces mid-session. Writes only after grouped approval.
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
See [PLACEMENT.md](PLACEMENT.md) — routes each candidate fact by scope + cohesion (place vs kind-of-file vs project-wide vs worktree-family).

## STAPLES.md — cross-cutting staples registry (this skill also stewards it)
Beyond CLAUDE.md/rules, this skill is the **sole writer** of each service's `{service}/STAPLES.md` — a registry of **staples**: delivered capabilities that became standing expectations (e.g. deep-linking, Excel import/export). A staple imposes an obligation on any **future** feature whose work matches its **Trigger**; the AFK chain consults it at grill/design/plan/review time, and only this skill writes it. The file self-documents its entry format (`Status / Trigger / Obligation / Reference / Since`); keep new entries to that shape. Inclusion bar for a new staple: it's a **cross-cutting** obligation (applies across features, keyed to a trigger), **durable**, and has a real **Reference** exemplar (or an explicit `TODO` until one ships). One-off feature behaviour is NOT a staple — it goes in the feature's own docs. Writes go through the same **propose → approve → write** protocol and the cross-worktree fan-out (it's a per-directory in-repo steering note like any other). Invoked to register/advance a staple most often by the terminal `NNNN-sync-harness` subtask at feature delivery, or standalone to promote one retroactively.

## Content style
See [STYLE.md](STYLE.md) — compression, verbatim identifiers, generic-over-volatile, precision, leaf-file shape.

## Audit
See [AUDIT.md](AUDIT.md). Surgical by default; full reorg only with `--deep`. Discovery-safety rules (scoping, excludes, CrowdStrike guard) live in AUDIT.md's Discovery section.

## Propagation (cross-worktree fan-out)
A captured learning must land **immediately in every one of the developer's worktrees** — branch isolation must not strand a note in one checkout. Model: **in-repo per-directory notes, divergence solved by propagation** (not an out-of-repo `~/.claude/shared` @import layer).

After approval, authoring/updating a note **invokes the fan-out shell** [`scripts/fanout-shell.py`](scripts/fanout-shell.py) `propagateSteeringNote(path, content)`. It:
- enumerates the developer's worktrees via `git worktree list --porcelain`;
- reads each worktree's current target-file state and asks the pure planner ([`scripts/fanout-planner.py`](scripts/fanout-planner.py) `computeFanOutPlan`) for one decision per worktree — `write | skip(reason) | noop | refuse`;
- executes **current-worktree-first** (the primary, which must succeed); siblings best-effort and independent — dirty-conflict sibling **skipped + warned** (never clobbered), already-equal file is no-op, sibling write failure warns and continues;
- on `git worktree list` failure / single worktree, writes the **primary only** and warns;
- returns a **reconcile summary** (written / noop / skipped+reason / refused) — surface it so the developer can reconcile any skipped (dirty) siblings.

The boundary is **baked**, fail-closed (see Safety). Functional-core / imperative-shell: all decision logic in the pure planner, only the shell touches git and disk.

## Proposal protocol
Group by target file. Per change: diff · one-line **why** · **placement rationale** (why here, not a level up/down) · moves as `src → dest` · cross-worktree edits tagged `propagates: N worktrees` (per the fan-out summary). Approval: **apply-all / by-file / by-number**. Write only approved (native Edit; Write for new files). No provenance markers — approval is the gate; treat human-authored lines with equal respect (propose cuts, never auto-cut).

## Safety
- Never write without approval.
- **Baked write boundary (fail-closed).** Autonomous writes confined to 11xxx turf — `("11???*/**", "tools/payable/**")`, the literal `BAKED_BOUNDARY` constant — and **never** the neutral root `CLAUDE.md` or root `GLOSSARY*`. The boundary is baked into the fan-out (`scripts/fanout-shell.py` `BAKED_BOUNDARY`), not a config file or per-call argument; any target outside it is **refused before any write**.
- **Cross-worktree divergence is solved by propagation (see Propagation), never by a `~/.claude/shared` @import layer.**
- Discovery safety per [AUDIT.md](AUDIT.md) Discovery (never scan system roots).
