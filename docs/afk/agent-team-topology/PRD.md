# Agent team topology and multi-model

## Problem Statement

A run is one agent on one model. Work that needs independent thinking — research, grounding, design, planning, review, audit — gets one opinion, and the reader cannot tell a checked answer from a confident wrong one.

Concrete pains:

- One model's blind spot becomes the run's blind spot. Nothing disagrees, so nothing surfaces.
- A provider usage limit halts work another provider could carry. The human returns hours later to a run that stopped.
- Nothing records what a run started. A failed or finished run can leave agents and background processes alive on the machine, and a live trial proved a parent's exit does not take its children with it.
- When an agent dies mid-work, what it learned dies with it. The replacement starts cold, and the dying agent cannot be asked for a handoff — that request is exactly what an exhausted provider refuses.
- A user who wants a second model on a role has no way to ask for one.

## Solution

A run may use a **team** of agents instead of one, shaped by a **pattern**: which roles exist, which model fills each, how long each lives, and which roles may talk to each other directly. Team patterns and multi-model are optional and independent.

Whenever the plugin is enabled and a pane transport is found, every agent that does a role's work starts as a **pane agent**: an agent that writes a plugin artifact, code or a ledger, or returns a gate verdict. An agent that only reads and returns text to its parent is a **helper subagent**, which a pane agent starts for itself to keep its own context small. One configuration key switches role agents back to subagents (ADR-0013). Pane agents open in tabs apart from the contact agent, at most 4 to a tab. Each is named by its goal, role, model and effort.

One **contact agent** is the only agent the human talks to, and the only agent that starts and stops team agents; another agent that needs one sends it a start request. Agents are started through a **transport** — the mechanism that starts, messages, reads and closes an agent. Everything a run starts is written to a **run manifest**, so cleanup can kill it and a dashboard can show it. The contact agent stops each agent and closes its pane when the agent's lifespan ends. An agent that dies is resumed in its own harness session first, and replaced from its checkpoint only when that fails. Agents write a **knowledge store** as they work, so a later stage reads what an earlier stage learned. It is deleted when the run ends, and nothing in it is kept (ADR-0018).

A pattern is a reusable team shape. It knows nothing of the workflow; its description says how and when it is useful. The contact agent reads the descriptions and proposes patterns for the task, possibly several combined, and the human picks. The plugin ships five built-in patterns and no stage map. Every pattern that starts agents meets the **pattern standard** (the 4 properties PS-1 to PS-4): duties kept apart, independent checks, several angles on a problem, and maximum autonomy. Inside a team, agents message each other directly along the talk edges the pattern declares. A role's result goes to its **report target** (the agent named to receive it), by default the agent that asked for the role (ADR-0015). The contact agent gets a copy of each finished, parked and exited message to keep the manifest. It reads a result only when it is the target.

The rules on which agent may start agents, commit, open a change request or write the tracker hold by convention. Each agent's brief states them. No runtime check can tell one agent from another, so the run does not refuse a break of these rules (ADR-0016).

Roles may run on models from different providers. When a provider fails, a single-model role continues on an equivalent model from another provider; a debate role waits, because substituting one side of a debate destroys the debate.

## Catalog

### Transports

| ID | Transport | Start | Cleanup | Status |
|----|-----------|-------|---------|--------|
| TR-1 | Harness subagents | The harness spawns its own child | Harness owns the lifecycle | Supported |
| TR-2 | Headless runs | The plugin starts the process | Operating-system job owns the process tree | Supported |
| TR-3 | Multiplexer panes | The plugin starts a pane | Job where the start is owned; pane close otherwise | Supported |
| TR-4 | Desktop-tool terminals | The tool starts its own terminal | The tool's own close-by-id, per recorded terminal | Supported *(unverified premise: the desktop tool's start, team-stop and terminal-close verbs work on this machine — read from the installed binary's own help, never run)* |

With no pane transport found, or with the switch set back, role agents and patterns run on TR-1 and the run report says so. A TR-1 agent returns its report as text, and the agent that started it writes the file; Claude Code refuses a report file written by a subagent.

### Agent classes and permissions

| ID | Class | May start agents | May commit and push | May open a change request | May merge | May write the tracker | May write repository configuration |
|----|-------|------------------|---------------------|---------------------------|-----------|----------------------|-------------------------------------|
| AC-H | Human | — | Yes | Yes | **Yes, only** | Yes | Yes |
| AC-C | Contact agent | **Yes, only** | Yes | Yes | No | Per existing tracker rules | Only the settings copy (AC-064) |
| AC-S | Spawned agent | No | Only in the builder role, on the feature branch; the `/afk:bug` fixer on its own fix branch (AC-060) | Only the `/afk:bug` fixer (AC-060) | No | Only the `/afk:bug` publisher (AC-060) | No |
| AC-B | Non-contact hub role | No | No | No | No | No | No |

These rules hold by convention: each agent's brief states them, and no runtime check can tell one agent from another (ADR-0016).

### Role lifespans

| ID | Lifespan | Closed when |
|----|----------|-------------|
| LS-1 | Turn | The role sends finished for its one exchange |
| LS-2 | Step | The pattern step that needs the role ends: every agent the step started has sent finished or is lost |
| LS-3 | Feature | The run ends |

At a lifespan's end, the contact agent stops the agent and closes its pane (AC-050).

### Built-in patterns

| ID | Pattern | Agents started | Shape | Its description says it helps with |
|----|---------|----------------|-------|-------------------------------------|
| BP-1 | solo | 0 | The contact agent does the work itself | Mechanical work; synthesis of the human conversation |
| BP-2 | debate | 2-3, plus a moderator | Blind drafts, cross-critique, revise, a verdict per agent | Research, grounding, design options, scenario design; audit of a written draft |
| BP-3 | build-verify | 4 | 1 builder, 2 reviewers on different models, 1 verifier | One unit of build work: tests first, verification, review |
| BP-4 | review-panel | 2-3, plus a moderator | Reviewers review one finished change blind, then critique each other | A review after a unit of work, a final review, an audit of a written draft |
| BP-5 | afk-lite | 7 | 1 orchestrator hub, 2 planners, 1 builder, 1 verifier, 2 reviewers | A bug fix or small enhancement, end to end |

### Pattern standard

