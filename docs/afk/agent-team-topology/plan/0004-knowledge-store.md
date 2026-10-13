## Goal
Build the knowledge store module scripts/team/knowledge.py (file name: plan decision D-3): it writes entries unfinished, lets only the author's clean exit or a debate-step stamp mark one finished, and filters reads per stage, releasing a peer's debate draft only when a finished draft exists for every debater role of that work item. The slice ends at the module and its tests: deleting the store at cleanup and the debate's resume or replacement are other subtasks.

## Complexity
standard

## Design refs
- SDD: SDD.md#§8 L7 — Module Decomposition — row "Knowledge store module" binds the public interface
- SDD: SDD.md#§4 L3 — Data Architecture — the knowledge-store record and entry fields
- SDD: SDD.md#§6 L5 — Domain Model — the entry lifecycle and the read rule for same-stage peers
- SDD: SDD.md#§7 L6 — Process & Coordination — use case "Read peer knowledge" and failure row "A debater dies with its draft unfinished"
- ADR: adr/requirements/0018-nothing-in-the-knowledge-store-survives.md — nothing in the store survives the run or is promoted

## Scope
- scripts/team/knowledge.py
- scripts/tests/test_team_knowledge.py

## Seams
- (none — new module; no SDD §14 or §9b row covers the knowledge store)

## Acceptance
- [ ] Implements the public interface in SDD §8 row "Knowledge store module" unmodified: write entry, mark finished, read finished, with the entry lifecycle, the finished stamp, the per-stage read filter and the debate release rule per work-item id inside the module (SDD §8 row "Knowledge store module")
- [ ] The store is one file per entry in the ignored agent directory, keyed by feature, and an entry's identity is its author and time together (SDD §4)
- [ ] Every entry carries author, role, model, time and ground; the time is UTC, ISO 8601, to the second (PRD AC-018)
- [ ] An entry is created unfinished; only the authoring agent's clean exit marks it finished, and an entry from an agent that ended early stays unfinished, with nothing repairing it (PRD AC-016)
- [ ] Each debate step's entry (draft, critique, revision, verdict) is finished when its author stamps it, and a verdict entry always carries its reason (PRD AC-016)
- [ ] A verdict entry carries one verdict per agent, AGREE or DISAGREE-FINAL, with its reason; the module emits no single combined verdict or combined findings list (PRD AC-007)
- [ ] Within one stage, a read returns only finished entries from peers; across stages, a later stage reads earlier stages' finished entries (PRD AC-017)
- [ ] In a debate, a peer's draft for a work item is released only when every debater role of that item has a finished draft; a replacement debater's finished draft fills its role and the dead debater's unfinished draft is skipped (PRD AC-017)
- [ ] When a debater dies with its draft unfinished, nothing is released and the read for the other debaters returns no peer draft (SDD §7)
- [ ] The store's location is excluded from version control, and nothing in the module promotes an entry to another record (PRD AC-019)
- [ ] Conforms to requirement ADR-0018 — nothing in the knowledge store survives the run or is promoted first; no silent pattern substitution (requirement ADR-0018)
- [ ] Every artifact in ## Produces exists with its declared contract (SDD §8 row "Knowledge store module")

## Produces
- scripts/team/knowledge.py#def write_entry( — write an unfinished entry with author, role, model, time, ground
- scripts/team/knowledge.py#def mark_finished( — only the author's clean exit marks it finished
- scripts/team/knowledge.py#def read_finished( — per-stage read filter; a peer's draft only when a finished draft exists for every debater role

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `python -m py_compile scripts/team/knowledge.py && grep -n 'def write_entry(' scripts/team/knowledge.py && grep -n 'def mark_finished(' scripts/team/knowledge.py && grep -n 'def read_finished(' scripts/team/knowledge.py` | code builds; the Produces anchors exist |
| unit | `python -m pytest scripts/tests/test_team_knowledge.py -q`, cases: an unfinished entry is hidden from a peer; the debate release happens only when every debater role has a finished draft; an entry from an agent that ended early stays unfinished; a replacement's finished draft fills the role; a verdict entry without a reason is refused | the entry lifecycle and the read filter |

