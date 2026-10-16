# Cross-critique — planner-codex, round 2

Date: 2026-09-15. Inputs: `PROPOSAL-claude.md`, `FACTS-claude.md`, `PROPOSAL-codex.md`, `FACTS-codex.md`, and `BRIEF.md`.
`BLOCKING` means resolve before implementing the affected contract. `ADVISORY` means a recommended refinement.
Fact identifiers retain their source namespace. Design objections are judgments, not additional verified facts.
JSONL means one JavaScript Object Notation object per line.

## A. Numbered objections to PROPOSAL-claude.md

1. **BLOCKING — Define termination for running headless agents.** Sections b and d say there is “nothing to kill.” This applies only after confirmed exit. Cancellation, hangs, startup hooks, and descendants still need owned termination. Our bounded run observes 23 processes before timeout cleanup. Also replace background `claude rm` with `stop` when retaining history; `rm` deletes the session and worktree. Require exit confirmation and cleanup status in `close`.
   **Facts:** `FACTS-codex.md` C040–C045; `FACTS-claude.md` CN-05, PL-33.

2. **BLOCKING — Enforce role permissions through the selected transport.** An owned worktree does not restrict machine access. Claude's default permission mode is not demonstrated read-only enforcement. The 1DevTool direct-run recipe injects bypass flags, including for a planner. Define required permission capabilities per role and refuse a transport that cannot enforce them. Unrestricted execution requires separate authorization and containment policy.
   **Facts:** `FACTS-claude.md` DT-12, CN-03, CX-07; `FACTS-codex.md` C046, C063, C079.

3. **BLOCKING — Separate evidence freshness from claim verification.** Section c promotes claims through hashes, successful commands, or existing fact references. Those checks establish evidence properties, not the asserted conclusion. An unchanged line can have changed callers or configuration. Preserve a separate conclusion verdict and its reviewer or executable assertion. Automatic checks may invalidate evidence; they must not silently promote an inference to fact.
   **Facts:** `FACTS-claude.md` KS-05–KS-07, PL-29; `FACTS-codex.md` C070–C078. `LEDGER-FORMAT.md` distinguishes supporting nodes, claims, and counter-checks.

4. **BLOCKING — Do not authorize command replay from producer-supplied `safe:true`.** That label cannot prove a command is read-only or still safe. A repository script can change after capture. Verification needs approved probe definitions, argument validation, executable identity, permissions, timeout, and output redaction. Preserve arbitrary command evidence without automatically executing it.
   **Facts:** `FACTS-codex.md` C068, C076, C079; `FACTS-claude.md` PL-20, PL-29. The replay rule is a new design choice, not an existing authorization mechanism.

5. **BLOCKING — Scope fact identity and settle conflicting events explicitly.** A hash of claim text alone merges identical sentences from different versions, accounts, or repositories. Last-event-wins can also overwrite a supported refutation with a later stale verification. Namespace claims by subject and scope; distinguish observations from adjudication. Serialize concurrent appends and make retries idempotent. A shared writer script alone does not establish those properties.
   **Facts:** `FACTS-claude.md` KS-05, KS-10; `FACTS-codex.md` C068–C077. `LEDGER-FORMAT.md` rejects conflicting records and conservatively combines claim classifications.

6. **BLOCKING — Make retained knowledge and resumable history conditional capabilities.** Section b generalizes session resumption, but ephemeral Codex runs do not retain resumable sessions. Its repair rule also closes an agent after failed verification without establishing that the findings were durably written. Require a recorded artifact receipt before normal retirement. On forced termination, preserve available capture and explicitly record any lost or unfinished knowledge. Retain cited evidence outside merge-deleted artifacts, or relocate it before cleanup.
   **Facts:** `FACTS-codex.md` C047, C066–C067, C079–C080; `FACTS-claude.md` CN-03, KS-16–KS-17.

7. **BLOCKING — Add an actual single-agent selection and close the independent-configuration cases.** `solo` aliases `native`, which still spawns existing subagents. This does not implement the requested topology `none`. The `second-opinion` pattern requires another provider, conflicting with same-provider teams unless explicitly restricted. Also resolve `providers.cross_model:true` when `agent` is absent: section f both disables the adapter and requires headless execution. Specify all combinations and their effective behavior.
   **Facts:** `FACTS-claude.md` SP-01, SP-09, SP-21; `BRIEF.md` goals 4 and 6. Same-provider capability is a requirement, not an inferred platform feature.

