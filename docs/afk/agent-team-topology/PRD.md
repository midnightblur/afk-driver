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

A run may use a **team** of agents instead of one, shaped by a **pattern**: which roles exist, which model fills each, how long each lives, and which roles may talk to each other directly. Both team topology and multi-model are optional and independent; with neither configured the plugin behaves exactly as it does today.

One **contact agent** is the only agent the human talks to, and the only agent that starts and stops team agents. Agents are started through a **transport** — the mechanism that starts, messages, reads and closes an agent. Everything a run starts is written to a **run manifest**, so cleanup can kill it and a dashboard can show it. Agents write a **knowledge store** as they work, so a later stage reads what an earlier stage learned; it is deleted when the run ends.

Roles may run on models from different providers. When a provider fails, a single-model role continues on an equivalent model from another provider; a debate role waits, because substituting one side of a debate destroys the debate.

## Catalog

### Transports

| ID | Transport | Start | Cleanup | Status |
|----|-----------|-------|---------|--------|
| TR-1 | Harness subagents | The harness spawns its own child | Harness owns the lifecycle | Supported |
| TR-2 | Headless runs | The plugin starts the process | Operating-system job owns the process tree | Supported |
| TR-3 | Multiplexer panes | The plugin starts a pane | Job where the start is owned; pane close otherwise | Supported |
| TR-4 | Desktop-tool terminals | The tool starts its own terminal | The tool's own close-by-id, per recorded terminal | Supported *(unverified premise: the desktop tool's start, team-stop and terminal-close verbs work on this machine — read from the installed binary's own help, never run)* |

With no transport available a pattern runs on TR-1 and says so in its report.

### Agent classes and permissions

| ID | Class | May start agents | May commit and push | May open a change request | May merge | May write the tracker | May write repository configuration |
|----|-------|------------------|---------------------|---------------------------|-----------|----------------------|-------------------------------------|
| AC-H | Human | — | Yes | Yes | **Yes, only** | Yes | Yes |
| AC-C | Contact agent | **Yes, only** | Yes | Yes | No | Per existing tracker rules | No |
| AC-S | Spawned agent | No | Yes, own branch | No | No | No | No |
| AC-B | Non-contact hub role | No | Yes, own branch | No | No | No | No |

### Role lifespans

| ID | Lifespan | Closed when |
|----|----------|-------------|
| LS-1 | Turn | The role's single exchange completes |
| LS-2 | Phase | The phase that needs the role completes |
| LS-3 | Feature | The run ends |

## User Stories

1. As a developer, I want deep-thinking work done by two models that critique each other, so that I see a real disagreement instead of one model's confident guess.
2. As a developer, I want a run to survive one provider's usage limit, so that I do not come back to work that stopped hours ago.
3. As a developer, I want every agent and background process a run started to be killed when it ends, so that nothing is left running on my machine.
4. As a developer, I want to describe my own team shape for one task, so that I am not limited to the shapes that shipped.
5. As a developer, I want to see what each agent in a run is doing and which are parked, so that a waiting team does not look like a hung one.

## Acceptance Criteria