## Context excerpts
> (SDD §8 row "Knowledge store module") | Knowledge store module | Entry lifecycle, finished stamp, per-stage read filter, the debate release rule per work-item id, counting roles (S-138, S-193) | write entry, mark finished, read finished; a peer's draft only when a finished draft exists for every debater role (S-193) | none | Knowledge store |
> (SDD §4) | Knowledge store | One file per entry, ignored agent directory, keyed by feature (S-9) | Per run of one feature | None | Deleted by the explicit cleanup step that closes desktop-tool terminals (S-12); never promoted (S-14, S-87) | Same version rule | No | No |
> (SDD §4) Knowledge-store entry. Identity: author and time together; entries are appended, never looked up.
> (SDD §4) | finished | true or false | no | false | — | K1 to K2 on the author's clean exit; a debate-step entry moves to K2 when its author stamps it | — | AC-016 | S-138, DEB-2, AC-016 |
> (SDD §4) | verdict | one of AGREE, DISAGREE-FINAL | yes; set only on a verdict entry | null | — | Only when debate step is verdict | — | Per-agent verdict (AC-007) | S-137, DEB-1, AC-007 |
> (SDD §4) | reason | text | Required on a verdict entry. Optional on draft, critique and revision entries. Empty outside a debate (S-175) | empty (null) (S-175) | — | Required when debate step is verdict | — | — | S-137, DEB-1 |
> (SDD §6) | K1 | unfinished | Being written; no same-stage peer reads it; an early-ended author leaves it here, and nothing repairs it | K2 | The authoring agent, on creating it | — |
> (SDD §6) | K2 | finished | Readable by same-stage peers and later stages. A debate draft is readable by a peer debater only when a finished draft exists for every debater role of the work item. The rule counts roles, not agents, so a replacement debater's finished draft fills its role (S-193). Terminal until deletion | terminal | The authoring agent's clean exit; for a debate-step entry, its author's stamp | S-138, DEB-2, AC-016 |
> (SDD §6) | I4 | A same-stage peer reads an entry only when finished. A debater reads a peer's draft for a work item only when a finished draft exists for every debater role of that item (release rule; roles, not agents) (S-193). The work-item id, not the stage, governs reads between debate steps | Knowledge store | The reader's finished filter; for the release rule, the read of finished entries in the knowledge store module (S-193) | Nothing read; an orphan is skipped for ever. When a debater dies with its draft unfinished, nothing is released and the other debaters wait. The contact agent notices the death (the entry moves to lost). It first starts a new pane that resumes the dead debater's harness session (S-213); if that fails, it starts a replacement on the same model, as a new entry that reads the role's checkpoint. When no replacement can start, the debate waits; past the provider's wait limit, it parks with a dated report. The dead agent's unfinished entry is skipped for ever (S-193) | S-138, DEB-2, AC-017 |
> (SDD §7) | Read peer knowledge | An agent | None | Filtered to finished entries (S-45) | One file per entry |
> (SDD §7) | A debater dies with its draft unfinished | the entry moves to lost (S-193) | nothing is released; the other debaters wait. Resume first; else a replacement on the same model reads the role's checkpoint. When no replacement can start, the debate waits, and past the provider's wait limit it parks with a dated report (S-193, S-213) | human decides | Contact agent |
> (PRD AC-007) **AC-007** In a debate, no agent sees another agent's output for the same piece of work before writing its own. Agreement is reported per agent, each verdict with its reason; no single combined verdict or combined findings list is emitted.
> (PRD AC-016) **AC-016** A knowledge-store entry is created unfinished. Only the authoring agent's clean exit marks it finished. An entry from an agent that ended early stays unfinished. In a debate, each debater role keeps its model for the whole debate: a debater that dies is resumed, or replaced on the same model (AC-055) *(unverified premise: a harness session killed in the middle of a turn resumes cleanly from its session id, and Codex reports a session id at start)*. Each debate step's entry (draft, critique, revision, verdict) is finished when its author stamps it, and a verdict always carries its reason.
> (PRD AC-017) **AC-017** Within one stage, an agent reads only finished entries from its peers. In a debate, a peer's draft for a work item is released only when every debater role of that item has a finished draft. A replacement debater's finished draft fills its role, and the dead debater's unfinished draft is skipped. While a debater role has no finished draft and no replacement can start, the debate waits (AC-022, AC-023). Across stages, a later stage reads earlier stages' finished entries.
> (PRD AC-018) **AC-018** Every knowledge-store entry carries author, role, model, time and ground.
> (PRD AC-019) **AC-019** The knowledge store is excluded from version control and is deleted when the run's artifacts are cleaned up. Nothing in it survives the run, and nothing is promoted to another record first (ADR-0018).
> (requirement ADR-0018) The knowledge store is excluded from version control and deleted with the run, and nothing in it is promoted to another record first. Each run detects its environment again, as detection reads the session it is in, not the machine. This supersedes ADR-0002, whose consequence promoted qualified environment facts into a durable register before deletion.

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
