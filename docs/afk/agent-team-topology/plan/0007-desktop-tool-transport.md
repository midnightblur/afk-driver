## Goal
Add the desktop-tool transport kind (TR-4) under adapters/transport/desktop/ and its 1DevTool recipe adapters/transport/desktop/1devtool.md (file names: plan decision D-3). The trial that finds the tool's delivery ways and tab support runs first and is recorded as a probe row in providers/CONFORMANCE.md; no kind code is written before it. The kind answers agent-list with exit 3, keeps the process id as its handle and the terminal identifier as its own field, and closes a terminal by that identifier inside agent-stop. The slice ends at the kind and its recipe: cleanup's use of the close and the other kinds are other subtasks.

## Complexity
standard

## Design refs
- SDD: SDD.md#§9b External Seams & Failure Affordance — rows "Desktop-tool terminal close verb (TR-4)" and "1DevTool delivery and tabs"
- SDD: SDD.md#§3 L2 — Service Boundaries & Integration — agent-list's exit 3 for a kind whose handle is not a pane id
- SDD: SDD.md#§4 L3 — Data Architecture — the agent entry's handle and terminal identifier fields
- SDD: SDD.md#§13 Open Questions — Q2, Q21 (desktop part), V29, V32
- ADR: adr/design/0011-recipe-per-multiplexer-tool.md — one recipe file per tool; tabs follow the recipe