8. **BLOCKING — Do not make daily generation the normal availability probe.** The reported Codex “Reply OK” run consumes 18,541 tokens. A trivial prompt does not bound startup context or hook cost. Probe local authentication and available account/quota metadata first. Keep quota and model entitlement unknown when unmeasured. A generation probe needs an explicit budget and selection policy; yesterday's successful cheap-model request does not prove today's frontier-model access.
   **Facts:** `FACTS-claude.md` CN-13, CX-04; `FACTS-codex.md` C068–C078.

9. **BLOCKING — Preserve explicit provider and transport choices.** Section e substitutes the harness provider when an explicitly named provider fails, unless `strict` is set. Recording a decision does not authorize that substitution. Apply configured fallback only to automatic selection or an explicitly approved fallback list. Likewise, optional transport degradation must preserve the task's required permissions, independence, and communication capabilities.
   **Facts:** `FACTS-claude.md` PL-20, PL-29, DT-13; `FACTS-codex.md` C031, C046. The fallback default is the disputed design choice.

10. **BLOCKING — Correlate each submission with its result and completion event.** The transport table returns only `{state}` from send/wait. Herdr explicitly warns that the current turn's completion can satisfy a wait for another submission. Add submission identifiers, expected result identifiers, reconciliation, and uncertain-delivery handling. Also state which external event wakes the manager after timeout. A helper writing a file does not itself resume the waiting manager.
    **Facts:** `FACTS-claude.md` HR-07, HR-09, PL-33, CN-15; `FACTS-codex.md` C025–C031.

11. **ADVISORY — Treat terminal capabilities as more than visibility.** The summary says terminal tools add visibility only. The documented transports also provide attributed messaging, consent, approval interaction, and persistent controller state. Advertise those capabilities separately. File exchange is useful, but it cannot replace a required approval or authenticated message.
    **Facts:** `FACTS-claude.md` HR-06, DT-08, DT-11, CN-10; `FACTS-codex.md` C029–C033, C051–C052.

12. **ADVISORY — Keep synthesis ownership and review quality explicit.** Planner roles can research and draft from supplied artifacts. They must not take over the contact's conversation synthesis or single-writer decisions. Each debate round must satisfy the configured frontier tier; escalation is for unresolved points, not permission to weaken the first judgment. Clarify the referee rule when the contact uses the same model as a participant.
    **Facts:** `FACTS-claude.md` PL-25–PL-26, PL-29, PL-32, SP-12–SP-13.

13. **ADVISORY — Reduce phase 1 and use runtime rendering only.** The proposed first phase introduces storage, probes, a transport family, review integration, setup changes, and configuration together. First prove that a fresh consumer can use a terminated planner's evidence. Then add provider routing and external transport. Keep rendered fact digests temporary or on demand; avoid a second committed source of truth.
    **Facts:** `FACTS-claude.md` PL-08, PL-39–PL-40, KS-16–KS-17; `FACTS-codex.md` C023–C024.

## B. Facts disputed or not reproduced

| Fact in FACTS-claude.md | Assessment | Evidence and required qualification |
|---|---|---|
| DT-02 | Dispute the headless return shape | `EVIDENCE-codex-live.json` returns agent/output/exitCode/duration and timeout fields, without `runId`. Scope `runId/teamId` to the controller path that supplies them. `FACTS-codex.md` C011, C013, C042–C043. |
| DT-03 | Missing terminal qualifier | Automatic worktree creation applies to terminal write-category runs. Do not apply this rule to every headless run. `FACTS-codex.md` C014. |
| DT-07 | Missing swarm qualifier | The Codex/Claude/Cursor sandbox restriction belongs to headless swarm workers, not every headless Team member or direct run. `FACTS-codex.md` C018–C020. |
| DT-10 | Partially contradicts this planner's observation | Codex/Claude `unverified` matches. The claim that others are `not-found` omits Grok `detected`, version 1.0.5, in this planner's `list --json` result. Treat installation results as timestamped snapshots; the difference may reflect environment or timing. |
| DT-17 | Update with the narrower live result | Spawn and timeout termination are now verified for direct headless execution. Team stop still lacks live proof here. `FACTS-codex.md` C042–C045; `EVIDENCE-codex-live.json`. |
| KS-06 | Accept the stated line-identity mechanism | `LEDGER-FORMAT.md` confirms comparison by class, file, and line hash. I dispute its use as semantic verification in the proposal, not this fact's line-shift behavior. |
| CN-03, CN-05, CX-02 | Command-help claims reproduced | Local help confirms the listed permission controls, Claude background lifecycle commands, and Codex queue/daemon commands. Live enforcement, queue delivery, and background stop were not tested this round. |
| CN-04, HR-14 | Resumption not reproduced this round | Require a persisted session and access to its session store. Do not generalize to ephemeral runs or deleted sessions. `FACTS-codex.md` C066–C067, C080. |
| CN-08 | Inference remains unresolved | An inherited environment marker is insufficient to establish native child depth. Do not use it alone as the team-spawn authority check. `FACTS-claude.md` already marks its semantics inferred. |
| HR-22 | Accept only its source-session scope | The reported sandbox failure does not establish that all future herdr access requires full bypass. Test the selected permission path. `FACTS-codex.md` C068 illustrates why environment failure needs separate classification. |
| CN-13, CX-04 | Historical runs not repeated | I accept their reported timing/token data as attributed evidence, not independently reproduced measurements. No additional generation probe runs in this critique. |
| HR-01–HR-25 | No new herdr lifecycle trial | This round does not repeat pane creation, messaging, or closure. Documentation and prior-session claims retain their original evidence boundary. |

