## Goal
Build the manifest module scripts/team/manifest.py (file name: plan decision D-3): the one place that holds the run manifest's schema, takes the directory mutex, publishes by write-then-rename, serves every read and refuses any agent-state move the lifecycle table does not allow. It also builds the running checkpoint's path from the feature and the role. The slice ends at the module and its tests: who calls it (the team entry script, cleanup, the team skill) are other subtasks.

## Complexity
complex

## Design refs
- SDD: SDD.md#§8 L7 — Module Decomposition — row "Manifest module" binds the public interface
- SDD: SDD.md#§4 L3 — Data Architecture — the run manifest, agent entry, process entry and running checkpoint records
- SDD: SDD.md#§6 L5 — Domain Model — the agent lifecycle table and the invariants on the manifest
- SDD: SDD.md#§7 L6 — Process & Coordination — failure row "Manifest write collision"
- SDD: SDD.md#§9 L8 — Tactical Patterns — manifest validation is hand-written
- ADR: adr/design/0002-enforced-agent-lifecycle.md — the module declares the allowed-next table and refuses an illegal move, naming it
- ADR: adr/design/0003-single-writer-manifest.md — one writer, a directory mutex and write-then-rename

## Scope
- scripts/team/manifest.py
- scripts/team/__init__.py
- scripts/tests/test_team_manifest.py

## Seams
- (none — new module; no SDD §14 or §9b row covers the run manifest, which is new design work per §14 note INV-008)

## Acceptance
- [ ] The module's public interface is record, move and read, and no caller learns of the lock (SDD §8 row "Manifest module")
- [ ] Implements the public interface in SDD §8 row "Manifest module" unmodified, with the schema, the directory mutex, the atomic publish, every read and the transition table inside the module (SDD §8 row "Manifest module")
- [ ] The manifest is one JSON file per feature, keyed by feature identifier, carrying a format version, the owning contact session, the owner generation, a list of agent entries and a list of process entries (SDD §4)
- [ ] A manifest with an unknown format version is treated as a foreign file: not read, not deleted, reported once (SDD §4)
- [ ] Each agent entry carries role, model, state and park-until time, beside the other agent-entry fields of the entity design; a helper subagent has no entry (PRD AC-012)
- [ ] A process entry is keyed by process identifier and carries owner, label and started-at, with no state field (SDD §4)
- [ ] A new contact session adopts an existing manifest by feature identifier and contact session rather than starting a second one: it rewrites the owning contact session and adds 1 to the owner generation under the folder lock (PRD AC-015)
- [ ] The module builds a role's running checkpoint path from the feature and the role, one checkpoint per role per run, so a replacement agent can read it without asking the dead agent (PRD AC-024)
- [ ] The agent state is one of starting, working, parked, finished, lost, cleaned, unkillable, and a new entry starts in starting (SDD §6)
- [ ] Every move the lifecycle table allows succeeds, and every other move raises the refusal, naming the attempted move; cleaned is the only terminal state, and a resume or a replacement is a new entry, never an edge back (SDD §6)
- [ ] The module is the one built guardian of the rule that an agent's state changes only along a table edge (SDD §6)
- [ ] A manifest write never lands on top of another: while the mutex is held the losing writer waits, a stale lock is stolen atomically, and 2 racing writers lose no update (SDD §7)
- [ ] No reader sees a half-written manifest: every write goes to a temporary file that is then renamed (ADR-0003)
- [ ] The move from working, parked, finished or lost to cleaned, and to unkillable when a stop or pane close fails, are legal moves the module accepts (PRD AC-050)
- [ ] Before a resume the old entry can move to cleaned, or to unkillable when its stop fails, and the module offers no edge from the old entry back to starting (PRD AC-056)
- [ ] Manifest validation is hand-written inside the module; no schema library is added (SDD §9)
- [ ] Conforms to ADR-0002 — the module declares the allowed-next table A1 to A7 and refuses an illegal move by name; no silent pattern substitution (ADR-0002)
- [ ] Conforms to ADR-0003 — every write takes the directory mutex and publishes by write-then-rename (ADR-0003)
- [ ] Every artifact in ## Produces exists with its declared contract (SDD §8 row "Manifest module")

