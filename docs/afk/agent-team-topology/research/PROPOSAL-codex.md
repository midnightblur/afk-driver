# Proposal — optional teams and provider selection

Owner: `planner-codex`. Date: 2026-09-15. Status: independent proposal; no plugin source changes.
Read `LANGUAGE.md` before extending this artifact.
Evidence: [FACTS-codex.md](FACTS-codex.md), referenced below by stable `C` identifiers.
AFK means away from keyboard. CLI means command-line interface. MCP means Model Context Protocol.

## Recommendation

Separate topology, transport, and model selection into independent configuration choices.
Keep current execution unchanged when the new settings are absent.
Keep one contact agent accountable for human requests, approvals, and the integrated result.
Make agent termination conditional on durable findings and verified process cleanup.

This proposal changes two assumptions in the earlier handoff:

| Earlier assumption | Proposed decision | Reason |
|---|---|---|
| Headless transport becomes the default | Preserve the existing harness behavior; headless is an explicit selection | Optional adoption must not replace today's execution |
| Each task needs a separate manager | Let the contact manage a small team; add a manager only for a chosen hierarchy | Avoid another session when its state adds no value |
| Owned worktrees permit unrestricted builders | Use owned worktrees plus enforced permissions; unrestricted execution requires a separately approved containment policy | A worktree separates files; it does not restrict credentials or machine access |
| 1DevTool might support termination | Headless timeout termination is verified; controller stop remains an integration requirement | C037–C048 distinguish live evidence from interface documentation |

Earlier handoff: `C:\Users\mvu\AppData\Local\Temp\handoff-P1aHuF.md`, lines 34–74.

## A. Topology and built-in patterns

Options: embed topology in each skill; require a dedicated team platform; define a small harness-neutral role graph.
Recommend the role graph. A role graph lists roles, ownership, dependencies, and permitted communication.
Transport capabilities determine whether that graph can run; they do not select the graph.

| Selection | Behavior | Initial support |
|---|---|---|
| Unset | Existing delegation and lifecycle rules | Required compatibility case |
| `none` | One agent performs the task | Explicit opt-in; report any stage that requires independence |
| `native` | Use harness-native children and existing disk contracts | Preserve current role rules |
| `managed` | Bind user-created agents through explicit identifiers and permissions | Do not terminate user-owned sessions |
| `team` | Own and supervise roles using a selected pattern | Require transport conformance |

Proposed built-in patterns:

| Pattern | Roles and flow | Termination boundary |
|---|---|---|
| `delivery` | Contact coordinates planners, isolated builders, and independent reviewers | Retire each role after its artifacts are accepted |
| `panel` | Independent planners or reviewers produce evidence; contact adjudicates | Retire the panel after the decision is recorded |
| `pipeline` | Ordered roles consume their predecessor's accepted artifact | Retire each stage after consumer acknowledgement |
| `hierarchy` | Contact delegates partitions to managers; each manager reports one digest | Retire a partition after all its descendants settle |

Ship `delivery` and `panel` first. Add pipeline and hierarchy after their lifecycle tests pass.
Users can save a role graph in repository configuration or supply one for the current task.
Use one schema for both. Validate unknown roles, cycles, duplicate file ownership, permission edges, and capacity before spawning.
Do not infer human approval from a configured communication edge.

## B. Spawn, reuse, and terminate

Options: keep every agent alive; respawn for every turn; reuse only when history is required.
Recommend reuse when the next assignment explicitly needs that session's private working context.
Prefer fresh reviewers and new planning rounds after a phase ends.

| Lifecycle event | Required action |
|---|---|
| Before spawn | Resolve role, provider, model, permissions, ownership, worktree, input references, and deadline |
| Spawn receipt | Persist owned run/session/process identifiers before waiting |
| Work underway | Record progress events and changed evidence; enforce capacity and elapsed-time limits |
| Follow-up | Reuse only a compatible session; otherwise create a fresh agent from accepted artifacts |
| Role completion | Agent publishes claims, evidence, unresolved questions, and a short handoff |
| Before termination | Coordinator validates artifacts and records their receipt; required consumers acknowledge their inputs |
| Termination | Close only owned agents; wait for process exit and inspect owned descendants |
| Failed cleanup | Mark cleanup incomplete and block conflicting successor work |
| Coordinator restart | Reconcile recorded identifiers with transport state before sending or spawning |