- [ ] **AC-001** With neither team topology nor multi-model configured, a run behaves exactly as it does before this feature: one agent, one model, no manifest, no knowledge store.
- [ ] **AC-002** Team topology and multi-model are independently switchable; all four combinations run.
- [ ] **AC-003** A pattern is accepted as data, whether it shipped with the plugin or the user wrote it, and a user-written pattern may declare every field a built-in one declares.
- [ ] **AC-004** A pattern may be used once without being saved.
- [ ] **AC-005** A pattern whose role cannot be filled is **refused at start**, naming the unfillable role. A pattern with every role fillable starts. No reduced shape runs in place of a refused one.
- [ ] **AC-006** Research, grounding, design, planning, review and audit work runs the debate pattern with two agents or more on different models.
- [ ] **AC-007** In a debate, no agent sees another agent's output for the same piece of work before writing its own. Agreement is reported per agent; no single combined verdict is emitted.
- [ ] **AC-008** All agents in a run work in one worktree, created once per feature or bug. A run never creates a worktree per agent.
- [ ] **AC-009** Only the contact agent starts or stops a team agent. A start or stop attempted by any other agent class is refused.
- [ ] **AC-010** A spawned agent may commit and push its own branch. Opening a change request from a spawned agent is refused; the contact agent opens it. Merging is refused for every agent class.
- [ ] **AC-011** A spawned agent's attempt to write repository configuration or the tracker is refused.
- [ ] **AC-012** Every agent and every background process a run starts appears in the run manifest, keyed by feature identifier and owning contact session, carrying role, model, state and park-until time.
- [ ] **AC-013** Cleanup kills every process the manifest names, and reports by name every process it could not kill. A phase does not report finished while the manifest holds an unkilled process.
- [ ] **AC-014** A background process started by an agent and never registered is still killed when its owning agent's process tree is closed.
- [ ] **AC-015** A new contact agent adopts an existing manifest by feature identifier and contact session rather than starting a second one.
- [ ] **AC-016** A knowledge-store entry is created unfinished. Only the authoring agent's clean exit marks it finished. An entry from an agent that ended early stays unfinished.
- [ ] **AC-017** Within one stage, an agent reads only finished entries from its peers. Across stages, a later stage reads earlier stages' finished entries.
- [ ] **AC-018** Every knowledge-store entry carries author, role, model, time and ground.
- [ ] **AC-019** The knowledge store is excluded from version control and is deleted when the run's artifacts are cleaned up. Nothing in it survives except environment facts promoted to the durable register before deletion.
- [ ] **AC-020** No availability or quota check runs before or during a run. A provider failure is detected when a call fails, never predicted.
- [ ] **AC-021** Authentication is checked once per provider before the first spawn. A provider that fails authentication is reported before any agent starts; one that passes is not re-checked during the run.
- [ ] **AC-022** On a provider failure, a single-model role continues on an equivalent model from another provider, where the tier map supplies one. A debate role does not substitute; it waits.
- [ ] **AC-023** Beyond the provider's wait horizon the run parks and writes a dated report naming the provider, the role and the time it parked. It does not continue in a reduced shape.
- [ ] **AC-024** A role's running checkpoint is written while the role works, not at the end, and a replacement agent reads it without asking the dead agent for anything.
- [ ] **AC-025** A spawned agent receives a written brief and never the contact agent's conversation.
- [ ] **AC-026** Detection reports which agent tools are usable in the **session the human and agents are in**, not merely installed on the machine.
- [ ] **AC-027** A tool whose command is present but whose required setting is disabled is reported as a named fixable setting, not as a missing tool. A tool genuinely absent is reported as absent.
- [ ] **AC-028** Setup always offers the optional multiplexer install; declining it leaves every other transport working.
- [ ] **AC-029** A dashboard reading the manifest distinguishes a parked agent from a hung one, showing the park-until time.
- [ ] **AC-030** On a conflict between configuration and detection, the plugin asks the human when one is present, and parks naming the conflict when none is.
- [ ] **AC-031** On TR-4, cleanup closes each terminal recorded in the manifest by its recorded identifier, and reports by name any terminal it could not close *(unverified premise: the desktop tool's start, team-stop and terminal-close verbs work on this machine — read from the installed binary's own help, never run)*.

## Access & validation policy

| Capability / User Story | Permitted role(s) | Denied role(s) | Data scope | Key validation rules |
|---|---|---|---|---|
| Start or stop a team agent | Contact agent (AC-C) | Spawned agent (AC-S), non-contact hub (AC-B) | The run's own manifest, keyed by feature + contact session | Pattern must have every role fillable, else refuse at start |
| Commit and push | Human, AC-C, AC-S, AC-B | — none denied; stated deliberately | The agent's own branch in the one shared worktree | Push to own branch only |
| Open a change request | Human, AC-C | AC-S, AC-B | The feature's branch | One per feature |
| Merge | Human (AC-H) | AC-C, AC-S, AC-B — every agent class | The target branch | Merge is the guard on agent write access |
| Write the tracker | Human, AC-C under existing tracker rules | AC-S, AC-B | The feature's ticket | Existing tracker-writer boundary unchanged |
| Write repository configuration | Human | AC-C, AC-S, AC-B — every agent class | `.afk` configuration and repository settings | No agent writes configuration |
| Read a peer's knowledge-store entry | AC-S, AC-B, AC-C | Any agent reading an **unfinished** peer entry in its own stage | Entries for this run only | Same-stage reads require the entry marked finished |
| Delete the knowledge store | Cleanup, run by AC-C | AC-S, AC-B | This run's store | Deletion happens after promotion of environment facts |
| Read the run dashboard | Human, any agent | — none denied; read-only surface | This run's manifest | Read-only; never writes manifest state |

## Implementation Decisions

Modules, as approved:

| Module | Responsibility |
|---|---|
| Transport adapter family | A fifth adapter family; verbs start, is-alive, send, stop, list; kinds per TR-1..TR-4. Answer shapes follow the existing adapter contract. |
| Run manifest | The stateful register the transport family lacks. Keyed by feature identifier + contact session. Read by cleanup and the dashboard. |
| Pattern data and resolver | Parses a pattern, fills roles, applies talk edges, refuses at start on an unfillable role (ADR-0005). |
| Model equivalence and provider fallback | Resolves an equivalent model across providers; substitutes or parks (ADR-0001). |
| Cleanup extension | Kills the manifest's processes; deletes the knowledge store; reports what it could not kill. |
| Knowledge store | Entry lifecycle, the unfinished/finished stamp, per-stage read rules. |
| Detection | Reads the session, not the machine; finds a tool by user-profile location; reports a disabled setting as fixable (ADR-0009). |
| Configuration schema | New keys for topology, pattern selection and role-to-model mapping. |
| Dashboard section | A read-only parser over the manifest for team and agent state. |

Decisions recorded here rather than as ADRs:

- **Cleanup mechanism** is an operating-system job owning each agent's whole process tree, with a descendant sweep where the start is not ours to own. The *mechanism* is design-layer; the *guarantee* is AC-013 and AC-014.
- **Cross-provider equivalence reads the existing model-tier map sideways** — same tier row, different harness column. The map states tier-by-harness selection and does not today state cross-provider substitution; this PRD makes that reading the rule.
- **Where team agents sit in the existing nesting cap** must be stated explicitly by the design, so the three-level cap is not silently exceeded when a team agent spawns its own helpers.
- **A candidate new staple** is not raised: this repository has no staples registry (see Further Notes).

## Testing Decisions

Test external behaviour, not internals. All four module groups are built test-first, as chosen:

| Group | What a good test looks like here |
|---|---|
| Cleanup + run manifest | Start a process tree, close the owner, assert nothing survives — the case a live trial proved does not hold by default on Windows. Assert the unkillable process is reported by name, not silently dropped. |
| Pattern resolver + refusal | A pattern with an unfillable role refuses at start and names the role; a fillable one starts. Talk edges outside the declared set are refused. |
| Transport adapter family | The verb set against TR-1, which needs no external tool. TR-3 and TR-4 need their tool present, so their tests are environment-gated rather than skipped silently. |
| Detection + provider fallback | A present command with a disabled setting reports fixable, not missing. A single-model role substitutes; a debate role waits. Beyond the horizon, a dated park report is written. |

Prior art: the existing process-tracking state file used by the build-gate app-start path is the closest precedent for the manifest's shape.

## Out of Scope

- **Nested team patterns** — a manager role running its own sub-team. Tracked as issue 25, which names what must be proved first: nesting, reporting, restart recovery, cleanup.
- **A strict single-agent mode.** Topology governs main roles only; every agent may always fan out its own native subagents.
- **Cost estimation before a run.** A fixed slice of each provider window is reserved for the contact agent; patterns spend the rest. Nothing is predicted (ADR-0001).
- **Durable knowledge.** The store is not a knowledge base. The requirements, design and decision records remain the durable record.
- **Enforcing resource limits on a spawned agent.** That is the harness's business.
- **Agents merging anything.** Merging stays with the human.

## Further Notes

### Assumptions this PRD rests on

- **AS-1 (unverified premise: the desktop tool's team-stop and terminal-close verbs work on this machine).** TR-4's commands were read from the installed binary's own help and have never been run here. The live trial is blocked on the desktop application being open with local terminal attach enabled. Graded surface-verified and trial-pending by explicit human decision (ADR-0008). Requirements resting on TR-4 — the TR-4 row of the transport catalog, and AC-013's coverage of TR-4 — inherit this label. TR-1 through TR-3 do not.

### Verified, and worth keeping

- A headless parent's exit does **not** kill its descendants on Windows. Proven by live trial: the parent exited cleanly and both a child and a grandchild kept running until killed by hand. This is why registration alone is not cleanup (ADR-0007).
- A provider usage read can be performed without starting a generation turn, and the read does not move the usage counter. Proven by live trial: two reads, identical in every quota field. No design depends on it, because no availability check runs (ADR-0001); it is recorded so the question is not reopened.
- The desktop tool's control surface is its command line. Its background service exposes no agent-control verb by deliberate design, so detection must never ask that service whether teams are possible.

### Environment limitations

- The desktop tool's command is not on the command path; it lives in the user profile. A detector checking only the command path reports a usable tool as missing (ADR-0009).

### Staples

This repository has no staples registry — verified by filename and content search; the registry lives in consuming repositories. No staple is folded in, and none is skipped silently.
