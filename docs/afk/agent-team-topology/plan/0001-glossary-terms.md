## Goal
Add to the plugin-root GLOSSARY.md the terms the design defines and the root glossary does not hold, written directly by the plugin author, the root glossary's steward (FRESHNESS.md:44; plan D-31). The entries for pane agent and pane transport land here first, since the review-gate docs slice uses both terms. The slice adds the charter to the Team pattern entry, replaces the Talk edges entry's claim that unlisted messages relay through the contact agent, and fixes the copy of that entry in docs/afk/agent-team-topology/LAVISH-TIPS.md. The slice ends at glossary text: no code, no skill prose.

## Complexity
mechanical

## Design refs
- SDD: SDD.md#§13 Open Questions — row Q1 lists the terms the root glossary lacks and the two entries to fix
- SDD: SDD.md#§4 L3 — Data Architecture — the charter file record the new entry describes
- SDD: SDD.md#§14 L9 — Implementation Seams & Change Impact — row "GLOSSARY.md:319 and README.md:603": pane agent and pane transport land before its 2 lines

## Scope
- GLOSSARY.md
- docs/afk/agent-team-topology/LAVISH-TIPS.md

## Seams
- (none — documentation only; no SDD §14 seam row covers the glossary entries)

## Acceptance
- [ ] GLOSSARY.md holds one entry for each term the open-question row on terms lists: run, role, spawned agent, hub, stage, topology map, team entry script, pane agent, role agent, helper, builder, moderator, pattern step, resolved pattern, afk-lite, requester, report target, multiplexer, recipe, run directory, inbox, envelope, message body, result file, completion signal, job supervisor, wait job, stall watchdog, owner generation, harness session id, stage map, pane switch, pattern standard, charter, charter file and one-off pattern; a term the glossary already holds is not added twice (SDD §13 Q1)
- [ ] GLOSSARY.md holds a **Pane agent** entry and a **Pane transport** entry, in the change this subtask ships, before the review-gate docs slice rewrites GLOSSARY.md:319 and README.md:603 with those terms (SDD §14 row "GLOSSARY.md:319 and README.md:603")
- [ ] The executor writes the entries directly into GLOSSARY.md as plugin author, the steward FRESHNESS.md:44 names. /afk:glossary is not used: it stewards domain glossaries only and routes through a GLOSSARY-MAP.md this repository lacks (skills/utils/glossary/SKILL.md:3-6, :38) (plan D-31) (SDD §13 Q1)
- [ ] The **Charter file** entry says: one file per role per run, in the run directory, holding the charter's pattern part and then that role's part, and for a one-off pattern the run's only copy of its charter (SDD §4)
- [ ] The **Charter** entry says every pattern that starts agents carries a charter, never empty: a pattern part with the pattern's purpose and how it meets the pattern standard, and one part per role (PRD AC-066)
- [ ] The **One-off pattern** entry says: a pattern written for one task and not saved, which has no record, reaches the run in the fields of a pattern record with its charter, and is checked as a record with roles (PRD AC-066)
- [ ] The Team pattern entry (GLOSSARY.md:38) no longer holds for a pattern that starts agents, so it gains the charter among what such a pattern carries (SDD §13 Q1)
- [ ] The Talk edges entry (GLOSSARY.md:58) no longer says anything not listed relays through the contact agent; it says every message off a declared edge is refused, naming the edge, and names the four paths that need no edge (PRD AC-035)
- [ ] The Talk edges entry says a role and its report target, whoever it is, may message each other both ways with no declaration, and siblings message each other only along declared edges (PRD AC-069)
- [ ] The copy of the Talk edges entry at docs/afk/agent-team-topology/LAVISH-TIPS.md:49 carries the same corrected text (SDD §13 Q1)
- [ ] Every artifact in ## Produces exists with its declared contract (SDD §13 Q1)

## Produces
- GLOSSARY.md#**Pane agent** — glossary entry: an agent in its own terminal pane
- GLOSSARY.md#**Pane transport** — glossary entry: a transport that starts pane agents; finding one turns the pane-agent default on
- GLOSSARY.md#**Charter file** — glossary entry: one file per role in the run directory, the pattern part plus that role's part
- GLOSSARY.md#**One-off pattern** — glossary entry: a pattern used once without being saved

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `grep -nF '**Charter file**' GLOSSARY.md && grep -nF '**One-off pattern**' GLOSSARY.md && grep -nF '**Charter**' GLOSSARY.md && grep -nF '**Pane agent**' GLOSSARY.md && grep -nF '**Pane transport**' GLOSSARY.md` | the Produces anchors and the new term entries exist |
| static | `! grep -nF 'Anything not listed relays through the contact agent' GLOSSARY.md docs/afk/agent-team-topology/LAVISH-TIPS.md` | the Talk edges entry and its copy no longer say unlisted messages relay through the contact agent |
| static | `afk-python -m pytest scripts/tests/test_glossary_usage.py -q` | the glossary usage check still passes with the new entries |