- [ ] The run manifest stays in the main checkout's ignored agent directory (S-102); agents write run-directory files through the team script or a shell, never an edit tool, since the protected-branch guard refuses an agent's edit-tool write to any target in the main checkout and is the gate for those writes (SDD §5 row "Write repository configuration")
## Produces
- scripts/team/manifest.py#class TransitionRefused — refusal raised naming the refused move
- scripts/team/manifest.py#def record_entry( — record(entry) under the directory mutex, atomic publish
- scripts/team/manifest.py#def move_entry( — move(agent-id, to) per the transition table
- scripts/team/manifest.py#def read_manifest( — every read of the run manifest

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `python -m py_compile scripts/team/__init__.py scripts/team/manifest.py && grep -n 'class TransitionRefused' scripts/team/manifest.py && grep -n 'def record_entry(' scripts/team/manifest.py && grep -n 'def move_entry(' scripts/team/manifest.py && grep -n 'def read_manifest(' scripts/team/manifest.py` | code builds; the Produces anchors exist |
| unit | `python -m pytest scripts/tests/test_team_manifest.py -q`, cases: every allowed and every refused move; 2 writers racing lose no update; a stale lock is stolen; an unknown format version is reported once and left in place; a new contact session adopts the manifest by feature identifier and contact session (AC-015); the checkpoint path from feature and role | the lifecycle table, the lock and adoption |