## Scope
- adapters/transport/desktop/**
- providers/CONFORMANCE.md
- scripts/tests/test_team_transport_desktop.py

## Seams
- (none — the §9b rows this slice touches, "Desktop-tool terminal close verb (TR-4)" and "1DevTool delivery and tabs", have no §14 row; their seam-tests are in ## Verification)

## Acceptance
- [ ] Before any kind code is written, the trial of the desktop tool finds its delivery ways and tab support and is recorded as a probe row in providers/CONFORMANCE.md (SDD §13 V32)
- [ ] The 1DevTool recipe states how detection recognises the tool, how each of the six verbs maps to its commands, its best delivery way and tab support as the trial found them, and its known traps (SDD §9b row "1DevTool delivery and tabs")
- [ ] The trial's findings on delivery say which agents use an inbox on this tool, and until resume is proven an empty session id means a fresh agent reads the checkpoint (SDD §13 Q21)
- [ ] A desktop tool that cannot make tabs uses panes and says so at run start; when a tool that can make tabs fails to make one, the start is refused, naming the tab (PRD AC-054)
- [ ] The tool takes the same message commands as every other tool and delivers in the best way it offers; where it can deliver without touching an input box, it delivers that way, to the contact agent too (PRD AC-057)
- [ ] The TR-4 kind answers agent-list with exit 3, unsupported, since its handle is not a pane id (SDD §3)
- [ ] The TR-4 kind's handle is the process id, and the terminal identifier is its own field, returned in agent-start's answer (SDD §4)
- [ ] agent-stop closes a TR-4 terminal by its recorded terminal identifier; a failed close answers pane closed false and names the terminal identifier in place of the pane id (SDD §9b row "Desktop-tool terminal close verb (TR-4)")
- [ ] On TR-4, every terminal the manifest records can be closed by its recorded identifier, and a terminal that could not be closed is reported by name (PRD AC-031)
- [ ] The close verb rests on the tool's documentation until the live trial runs, and a verb that differs from the documented one is recorded against row E3 (SDD §13 Q2)
- [ ] Before the desktop tool's transport code merges, the environment-gated TR-4 verb test runs with the tool open and terminal attach on (SDD §13 V29)
- [ ] Conforms to ADR-0011 — one recipe file for the tool in its kind's folder; tabs follow the same recipe; no silent pattern substitution (ADR-0011)
- [ ] Every artifact in ## Produces exists with its declared contract (SDD §9b row "1DevTool delivery and tabs")
- [ ] The seam-test for the close verb asserts on the tool's real output: a terminal recorded by identifier is gone after agent-stop (SDD §9b row "Desktop-tool terminal close verb (TR-4)")

## Produces
- adapters/transport/desktop/1devtool.md#Delivery ways — the 1DevTool recipe from the S-214 trial
- adapters/transport/desktop/transport.sh#verb_agent_stop — TR-4 kind; agent-stop closes a terminal by its recorded identifier

## Consumes
- 0006-transport-family-and-herdr adapters/transport/multiplexer/herdr.md#Known traps (herdr) — the recipe file shape to follow

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `bash -n adapters/transport/desktop/transport.sh && grep -n 'Delivery ways' adapters/transport/desktop/1devtool.md && grep -n 'verb_agent_stop' adapters/transport/desktop/transport.sh` | code parses; the Produces anchors exist |
| unit | `python -m pytest scripts/tests/test_team_transport_desktop.py -q`, cases: agent-list answers exit 3; a tool with no tabs reports panes at run start; the handle is the process id and the terminal identifier its own field | the kind's answers |
| integration | Environment-gated on the desktop tool open with terminal attach on: the trial S-214 names, recorded as a probe row in providers/CONFORMANCE.md before any kind code is written | V32; seam-test for the row "1DevTool delivery and tabs" |
| integration | Environment-gated on the desktop tool open with terminal attach on: the TR-4 verb test closes a terminal by its recorded identifier inside agent-stop | V29; Q2; seam-test for the row "Desktop-tool terminal close verb (TR-4)" |

## Context excerpts
> (SDD §9b row "Desktop-tool terminal close verb (TR-4)") | Desktop-tool terminal close verb (TR-4) | The installed desktop tool | Closes a terminal by recorded identifier; runs inside agent-stop (S-234) — unverified premise (AS-1, E3): the verb was read from the installed tool's help and never run here, since the live trial needs the desktop tool open with terminal attach on (GRILL-LOG.md:10, :24) | Close fails → named in the cleanup report | Environment-gated TR-4 verb test (PRD Testing Decisions); §13 V29; the live trial is pending |
> (SDD §9b row "1DevTool delivery and tabs") | 1DevTool delivery and tabs | The installed desktop tool | Delivery ways and tab support not known (S-214) — unverified premise: no trial of the tool has run here; its command is not on this machine's path and its connection was down (GRILL-LOG.md:24) | A tool that cannot make tabs uses panes and says so at run start (S-211) | A trial finds its delivery ways and tab support before its code is written (S-214); §13 V32 |
> (SDD §3) exit 3 unsupported where the kind cannot enumerate; cleanup then skips the stray list, and its report says that the kind cannot list agents (audit round 3, agent-decided). A kind whose handle is not a pane id, TR-4 included, answers exit 3 too (audit round 4 and audit round 5, agent-decided)
> (SDD §4) | handle | text | no | none | — | from agent-start | — | For a pane kind, a transport kind that opens panes, the handle is the pane id: cleanup closes the pane by it, and an unkillable line names the pane by it (S-225; audit L14, agent-decided). For a kind that opens no panes, TR-4 included, the handle is the process id, and TR-4's terminal identifier stays its own field (audit round 7, agent-decided). Unverified: that a TR-1 child, whose harness owns its lifecycle (PRD transport TR-1), has a process id the script can read | S-225; audit L14, audit round 7 (agent-decided) |
> (SDD §4) | terminal identifier | text | yes | empty | — | TR-4 only; from agent-start's answer, and the contact agent writes it with kind and handle (audit round 8, agent-decided) | — | AC-031: agent-stop closes the terminal by it (audit round 8, agent-decided), and its answer reports that close in pane closed and names this identifier in place of the pane id, so a failed close reaches unkillable and the cleanup report (audit round 9, agent-decided) | audit round 8, audit round 9 (agent-decided) |
> (SDD §13 Q2) Q2: Row E3 and TR-4 rest on the desktop tool's close verb, read from documentation, never run (PRD AS-1). A differing verb voids HL-5 E3 by the drift rule
> (SDD §13 Q21) Q21: Trials owed. Probe 2026-09-30 (providers/CONFORMANCE.md:440) passed on both harnesses: a blocked pane agent took a relayed answer, and a session resumed in a new pane kept its context; on Codex the resume worked only when typed with herdr pane run. Still owed before the resume design binds: how Codex sets a session id at start, whether a session killed in the middle of a turn resumes cleanly, and a resumed session's permissions (S-213, HL3-3). Before the desktop tool's code is written: 1DevTool's delivery ways and tab support; its delivery may change which agents use an inbox (S-214, HL1-6). Delivery to other agents is proven for herdr only (T11; providers/CONFORMANCE.md:439). Until then an empty session id means a fresh agent reads the checkpoint (S-219, S-233)
> (SDD §13 V29) V29: Whether the desktop tool's terminal close verb (TR-4) closes a terminal by its recorded identifier inside agent-stop. The verb was read from the tool's help and never run here (PRD AS-1; GRILL-LOG.md:10, :24). Without it the design still works: a failed close is named in the cleanup report (PRD AC-031), and herdr is the transport the probes ran. §9b row 'Desktop-tool terminal close verb (TR-4)'. Proven at build by: the environment-gated TR-4 verb test (PRD Testing Decisions), run with the tool open and terminal attach on
> (SDD §13 V32) V32: Which delivery ways the 1DevTool desktop tool offers and whether it makes tabs; no trial has run here (S-214; GRILL-LOG.md:24). Without it the design still works: the tool's code is not written until the trial finds both (S-214), and a tool that cannot make tabs uses panes and says so at run start (S-211). §9b row '1DevTool delivery and tabs'. Proven at build by: the trial S-214 names, recorded as a probe row in providers/CONFORMANCE.md
> (PRD Catalog) | TR-4 | Desktop-tool terminals | The tool starts its own terminal | The tool's own close-by-id, per recorded terminal | Supported *(unverified premise: the desktop tool's start, team-stop and terminal-close verbs work on this machine — read from the installed binary's own help, never run)* |
> (PRD AC-031) **AC-031** On TR-4, cleanup closes each terminal recorded in the manifest by its recorded identifier, and reports by name any terminal it could not close *(unverified premise: the desktop tool's start, team-stop and terminal-close verbs work on this machine — read from the installed binary's own help, never run)*.
> (PRD AC-054) **AC-054** A tool that cannot make tabs uses panes and says so at run start. When a tool that can make tabs fails to make one, the start is refused, naming the tab. On a tool that can make tabs, no pane agent opens in the contact agent's tab.
> (PRD AC-057) **AC-057** Every tool takes the same message commands. Each tool delivers a message in the best way that tool offers. A tool that can deliver without touching an agent's input box delivers that way, to the contact agent too.
> (PRD AS-1) **AS-1 (unverified premise: the desktop tool's team-stop and terminal-close verbs work on this machine).** TR-4's commands were read from the installed binary's own help and have never been run here. The live trial is blocked on the desktop application being open with local terminal attach enabled. Graded surface-verified and trial-pending by explicit human decision (ADR-0008). Requirements resting on TR-4 — the TR-4 row of the transport catalog, and AC-013's coverage of TR-4 — inherit this label. TR-1 through TR-3 do not. The desktop tool's message delivery and tab support are also untried; a trial finds them before its code is written, and AC-035 and AC-054 cover a tool that lacks them.
> (ADR-0011) Each tool gets one recipe file in its transport kind's folder (S-168). The recipe states how detection recognises the tool in this session, how each of the six verbs maps to the tool's commands, and the tool's known traps from its trial log (S-168). The pane close runs inside agent-stop, so the contract keeps six verbs (S-234). Agents call only the team entry script. Its error output and the pane-agent rule point at the recipe for the tool in use (S-168). The command contract is the same for every tool. Each recipe names the tool's best delivery way, and the tool's code uses it; a tool that can deliver without touching the input box uses that way, also for the contact agent (S-214). Tabs follow the same recipe; a tool that cannot make tabs uses panes and says so at run start (S-211).

## Parent PRD
docs/afk/agent-team-topology/PRD.md

## Parent SDD
docs/afk/agent-team-topology/SDD.md

## Blocked by
0006-transport-family-and-herdr

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality
during implementation, classify per the decision protocol (`DECISIONS.md`,
workflow plugin root): a two-way-door correction is recorded in
`plan/DECISIONS.md` and implemented; a one-way door or a tie exits
`design_conflict` quoting the SDD section + the conflict. Never override off
the record. Parked conflicts route back to `/afk:grill-solution` for a
superseding ADR.
