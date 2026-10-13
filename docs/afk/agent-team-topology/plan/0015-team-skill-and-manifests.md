## Goal
Write the team skill, the contact agent's run procedure (the contact agent is the agent the human talks to), at skills/afk/team (file name: plan decision D-3), and list it in both plugin manifests, AGENTS.md and the readme. The procedure picks or proposes a pattern, checks the spawn permission, starts and stops every pane agent (an agent in its own terminal pane) through the team entry script, keeps one wait job per run, handles the contact inbox and provider failures, resumes before it replaces, stops each agent at its lifespan's end and runs cleanup at run end. The slice ends at the skill and its registration: the stage-skill spawn points that hand work to it, the review, adversary, fix and bug changes are other subtasks.

## Complexity
complex

## Design refs
- SDD: SDD.md#§14 L9 — Implementation Seams & Change Impact — row "Twin plugin manifests `manifest_skills`, checked by `gate_native_contract`" binds the registration
- SDD: SDD.md#§7 L6 — Process & Coordination — the sequences the skill drives: Start a role, Wait for messages, Resume, Close at lifespan end, Cleanup, Provider failure
- SDD: SDD.md#§8 L7 — Module Decomposition — rows "Team entry script", "Spawn permission check", "Wait script", "Job supervisor", "Cleanup", "Model equivalence" the skill calls
- SDD: SDD.md#§13 Open Questions — Q22 (a start request carried out by the contact agent is unproven)
- ADR: adr/design/0008-one-wait-job-per-run.md — one wait job per run (supersedes adr/design/0004-wait-job-with-probe.md)
- ADR: adr/design/0012-autopilot-subtask-agent-is-the-builder.md — under /afk:autopilot the contact agent opens the Draft change request