The human's direction, 2026-09-30: every pattern, built-in or written for one task, is designed to meet all 4 properties, and every agent that builds a pattern knows them. The right-hand column is the agent's testable reading of that direction, decided under the same day's delegation and not yet audited by the human.

| ID | Property | A pattern meets it when |
|----|----------|-------------------------|
| PS-1 | Segregation of duty | The role that produces a piece of work never checks it |
| PS-2 | Independent cross-check and audit | At least 1 agent that did not produce a piece of work checks it, and each checker writes its first findings before it sees another checker's |
| PS-3 | Several angles on a problem | A problem that needs thinking gets at least 2 agents that differ in model or in brief |
| PS-4 | Maximum autonomy | The team runs to its end without the human, stops only at the stops its description names, and decides and records everything else |

BP-1 solo starts no agent, so the standard does not bind it (agent-decided). Where solo drafts a document, the audit AC-006 requires meets the standard.

## User Stories

1. As a developer, I want deep-thinking work done by two models that critique each other, so that I see a real disagreement instead of one model's confident guess.
2. As a developer, I want a run to survive one provider's usage limit, so that I do not come back to work that stopped hours ago.
3. As a developer, I want every agent to stop as soon as its job is done, and everything a run started to be killed when the run ends, so that nothing is left running on my machine.
4. As a developer, I want to describe my own team shape for one task, so that I am not limited to the shapes that shipped.
5. As a developer, I want to see what each agent in a run is doing and which are parked, so that a waiting team does not look like a hung one.
6. As a developer, I want a lighter team for a bug fix or a small enhancement that still grounds, designs, debates, verifies and tests on its own, so that small work is checked too without me driving each step.
7. As a developer, I want to combine built-in patterns for one task, so that I get, for example, two models verifying a build independently without writing a new pattern.
8. As a developer, I want every agent that does role work to run where I can see it, in tabs apart from the agent I talk to and named for what it does, so that I can watch it, read its output and stop it, and it can write its own files.
9. As a developer, I want every team shape to keep duties apart, check work independently, look at a problem from several angles and run without me wherever it can, so that I can trust what a team hands back.
10. As a developer, I want an agent that dies mid-work to pick up where it stopped, so that its work and what it learned are not lost.

## Acceptance Criteria

