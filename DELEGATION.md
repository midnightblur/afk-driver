# Delegation protocol

How AFK skills protect the orchestrating agent's context window. Binding on every skill. The orchestrator's context is the run's scarcest resource: any step that reads a lot but whose product is small runs in a subagent — orchestrator keeps the conclusion, never the inputs.

## Must-delegate triggers

A step matching **any** trigger runs in a subagent — "looks small this time" is no exemption:

1. **Fact-extraction reads** — reading >2 files (docs or code) only to extract facts, build a digest, or assemble citations. Child returns the digest; orchestrator never opens the sources.
2. **Repo-wide search / claim verification** — claim grounding, blast-radius greps, anchor checks, drift scans across many files.
3. **Suite / build / tier execution** — verification tiers, test suites, builds, any long-output shell run. Child triages the raw output itself, returns per-item verdicts + a failure digest.
4. **Large-diff analysis** — a diff over ~300 lines is read and analyzed in a child, never inline.
5. **External intake** — Jira / GitLab / web pulls. Child returns a task-shaped digest, not the payload.

## Never delegate

1. **The human conversation** — interviews, approvals, anything needing the user mid-step.
2. **Conversation synthesis** — a child cannot see the session; a skill whose input *is* the conversation keeps its synthesis spine inline (its research/verification sub-steps still delegate per the triggers above).
3. **Single-writer stamps** — progress-tracker cells, journal appends, index rows: child reports, owning skill writes (ownership map: plugin `CLAUDE.md`, "Section ownership invariants").
4. **Accumulated-nuance loops** — steps whose next decision needs the full texture of the previous one (e.g. the TDD inner loop) stay inline; only their bulk sub-steps (a suite run, a wide read) delegate.

## Spawn rules

- **Independent children go in ONE message** (parallel spawns) — never sequential when there is no data dependency.
- **Overlap the human's think-time.** In an interactive phase, spawn delegations in background **before yielding the turn** — grounding for the pending question's premises, pre-fill for an accumulating batch, the likely next question's verification — so digests land while the human reads and types. Nothing locks in before its digest returns; only the waiting moves.
- **Named types first**: `afk-reader` (read-only digester — reads, searches, verifies; cannot edit) and `afk-runner` (executes commands/suites, triages their output; writes only evidence files). Fall back to a general-purpose child only when it must edit project files. (Per-provider spawn vocabulary: `PROVIDERS.md`.)
- **Hand a child paths + a task, never content** — nothing it can read itself.
- **Nesting cap: three levels** — orchestrator → per-unit child → that child's helpers. Helpers do not spawn. (Codex: requires the `max_depth` config from `codex-sync/config-fragment.toml`; at its default of 1, helper steps run inline — degraded, not broken.)
- **Blind where the skill demands it.** A skill's information-diet rules (what the child must NOT see) override convenience; when a fresh perspective is the point, the child gets artifacts, never the run's reasoning.

## Model selection

Role-based tiers — the role decides the model, named explicitly per provider in `PROVIDERS.md` ("Model tiers"). "Inherit the session model" is never a tier: every spawn names its tier.

- **frontier tier — judgment that shapes the work**: grilling, planning/slicing, code review and dispute adjudication, adversarial probes, and any verdict acted on without re-checking (a confirm/refute gating a spec, ship, or publish step). Best model available, explicitly. A judge is never a cheaper model than the implementor it judges.
- **implementation tier — executing work the frontier tier laid out**: any child writing product code against a plan/contract/design authored at the frontier tier. One rung below frontier — never the frontier model itself (the frontier intelligence is already in the plan); one rung lower again when the slice is on the simpler side.
- **digest tier** — the `afk-reader`/`afk-runner` default: reads, searches, suite triage, mechanical chores (bulk renames, format fixes, anchor greps — run these at low reasoning effort), and research whose digest the orchestrator treats as advisory and spot-checks via citations.
- **Plugin/harness work is always frontier.** Any agent editing the AFK plugin or the harness it ships and stewards (skills, doctrine files, hooks, agent defs, the codex mirror/generator, CLAUDE.md steering artifacts) runs frontier-tier regardless of the edit's apparent size — a plugin defect multiplies into every run it drives.
- Callers override per-spawn — always upward. Escalate the moment a digest stops being advisory; never downgrade to save tokens on a verdict.

## Return contract

- Return ends with a terse structured tail owned by the invoking skill's grammar (`OUTCOME:` line, findings JSON, verdict token — never a new token, per `REPORTING.md`). A skill defining no grammar gets the default: `OUTCOME: <ok|fail|blocked> — <one line>`.
- Body ≤ ~30 lines. Every claim carries a citation — `file:line`, or command + exit code — so the orchestrator spot-checks without re-reading the child's inputs.
- **Bulk evidence never rides the return.** Logs, traces, raw suite output go to a file (the run's artifact dir when the skill has one, else the scratchpad); the return carries the path.
- Orchestrator acts on the digest. Re-reading what the child already read defeats the delegation; spot-checks go through the citations.
