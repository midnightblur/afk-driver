# Delegation protocol

How AFK skills protect the orchestrating agent's context window. Binding on every skill. The orchestrator's context is the run's scarcest resource: any step that reads a lot but whose product is small runs in a subagent, so the orchestrator keeps the conclusion — never the inputs. The second dividend is quality: a fresh child judges evidence without the run's accumulated bias.

## Must-delegate triggers

A step matching **any** trigger runs in a subagent — "it looks small this time" is not an exemption:

1. **Fact-extraction reads** — reading more than 2 files (docs or code) only to extract facts, build a digest, or assemble citations. The child returns the digest; the orchestrator never opens the sources.
2. **Repo-wide search / claim verification** — claim grounding, blast-radius greps, anchor checks, drift scans across many files.
3. **Suite / build / tier execution** — verification tiers, test suites, builds, any long-output shell run. The child triages the raw output itself and returns per-item verdicts + a failure digest.
4. **Large-diff analysis** — a diff over ~300 lines is read and analyzed in a child, never inline.
5. **External intake** — Jira / GitLab / web pulls. The child returns a task-shaped digest, not the payload.

## Never delegate

1. **The human conversation** — interviews, approvals, anything that needs the user mid-step.
2. **Conversation synthesis** — a child cannot see the session; a skill whose input *is* the conversation keeps its synthesis spine inline (its research/verification sub-steps still delegate per the triggers above).
3. **Single-writer stamps** — progress-tracker cells, journal appends, index rows: the child reports, the owning skill writes (ownership map: plugin `CLAUDE.md`, "Section ownership invariants").
4. **Accumulated-nuance loops** — steps whose next decision needs the full texture of the previous one (e.g. the TDD inner loop) stay inline; only their bulk sub-steps (a suite run, a wide read) delegate.

## Spawn rules

- **Independent children go in ONE message** (parallel Agent calls) — never sequential when there is no data dependency.
- **Named types first**: `afk-reader` (read-only digester — reads, searches, verifies; cannot edit) and `afk-runner` (executes commands/suites and triages their output; writes only evidence files). Fall back to `general-purpose` only when the child must edit project files.
- **Hand a child paths + a task, never content.** Anything the child can read itself is not pasted into its prompt.
- **Nesting cap: three levels** — orchestrator → per-unit child → that child's helpers. Helpers do not spawn.
- **Blind where the skill demands it.** A skill's information-diet rules (what the child must NOT see) override convenience; when a fresh perspective is the point, the child gets artifacts, never the run's reasoning.

## Model selection

- **haiku for facts** — binary/mechanical checks (anchor greps, exit-code probes, existence/validation) where a wrong answer is self-evident downstream.
- **sonnet for digests** — the `afk-reader`/`afk-runner` default (set in their definitions): reads, searches, suite triage, and research whose digest the orchestrator treats as advisory and can spot-check via citations.
- **inherit for verdicts and product code** — any child that writes production code, and any research whose verdict is acted on without re-checking (a confirm/refute that gates a spec or a publish step). A judge is never a cheaper model than the implementor it judges.
- Callers override per-spawn (the Agent call's `model`) — always upward. Escalate the moment a digest stops being advisory; never downgrade to save tokens on a verdict.

## Return contract

- The return ends with a terse structured tail owned by the invoking skill's grammar (`OUTCOME:` line, findings JSON, verdict token — never a new token, per `REPORTING.md`). A skill that defines no grammar gets the default: `OUTCOME: <ok|fail|blocked> — <one line>`.
- Body ≤ ~30 lines. Every claim carries a citation — `file:line`, or command + exit code — so the orchestrator can spot-check without re-reading the child's inputs.
- **Bulk evidence never rides the return.** Logs, traces, raw suite output go to a file (the run's artifact dir when the skill has one, otherwise the scratchpad); the return carries the path.
- The orchestrator acts on the digest. Re-reading what the child already read defeats the delegation; spot-checks go through the citations.