- [ ] **AC-001** With no team pattern and no multi-model configured, and with role agents switched back to subagents or no pane transport found, a run behaves as it did before this feature: one agent, one model, no manifest, no knowledge store. One difference: a subagent's report file is written by the agent that started it (AC-044).
- [ ] **AC-002** Team topology and multi-model are independently switchable; all four combinations run.
- [ ] **AC-003** A pattern is accepted as data, whether it shipped with the plugin or the user wrote it, and a user-written pattern may declare every field a built-in one declares.
- [ ] **AC-004** A pattern may be used once without being saved. It is never written to repository configuration; the run keeps one resolved copy in its run directory, excluded from version control and deleted at cleanup.
- [ ] **AC-005** A pattern whose role cannot be filled is **refused at start**, naming the unfillable role. A pattern with every role fillable starts. No reduced shape runs in place of a refused one.
- [ ] **AC-006** Research, grounding, design, planning, review and audit work runs the debate pattern with two agents or more on different models. For the PRD, the design document and the plan, the contact agent writes the draft, and two agents on different models audit it blind and debate their findings; that audit is the debate.
- [ ] **AC-007** In a debate, no agent sees another agent's output for the same piece of work before writing its own. Agreement is reported per agent, each verdict with its reason; no single combined verdict or combined findings list is emitted.
- [ ] **AC-008** All agents in a run work in one worktree, created once per feature or bug. A run never creates a worktree per agent.
- [ ] **AC-009** Only the contact agent starts or stops a team agent. Every other agent's brief forbids a direct start or stop; the agent sends a start request instead (AC-042). A start request whose requester is not a live agent in the run manifest is refused. Nothing refuses a direct start or stop by a pane agent at runtime (ADR-0016).
- [ ] **AC-010** A run uses one feature branch in its one worktree. Two kinds of spawned agent commit and push: the builder, one at a time, on the feature branch (ADR-0010), and the `/afk:bug` fixer, on its own fix branch (AC-060). Each builder commit names the role it came from. Under `/afk:fix`, the caller commits instead of the builder (AC-037). Under `/afk:autopilot`, the agent that runs a subtask is the builder: it commits, pushes and updates the change request's checklist. There, the contact agent pushes the feature branch and then opens the Draft change request, before the first subtask starts (decided by the agent, grill log row of 2026-10-05 on the design audit, L20). No spawned agent other than the `/afk:bug` fixer opens a change request. No agent force-pushes or deletes a remote branch; the builder corrects a bad push with a new commit. No agent merges. These rules hold by convention (ADR-0016).
- [ ] **AC-011** No spawned agent writes repository configuration or the tracker. One exception: the `/afk:bug` publisher writes the tracker within its grant (AC-060). No agent writes repository configuration except through the contact agent's settings copy (AC-064). These rules hold by convention (ADR-0016).
- [ ] **AC-012** Every team agent and every background process a run starts appears in the run manifest; a helper subagent does not (AC-043). The manifest is keyed by feature identifier and carries the owning contact session, which a new contact session rewrites when it adopts the run (AC-015). Each agent entry carries role, model, state and park-until time.
- [ ] **AC-013** Cleanup kills every process the manifest names and closes every pane the run opened. It reports by name every process it could not kill and every pane still open. It stops no agent the manifest does not name; it lists each one it finds, by name and pane, in its report, and the human stops it (decided by the agent, grill log correction of 2026-10-05 for audit round 3). Before a kill, cleanup checks that the recorded identifier still names the recorded process. On a mismatch, or when no process has that identifier, it kills nothing, removes the entry and reports it as already gone; it moves an agent's entry to cleaned instead of removing it (decided by the agent, grill log row of 2026-10-05 on audit round 12). When the manifest records no start time for the process, cleanup cannot make that check and kills nothing: when no live process has the identifier, it moves the entry to cleaned and reports it as already gone; when a live process has it, it reports that process by name as one it could not kill, and a later cleanup moves the entry to cleaned once the human has stopped it (decided by the agent, grill log row of 2026-10-05 on audit round 10; moved to cleaned: the row on audit round 12). A phase does not report finished while the manifest holds an unkilled process. Its coverage of TR-4 rests on an unverified premise *(unverified premise: the desktop tool's start, team-stop and terminal-close verbs work on this machine — read from the installed binary's own help, never run)*.
- [ ] **AC-014** A background process started by an agent and never registered is still killed when its owning agent's process tree is closed.
- [ ] **AC-015** A new contact agent adopts an existing manifest by feature identifier and contact session rather than starting a second one.
- [ ] **AC-016** A knowledge-store entry is created unfinished. Only the authoring agent's clean exit marks it finished. An entry from an agent that ended early stays unfinished. In a debate, each debater role keeps its model for the whole debate: a debater that dies is resumed, or replaced on the same model (AC-055) *(unverified premise: a harness session killed in the middle of a turn resumes cleanly from its session id, and Codex reports a session id at start)*. Each debate step's entry (draft, critique, revision, verdict) is finished when its author stamps it, and a verdict always carries its reason.
- [ ] **AC-017** Within one stage, an agent reads only finished entries from its peers. In a debate, a peer's draft for a work item is released only when every debater role of that item has a finished draft. A replacement debater's finished draft fills its role, and the dead debater's unfinished draft is skipped. While a debater role has no finished draft and no replacement can start, the debate waits (AC-022, AC-023). Across stages, a later stage reads earlier stages' finished entries.
- [ ] **AC-018** Every knowledge-store entry carries author, role, model, time and ground.
- [ ] **AC-019** The knowledge store is excluded from version control and is deleted when the run's artifacts are cleaned up. Nothing in it survives the run, and nothing is promoted to another record first (ADR-0018).
- [ ] **AC-020** No availability or quota check runs before or during a run. A provider failure is detected when a call fails, never predicted.
- [ ] **AC-021** Authentication is checked once per provider before the first spawn. A provider that fails authentication is reported before any agent starts; one that passes is not re-checked during the run.
- [ ] **AC-022** On a provider failure, a single-model role continues on an equivalent model from another provider, where the tier map supplies one. A debate role does not substitute; it waits.
- [ ] **AC-023** Beyond the provider's wait horizon the run parks and writes a dated report naming the provider, the role and the time it parked. It does not continue in a reduced shape.
- [ ] **AC-024** A role's running checkpoint is written while the role works, not at the end, and a replacement agent reads it without asking the dead agent for anything.
- [ ] **AC-025** A spawned agent receives a written brief and never the contact agent's conversation.
- [ ] **AC-026** Detection reports which agent tools are usable in the **session the human and agents are in**, not merely installed on the machine.
- [ ] **AC-027** A tool whose command is present but whose required setting is disabled is reported as a named fixable setting, not as a missing tool. A tool genuinely absent is reported as absent.
- [ ] **AC-028** Setup offers the optional multiplexer install only when the multiplexer's check command fails. With no human present, setup skips the install and reports it as skipped. After an install, setup runs the check again, reports a failed check as not fixed, and prints the one-line uninstall command. Declining or skipping the install leaves every other transport working.
- [ ] **AC-029** A dashboard reading the manifest distinguishes a parked agent from a hung one, showing the park-until time.
- [ ] **AC-030** On a conflict between configuration and detection, the plugin asks the human when one is present, and parks naming the conflict when none is.
- [ ] **AC-031** On TR-4, cleanup closes each terminal recorded in the manifest by its recorded identifier, and reports by name any terminal it could not close *(unverified premise: the desktop tool's start, team-stop and terminal-close verbs work on this machine — read from the installed binary's own help, never run)*.
- [ ] **AC-032** A pattern carries a description of how and when it is useful and names no workflow stage. The plugin ships no stage map. The human's configuration may map a stage to one pattern, or to a list of patterns combined into one team. With no entry, the contact agent proposes patterns from their descriptions, possibly several combined, and the human picks. With no pattern picked, or no human present, the stage runs as it does today.
- [ ] **AC-033** Patterns combine: a pattern may include other patterns by name, and the pattern that includes owns the link (solution grill S-229); a role may run as a debate on different models. The included patterns' steps follow the including pattern's own steps, in the order of its includes, depth first, and 2 combined patterns that define one role name differently are refused at start (decided by the agent, grill log row of 2026-10-05, Q28). Before any agent starts, the combination becomes one team with one manifest, one set of talk edges and one cleanup, and the contact agent starts every agent. A pattern that includes itself, directly or through others, is refused at start.
- [ ] **AC-034** The plugin ships the built-in patterns BP-1 to BP-5, each a named record with a version.
- [ ] **AC-035** Agents message each other directly only along the talk edges the pattern declares, each edge listing the message types it allows. Every other message is refused, naming the edge. Four paths need no declared edge: every agent may send the contact agent a start request and its own finished, parked and exited messages; the contact agent may message any agent it started; a role's finished message goes to its report target, which the run takes from the manifest and the pattern (decided by the agent, grill log row of 2026-10-05 on the design audit, L5); and a role and its report target, whoever it is, may message each other, both ways (AC-069; decided by the agent, grill log row of 2026-10-06 on the pattern charter, C4, and the row of 2026-10-06 on audit round 15). A pattern that needs a messaging ability the transport lacks is refused at start, naming the ability.
- [ ] **AC-036** Every debate has a moderator agent: the pattern's hub, else one the pattern resolver adds. A pattern whose debate moderator cannot be filled is refused at start, naming the debate.
- [ ] **AC-037** afk-lite runs for `/afk:fix`. In an interactive run it stops for the human after its design step, on a one-way door, and on a DISAGREE-FINAL point; a stop after the design step ends with the status `blocked`, carrying the design. In driven mode no human is present, so the design step does not stop: afk-lite classifies its design per the decision protocol (`DECISIONS.md`, plugin root). A two-way door is recorded in the decision ledger and the run continues. A one-way door or a DISAGREE-FINAL point ends `/afk:fix` with the status `needs_decision`, carrying the design; the caller passes it up unchanged, and `/afk:autopilot` parks the subtask (ADR-0019, decided by the agent). The `/afk:bug` fixer keeps its own stop in every run: blocked, notify, resume (solution grill S-164). Otherwise afk-lite ends where `/afk:fix` ends: changes left uncommitted in the working tree and an `OUTCOME:` line from `/afk:fix`'s status set, which gains `needs_decision` in driven mode only. The caller commits, as it does today (ADR-0014). With role agents switched back to subagents, `/afk:fix` runs in one agent, as it did before this feature.
- [ ] **AC-038** The existing build, review and final-review gates keep their owners. A pattern role inside a gate is a worker that gate calls. A worker may write its own report file that the gate names; no worker writes the gate's other files or its status.
- [ ] **AC-039** No pattern carries an agent, message or spend limit.
- [ ] **AC-040** An agent that does a role's work — it writes a plugin artifact, code or a ledger, or it returns a gate verdict — starts as a pane agent. An agent that only reads and returns text to its parent is a helper subagent.
- [ ] **AC-041** The pane-agent default applies whenever the plugin is enabled and a pane transport is found; nothing needs configuring. One configuration key switches role agents back to subagents. A session without the plugin enabled is unchanged.
- [ ] **AC-042** A role agent that needs another pane agent sends the contact agent a start request. The request names the pattern step, the requester and the lifespan, and lists 1 or more agents, each with a role and a brief. The request's lifespan applies to every agent it lists and wins over the lifespan the pattern gives the role (decided by the agent, grill log row of 2026-10-05 on the design audit, L50). It may name the effort (AC-052). The run refuses a request before delivery and names the failed check. It refuses when: a field is missing or malformed; the request's version is unknown; the step is not in the resolved pattern, unless it is a `solo:` step; a role is not in that step; the lifespan is not Turn, Step or Feature; or a refusal in AC-009, AC-043 or AC-052 applies. A request from a stage with no stage map entry names the step `solo:` followed by the role. The run accepts that step only when the role is a known role agent type, and refuses it from a stage that has a stage map entry (decided by the agent, grill log row of 2026-10-05, Q33). Otherwise the contact agent starts the agents and records them in the run manifest (AC-009). When the contact agent declines, it messages the requester with the request's message id and the reason.
- [ ] **AC-043** A pane agent starts helper subagents for bulk reads, repository searches, test runs and large diffs, to keep its own context small. The plugin's named helper types and model tiers apply to helpers. A helper has no run-manifest entry and starts no agent. A start request past the plugin's 3-level nesting limit is refused.
- [ ] **AC-044** With no pane transport found, or with the switch set back, role agents run as subagents and the run report says so. Such a subagent returns its report as text, and the agent that started it writes the report file.
- [ ] **AC-045** Pane agents meet the gate rules: each review round gets new reviewers that saw nothing of the build; each reviewer returns one findings set, which the review orchestrator merges and numbers; the adversary stays blind to the diff and the tests.
- [ ] **AC-046** No message changes text the human has typed into the contact agent and not sent: a message never goes into the contact agent's input box. Where a tool delivers only by typing into a pane, the contact agent's messages land in its **inbox** (a folder that holds its messages). No other agent has an inbox. Every other agent gets its messages in its pane, and nobody types in those panes. A message that arrives while such a pane holds unsent text is submitted together with that text.
- [ ] **AC-047** The pane-agent rule is stated once, where every session with the plugin enabled reads it; skills point at it.
- [ ] **AC-048** The pattern names each role's report target; where it names none, the target is the agent that asked for the role. A role's result goes only to its report target. The run delivers the role's finished message to the target the manifest and pattern name, whatever target the sender wrote, and a copy to the contact agent (AC-049). When the target cannot be reached, the contact agent passes the result's location to a replacement agent or tells the human.
- [ ] **AC-049** The contact agent gets a copy of every finished, parked and exited message. It uses the copy to keep the manifest, and to pass a result's location on when the target cannot be reached (AC-048). It reads a role's result only when it is that role's report target.
- [ ] **AC-050** When an agent's lifespan ends (LS-1 to LS-3), the contact agent stops the agent, closes its pane and marks its manifest entry cleaned. A stop or a pane close that fails marks the entry unkillable, and a failed close names the pane; run cleanup tries again.
- [ ] **AC-051** Every pane agent has a name of 4 parts: goal, role, model and effort. The goal is the ticket key, else the feature name cut to 16 characters. The effort is lo, med, hi or max. Where two names match, the later ones end in #2, #3 and so on. The pane label is the 4 parts joined by spaces. Where a tool refuses spaces in agent names, the agent name is the 4 parts in lowercase, joined by '-', at most 32 characters, for example `proj-1220-reviewer-opus-hi-2`. In every part each character the tool refuses becomes '-', and a part whose first character is not a lowercase letter gets the prefix `g-` (decided by the agent, grill log row of 2026-10-05 on audit round 2 and the grill log correction of 2026-10-05 for audit round 3); a suffix such as '-2' counts inside the 32 characters, and the goal part is cut first (decided by the agent, grill log row of 2026-10-05 on the design audit, L15). Before that cut, the agent name's model part drops a vendor prefix (`claude-`, `gpt-`), then becomes legal by the rule above, then is cut to 8 characters (decided by the agent, grill log correction of 2026-10-05 for audit round 4 and grill log row of 2026-10-05 on audit round 5), and the pane label carries the same model part (grill log clarification of 2026-10-05 for audit round 5). The prefix `g-` counts inside the 32 characters, and when the role, model, effort and suffix leave no room for 1 goal character, or for `g-` and 1 character when the goal needs `g-`, the start is refused, naming the name (decided by the agent, grill log row of 2026-10-05 on audit round 2 and grill log row of 2026-10-05 on audit round 6). The 3 '-' that join the 4 parts count too: the room for the goal is 32 less 3 and the lengths of the role, the model, the effort and the suffix (decided by the agent, grill log row of 2026-10-05 on audit round 7). The run builds both forms from the start request; no agent types them. The pane label, the manifest entry and the cleanup report use the same name, and the manifest stores both forms.
- [ ] **AC-052** A start request may name the effort the agent runs with. With none, the plugin's model rules choose the effort for that role. The agent's name shows the effort it really runs with. A start request with an unknown effort is refused, naming the field.
- [ ] **AC-053** The contact agent's tab holds only the contact agent. On a tool that can make tabs, each pane agent opens in another tab, which holds at most 4 panes in a 2 by 2 grid. Agents of one pattern step share tabs, and a new tab opens when a tab is full. A tab is named by the goal and the pattern step. A tab closes when its last pane closes.
- [ ] **AC-054** A tool that cannot make tabs uses panes and says so at run start. When a tool that can make tabs fails to make one, the start is refused, naming the tab. On a tool that can make tabs, no pane agent opens in the contact agent's tab.
- [ ] **AC-055** When an agent dies or stops early, the contact agent first resumes the agent's harness session (its own conversation in its tool) in a new pane. Each resume is a new manifest entry with the same session id. With no session id recorded, or when the resume fails, the contact agent starts a fresh agent that reads the role's checkpoint (AC-024) *(unverified premise: a harness session killed in the middle of a turn resumes cleanly from its session id, and Codex reports a session id at start)*.
- [ ] **AC-056** Before a resume, the contact agent stops the old agent, closes its pane and marks its entry cleaned. When that stop fails, the contact agent marks the entry unkillable, does not resume, and tells the human.
- [ ] **AC-057** Every tool takes the same message commands. Each tool delivers a message in the best way that tool offers. A tool that can deliver without touching an agent's input box delivers that way, to the contact agent too.
- [ ] **AC-058** The pattern standard (PS-1 to PS-4) is stated once, where every agent that writes or proposes a pattern reads it. Skills point at it.
- [ ] **AC-059** Every pattern that starts agents, whether built-in or written or proposed by an agent, meets PS-1 to PS-4. Its description says how it meets each property, and so does its charter's pattern part (AC-066; decided by the agent, grill log row of 2026-10-06 on the pattern charter, C1).
- [ ] **AC-060** The `/afk:bug` publisher and fixer keep today's grants as pane agents (ADR-0017). The publisher creates 1 bug ticket, moves it once to Dev-Pending, and adds evidence comments to that ticket. The fixer commits, pushes, opens 1 Draft change request and marks it ready, only on its own fix branch. The fixer never merges. Both grants hold by convention (ADR-0016).
- [ ] **AC-061** A built-in or saved pattern record of an unknown version is refused at start, naming the pattern and the version; no smaller team runs instead. A record of an older, known version is read as it is.
- [ ] **AC-062** Reading configuration refuses 3 errors: a saved pattern that uses a built-in pattern's name; 2 saved patterns with one name; an include or a stage-map entry that names no pattern.
- [ ] **AC-063** Inside the `/afk:bug` fixer, a stop after afk-lite's design step moves the bug to blocked, carrying the design, and sends the developer a push notification. The developer's answer resumes the same fixer with its context. The fixer keeps its lane (the one slot for a live fixer) while blocked.
- [ ] **AC-064** Before the first agent starts in a worktree the run created, the contact agent copies the main checkout's git-ignored local settings file (`.claude/settings.local.json`) into that worktree. The copy never overwrites: when the file exists, the contact agent skips the copy and reports that. A failed copy leaves no partial file and starts no agent, and the error names the copy. To recover, the human copies the file or fixes the cause, and the contact agent starts the agent again. Deleting the copied file undoes the copy.
- [ ] **AC-065** The contact agent handles an inbox message without the human's help where its harness can wake it. Where the harness cannot, the contact agent says so at run start and handles its inbox at its next turn.
- [ ] **AC-066** Every pattern that starts agents, built-in, saved or written for one task, carries a charter, never empty. Its pattern part says the pattern's purpose and how the pattern meets PS-1 to PS-4. Each role has a part that says its responsibility, its deliverable, what it must not do, whom it reports to and when, whom it may message and why, and how it is expected to behave. A pattern with roles whose charter or any role part is missing is refused at start, naming it; no smaller team runs instead. A record with no roles, such as BP-1 solo, starts no agent and carries no charter, and the run checks no charter part on it (decided by the agent, grill log row of 2026-10-06 on audit round 16). A pattern written for one task has no record: it reaches the run in the fields of a pattern record, with its charter, and the run checks it as it checks a record with roles; a pattern written for one task with no roles carries no charter, and the run's charter files are the only copy of a one-task charter (decided by the agent, grill log row of 2026-10-06 on audit round 17). The charter's quality is an instruction to the agent that builds the pattern, not a check (decided by the agent, grill log row of 2026-10-06 on the pattern charter, C1).
  > The human's direction, 2026-10-06: "one thing I noticed is that we need to be clear about agent's reporting progress, whether to its higher level agents or lower level, or even siblings. good communication smooth out and speed up things. with that said, I think each team pattern should have "system prompt" kinda thing to clearly define role, responsibility, communication pattern, expected behaviors, etc"