The ledger introduction also needs a status correction. It defines `unverified` as documented but unexercised, then marks several documentation-only rows `verified`.
Choose one meaning and record evidence type separately. Neither convention should imply successful runtime operation.
The introduction's “No ... agent ... was created” also needs qualification: CN-13 and CX-04 describe new headless agent processes.

## C. Ideas adopted over PROPOSAL-codex.md

| Adopted idea from PROPOSAL-claude.md | Revision to my position | Conditions |
|---|---|---|
| JSONL events through one writer script | Prefer canonical structured events over separately authored Markdown fact tables for automated teams | Scoped identifiers, serialized writes, explicit verdict transitions; render readable digests on demand |
| `turn / phase / feature` lifespan | Make expected lifespan a declared role field | Lifespan is a policy boundary; process cleanup and retention checks still control closure |
| Spec-local durable knowledge | Store canonical records beside the feature's specifications | Add a repository catalog for cross-feature retrieval; retain referenced evidence outside deleted run artifacts |
| File-only `managed` mode | Make manual file exchange the minimum managed interface | Add live endpoint binding only when requested; retain user ownership of session lifetime |
| Narrow named patterns | Prefer `second-opinion` and `planner-duo` over my broader initial `delivery` pattern | Permit same-provider independent roles; cross-provider requirements are explicit |
| Explicit persistent roster and status command | Make recovery a deterministic projection of lifecycle events | Track submission ownership and process identity, not just session and pane identifiers |
| Reuse session history after closing a process | Permit later resumption when private context is still useful | Require demonstrated persistence and compatible scope; retain disk handoff as the baseline |

I retain my smaller first phase, non-generation default probes, explicit fallback policy, and separation of freshness from truth.
I also retain independent topology/provider settings and an actual `none` selection.

## D. Revised position by BRIEF.md section

| Section | Revised position |
|---|---|
| (a) Topology | Preserve native defaults; support none, managed, and team; start with configurable second-opinion and planner-duo patterns. |
| (b) Lifecycle | Declare turn/phase/feature lifespan; retire only after artifact receipt and owned cleanup; resume only proved persistent sessions. |
| (c) Knowledge | Use scoped JSONL events, one serialized writer, a repository catalog, retained evidence, and separate freshness and conclusion checks. |
| (d) Transport | Add an optional capability-based adapter with correlated submissions, bounded supervision, verified identity, and explicit transport selection. |
| (e) Availability | Probe installation, authentication, account, model, and quota separately; preserve unknowns; make generation checks explicitly budgeted. |
| (f) Opt-in | Keep topology and provider routing independent; define all configuration combinations; preserve explicit selections and unchanged defaults. |
| (g) Integration | Reuse adapters, role tiers, setup election, investigation records, and existing artifact ownership; prove every new runtime capability. |
| (h) Debate | Use independent drafts and bounded critique within existing settlement; preserve frontier quality and human decision ownership. |
| (i) Open issues | Settle enforced permissions, unknown-quota policy, evidence retention, attribution, and recovery before enabling affected execution paths. |
| (j) Delivery | First prove knowledge survives planner termination; then add provider routing, headless transport, terminal adapters, and broader patterns. |

Contact-review consumer: compare these objections with `PROPOSAL-claude.md` and reconcile accepted changes into the shared design.