## Context excerpts
> (SDD §13 Q1) Q1: Terms this document defines that the root glossary does not hold: run, role, spawned agent, hub, stage, topology map, team entry script (S-104), and the terms rounds 40 to 46 added: pane agent, role agent, helper, builder, moderator, pattern step, resolved pattern, afk-lite, requester, report target, multiplexer, recipe, run directory, inbox, envelope, message body, result file, completion signal, job supervisor, wait job, stall watchdog, owner generation, harness session id, stage map, pane switch, pattern standard, and the charter terms charter, charter file and one-off pattern (charter C1, C2, agent-decided); GLOSSARY.md:38's Team pattern entry lists no charter; INV-074 and INV-075 both read it as no longer holding for a pattern that starts agents, which settles INV-050's reading that it still held (main-merge delta 2); GLOSSARY.md:58's Talk edges entry, copied in LAVISH-TIPS.md:49, says anything not listed relays through the contact agent, but every message off a declared edge is refused, naming the edge, beside the paths that need no edge, one of them a role and its resolved report target, both ways, for messages (AC-035, AC-069; INV-050;
> (SDD §14 row "GLOSSARY.md:319 and README.md:603", Conventions / landmines) Pane agent and pane transport have no GLOSSARY.md entry yet; both land before the 2 lines, so the slice that writes them depends on the glossary slice (LANGUAGE.md:36; FRESHNESS.md:44; INV-070 c-888f1ed0;
> (SDD term table) | pane agent | An agent in its own terminal pane (S-153) |
> (PRD AC-041) The pane-agent default applies whenever the plugin is enabled and a pane transport is found; nothing needs configuring. One configuration key switches role agents back to subagents. A session without the plugin enabled is unchanged.
> (SDD §4) Charter file. Identity: the role, one per role per run (charter C2, agent-decided). Path: in the run directory, named by the role; the executor names the file, as it names the other files in the run directory (S-182; inferred). Writer: the team entry script, at resolve time, before any start, from the pattern record or, for a one-off pattern, from the charter its input carries (charter C2; audit round 17, agent-decided). Readers: the agent that fills the role, whose launch prompt names the file before its brief, as a resume's launch does again, and whom the SessionStart hook points back at it after a compaction (charter C2, charter C3', agent-decided); the row names no other reader (inferred). Content: the charter's pattern part, then the role's part (charter C2); for a one-off pattern these files are the run's only copy of its charter (audit round 17, agent-decided). Lifetime: from the resolve to cleanup, which deletes it with the run directory in step 2 (inferred from S-198); a new contact session that adopts the run finds it in place (inferred: adoption keeps the run directory, AC-015).
> (PRD AC-035) **AC-035** Agents message each other directly only along the talk edges the pattern declares, each edge listing the message types it allows. Every other message is refused, naming the edge. Four paths need no declared edge: every agent may send the contact agent a start request and its own finished, parked and exited messages; the contact agent may message any agent it started; a role's finished message goes to its report target, which the run takes from the manifest and the pattern (decided by the agent, grill log row of 2026-10-05 on the design audit, L5); and a role and its report target, whoever it is, may message each other, both ways (AC-069; decided by the agent, grill log row of 2026-10-06 on the pattern charter, C4, and the row of 2026-10-06 on audit round 15). A pattern that needs a messaging ability the transport lacks is refused at start, naming the ability.
> (PRD AC-066) **AC-066** Every pattern that starts agents, built-in, saved or written for one task, carries a charter, never empty. Its pattern part says the pattern's purpose and how the pattern meets PS-1 to PS-4. Each role has a part that says its responsibility, its deliverable, what it must not do, whom it reports to and when, whom it may message and why, and how it is expected to behave. A pattern with roles whose charter or any role part is missing is refused at start, naming it; no smaller team runs instead. A record with no roles, such as BP-1 solo, starts no agent and carries no charter, and the run checks no charter part on it (decided by the agent, grill log row of 2026-10-06 on audit round 16). A pattern written for one task has no record: it reaches the run in the fields of a pattern record, with its charter, and the run checks it as it checks a record with roles; a pattern written for one task with no roles carries no charter, and the run's charter files are the only copy of a one-task charter (decided by the agent, grill log row of 2026-10-06 on audit round 17). The charter's quality is an instruction to the agent that builds the pattern, not a check (decided by the agent, grill log row of 2026-10-06 on the pattern charter, C1).
> (PRD AC-069) **AC-069** Reporting up: each role sends its report target progress as a message at each milestone its charter names, at once on a blocker or a question, and finished at the end. Reporting down: a report target sends the roles that report to it only answers to their questions and data their current duty uses, never an instruction, a new duty or a stop, since every duty comes in the launch prompt (settled, S-150) and only the contact agent stops an agent (AC-009). A report target that wants a role's work changed or stopped asks its own report target, up to the contact agent, which stops the agent and starts a new one with the duty in its launch prompt. A role and its report target, whoever it is (another role, the agent that asked, or the contact agent), may message each other both ways with no declaration, and no other pair may without a declared edge; siblings message each other only along declared edges (AC-035) (decided by the agent, grill log row of 2026-10-06 on the pattern charter, C4, and the row of 2026-10-06 on audit round 15).

## Parent PRD
docs/afk/agent-team-topology/PRD.md

## Parent SDD
docs/afk/agent-team-topology/SDD.md

## Blocked by
(none)

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality
during implementation, classify per the decision protocol (`DECISIONS.md`,
workflow plugin root): a two-way-door correction is recorded in
`plan/DECISIONS.md` and implemented; a one-way door or a tie exits
`design_conflict` quoting the SDD section + the conflict. Never override off
the record. Parked conflicts route back to `/afk:grill-solution` for a
superseding ADR.