- [ ] **AC-067** When a pattern is resolved, the run writes one charter file per role into the run directory: the pattern part and that role's part. An agent's launch prompt names its charter file before its brief, so the charter is the agent's standing instruction and the brief its task. An agent with no resolved pattern, such as one started for a `solo:` step in a stage with no stage map entry (AC-042), has no charter file, and its launch prompt names only its brief (inferred). The brief still carries the task and never the conversation (AC-025) (decided by the agent, grill log row of 2026-10-06 on the pattern charter, C2).
- [ ] **AC-068** An agent that resumes its session gets its charter file again: the resume's launch names the charter file before its prompt, as a first start does. After a compaction, where the plugin's start-of-session hook runs in a pane agent, the hook points the agent back at its charter file, and it prints nothing in any other session. Where a probe saw no start-of-session hook at a compaction, as on Codex, where no trusted printing hook was in place, the agent is taken as not pointed back after one; this gap is accepted, and a check at build records what a trusted hook does. A tool may also give the agent its charter as a native system prompt, but only where a check at build proves that the tool's flag works; it is never assumed (decided by the agent, grill log row of 2026-10-06 that replaces C3 of the row on the pattern charter, C3').
- [ ] **AC-069** Reporting up: each role sends its report target progress as a message at each milestone its charter names, at once on a blocker or a question, and finished at the end. Reporting down: a report target sends the roles that report to it only answers to their questions and data their current duty uses, never an instruction, a new duty or a stop, since every duty comes in the launch prompt (settled, S-150) and only the contact agent stops an agent (AC-009). A report target that wants a role's work changed or stopped asks its own report target, up to the contact agent, which stops the agent and starts a new one with the duty in its launch prompt. A role and its report target, whoever it is (another role, the agent that asked, or the contact agent), may message each other both ways with no declaration, and no other pair may without a declared edge; siblings message each other only along declared edges (AC-035) (decided by the agent, grill log row of 2026-10-06 on the pattern charter, C4, and the row of 2026-10-06 on audit round 15).
- [ ] **AC-070** A progress message's text opens with one line, `progress: MILESTONE — SENTENCE`, where MILESTONE names the milestone and SENTENCE is one sentence; the rest stays free text. The contact agent gets no copy of a progress message, and reads progress only when it is the report target (decided by the agent, grill log row of 2026-10-06 on the pattern charter, C5).
- [ ] **AC-071** The built-in patterns that start agents, BP-2 to BP-5, ship their charters in the same change that ships them, and an agent that writes a pattern for one task writes its charter to the same standard, and passes it to the run with the pattern (decided by the agent, grill log row of 2026-10-06 on the pattern charter, C6, the row of 2026-10-06 on audit round 16 and the row of 2026-10-06 on audit round 17).

