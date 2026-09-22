---
name: agents-md
description: Stewards AGENTS.md, role sidecars, .claude/rules, and STAPLES.md. Use on /agents-md, for project-memory create/update/audit, staples, or when a durable learning surfaces mid-session.
---

> **Language:** read `LANGUAGE.md` (plugin root) first — it binds every word this skill produces.

# agents-md — project-memory steward

Steer, don't document. Trust agents to read code; capture only what code won't reveal. Always **propose → approve → write**. Never write unasked.

## The instruction-file standard (any repo this skill stewards)

Decision record: `adr/0003-agents-md-instruction-standard.md`. Per-harness discovery facts (which harness reads which file, walk order, size caps) live in `providers/HARNESS-MATRIX.md` — read there, never restated here.

- **`AGENTS.md` is the source in every directory.** Per-directory steering lands in `AGENTS.md`, not `CLAUDE.md`.
- **One root `CLAUDE.md` bridge, holding only `@AGENTS.md`.** It is the floor for a session that cannot read `AGENTS.md` natively (including the first session after a harness upgrade). No other `CLAUDE.md` in the tree.
- **No `@path` imports inside any `AGENTS.md`.** The root bridge's `@AGENTS.md` is the one allowed import. Imported content that passes the inclusion bar is inlined into the nearest `AGENTS.md`, or the shared file becomes a nested `AGENTS.md` at its natural directory. Trigger pointers only for content both large and rarely needed.
- **`AGENTS.override.md` is banned in a repository** — gitignore `**/AGENTS.override.md`.
- **Per-dev and plugin steering live in the user-global files** (`~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`), never committed.
- **Repo-scoped personal preference goes in `CLAUDE.local.md`**, gitignored as `**/CLAUDE.local.md`.
- **`.claude/rules/*.md` keep full bodies.** One line in each service `AGENTS.md` names the rules directory for tools without the plugin.

## Modes (auto-detect; user may force via arg)

| Mode | Trigger | Does |
|---|---|---|
| HARVEST | durable signal mid-session, or "remember this / update AGENTS.md" | propose targeted additions from session learnings |
| AUDIT | "audit / check / dedup / reorganize AGENTS.md" | scan tree → dup/contradiction/staleness/mechanical/bar checks |
| BOOTSTRAP | dir has no `AGENTS.md`, "create AGENTS.md" | lean scoped exploration → minimal steering file |

Auto-fire: **HARVEST only**, on durable signal → propose ONE item. AUDIT + BOOTSTRAP manual. Signal = same correction twice · gotcha found · pattern established · review catch code won't reveal. One-off / obvious-from-code / this-session-only → do NOT harvest.

Lesson-ledger tie-in: a harvested signal that is a *workflow* lesson (bar + protocol: `skills/afk/lessons/CAPTURE.md`) also gets a ledger event via `hooks/lesson-append.sh` — `opened` then `applied` when the proposal is approved and written, `opened` alone when detected but declined or no human is present. Cross-session recurrence ("same correction twice" spanning sessions) is exactly what the ledger makes visible.

BOOTSTRAP done when every emitted line passes the 4-gate inclusion bar and the proposal is approved before any write.

## Inclusion bar + placement
Read [PLACEMENT.md](PLACEMENT.md) before proposing — every candidate line passes its 4-gate inclusion bar and routes by its placement engine (scope/cohesion, then audience). This skill stewards the role sidecars (`IMPL.md`/`TESTING.md`/`DEBUG.md`) alongside `AGENTS.md` — same bar, same proposal protocol.

## STAPLES.md — cross-cutting staples registry (this skill also stewards it)
This skill is the **sole writer** of each service's `{service}/STAPLES.md` (what a staple is + how the chain consults it: plugin-root `AGENTS.md` "Staples registry"). The file self-documents its entry format (`Status / Trigger / Obligation / Reference / Since`); keep new entries to that shape. Inclusion bar for a new staple: **cross-cutting** obligation (applies across features, keyed to a trigger), **durable**, real **Reference** exemplar (or explicit `TODO` until one ships). One-off feature behaviour is NOT a staple — it goes in the feature's own docs. Writes go through the same **propose → approve → write** protocol. Invoked to register/advance a staple most often by the terminal `NNNN-sync-harness` subtask at feature delivery, or standalone to promote one retroactively.

## Known debt — the durable home for adjudicated shortcomings (this skill also stewards it)
This skill is the **sole writer** of each `AGENTS.md`'s optional `## Known debt` section: shortcomings that are real, understood, and deliberately not fixed, so the next agent on that ground does not re-propose a rejected fix. Placed at the nearest `AGENTS.md` to the code, by the same scope/cohesion rule as any other line. Entry shape: one bolded sentence naming the shortcoming, then what was considered and **why it was rejected**, then the condition that would reopen it. A reason is mandatory — an entry that only names the flaw is a `// TODO:` at the wrong altitude, and belongs at the code site instead.

Inclusion bar, beyond the standard four gates: the debt must be **adjudicated** (someone decided not to fix it, with a reason) and **durable** (it survives this feature). An open finding is not known debt, and neither is a one-line cleanup nobody has ruled on. `/afk:review` routes `product-debt` findings here; `/afk:preflight` PF-4d refuses to go green while an accepted one has no entry. Writes go through the same **propose → approve → write** protocol.

## Content style
Read `LANGUAGE.md` (plugin root) — the concision bar (§3) plus its "Steering notes" section — and apply it to every note written.

## Audit
See [AUDIT.md](AUDIT.md). Surgical by default; full reorg only with `--deep`. Discovery-safety rules (scoping, excludes, CrowdStrike guard) live in AUDIT.md's Discovery section.

## Proposal protocol
Group by target file. Per change: diff · one-line **why** · **placement rationale** (why here, not a level up/down) · moves as `src → dest`. Approval: **apply-all / by-file / by-number**. Write only approved (native Edit; Write for new files). No provenance markers — approval is the gate; treat human-authored lines with equal respect (propose cuts, never auto-cut).

## Safety
- **Write boundary (fail-closed).** Autonomous writes confined to the service directories the feature touches — and **never** the repo-root `AGENTS.md` (or its `CLAUDE.md` bridge) or root `GLOSSARY*`. Any target outside is **refused before any write**.
- **`~/.claude/shared` write boundary.** Write in-repo only; never route steering out to `~/.claude/shared`. This skill owns this boundary — `PLACEMENT.md` points here for it.
- Discovery safety per [AUDIT.md](AUDIT.md) Discovery (never scan system roots).
