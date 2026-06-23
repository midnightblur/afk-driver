---
name: claude-md
description: Create, maintain, audit, and enhance CLAUDE.md / .claude/rules / shared-md files across a project hierarchy. Use when the user runs /claude-md, asks to create/update/audit/improve/dedup/reorganize CLAUDE.md or project memory, mentions "project memory" or "CLAUDE.md maintenance", or when a durable learning surfaces mid-session (repeated correction, gotcha discovered, pattern established) that belongs in project memory. Writes only after grouped, cherry-pickable approval.
---

# claude-md — project-memory steward

Senior-dev-over-the-shoulder. Right hint at right level. Steer, don't document.
Trust agents to read code; capture only what reading code won't reveal.
Always **propose → approve → write**. Never write unasked.

## Modes (auto-detect; user may force via arg)

| Mode | Trigger | Does |
|---|---|---|
| HARVEST | durable signal mid-session, or "remember this / update CLAUDE.md" | propose targeted additions from session learnings |
| AUDIT | "audit / check / dedup / reorganize CLAUDE.md" | scan tree → dup/contradiction/staleness/mechanical/bar checks |
| BOOTSTRAP | dir has no CLAUDE.md, "create CLAUDE.md" | lean scoped exploration → minimal steering file |

Auto-fire: **HARVEST only**, on a durable signal → propose ONE item. AUDIT + BOOTSTRAP manual.
Signal = same correction twice · gotcha found · pattern established · review catch code won't reveal.
One-off / obvious-from-code / this-session-only → do NOT harvest.

## Inclusion bar — every line passes ALL 4
1. **non-obvious** — not quickly derivable from the code
2. **durable** — will recur
3. **steering** — changes what an agent does/decides
4. **non-dup** — not already in an ancestor file

Unsure → **omit silently**. Pointer one-liners > explanations (`X in Y; gotcha: Z`).

## Placement
See [PLACEMENT.md](PLACEMENT.md). Cohesion test: about a *place* → subdir `CLAUDE.md`;
about a *kind-of-file* anywhere → `.claude/rules/`+`paths:`; project-wide → root `CLAUDE.md`;
cross-cutting principle for the worktree family → write the per-directory note **in-repo** and
**propagate it across worktrees** (see Propagation) — never route it out to `~/.claude/shared`.

## Content style
Dense-but-parseable caveman. See [STYLE.md](STYLE.md). Verbatim: paths, commands, flag/field
names, errors. Keep directive subject+scope. Match target file's existing heading depth/density.
Stay generic — no version numbers / counts / dates (go stale → wrong-but-authoritative);
state the rule, not the current value.
**Leaf/subdir CLAUDE.md = directive only** — emit the `## …` heading + body, NO `# CLAUDE.md — <dir>`
title and NO `Scope:` / `Inherits` preamble (dir path scopes it, ancestors auto-load; banner = tokens,
not steering). Legacy leaf files with that banner are not the pattern to copy.

## Audit
See [AUDIT.md](AUDIT.md). Surgical by default; full reorg only with `--deep`.
Discovery scoped to git-repo root (or cwd) — NEVER recurse from system roots; skip vendor/build/.git;
honor `claudeMdExcludes`.

## Propagation (cross-worktree fan-out)
A captured learning must land **immediately in every one of the developer's worktrees** — branch
isolation must not strand a note in one checkout. The model is **in-repo per-directory notes,
divergence solved by propagation** (not by an out-of-repo `~/.claude/shared` @import layer).

After approval, authoring/updating a note **invokes the fan-out shell**
[`scripts/fanout-shell.py`](scripts/fanout-shell.py) `propagateSteeringNote(path, content)`. It:
- enumerates the developer's worktrees with `git worktree list --porcelain`;
- reads each worktree's current state of the target file and asks the pure planner
  ([`scripts/fanout-planner.py`](scripts/fanout-planner.py) `computeFanOutPlan`) for one decision per
  worktree — `write | skip(reason) | noop | refuse`;
- executes **current-worktree-first** (the primary, which must succeed); siblings are best-effort and
  independent — a dirty-conflict sibling is **skipped + warned** (never clobbered), an already-equal
  file is a no-op, a sibling write failure warns and continues;
- on `git worktree list` failure / a single worktree, writes the **primary only** and warns;
- returns a **reconcile summary** (written / noop / skipped+reason / refused) — surface it so the
  developer can reconcile any skipped (dirty) siblings.

The boundary is **baked**, fail-closed (see Safety). This is functional-core / imperative-shell: all
decision logic is in the pure planner, only the shell touches git and disk.

## Proposal protocol
Group by target file. Per change: diff · one-line **why** · **placement rationale** (why here, not a
level up/down) · moves as `src → dest` · cross-worktree edits tagged `propagates: N worktrees` (per the
fan-out summary). Approval: **apply-all / by-file / by-number**. Write only approved (native Edit; Write
for new files). No provenance markers — approval is the gate; treat human-authored lines with equal
respect (propose cuts, never auto-cut).

## Safety
- Never write without approval.
- **Baked write boundary (fail-closed).** Autonomous writes are confined to the 11xxx turf —
  `11xxx*/**` and `tools/payable/**` — and **never** the neutral root `CLAUDE.md` or root `GLOSSARY*`.
  The boundary is a constant baked into the fan-out (`scripts/fanout-shell.py` `BAKED_BOUNDARY`), not a
  config file or a per-call argument; any target outside it is **refused before any write**. afk
  is purpose-built for 11xxx, so it knows the boundary natively.
- **Cross-worktree divergence is solved by propagation, not by `~/.claude/shared`.** Don't route a
  shared-worthy principle out to a personal `~/.claude/shared` @import; write it as an in-repo
  per-directory note and let the fan-out propagate it to every worktree (see Propagation). One author
  step → every worktree, no merge, no out-of-repo layer. (Truly personal, all-projects prefs still
  belong in `~/.claude/CLAUDE.md`; uncommitted local-only notes in gitignored `CLAUDE.local.md`.)
- Discovery never scans system roots (CrowdStrike guard).