## Access & validation policy

| Capability / User Story | Permitted role(s) | Denied role(s) | Data scope | Key validation rules |
|---|---|---|---|---|
| Start or stop a team agent | Contact agent (AC-C) | Spawned agent (AC-S), non-contact hub (AC-B), helper subagent | The run's own manifest, keyed by feature | Pattern must have every role fillable, else refuse at start. Any other agent asks by a start request (AC-042); a requester that is not a live agent in the manifest is refused |
| Commit and push | Human, AC-C, AC-S in the builder role; the `/afk:bug` fixer on its own fix branch | AC-S in any other role, AC-B. Every agent: force-push, deleting a remote branch | The one feature branch in the one shared worktree | One builder at a time; each commit names its role |
| Message another agent | Roles joined by a declared talk edge; every agent to the contact agent, for start requests and its own finished, parked and exited messages; the contact agent to any agent it started; a role to its report target, for its finished message (AC-035); a role and its report target, both ways, for messages (AC-069) | Any other pair; any message type the edge does not list | This run's team | The message type is on the edge's list. A finished message goes to the role's report target, with a copy to the contact agent (AC-048) |
| Read a role's result file | The role's report target | Every other agent, the requester and the contact agent included, unless one is the target | This run's result files | — |
| Read or write a role's checkpoint | The role's agent writes it; the next agent in that role and the contact agent read it | Every other agent | One checkpoint per role per run | — |
| Open a change request | Human, AC-C; the `/afk:bug` fixer, 1 Draft on its own fix branch | AC-S, AC-B | The feature's branch | One per feature |
| Merge | Human (AC-H) | AC-C, AC-S, AC-B — every agent class | The target branch | Merge is the guard on agent write access |
| Write the tracker | Human, AC-C under existing tracker rules; the `/afk:bug` publisher within its grant (AC-060) | AC-S, AC-B | The feature's ticket | Existing tracker-writer boundary unchanged |
| Write repository configuration | Human; AC-C only for the settings copy (AC-064) | Every agent class, for every other write | `.afk` configuration and repository settings | The settings copy never overwrites; no other agent write |
| Read a peer's knowledge-store entry | AC-S, AC-B, AC-C | Any agent reading an **unfinished** peer entry in its own stage | Entries for this run only | Same-stage reads require the entry marked finished |
| Delete the knowledge store | Cleanup, run by AC-C | AC-S, AC-B | This run's store | Deleted after every process the manifest names is killed; nothing is promoted (AC-019) |
| Read the run dashboard | Human, any agent | — none denied; read-only surface | This run's manifest | Read-only; never writes manifest state |