Use an external supervisor for deadlines and abandoned descendants. An idle agent cannot enforce a prose deadline.
Reuse the existing watchdog mechanism where its event delivery works (`DELEGATION.md:32–39`).
Require explicit process ownership; PID alone is insufficient when identifiers can be reused.
Persist creation time or an operating-system handle alongside the PID.
On Windows, test process-tree termination explicitly. Our trial proves only its observed process set (C044).

Completed agents need no live session merely to preserve their conclusions.
For interrupted agents, retain the last accepted evidence and mark unfinished claims unverified.
A transient execution error must not erase a completed research record.

## C. Knowledge that survives termination

Options: transcript archives; a vector database; versioned Markdown records with linked evidence.
Recommend Markdown records through the existing local notes mechanism.
`ADAPTERS.md:88–106` already makes repository files canonical, even when another notes tool is selected.

Proposed durable location: `docs/afk/knowledge/`. Confirm the final path before implementation.
Keep these records outside `plan/`, which existing cleanup deletes after merge (`CLAUDE.md:160`).
Keep temporary logs outside the repository unless an accepted record needs them as evidence.

### Format

Retain the fact table demonstrated in FACTS-codex.md.
Add record-level metadata: owner, task, scope, repository revision, provider/model, observation time, and input references.
Each claim gets a stable identifier, evidence type, evidence reference, status, and explicit invalidation condition.
Source evidence includes file path, line anchor, and revision or digest.
Runtime evidence includes command, environment identity, exit result, relevant excerpt, and observation time.
Store no credentials or private transcript content that the producer cannot share.

Use one canonical file per owning producer and research partition.
A single steward maintains a catalog of identifiers, subjects, scope, and file pointers.
The catalog contains pointers; it does not copy claims.
Use the existing investigation ledger for code-boundary coverage. Link its identifiers instead of creating a second coverage ledger.

### Producer and consumer flow

1. Coordinator assigns a subject and existing relevant claim identifiers.
2. Producer checks the catalog before researching. Fresh matching evidence is consumed; gaps become new work.
3. Producer records claims and evidence before reporting completion.
4. A deterministic validator checks identifiers, links, metadata, evidence digests, and required fields.
5. Frontier review verifies consequential conclusions; a passed format check does not prove the conclusion.
6. Steward accepts the record and updates the catalog.
7. Consumers receive claim identifiers and scoped excerpts. Each consumer records accepted, stale, disputed, or missing inputs.
8. Coordinator permits producer termination after the record and required receipts exist.

For deeper research, preserve the earlier claim and link the new record with `supersedes` or `extends`.
Conflicting conclusions remain visible until adjudication; timestamps alone do not decide truth.
Before reuse, compare revision/digests and time-sensitive expiry conditions.
Invalidate affected claims after relevant file or provider changes; do not invalidate unrelated evidence.

Inference: preventing every repeated discovery is impossible across concurrent or unavailable stores.
Subject ownership, catalog lookup, and duplicate checks can prevent avoidable repeat work.
Measure reused claims, stale inputs, repeated research, and claims lost during termination.

## D. Transport and environment detection

Options: call each platform from skill prose; extend provider hooks only; add an optional transport adapter family.
Recommend the adapter family. Existing adapter contracts already distinguish `unsupported` from `unavailable` (`ADAPTERS.md:27–38`).

Proposed verbs: `probe`, `spawn`, `send`, `wait`, `read`, `close`.
Use capability fields for resume, interruption, events, process cleanup, interactive approval, isolation, and authenticated messaging.
Do not claim these capabilities solely because a command exists.

| Transport | Expected implementation | Proven boundary |
|---|---|---|
| Native | Harness child tools | Respect `CAPABILITIES.md` and provider conformance |
| Headless | Direct provider CLI under an owned supervisor | Codex flags documented; explicit session resume available, C062–C067 |
| herdr | Owned panes and its control API | Contact's BRIEF.md evidence; this planner did not independently test it |
| 1DevTool | CLI teams/links/collect/stop when attributed | Direct run and timeout verified; team control unavailable here, C006/C045 |
| Managed | Explicit user-provided endpoints and permissions | No ownership of their lifetime unless separately granted |

Normalize receipts around task, role, run, submission, sequence, status, and artifact identifiers.
Separate result completion from transport exit and cleanup completion.
Apply an idempotency key to spawn and send where supported; otherwise reconcile before retrying.
Preserve uncertain delivery as a distinct state (C031).

Detection should report several facts, not one guessed environment label:

| Layer | Probe | Interpretation |
|---|---|---|
| Harness | Available native capabilities and active provider | Controls native delegation options |
| Terminal host | herdr markers; 1DevTool `whoami` | Candidate host, verified through its supported control interface |
| Controller | Read-only health/capability request | Installed or advertised does not mean enabled; C052 |
| Attribution | Authenticated caller identity | Required for 1DevTool team operations; C005–C006 |
| Provider | Scoped readiness checks from section E | Separate from terminal host |

Keep explicit configuration authoritative. Auto-detection supplies available choices, not permission to replace the selected transport.
If both hosts are present, preserve both observations and require the selected transport to pass its own probe.
Plain-terminal detection needs no host control service; direct headless execution remains available when selected.

1DevTool restrictions materially affect this adapter:

- Its MCP chart tools author drafts; they cannot spawn agents (C049–C060).
- Tasks dispatch belongs to the human; do not use task creation as autonomous worker assignment (C054/C058).
- Direct `run` uses unrestricted Codex execution and ephemeral sessions (C046/C079–C080).
- A role requiring read-only enforcement must use a proved safe transport; prompt instructions alone are insufficient.
- Link consent, attribution, and uncertain receipts must survive normalization (C029–C033).

## E. Provider availability without a costly call

Options: installed binary check; local authentication check; layered account/limits checks; a small generation request.
Recommend layered checks by default, with no generation request.
Do not promise that any preflight proves the next request will succeed (C078).

Represent installation, configuration, authentication, billing source, model access, quota, and last successful request separately.
Each field carries `verified`, `unknown`, or `unavailable`, its evidence source, and observation time.
A local plan label is evidence of the recorded account, not guaranteed current subscription entitlement.

| Step | Codex | Claude |
|---|---|---|
| Installation | Resolve executable and version | Resolve executable and version |
| Local auth | `login status`; classify sandbox errors separately | `auth status --json`; retain only needed fields |
| Account | Initialize application server; `account/read` without generation | Use auth status and configured billing source; do not expose credentials |
| Models | Paginate `model/list`; match the selected identifier and effort | Use supported account/model metadata when available; otherwise unknown |
| Quota | `account/rateLimits/read`; inspect all applicable windows and reset times | Reuse existing status-line limits; cold-start headless quota remains unknown here |
| Optional stronger check | One explicitly budgeted trivial generation on the selected model | Same, only when authorized and necessary |

Codex protocol methods are documented in C071–C072; their live quota response remains unverified here.
Bound the application-server process and close it after collecting responses.
Claude `/usage` is an interactive option, with the cost limitation in C073–C075.
Do not scrape private credentials or invent an undocumented endpoint to make an unknown result appear verified.

Cache by provider, executable/version, configuration identity, account identity, and selected model.
Invalidate on credential/configuration changes and quota reset boundaries; expose the observation time to the coordinator.
Recheck quota after a quota failure rather than repeatedly invoking the same model.
Distinguish quota exhaustion, missing entitlement, login failure, network failure, and local sandbox failure.

Unknown quota can be allowed by explicit task policy, with the first real task attempt supplying operational evidence.
Provider switching requires configured permission and compatible role/model quality.
Never reroute an explicitly selected provider silently.

## F. Independent opt-in and compatibility

Options: one combined team flag; implicit enablement from installed tools; independent controls.
Recommend independent topology and model-routing controls.

| Topology configured | Multiple providers configured | Expected behavior |
|---|---|---|
| No | No | Existing default behavior |
| Yes | No | All selected roles use the current approved provider |
| No | Yes | Existing delegation shape selects configured provider/model by role |
| Yes | Yes | Role graph and provider routing both apply |

Machine-local provider credentials and executable overrides stay outside committed shared configuration.
Unknown keys remain validation errors (`CONFIG.md:103–107`).
No new package installation, provider probe, process, or external write runs when the extension is disabled.
Existing user-selected approval and review policies remain binding.

## G. Fit with existing plugin mechanisms

| Existing mechanism | Proposed integration |
|---|---|
| `ADAPTERS.md` | Add one optional family, normalized contract, kind registry, and explicit unsupported/unavailable behavior |
| `CONFIG.md` / `afk-config.py` | Register independent topology, role pattern, transport, and provider policy fields |
| `DELEGATION.md` | Keep role-based tiers; topology changes delivery, not judgment quality |
| `PROVIDERS.md` | Keep provider-specific models and command mechanics here and in provider adapters |
| `CAPABILITIES.md` | Declare continuation, messaging, approval, event, and termination capabilities with tested limits |
| `/afk:setup` MANIFEST | Add optional herdr detection/install offer, transport conformance, and provider readiness probes |
| `/afk:autopilot` | Replace only selected spawn delivery; retain one subtask contract and current status ownership |
| `/afk:execute` | Retain worktree, validation, review, and outcome ownership; accept referenced knowledge as additional context |
| Review settlement | Keep independent concerns and existing adjudication; incorporate debate evidence without a second uncontrolled retry loop |
| Notes and investigation | Store durable knowledge through notes; reuse investigation identifiers for coverage |
| `FRESHNESS.md` | Update dependency and artifact registries with each new adapter or runtime artifact |

