---
name: investigate
description: "Answer a question about existing code to closure, not to the first grep: how X works, what depends on X, what breaks if X changes, what edge cases exist, whether Y exists. Use whenever a claim about existing code will be stated as fact."
---

> **Language:** read `LANGUAGE.md` (plugin root) first — it binds every word this skill produces.

Runs one code investigation to closure and writes its coverage ledger. The completion contract — question types, boundary catalog, dispositions, verdicts, closure, counter-search, proportionality — is `${AFK_PLUGIN_ROOT}/INVESTIGATION.md`; read it before step 1. The ledger grammar and the reply shape are [`LEDGER-FORMAT.md`](LEDGER-FORMAT.md).

This skill is the single writer of the ledger. Tracers return fragments; only this skill merges them.

## Steps

1. **Classify.** Pick the question type from the table in `${AFK_PLUGIN_ROOT}/INVESTIGATION.md` § "Question types". A question carrying two types runs as the wider one.
2. **Resolve the subject.** Name the symbols the question is about and pin the snapshot: `git rev-parse HEAD`. Ambiguous subject → ask the human before spending a run.
3. **Seed map.** Run the deterministic pre-pass:

   ```sh
   python "$AFK_PLUGIN_ROOT/skills/utils/investigate/scripts/seed_map.py" \
     --repo <repo root> --subject <name> --type <Q1..Q5> --config auto \
     --out <scratch>/seed.json
   ```

   It enumerates every boundary class it has a method for and marks the rest
   `unverified(no enumeration method)`. No `investigation:` block in the
   repository's `.afk/config.yaml` → the generic defaults run alone; say so in
   the reply and name the fix: declare `investigation:` in `.afk/config.yaml`
   (schema: `${AFK_PLUGIN_ROOT}/CONFIG.md`).
4. **Fan out.** Apply the proportionality rule (`INVESTIGATION.md` § "Proportionality"). Cluster the seed map's hits by module and boundary, then spawn one `afk-tracer` per cluster **in one message** — or one tracer for the whole run when the rule does not call for fan-out. Each spawn carries: the repository root, the question, its type, the path to its slice of the seed map, the fragment output path, and one sentence stating the nesting depth it may use. Arm the stall watchdog (`${AFK_PLUGIN_ROOT}/DELEGATION.md` § "Stall watchdog").
5. **Merge and reopen.** Fold every fragment into one ledger. A node a fragment discovered that no boundary covered reopens the queue: spawn a delta tracer for it. Where `INVESTIGATION.md` § "Counter-search" requires an agent-driven pass, spawn a fresh tracer told to use a different method and blind to the first tracer's conclusions.
6. **Validate.** Run:

   ```sh
   python "$AFK_PLUGIN_ROOT/skills/utils/investigate/scripts/validate_coverage.py" \
     --ledger <ledger dir>/COVERAGE.json
   ```

   Exit 1 → fix what it names, or record the verdict as `partial`. Never publish an unvalidated ledger as closed.
7. **Write and reply.** Write `COVERAGE.json` and `REPORT.md` to the ledger directory ([`LEDGER-FORMAT.md`](LEDGER-FORMAT.md) owns both the names and the location rule), then reply in the fixed shape that file defines, ending `OUTCOME: <ok|fail|blocked> — <one line>`.

## Refusals

- A repository that is not a git checkout: the snapshot cannot be pinned, so the run stops.
- A question about code that does not exist yet: that is design work, not an investigation.
- A verdict of `closed` while any boundary is `unverified`: the verdict is `closed-with-frontier` or `partial`, never `closed`.