Every row holds by convention: an agent's brief states its rights, and no runtime check can tell one agent from another (ADR-0016). The refusals in the last column check only what the run can see, such as a pattern, a request's fields or a declared edge.

## Implementation Decisions

Modules, as approved:

| Module | Responsibility |
|---|---|
| Transport adapter family | A fifth adapter family; verbs agent-start, agent-send, agent-status, agent-read, agent-stop, agent-list; kinds per TR-1..TR-4. Builds each pane agent's label, agent name and tab from the start request, and delivers each message the best way its tool offers. Answer shapes follow the existing adapter contract. |
| Run manifest | The stateful register the transport family lacks. Keyed by feature identifier; the owning contact session is a field that adoption rewrites. Holds each agent's names and harness session id. Read by cleanup and the dashboard. |
| Pattern data and resolver | Parses a pattern, combines patterns into one team before start, fills roles, adds a moderator where a debate names none, applies talk edges and report targets. Refuses at start on an unfillable role, a self-including pattern, an unknown record version (ADR-0005, ADR-0012, ADR-0015) or a missing charter or role part (AC-066). Writes one charter file per role and adds the report-target edges (AC-067, AC-069). Holds the built-in patterns BP-1 to BP-5, with their charters, as data. |
| Model equivalence and provider fallback | Resolves an equivalent model across providers; substitutes or parks (ADR-0001). |
| Cleanup extension | Stops each agent and closes its pane at its lifespan end. At run end, kills the manifest's processes after an identity check, closes panes, deletes the run's files with the manifest last, and reports what it could not kill or close and each agent it found that the manifest does not name, which it does not stop. |
| Knowledge store | Entry lifecycle, the unfinished/finished stamp, per-stage read rules, the debate step records and their release rule, counted by debater role. |
| Detection | Reads the session, not the machine; finds a tool by user-profile location; reports a disabled setting as fixable (ADR-0009). |
| Configuration schema | New keys for topology, an optional stage-to-pattern map, saved patterns, role-to-model mapping and the pane-or-subagent switch. Refuses the pattern-name and include errors AC-062 lists. |
| Dashboard section | A read-only parser over the manifest for team and agent state. |

Decisions recorded here rather than as ADRs:

- **Cleanup mechanism** is an operating-system job owning each agent's whole process tree, with a descendant sweep where the start is not ours to own. The *mechanism* is design-layer; the *guarantee* is AC-013 and AC-014.
- **Cross-provider equivalence reads the existing model-tier map sideways** — same tier row, different harness column. The map states tier-by-harness selection and does not today state cross-provider substitution; this PRD makes that reading the rule.
- **Where team agents sit in the existing nesting cap** is settled: a helper starts no agent, and a start request past the 3-level cap is refused (AC-043).
- **Team roles inside existing gates.** The build gate, the review gate and the final review call pattern roles as their workers: reviewers fill the review fan-out, the verifier fills the fresh adversary session. Only `/afk:fix` runs a team for bugs. These are changes to existing behaviour and need the design's change-impact rows.
- **Pane agents by default.** Role agents run as pane agents whenever the plugin is enabled and a pane transport is found; helpers stay native subagents (ADR-0013). Every current spawn step that starts a role agent changes; the design lists them.
- **One home for the pane-agent rule.** The rule lives where every plugin-enabled session reads it; skills point at it. Which file that is, is design.
- **One home for the pattern standard.** It lives beside the pattern schema, where every agent that writes or proposes a pattern reads it (AC-058). Which file that is, is design.
- **afk-lite under `/afk:fix` leaves the commit to the caller** (ADR-0014): an exception to ADR-0010's builder commits. The `/afk:bug` fixer's commits on its own fix branch are another (ADR-0017, AC-010). ADR-0020 corrects ADR-0010 and ADR-0014 to name both.
- **Results go to the report target** (ADR-0015). The contact agent keeps a copy of each finished, parked and exited message to keep the manifest (AC-049).
- **Agent-class rules hold by convention** (ADR-0016). The run refuses only what it can see. Examples: an undeclared talk edge, a malformed start request, a requester that is not a live agent.
- **The `/afk:bug` publisher and fixer keep their grants** as pane agents (ADR-0017).
- **Nothing in the knowledge store survives the run** (ADR-0018, superseding ADR-0002).
- **Resume before the checkpoint.** A dead agent's harness session is resumed first; the checkpoint is the fallback (AC-055). Not an ADR: the order is easy to reverse.
- **Close at lifespan end.** Each agent stops and its pane closes when its lifespan ends; run cleanup catches what is left (AC-050).
- **A candidate new staple** is not raised: this repository has no staples registry (see Further Notes).

## Testing Decisions

Test external behaviour, not internals. Every module group below is built test-first:

| Group | What a good test looks like here |
|---|---|
| Cleanup + run manifest | Start a process tree, close the owner, assert nothing survives — the case a live trial proved does not hold by default on Windows. Assert the unkillable process is reported by name, not silently dropped. A recorded identifier that now names another process is not killed; its entry is reported as already gone. A pane whose close fails is named in the report. |
| Pattern resolver + refusal | A pattern with an unfillable role refuses at start and names the role; a fillable one starts. A combined pattern becomes one team with every agent listed once; a self-including pattern refuses. A message outside the declared edges, or of a type the edge does not list, is refused. A finished message reaches only the report target, whatever the sender wrote. An unknown record version and a debate with no fillable moderator refuse at start. A pattern with no charter, or with a role that has no charter part, refuses at start and names it. |
| Transport adapter family | The verb set against TR-1, which needs no external tool. TR-3 and TR-4 need their tool present, so their tests are environment-gated rather than skipped silently. The label and the agent name follow the 4-part rule; an unknown effort, and a name with no room for 1 goal character, are refused. Tabs and resume need the tool and the harness, so they are environment-gated too. |
| Role and helper line | With a pane transport, a role agent starts in a pane; with the switch set back it starts as a subagent and its parent writes its report file. On a tool that delivers only by typing into panes, a message to the contact agent lands in its inbox, never in its input box. A start request from an agent not live in the manifest is refused. |
| Detection + provider fallback | A present command with a disabled setting reports fixable, not missing. A single-model role substitutes; a debate role waits. Beyond the horizon, a dated park report is written. |

Prior art: the existing process-tracking state file used by the build-gate app-start path is the closest precedent for the manifest's shape.

## Out of Scope

- **Nested team patterns** — a manager role running its own sub-team. Tracked as issue 25, which names what must be proved first: nesting, reporting, restart recovery, cleanup.
- **A strict single-agent mode.** Topology governs role agents only; every pane agent may always start its own helper subagents.
- **Cost estimation, caps and a reserved share.** Nothing is predicted (ADR-0001), and no agent, message or spend limit exists. A team shares the human's usage window with the contact agent; nothing reserves a share for it (ADR-0011).
- **A shipped stage map.** Patterns are not attached to workflow stages (ADR-0012).
- **Durable knowledge.** The store is not a knowledge base, and nothing in it is promoted (ADR-0018). The requirements, design and decision records remain the durable record.
- **Enforcing resource limits on a spawned agent.** That is the harness's business.
- **Runtime enforcement of agent-class rules.** Briefs state the rules; review, or a human reading the diff, finds a break after the work (ADR-0016).
- **Agents merging anything.** Merging stays with the human.

## Further Notes

### Assumptions this PRD rests on