Evidence: `ADAPTERS.md:137–148`, `CONFIG.md:18–31`, `DELEGATION.md:41–50`, `PROVIDERS.md:51–71`.
Execution references: `skills/afk/autopilot/SKILL.md:32–42`, `skills/afk/execute/SKILL.md:37–39,99–120`.
Review reference: `skills/afk/review/SKILL.md:41–45,63–88,108–110`.

Role quality remains explicit. Planning, reviews, and consequential judgments use frontier tier.
Implementation follows the existing pinned tier rules; plugin/harness work remains frontier tier.
A cheaper fallback must not perform a judgment whose required tier is unavailable.
Native continuation remains constrained by current conformance, even though this research session exposes additional tools.

## H. Debate and independent review

Options: debate every task; debate until agreement; trigger a bounded independent review of disputed decisions.
Recommend trigger-based debate with independent first drafts.
Triggers: unresolved architectural alternatives, conflicting evidence, costly irreversible choices, or an explicit user request.
Use the same mechanism for planning and review; bind its output to the relevant existing decision owner.

Proposed default: one independent draft round and up to 2 critique rounds.
Each critique names claim identifiers, contradictory evidence, and a proposed resolution.
Agreement requires compatible reasons and checked evidence; matching conclusions alone are insufficient.
After the cap, a fresh frontier adjudicator resolves reversible technical disputes.
Human-locked decisions remain with the human through the contact agent.

Multiple models are optional. When disabled, independent same-provider agents can perform the same protocol.
If cross-provider review is mandatory for a task, missing access blocks that requirement explicitly.
Do not weaken existing review independence by reusing the builder as its own reviewer.
Keep findings and adjudication in the existing settlement ledger; record debate artifacts by reference.

## I. Risks and questions for the contact agent

| Issue | Proposed default | Decision or evidence still needed |
|---|---|---|
| 1DevTool attribution | Enable controller transport only from an attributed terminal | Bounded terminal/team spawn-send-collect-stop conformance trial |
| 1DevTool unrestricted direct run | Do not select it for roles requiring sandbox enforcement | Prove a supported enforced-sandbox controller path |
| Unknown Claude quota | Report unknown; no hidden generation probe | Accept unknown-first-task policy or approve a bounded check |
| Durable findings | Repository Markdown plus linked retained evidence | Confirm path, retention, and treatment of sensitive evidence |
| Planner lifetime | Retire after recorded decisions and accepted evidence | Identify tasks whose continuation needs private context |
| Debate cost | Triggered, bounded, observable | Confirm cap and conditions for cross-provider review |
| Controller crash | Reconcile owned runs from durable receipts | Prove restart recovery and duplicate prevention |
| Native capability drift | Adapter conformance over advertised capability | Verify each supported harness version |

These questions belong to the contact agent's design discussion. This proposal does not claim their approval.

## J. Phased delivery

| Phase | Smallest useful result | Acceptance evidence |
|---|---|---|
| 1 | Durable records, catalog, scoped retrieval, and termination receipts around existing native children | Kill a planner; a fresh consumer answers from accepted evidence without repeating the research |
| 2 | Independent provider routing and direct Codex headless adapter | Auth-only probes; unknown quota preserved; explicit session resume; bounded cancellation and process cleanup |
| 3 | Optional `delivery` and `panel` teams on one provider | Single contact; exclusive file ownership; capacity limit; crash recovery; fresh review |
| 4 | herdr adapter and optional setup installation offer | Install only after election; spawn/send/collect/close conformance |
| 5 | 1DevTool adapter | Attributed team and link tests; safe role permissions; verified stop and cleanup |
| 6 | Bounded debate, saved custom patterns, pipeline and hierarchy | Same-provider and multiple-provider cases; dispute cap; human-locked escalation |

Every phase tests the 4 compatibility cases in section F.
No phase replaces current default execution.
Phase 1 delivers the central value: planner knowledge remains usable after its process ends.