## Scope
- skills/afk/team/SKILL.md
- skills/afk/team/*.md
- .claude-plugin/plugin.json
- .codex-plugin/plugin.json
- README.md
- AGENTS.md
- skills/afk/setup/MANIFEST.md (:596-597)

## Seams
- implement: §14 row "Twin plugin manifests `manifest_skills`, checked by `gate_native_contract`" — the team skill in both manifests, mentions in AGENTS.md and the readme, the language pointer line, frontmatter naming its directory (INV-054)

## Acceptance
- [ ] Both .claude-plugin/plugin.json and .codex-plugin/plugin.json list `./skills/afk/team` with no trailing slash; AGENTS.md (the table 'The skills') and README.md §10 mention the skill, and CLAUDE.md, the one-line pointer @AGENTS.md, is not edited; its SKILL.md opens with the LANGUAGE.md pointer line, and its frontmatter name names its directory with a non-empty description, a value holding ': ' quoted (SDD §14 row "Twin plugin manifests `manifest_skills`, checked by `gate_native_contract`")
- [ ] The new prose holds no harness word, which native check A refuses; no gate code changes (SDD §14 row "Twin plugin manifests `manifest_skills`, checked by `gate_native_contract`")
- [ ] The skill is the first skill invoker of the multiplexer: in the same commit, the register row C15 · herdr line 'No skill invokes it' (MANIFEST.md:596-597) changes to name it (plan D-24) (SDD §14 row "Setup register `MANIFEST` and `install_block`")
- [ ] Briefs and the run procedure say agents write run-directory files through the team script or a shell, never an edit tool, so the manifest stays in the main checkout's ignored agent directory and the protected-branch guard is the gate for writes there (SDD §5 row "Write repository configuration")
- [ ] A subtask agent's rationale-post reuses the contact's Draft change request and never creates one (SDD §5 row "Open a change request")
- [ ] Pattern pick: with a stage map entry the skill uses its patterns; with none it proposes patterns from their descriptions, possibly several combined, and the human picks; with no pattern picked, or no human present, the stage runs as it does today (PRD AC-032)
- [ ] The skill points at the pattern standard's one home (scripts/team/patterns/STANDARD.md) when it proposes a pattern, and does not restate the standard (PRD AC-058)
- [ ] The skill points at the pane-agent rule in DELEGATION.md and does not restate it (PRD AC-047)
- [ ] Before a run's first transport command the skill runs the spawn permission check; a refusal stops the run and names the rule and /afk:setup (SDD §8 row "Spawn permission check")
- [ ] Every start, message, status read, output read, stop and list goes through the team entry script, one JSON object per verb; the skill never calls a transport tool directly (SDD §8 row "Team entry script")
- [ ] The skill keeps one wait job per run: before it starts a wait job it stops the job the manifest names and removes that line, when an agent parks, after each job ends, and when it takes over a run; after a job ends it handles every inbox message, then starts the next job (ADR-0008)
- [ ] Where the harness can wake the contact agent, it handles an inbox message without the human's help; where it cannot, it says so at run start and handles its inbox at its next turn (PRD AC-065)
- [ ] No availability or quota check runs before or during a run; a provider failure is detected when a call fails (PRD AC-020)
- [ ] Authentication is checked once per provider before the first spawn; a provider that fails is reported before any agent starts, and one that passes is not re-checked (PRD AC-021)
- [ ] On a provider failure a single-model role continues on an equivalent model from another provider, read from the PROVIDERS.md tier map; a debate role does not substitute and waits (PRD AC-022)
- [ ] Beyond the provider's wait horizon the run parks and writes a dated report naming the provider, the role and the park time; it does not continue in a reduced shape (PRD AC-023)
- [ ] When an agent dies or stops early, the skill first resumes its harness session in a new pane, as a new manifest entry with the same session id; with no session id, or a failed resume, it starts a fresh agent that reads the role's checkpoint (PRD AC-055)
- [ ] Before a resume the skill stops the old agent, closes its pane and marks its entry cleaned; when that stop fails it marks the entry unkillable, does not resume, and tells the human (PRD AC-056)
- [ ] When an agent's lifespan ends the skill stops the agent, closes its pane and marks its entry cleaned; a failed stop or close marks the entry unkillable, and a failed close names the pane (PRD AC-050)
- [ ] At run end the skill calls cleanup once and reports every survivor by name (SDD §7)
- [ ] All agents in a run work in one worktree, created once per feature or bug; the skill never creates a worktree per agent (PRD AC-008)
- [ ] A run uses one feature branch; briefs give commit and push only to the builder role and the /afk:bug fixer on its own fix branch; no agent force-pushes, deletes a remote branch or merges (PRD AC-010)
- [ ] Under /afk:autopilot the contact agent pushes the feature branch and then opens the Draft change request before the first subtask starts; the subtask agent is the builder (ADR-0012)
- [ ] Each brief says the spawned agent writes no repository configuration and no tracker, except the /afk:bug publisher within its grant (PRD AC-011)
- [ ] With no pane transport found, or the switch set back, role agents run as subagents and the run report says so (PRD AC-044)
- [ ] The contact agent keeps a copy of every finished, parked and exited message, uses it to keep the manifest, and reads a role's result only when it is that role's report target (PRD AC-049)
- [ ] With both switches off, and with subagents or no pane transport, a run behaves as it did before this feature (PRD AC-001)
- [ ] One live team run on herdr through the skill starts, messages, stops and cleans up a 2-role pattern, and proves that a worker's start request carried out by the contact agent runs (SDD §13 Q22)
- [ ] Every artifact in ## Produces exists with its declared contract (SDD §14 row "Twin plugin manifests `manifest_skills`, checked by `gate_native_contract`")

## Produces
- skills/afk/team/SKILL.md#contact agent's run procedure — the team skill, the contact agent's run procedure
- .claude-plugin/plugin.json#./skills/afk/team — the skill listed in the Claude manifest
- .codex-plugin/plugin.json#./skills/afk/team — the skill listed in the Codex manifest

## Consumes
- 0010-team-entry-script scripts/afk-team.py#def dispatch_verb( — every start, message and stop goes through the entry script
- 0011-job-supervisor scripts/team/supervisor.py#def supervise_agent( — exited and parked messages
- 0012-cleanup scripts/team/cleanup.py#def run_cleanup( — cleanup at run end
- 0013-provider-layer-codex PROVIDERS.md#equivalent model from another provider — the substitute model on a provider failure
- 0014-delegation-doctrine DELEGATION.md#pane-agent rule — the rule the skill points at

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `grep -n "contact agent's run procedure" skills/afk/team/SKILL.md`; `grep -n '"./skills/afk/team"' .claude-plugin/plugin.json .codex-plugin/plugin.json`; `grep -c '"./skills/afk/team/"' .claude-plugin/plugin.json .codex-plugin/plugin.json` prints 0 for each; grep the consumed anchors: `grep -n 'def dispatch_verb(' scripts/afk-team.py`, `grep -n 'def supervise_agent(' scripts/team/supervisor.py`, `grep -n 'def run_cleanup(' scripts/team/cleanup.py`, `grep -n 'equivalent model from another provider' PROVIDERS.md`, `grep -n 'pane-agent rule' DELEGATION.md` | Produces anchors present; both manifests list the skill with no trailing slash; consumed artifacts present |
| static | `python -m pytest scripts/tests/test_skill_frontmatter.py -q` | frontmatter names the directory; the language pointer line is present |
| static | `python -m pytest scripts/tests/test_skill_registry_gate.py scripts/tests/test_native_contract_events.py -q` | registry checks A, B, D and native checks A, B, C pass on the new skill; seam-test for the row "Twin plugin manifests `manifest_skills`, checked by `gate_native_contract`" |
| static | `grep -c 'No skill invokes it' skills/afk/setup/MANIFEST.md` prints 0 | the C15 row names its first skill invoker (plan D-24) |
| integration | environment-gated on herdr: one team run through the skill that starts, messages, stops and cleans up a 2-role pattern, recorded as a probe row in providers/CONFORMANCE.md | §13 Q22: a start request carried out by the contact agent runs |

## Context excerpts
> (SDD §14 row "Twin plugin manifests `manifest_skills`, checked by `gate_native_contract`", Planned change) C6, C7: the feature's skill in both manifests, mentions in AGENTS.md and the readme (CLAUDE.md:1 is the pointer @AGENTS.md; check B reads AGENTS.md and README.md, hooks/skill-registry-gate.sh:120-126), the language pointer line, frontmatter naming its directory with a non-empty description, a value holding ': ' quoted (hooks/lib/skill_frontmatter_check.py:33-34, :85-86; S-64, S-125)

> (SDD §14 row "Twin plugin manifests `manifest_skills`, checked by `gate_native_contract`", Conventions / landmines) A trailing slash in the Claude manifest passes check C and fails registry check A; in the Codex manifest it passes both (native-contract-gate.sh:197; skill-registry-gate.sh:72, :108). Check B accepts a mention anywhere in either file, but /afk:setup audit check 1 wants the skill in README §10 and the AGENTS.md table 'The skills' (AUDIT.md:12-17), so the mentions land there. Harness words in the new prose fail native check A (inferred, INV-054). Compatibility: only adds (S-246). Rollback: revert the commit, or install the previous plugin version (S-246)


> (SDD §8 row "Spawn permission check") Before a run's first transport command, confirm the harness will let the contact agent run the team entry script for all six transport verbs of §3 (agent-start, agent-send, agent-status, agent-read, agent-stop, agent-list); refuse, naming the rule, when it will not (AUTO-1) | check() → ok, or a refusal carrying the rule text

> (SDD §8 row "Team entry script", Public interface) the six verbs of §3, one JSON object each

> (SDD §8 row "Wait script", Public interface) 2 command-line arguments: the inbox folder and an optional park-until time (R46-WAIT card, accepted as S-226); reads no environment variable (S-128); waits the way the stall watchdog already waits

> (SDD §7) | Wait for messages | The contact agent parks an agent, a wait job ends, or the contact agent takes over a run (S-240) | Stop the job the manifest names and remove its line, then start the next job; after a job ends, handle every inbox message first (S-240) | The job checks the inbox every 10 seconds and exits at the first file or the earliest park-until time (S-226) | Contact agent only (I19) |

> (SDD §7) | Resume a dead or stopped agent | The contact agent finds the agent lost or stopped early (S-213) | First agent-stop on the old agent, which closes its pane, then cleaned on the old line; a failed stop sets unkillable, and nothing resumes (S-242). Then a new manifest line with the same harness session id; a fresh agent reads the checkpoint when the resume fails or no id is stored (S-213, S-219, S-233). On Codex a resume worked only when typed into a new pane with herdr pane run (providers/CONFORMANCE.md:440) | A fresh agent reads the old or the new checkpoint (S-41) | Contact agent only |

> (SDD §7) | Close at lifespan end | Turn: on its finished message. Step: when its pattern step completes, which is when every agent it started has sent finished or is lost (S-228). Feature: when the run ends (S-169, S-192) | agent-stop stops the agent and closes its pane in one call (S-234); then the contact agent writes cleaned on the manifest line (S-225) | — | Contact agent only |

> (SDD §7) | Provider failure | A failed call (AC-020) | — | — | Single-model role substitutes by tier row; debate role waits; beyond the horizon, park (AC-022, AC-023) |

> (SDD §13 Q22) Unproven premises in the signed packets: a worker's start request carried out by the contact agent never ran, since T12 was refused at the tab create (S-163); one allow rule on the team entry script covering tab create, pane split and the settings copy is not tried, and T7 saw the harness refuse an agent's edit of the settings file (S-167, S-191); a message to an agent waiting at a permission or dialog prompt is not tried (T11).

> (ADR-0008) One wait job per run (S-195). It checks the contact agent's inbox every 10 seconds, and exits at the first file or at the earliest park-until time (S-226). … The contact agent keeps the rule of one job, because only it writes the manifest. Before it starts a wait job, it stops the job the manifest names and removes that line: when an agent parks, after each job ends, and when it takes over a run. After a job ends, it handles every inbox message, then starts the next job (S-240).

> (ADR-0012) The subtask agent is the builder. It commits, pushes and updates the change request's checklist. The contact agent pushes the feature branch, then opens the Draft change request, before the first subtask starts (S-227, S-243; agent-decided, `GRILL-LOG.md` row "Agent-decided, 2026-10-05", design-audit open points, L20).

> (PRD AC-001) With no team pattern and no multi-model configured, and with role agents switched back to subagents or no pane transport found, a run behaves as it did before this feature: one agent, one model, no manifest, no knowledge store. One difference: a subagent's report file is written by the agent that started it (AC-044).

> (PRD AC-008) All agents in a run work in one worktree, created once per feature or bug. A run never creates a worktree per agent.

> (PRD AC-010) A run uses one feature branch in its one worktree. Two kinds of spawned agent commit and push: the builder, one at a time, on the feature branch (ADR-0010), and the `/afk:bug` fixer, on its own fix branch (AC-060). … No agent force-pushes or deletes a remote branch; the builder corrects a bad push with a new commit. No agent merges. These rules hold by convention (ADR-0016).

> (PRD AC-011) No spawned agent writes repository configuration or the tracker. One exception: the `/afk:bug` publisher writes the tracker within its grant (AC-060). No agent writes repository configuration except through the contact agent's settings copy (AC-064). These rules hold by convention (ADR-0016).

> (PRD AC-020) No availability or quota check runs before or during a run. A provider failure is detected when a call fails, never predicted.

> (PRD AC-021) Authentication is checked once per provider before the first spawn. A provider that fails authentication is reported before any agent starts; one that passes is not re-checked during the run.

> (PRD AC-022) On a provider failure, a single-model role continues on an equivalent model from another provider, where the tier map supplies one. A debate role does not substitute; it waits.

> (PRD AC-023) Beyond the provider's wait horizon the run parks and writes a dated report naming the provider, the role and the time it parked. It does not continue in a reduced shape.

> (PRD AC-032) A pattern carries a description of how and when it is useful and names no workflow stage. The plugin ships no stage map. The human's configuration may map a stage to one pattern, or to a list of patterns combined into one team. With no entry, the contact agent proposes patterns from their descriptions, possibly several combined, and the human picks. With no pattern picked, or no human present, the stage runs as it does today.

> (PRD AC-044) With no pane transport found, or with the switch set back, role agents run as subagents and the run report says so. Such a subagent returns its report as text, and the agent that started it writes the report file.

> (PRD AC-047) The pane-agent rule is stated once, where every session with the plugin enabled reads it; skills point at it.

> (PRD AC-049) The contact agent gets a copy of every finished, parked and exited message. It uses the copy to keep the manifest, and to pass a result's location on when the target cannot be reached (AC-048). It reads a role's result only when it is that role's report target.

> (PRD AC-050) When an agent's lifespan ends (LS-1 to LS-3), the contact agent stops the agent, closes its pane and marks its manifest entry cleaned. A stop or a pane close that fails marks the entry unkillable, and a failed close names the pane; run cleanup tries again.

> (PRD AC-055) When an agent dies or stops early, the contact agent first resumes the agent's harness session (its own conversation in its tool) in a new pane. Each resume is a new manifest entry with the same session id. With no session id recorded, or when the resume fails, the contact agent starts a fresh agent that reads the role's checkpoint (AC-024) *(unverified premise: a harness session killed in the middle of a turn resumes cleanly from its session id, and Codex reports a session id at start)*.

> (PRD AC-056) Before a resume, the contact agent stops the old agent, closes its pane and marks its entry cleaned. When that stop fails, the contact agent marks the entry unkillable, does not resume, and tells the human.

> (PRD AC-058) The pattern standard (PS-1 to PS-4) is stated once, where every agent that writes or proposes a pattern reads it. Skills point at it.

> (PRD AC-065) The contact agent handles an inbox message without the human's help where its harness can wake it. Where the harness cannot, the contact agent says so at run start and handles its inbox at its next turn.

> (SDD §5 row "Write repository configuration") | Write repository configuration | Human. One stated exception: the contact agent, through agent-start in the team entry script, copies the git-ignored .claude/settings.local.json of the main checkout into the run's worktree (S-191) | Every agent class, for every other configuration write (S-191) | The one allow rule on the team entry script covers the copy. The script never overwrites: when the file exists, it skips the copy and reports that (S-191). A write into the main checkout: the protected-branch guard refuses an agent's edit-tool write to any target there, and any shell command that is not read-only from a session in the main checkout (hooks/lib/protected_branch_guard.py:7-9, :418-457), so the contact session sits in a linked worktree on an unprotected branch (:424-436). Agents write run-directory files through the team script or a shell, never an edit tool, so the manifest stays where S-102 put it (GRILL-LOG.md:745 (7)). Every other configuration write: CONVENTION, no gate refuses it | S-191, SET-1, GRILL-LOG.md:745 (7) |

> (SDD §5 row "Open a change request") | Open a change request | Human, contact agent. Under /afk:autopilot the contact agent pushes the feature branch, then opens the Draft change request, before the first subtask starts (S-227, S-243; audit L20, agent-decided); /afk:execute finds the open change request and creates none (S-227). A subtask agent's rationale-post reuses the contact's Draft and never creates one, though rationale-post opens a Draft when no writable change exists (RATIONALE.md:52-54; GRILL-LOG.md:745 (6)). One stated exception: the /afk:bug fixer opens 1 Draft change request and marks it ready, only on its own fix branch, and never merges (S-238) | Any other spawned agent; non-contact hub | CONVENTION. Nothing observes who calls the forge; the fixer's grant is its brief (S-238) | S-227, S-238, AC-010, AC-060; audit L20 (agent-decided); GRILL-LOG.md:745 (6) |

## Parent PRD
docs/afk/agent-team-topology/PRD.md

## Parent SDD
docs/afk/agent-team-topology/SDD.md

## Blocked by
0010-team-entry-script, 0011-job-supervisor, 0012-cleanup, 0013-provider-layer-codex, 0014-delegation-doctrine

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality
during implementation, classify per the decision protocol (`DECISIONS.md`,
workflow plugin root): a two-way-door correction is recorded in
`plan/DECISIONS.md` and implemented; a one-way door or a tie exits
`design_conflict` quoting the SDD section + the conflict. Never override off
the record. Parked conflicts route back to `/afk:grill-solution` for a
superseding ADR.