- **AS-1 (unverified premise: the desktop tool's team-stop and terminal-close verbs work on this machine).** TR-4's commands were read from the installed binary's own help and have never been run here. The live trial is blocked on the desktop application being open with local terminal attach enabled. Graded surface-verified and trial-pending by explicit human decision (ADR-0008). Requirements resting on TR-4 — the TR-4 row of the transport catalog, and AC-013's coverage of TR-4 — inherit this label. TR-1 through TR-3 do not. The desktop tool's message delivery and tab support are also untried; a trial finds them before its code is written, and AC-035 and AC-054 cover a tool that lacks them.
- **AS-2 (unverified premise: a harness session killed in the middle of a turn resumes cleanly from its session id, and Codex reports a session id at start).** herdr records a Claude pane agent's session id (checked 2026-09-29). Not tried: the Codex case, and a resume after a kill in the middle of a turn. A trial checks both before the resume design binds. Until then, an empty session id means a fresh agent reads the checkpoint. Requirements resting on it: AC-055, and AC-016's resume of a dead debater.

### Verified, and worth keeping

- A headless parent's exit does **not** kill its descendants on Windows. Proven by live trial: the parent exited cleanly and both a child and a grandchild kept running until killed by hand. This is why registration alone is not cleanup (ADR-0007).
- A provider usage read can be performed without starting a generation turn, and the read does not move the usage counter. Proven by live trial: two reads, identical in every quota field. No design depends on it, because no availability check runs (ADR-0001); it is recorded so the question is not reopened.
- The desktop tool's control surface is its command line. Its background service exposes no agent-control verb by deliberate design, so detection must never ask that service whether teams are possible.

- Claude Code refuses a report file written by a subagent: "Subagents should return findings as text, not write report files." Observed when an investigation subagent wrote its report; a pane agent wrote the same three reports with no block.
- A herdr message sent to a pane that holds unsent typed text is added to that text and both are submitted as one prompt, on Claude Code and on Codex (trial T11, trial D). This is why AC-046 protects unsent text in the contact agent's pane only.
- A Claude agent refused a duty that arrived as a later pasted prompt and called it a prompt injection; the same duty given in its launch prompt was obeyed (trial T11).
- herdr refuses an agent name with spaces: `invalid_agent_name`, lowercase letters, digits, `-` or `_`, 1 to 32 characters. It accepts a pane label and a tab label with spaces (2026-09-29). This is why AC-051 has two forms of one name.

### Open questions

- **afk-lite's design stop as `blocked`.** The settled row calls this mapping inferred (solution grill S-207). The human accepted that card, but no row confirms the mapping on its own (AC-037).
- **Who hears of a lost agent.** A started agent that ends without a finished message is marked lost, and its requester is told (solution grill S-173). Where the report target is not the requester (AC-048), no row says whether the target is told too.

### Decided by the agent, not yet audited

Under the human's delegation of 2026-09-30, the agent took these calls with no settled row behind them:

- The pattern standard's right-hand column (PS-1 to PS-4), and the rule that a pattern's description says how it meets each property (AC-059).
- BP-1 solo is outside the standard, because it starts no agent.
- AC-032: with no pattern picked, or no human present, a stage runs as it does today. This joins AC-032's proposal step to the settled rule that a stage with no map entry runs as today.
- AC-032: a map entry may list patterns the resolver combines into one team (settled). ADR-0012 rejected an ordered list in a map entry; the agent reads that rejection as covering patterns run in sequence, not patterns combined into one team.
- AC-046: a message that reaches another agent's pane while it holds unsent text is submitted with that text. The settled rows say only that nobody types in those panes; the trial T11 fact under Verified shows the merge.
- AC-051: the lowercase agent name applies to any tool that refuses spaces in agent names; the settled rows name only herdr.
- AC-033: the included patterns' steps follow the including pattern's own steps, depth first, and a role name defined differently in 2 combined patterns is refused (grill log row of 2026-10-05, Q28).
- AC-037: in driven mode afk-lite does not stop after its design step; a one-way door or a DISAGREE-FINAL point ends `/afk:fix` with `needs_decision` (ADR-0019; grill log row of 2026-10-05, Q34).
- AC-042: a start request from a stage with no stage map entry names the step `solo:` followed by the role (grill log row of 2026-10-05, Q33).
- AC-010: under `/afk:autopilot` the contact agent pushes the feature branch before it opens the Draft change request (grill log row of 2026-10-05 on the design audit, L20).
- AC-035: a role's finished message to its report target needs no declared edge (same row, L5).
- AC-042: a start request's lifespan wins over the lifespan the pattern gives the role (same row, L50).
- AC-051: how the agent name's goal part becomes legal, and that the suffix counts inside the 32 characters (same row, L15).
- AC-051: one rule makes every part of the agent name legal, with `g-` before a part that does not start with a lowercase letter, and a start whose name has no room for 1 goal character is refused (grill log row of 2026-10-05 on audit round 2 and the grill log correction of 2026-10-05 for audit round 3).
- AC-013: cleanup stops no agent the manifest does not name; it lists each one it finds in its report, and the human stops it (grill log correction of 2026-10-05 for audit round 3).
- AC-051: the agent name's model part drops a vendor prefix, then becomes legal, then is cut to 8 characters, and the pane label carries the same model part (grill log correction of 2026-10-05 for audit round 4, its clarification of 2026-10-05 for audit round 5, and the grill log row of 2026-10-05 on audit round 5).
- AC-051: the prefix `g-` counts inside the 32 characters, and a goal that needs `g-` needs room for `g-` and 1 character, else the start is refused (grill log row of 2026-10-05 on audit round 6).
- AC-051: the 3 '-' that join the 4 parts count in the room for the goal: 32 less 3 and the lengths of the role, the model, the effort and the suffix (grill log row of 2026-10-05 on audit round 7).
- AC-013: when the manifest records no start time for a process, cleanup kills nothing; it reports the process as already gone when no live process has the identifier, else as one it could not kill, and a later cleanup moves the entry to cleaned once the human has stopped it (grill log row of 2026-10-05 on audit round 10; moved to cleaned: the row on audit round 12).
- AC-013: cleanup moves an agent's entry to cleaned rather than removing it (grill log row of 2026-10-05 on audit round 12).
- AC-066 to AC-071: the pattern charter, its 2 parts and the refusal of a missing one; one charter file per role, named in the launch prompt before the brief; the charter named again on a resume and the start-of-session hook pointing an agent back at it after a compaction; progress up and messages down between a role and its report target; the progress line; the built-in charters (grill log row of 2026-10-06 on the pattern charter, C1 to C6, from the human's direction of 2026-10-06 quoted under AC-066; its C3 replaced by the next grill log row, C3').
- AC-035: a role and its report target need no declared edge to message each other; AC-059: the charter's pattern part also says how the pattern meets each property (same row, C4 and C1).
- AC-069: down the report line a report target sends only answers and data, never an instruction, a new duty or a stop; AC-035 and AC-069: a role and its report target, whoever it is, message each other with no declared edge, and no other pair does (the row of 2026-10-06 on audit round 15).
- AC-066 and AC-071: a record with no roles, such as BP-1 solo, carries no charter, and the run checks no charter part on it (the row of 2026-10-06 on audit round 16).
- AC-066 and AC-071: a pattern written for one task reaches the run in the fields of a pattern record, with the charter its writer writes, and is checked as a record with roles; the run's charter files are its charter's only copy (the row of 2026-10-06 on audit round 17).
- AC-067: an agent with no resolved pattern has no charter file (inferred, AC-042).
- The new test cases in Testing Decisions, placed in the table's five groups.

### Environment limitations

- The desktop tool's command is not on the command path; it lives in the user profile. A detector checking only the command path reports a usable tool as missing (ADR-0009).

### Staples

This repository has no staples registry — verified by filename and content search; the registry lives in consuming repositories. No staple is folded in, and none is skipped silently.
