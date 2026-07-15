# Retro report format — `RETRO-{YYYY-MM-DD}.md`

Written by `/afk:retro` into the release folder it analyzed. One file per run; a later run writes a new dated file, never edits a prior (the trail of retros is itself evidence of whether proposals worked).

## Sections, in order

### Header

```
# Retro — {release folder} — {YYYY-MM-DD}
Scope: {n} features ({ticket ids}), {m} subtasks, journal window {first}..{last}
```

### 1. Features at a glance

One row per feature:

```
| Feature | Subtasks (done/parked/total) | Review (crit/high/med/low) | Adversary | Smoke | Wall-clock | Remediation cycles |
|---|---|---|---|---|---|---|
```

`Wall-clock` = first→last journal timestamp. `Remediation cycles` = re-review/re-adversary rounds summed over subtasks.

### 2. Signals

One `###` block per signal family that fired (recurring finding classes, park patterns, stall geography, grill-gap correlation, wiring debt, criterion yield, pattern-debt recurrence, lesson closure & recurrence — definitions in `SKILL.md`). Each block: aggregate numbers, then the occurrence list — every occurrence cited as `{ticket} {NNNN-slug} — {source}: {line/id}`. A family with nothing ≥2 occurrences states `no recurring signal`, one line.

### 3. Gate latency

Verbatim output of `gate-metrics-report.sh` plus one sentence per gate whose p95 breaches the budget (`hooks/README.md` "Latency metrics & budget"), naming the dominant component (`lock_wait_ms`, `package_ms`, run count).

### 4. Proposals (the load-bearing section)

At most 5, ranked by expected impact. Each:

```
### P{n}: {one-line title}
- Evidence: {occurrence list or metric numbers — copied from §2/§3, not re-derived}
- Hypothesis: {one sentence — the root cause in the workflow, not the code}
- Edit: {plugin file + section} — {proposed wording or precise change}
- Partners: {every lockstep/registry file the edit must touch in the same commit, or "none"}
- Expected effect: {the §2/§3 number this should move, and in which direction}
```

A proposal that grades or escalates a ledger lesson cites its `L-NNNN` id in Evidence.

### 5. Verdict on prior retro

If a prior `RETRO-*.md` exists in the folder: per proposal, one line — `applied` / `not applied` / `applied, signal gone` / `applied, signal persists` (the last means the hypothesis was wrong — say so). If none exists: `first retro for this release.`