## Context excerpts
> (SDD §8 row "Manifest module") | Manifest module | Schema, directory mutex, atomic publish, every read; the transition table | record, move, read; no caller learns of the lock (S-49) | none | Run |
> (SDD §4) | Run manifest | One JSON file, main checkout ignored agent directory (S-9, S-102) | One file per feature (S-11) | None | Deleted by the explicit cleanup step (HL-1) | Format version integer; unknown version = foreign file, not read, not deleted, reported once | No | No |
> (SDD §4) | Running checkpoint | One file per role per run; the script builds its path from the feature and the role (S-239) | Per feature and role | None | Deleted by the same cleanup step | Same version rule | No | No |
> (SDD §4) Run manifest file. Identity: the feature identifier; one per feature, shared by two runs of the same feature (adoption, AC-015).
> (SDD §4) | owning contact session | text | no | the session that created the file | — | adoption rewrites it | — | AC-012, S-11 | — |
> (SDD §4) | owner generation | whole number (S-176) | never empty (S-176) | 1 (S-176) | — | A new contact session that takes over the run adds 1 to it, under the folder lock, when it rewrites the owning contact session (S-176) | — | The owner generation is the takeover counter. Each agent entry copies this value at the start (S-176) | S-176, GEN-1 |
> (SDD §4) | state | one of starting, working, parked, finished, lost, cleaned, unkillable | no | starting | — | legal moves only (§6) | — | HL-4 A1–A7 | — |
> (SDD §4) Process entry. Identity: process identifier within one manifest. No state field: cleanup removes the entry when the kill succeeds; an entry left after cleanup is an unkilled process (I5).
> (SDD §4) Running checkpoint. Identity: feature identifier and role; one checkpoint for each role in each run, at a path the script builds from the feature and the role (S-239). Written by the agent filling the role, published by write-then-rename (S-41). The next agent in that role and the contact agent read it; every other agent is denied, by convention (S-239).
> (SDD §6) **Agent lifecycle (HL-4, signed).** The manifest module declares this table and refuses a write that is not a legal move, naming the attempted move (S-26, S-54). The Source column names the settled rows behind each row added or changed in rounds 40 to 46 (packet HL4-4, table 1, signed R-45; round-46 rows under the delegation, §0); such a row keeps the Meaning signed before round 40, except A7's, which adds the failed pane close (S-225, S-234), and a dash where it has none. A6's Meaning also covers an entry with no process recorded (audit round 8, agent-decided) and a process already gone (audit round 11, agent-decided), and A7's a process whose identity is unknown (audit round 10, agent-decided). A dash in Source marks a row signed before round 40. Each lifespan row states how an agent of that lifespan leaves the table (S-169).
> (SDD §6) Caption: cleaned is the only terminal state. A resume or a replacement is a new entry in starting, never an edge back (S-213); the old line moves to cleaned first, or to unkillable when its stop fails (S-242).
> (SDD §6) | I1 | Every agent and background process a run starts appears in the manifest | Run | The contact agent, writing the entry before the start | Structural for agents; a self-started process is still killed with its owner's tree but is invisible to the report until reported upward | — |
> (SDD §6) | I2 | Only the contact agent writes the manifest | Run | Convention | A violating write succeeds | — |
> (SDD §6) | I3 | An agent's state changes only along a table edge | Run | The manifest writer, which refuses the move | Write refused, move named. The one built guardian | — |
> (SDD §6) | I10 | A manifest write never lands on top of another | Run | Directory mutex, write-then-rename | A losing writer waits | — |
> (SDD §7) | Manifest write collision | mutex held | the loser waits | stale lock stolen atomically | Manifest module |
> (SDD §9) | Manifest validation | Hand-written checks inside the owning module; no schema library (S-56) | — |
> (PRD AC-012) **AC-012** Every team agent and every background process a run starts appears in the run manifest; a helper subagent does not (AC-043). The manifest is keyed by feature identifier and carries the owning contact session, which a new contact session rewrites when it adopts the run (AC-015). Each agent entry carries role, model, state and park-until time.
> (PRD AC-015) **AC-015** A new contact agent adopts an existing manifest by feature identifier and contact session rather than starting a second one.
> (PRD AC-024) **AC-024** A role's running checkpoint is written while the role works, not at the end, and a replacement agent reads it without asking the dead agent for anything.
> (PRD AC-050) **AC-050** When an agent's lifespan ends (LS-1 to LS-3), the contact agent stops the agent, closes its pane and marks its manifest entry cleaned. A stop or a pane close that fails marks the entry unkillable, and a failed close names the pane; run cleanup tries again.
> (PRD AC-056) **AC-056** Before a resume, the contact agent stops the old agent, closes its pane and marks its entry cleaned. When that stop fails, the contact agent marks the entry unkillable, does not resume, and tells the human.
> (PRD Testing Decisions) Prior art: the existing process-tracking state file used by the build-gate app-start path is the closest precedent for the manifest's shape.
> (ADR-0002) The manifest module declares the allowed-next table A1 to A7 and refuses a write that is not a legal move, naming the attempted move (S-26, S-54). It is the only state-transition enforcer in the plugin, and it applies to agent states only.
> (ADR-0003) Only the contact agent writes the manifest; an agent that needs an entry asks it (S-27). Every write takes a directory mutex and publishes by writing a temporary file and renaming it, so no reader sees a half-written kill list (S-10). The mechanism was the agent's call, accepted in round 2; the single writer was the human's (round 8, L5-3).

> (SDD §5 row "Write repository configuration") | Write repository configuration | Human. One stated exception: the contact agent, through agent-start in the team entry script, copies the git-ignored .claude/settings.local.json of the main checkout into the run's worktree (S-191) | Every agent class, for every other configuration write (S-191) | The one allow rule on the team entry script covers the copy. The script never overwrites: when the file exists, it skips the copy and reports that (S-191). A write into the main checkout: the protected-branch guard refuses an agent's edit-tool write to any target there, and any shell command that is not read-only from a session in the main checkout (hooks/lib/protected_branch_guard.py:7-9, :418-457), so the contact session sits in a linked worktree on an unprotected branch (:424-436). Agents write run-directory files through the team script or a shell, never an edit tool, so the manifest stays where S-102 put it (GRILL-LOG.md:745 (7)). Every other configuration write: CONVENTION, no gate refuses it | S-191, SET-1, GRILL-LOG.md:745 (7) |

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
