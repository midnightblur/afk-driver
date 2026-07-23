# Changelog

What changed for **devs using the plugin** — one line per feature/enhancement
you'd notice, grouped by date (no versions), newest first. Internal refactors,
wording sweeps, and review-fix churn are deliberately omitted. After a `git
pull`, skim the dates you missed, then `/reload-plugins` (and `/afk:setup` if
an entry says the dependency set changed).

Maintenance: a commit shipping a dev-visible change adds its one-liner under
today's date **in the same commit** — trigger owned by this file's
`FRESHNESS.md` registry row.

## 2026-07-23

- New skill `/afk:to-demo-plan`: turns a delivered feature into `DEMO-PLAN.md`, the script for the hour you spend showing it to **product owners and QA**. It reuses what the chain already settled — the PRD's pain + user stories, the verification plan's walked click-paths, the ADRs, the delivered diff — and lays them out as **beats** (what to *say*, the exact steps to *do*, the line to land, its minutes), each classed **show** (performed live) or **tell** (one sentence, so obvious behaviour never eats the clock). Ordered why → concepts → happy path → touch points → edges, with a **touch-point map** of everything the feature adds to / changes in / interacts with existing behaviour (every `changes` row must be shown — that's QA's regression scope), ≤3 decisions explained in consequence language, questions **pre-empted at the beat that raises them**, an explicit out-of-scope table, and a setup section so no beat depends on state nobody created. Budget: ≤60 min with ≥10 protected for questions. The plan demos *value*, not correctness — the gates already settled correctness. Repo-only; adds a `Demo plan` row to the ticket `INDEX.md`.

## 2026-07-22

- `/afk:grill-verification` now **resumes from `GRILL-LOG.md`** like the other two grills: its opening digest reads any existing checkpoint section, so the documented post-SDD re-run (design the deferred API scenarios) picks up the already-settled UI journeys and per-aspect verdicts from disk instead of re-walking them. It already wrote the section — only the read side was missing.

## 2026-07-21

- Ticket spec folders moved out of the packaged-resources tree: the convention is now `{service}/specs/{year}r{release}/{TICKET-ID}/` (was `{service}/src/main/resources/specs/...`). Payable's specs migrated to `11700-payable/specs/`; every path-carrying skill (`/afk:to-prd`, `/afk:fix`, `/afk:retro`) and doc updated. Specs no longer risk shipping in a service jar, so payable's pom stops overriding Maven `<resources>` (which had silently dropped `descriptor.yaml` and application-property filtering).
- `/afk:prototype` now renders through **lavish** (new RP-8): the mockup serves in the Lavish Editor, where the annotation toggle lets you drive the simulation as before *and* pin feedback to specific elements, select text, or hit embedded feedback controls — notes land back in the session via poll instead of being described in chat. Mockups stay fully portable (live controls marked `data-lavish-action`, `window.lavish` calls guarded — rules generalized into `LAVISH.md`'s new **Drivable artifacts** section, alongside the `poll --agent-reply` shape); plain-browser `file://` refresh remains the fallback.
- `/afk:to-ticket` re-publishes now leave a paper trail: when the ticket already carries a published description and the PRD changed (requirement gaps closed, scope added/cut), the skill distills the delta into `TICKET-CHANGES.md` and the engine posts it as an **issue comment** right after the description update (`--changes`; one confirmation gates both writes) — the description keeps showing current truth, comments record how the requirements moved. The dry-run summary gained an `action` line (`first publish` / `re-publish`), and a first publish skips the comment with a warning.
- `/afk:prototype` mockups now render **in situ**: every new screen sits inside a replica of the real app shell (nav, header, breadcrumbs, active item), and the feature's **neighbor pages** — where each story enters from and where it navigates to — appear as shallow drivable stubs, so you reach the new UI by clicking from where you'd really start. The capability walk drives each story from its entry-point stub, and the fidelity pass diffs shell + nav chrome too — familiarity is the instrument for spotting gaps.

## 2026-07-20

- `/afk:grill-requirements` "Challenge the want" gains a third standing obligation: every validity change (new gate, admin mode/toggle, curation, removal) is walked over still-editable records created before the change or under the other setting — every record the change makes rejectable needs a named, role-reachable repair affordance, and "no silent migration" decisions must name that affordance in the same requirement. New exit-gate bullet enforces it.
- `/afk:understand` is now the one-stop shop for **learning any piece of code** — it takes a shipped feature (`{plan-dir}`), a **GitLab MR URL**, or a **code area** (`path:`/`symbol:`) and produces the same self-contained interactive HTML learning artifact for each (`/afk:to-code-walkthrough` is retired; its MR fetcher, spec discovery, and size gates moved into understand). The artifact also became a much better teacher: learning objectives + key concepts & constraints up front, a one-sentence mental model re-invoked through walkthrough and recap, the walkthrough split into **one tour step per seam/flow group** (stated ordering rationale, plain-language overview before code), evidence-grounded "where you'd naturally go wrong" callouts, optional one-question checks per group, and a recap section — all enforced by five new skeptic criteria (jargon-before-use, ordering rationale, objectives/recap integrity, representation match, grounded misconceptions). Shell chrome gained resume-where-you-left-off, per-step reading-time hints, and an **ask-the-teacher** button that assembles a context-rich clipboard prompt for a live Claude Code session (page stays fully offline). The interactive-walkthrough widget catalog grew two teaching widgets: a **before/after comparator** and a **predict-then-reveal** pause.
- New skill `/afk:gc`: post-merge spec compaction. After a feature's MR merges, it proposes — and on your approval deletes — the ticket folder's run artifacts (whole `plan/`, `GRILL-LOG.md`, publish intermediates), keeping the evergreen docs (PRD/SDD/ADRs/VERIFICATION-PLAN/PROTOTYPE/INDEX/understanding) and recording the git archive ref in `INDEX.md`. Stops stale subtask contracts and settled review findings from surfacing in future sessions' greps as current truth. `plan/`'s lifespan (slicing → merge) is now declared in `/afk:to-subtasks`, and `/afk:preflight`'s success report points at the post-merge step.

## 2026-07-19

- `/afk:setup base` now checks the IntelliJ IDE max heap (W7): every installed `IntelliJIdea*` config dir must set `-Xmx` ≥ 16384 MB (default target; pick your own at the election) — the stock 2 GB heap thrashes on a monorepo reimport. Fix upserts the `-Xmx` line in `idea64.exe.vmoptions`, leaving other options untouched.
- `/afk:prototype` now settles a **drivable** mockup, not a picture: every PRD User Story / Acceptance Criterion must be clickable in the HTML (simulated client-side against fixtures) or logged as a gap — enforced by a pre-settle **capability walk** — and a **fidelity pass** diffs the mockup side-by-side against the live app (or the `/afk:design-system` catalog), with the fidelity basis (`live-verified`/`catalog`/`source-only`) recorded in `PROTOTYPE.md`. Anchoring is layered: catalog first, live-DOM lifts second, source digest as fallback.
- Grill sessions got faster, same rigor — agent work now overlaps your think-time instead of alternating with it: delegation doctrine adds a think-time overlap rule (background digests spawned before the turn yields — `DELEGATION.md`); confirm-batch evidence pre-fills as items accumulate instead of at the batch boundary (`TRIAGE.md`); the L9 seam walk fans out parallel draft seam rows and interviews only the mismatches, with compatibility auditors launching as each area locks; `/afk:grill-requirements` and `/afk:grill-solution` open with a parallel pre-brief digest (glossary, staples, ADRs, prior grill log) instead of mid-session reads; the devil's-advocate pass runs alongside the final confirm batch; lavish renders warm up at phase start and live artifacts re-render at question boundaries (`LAVISH.md`).
- `/afk:to-ticket` no longer publishes the raw PRD: it first distills a requirements-level `TICKET.md` (User Stories + Acceptance Criteria mandatory; no technical depth, no repo-artifact references) and publishes that — Product Owner/QA-readable ticket descriptions.

## 2026-07-17

- `/afk:setup base` is now elective per item: the pre-fix report doubles as a pick list of every base-tier item needing action (toolchain pins + all workstation apps/OS config, including anything added to the register later), so you install only what you'll use — deselected items report `skipped (user choice)` instead of `needs-human`. The skill-load-bearing default surface stays mandatory.
- New utility `/afk:review-qa-tests`: review a QA team's **manual** test cases (typically a spreadsheet) against the feature's requirements and annotate their sheet in place — missing scenarios as new rows (only the human columns filled, scoring left to QA), fixes to existing cases as threaded comments. Writes strictly at requirements/behaviour level: the QA reader is treated as **black-box** (nothing about code, bugs, or dev process reaches a comment), and a **manual reach** filter recommends dropping cases only automation can exercise (injected faults, multi-instance, true races). Ambiguities settle with you before anything is written. Ships an `EXCEL.md` recipe + a reusable `annotate_sheet.py` that writes real threaded comments (not legacy notes) and dodges the two orphan-relationship faults that make Excel prompt to repair.

## 2026-07-16

- `APP_START_SKIP_UI=false` now actually serves a frontend. It was a silent no-op: the default Maven profile leaves `*-ui` out of the reactor, so the UI never built, the app's `public/` stayed empty, and the instance booted serving nothing — a browser tier would pass against a page that wasn't there. `app-start-gate.sh` now runs the service's own `build_ui.sh` before packaging the leaf, refuses to boot (exit 2) if the build leaves no `public/index.html`, and clears the SPA target before each build so a reprovision serves the fresh UI rather than a stale copy nested one level deep (`cp -R` nests into `public/spa/` when `public/` already exists). Reaching for Maven's `-DskipUi=false -DpipelineBuild=true` instead would force every in-house UI lib to rebuild (`skipUi` is global) — needing a vite/rollup native binary that isn't pinned on all dev platforms, to remake a `dist/` that already exists. New env var: `CI_PROJECT_DIR` (optional, defaults to the repo root).
- Lesson ledger made trustworthy on Windows: `lesson-digest.sh` no longer reports a parse-failed ledger as "no lessons recorded" (it now says `ledger unreadable` and tolerates stray non-UTF-8 bytes per line), and `lesson-append.sh` emits ASCII-safe JSON so console-codepage output can't corrupt the ledger again.
- Settle loop (`skills/afk/review/SETTLEMENT.md`): a fix that introduces new behaviour is now a design change, not a patch — the implementor must enumerate its failure modes and pin each with a test in the same fix commit, instead of letting successive review rounds design the feature one finding at a time.
- Mission control rebuilt as a two-layer interactive dashboard (spec design ADR-0008). The page is now a navigable app (sidebar sections, keyboard nav, page-wide legend tooltips, freshness dots) instead of one scroll of raw tables. **Live** sections stay deterministically derived and gained real synthesis: an Overview hero (phase ribbon, status bar, gate chips, artifact inventory), Progress with per-subtask sub-phase detail (settle round, review verdict, per-subtask commits mined from subject tags + journal-recorded hashes), a filterable Timeline, Gates (smoke + preflight + rollup + adversary), auto-mined Insights (open parks/blockings/advisories with superseded items dropped), and feature-scoped Diffs. **Digest** sections (architecture module DAG, steppable flow simulations, entities, ADR decision cards, critical-logic shortlist, legend) render committed hash-stamped `plan/digests/*.json` authored by the new `/afk:mission-control build` mode — schemas + digestibility rules in the skill's `DIGEST-FORMAT.md`; stale/unbuilt digests render an amber hint and launching never spends tokens. Renderer CLI grew `--check-digests`; panel parsers moved `scripts/mc/panels/` → `scripts/mc/sections/`.
- Model selection goes role-based and provider-named: `DELEGATION.md` now defines three tiers — **frontier** (grills, planning/slicing, review + adjudication, gating verdicts: Fable, or Opus if unavailable), **implementation** (product code from a frontier-authored plan: Opus, never Fable; Sonnet for simpler slices), **digest** (Sonnet; mechanical chores at low effort) — with Codex CLI equivalents (`gpt-5.6-sol`/`-terra`) named in `PROVIDERS.md`. "Inherit the session model" is gone; autopilot's `## Complexity` routing follows the tiers; and any work on the plugin/harness itself always runs frontier.
- New utility `/afk:settle-mr`: review any GitLab MR (URL or IID — bug fixes and small work outside the AFK chain) against a real MR-head worktree checkout, using the same review machinery and settle loop as the AFK gates, with the MR itself as the ledger — every finding is an inline MR discussion, fixes/disputes/adjudication verdicts reply on the threads, and a managed summary comment keeps the round accounting, so sessions and devs can hand the MR off mid-loop. Your own MR defaults to the auto-fix loop (fixer subagents read findings from the MR threads, fix-or-dispute on merit, commit+push per round until nothing actionable remains); someone else's MR defaults to review-only, each re-invocation a follow-up round over new commits + author replies. Never merges. Replaces the personal `gitlab-mr-review` skill.
- Skill authoring is now doctrine-at-write-time: plugin `CLAUDE.md` requires loading `writing-great-skills` before creating or editing any skill file, replacing after-the-fact audits.
- Worktrees stop competing over `~/.m2`: `create-worktree` now provisions a private per-worktree Maven repo — it writes `.mvn/maven.config` (`-Dmaven.repo.local=<worktree>/.m2/repository`, picked up automatically by every `./mvnw` run, the maven-invoking hooks, and IntelliJ) and seeds it from your local repo minus `*-SNAPSHOT` dirs (robocopy, `cp -a` fallback; dependency set changed — C8). Opt out with `--no-m2`; `--m2-seed <path|none>` overrides the seed source. Retrofit an existing worktree by writing the same one-line `.mvn/maven.config` in it.
- Review gate goes multi-round: execute Step 10 and preflight PF-3 now settle the independent review through a fix-or-dispute settle loop (`skills/afk/review/SETTLEMENT.md`) — fresh re-review after every remediation, every finding (nits included) fixed or disputed, disputes adjudicated by fresh skeptics, and termination accounting (hard 10-round stalemate cap → flagged for a human) kept by the referee, never leaked into reviewer/adjudicator prompts. Rounds after the first review only the remediation delta (`--base` last-reviewed tip, full diff handed to reviewers as context) and stay cheap by construction: the reviewer fan-out consolidates to one `delta-sweep` reviewer plus signal-activated specialists (fix-owner concerns, delta triggers, or an oversized delta), and per-round re-verification is compile + local tests only — live tiers, mutation probe, and other expensive surfaces run once outside the loop. `/afk:review` grew `--tag` for per-round artifact naming; the adversary gate now carries its own 2-cycle cap.
- Token-lean runs, same gates: subtask contracts now carry `## Context excerpts` (slicing-time verbatim PRD/SDD/ADR quotes) so each executor works from its contract instead of re-reading the parent docs; execute's design-bar checklist reads and review's `refactor-safety` concern are trigger-gated by diff/slice shape; review materializes the diff once to a scratch file for all reviewers; `/afk:grill-verification` ingests sources via an `afk-reader` digest; maven-compile/ui-lint gates report triaged failure digests (full log to a file) instead of unbounded dumps.

## 2026-07-15

- Pass cache extended to all Stop gates: wiring, skill-registry, codex-drift, and genericity now skip their scans when the tree is unchanged since their last pass (`gate-cache.sh`, previously compile/lint/format only); wiring bypasses the cache in final mode.
- Glossary-first grilling: `/afk:grill-requirements` now actively hunts candidate terms from the first exchange (draft-then-verify questions, asked as soon as a term surfaces), gates exit on a user-verified entry per term, and commits the glossary before `/afk:to-prd`; `/afk:execute` reconciles `GLOSSARY.md` post-subtask when implementation semantics diverge from the grill-time definition.
- Conclude-at-detection self-improvement loop: new `/afk:lessons` steward + a main-checkout workflow lesson ledger (`.claude/lessons/LEDGER.jsonl`). Detection points capture classified lessons with drafted edits the moment they conclude (execute's review/adversary outcomes, `/afk:fix` Phase 3.5 — now records to the ledger instead of a handoff doc, `/afk:claude-md` HARVEST, `/afk:glossary` GRILL); `/afk:execute` reads open lessons before designing; preflight surfaces open drafts (new advisory row PF-4c); `/afk:retro` grades lesson closure and escalates recurrences (reword → relocate → checklist → gate).
- `/afk:setup base` now provisions the WSL2 runtime Docker Desktop requires (C7 — absent WSL surfaces as Docker's misleading "virtualization support not detected" error even with firmware virtualization on); also fixed two Windows probe false-negatives: H6 no longer trips on the `python3` Store stub, W5's `reg query` gets the `MSYS_NO_PATHCONV=1` prefix Git Bash needs.
- Faithful-input doctrine: api/e2e verification must drive the real client's interaction shape — never reshape an input to dodge an unexpected failure (that failure is a candidate defect). Rule added to the subtask contract's Verification template, both verification AUTHORING guides, payable's TESTING.md antipattern list, and `/afk:fix`'s escape analysis (new miss class `dodged-failure`).
- `/afk:setup base` grew a hosts-file check (W6): `127.0.0.1 proxy` must be in `C:\Windows\System32\drivers\etc\hosts` so `proxy`-hostname URLs resolve for local builds.
- Dual-provider support: the workflow now also runs under the OpenAI Codex CLI — a generated mirror (`.agents/skills/`, `.codex/`, AGENTS.md block) produced by `tools/payable/ai-agents/codex-sync/generate.py`, a `PROVIDERS.md` provider mapping, a provider shim for hooks (`hooks/lib/provider.sh`), Jira creds fallback to `~/.codex/config.toml`, `/afk:setup` section O for Codex provisioning, and a `codex-drift-gate.sh` Stop gate that keeps the mirror regenerated in the same commit.
- `/afk:setup`'s human-gated fixes are now one script: run `skills/afk/setup/scripts/setup_secrets.py` from your own terminal — prompts for tracker + SCM credentials, validates before writing, never echoes a secret, idempotent.
- The Jira MCP server now ships in-plugin (`mcp-servers/jira/server.py`) — no separate checkout; registered user-scoped under key `jira` (the setup script places it).
- Wiring gate diffs new files against `origin/master` instead of your branch's upstream — other teams' merged files can no longer false-block your turn.
- `/afk:setup base` grew two checks: JDK distribution pinned to Amazon Corretto, and Windows long paths (OS registry flag + `git core.longpaths`).
- Registry gate now also blocks uncatalogued skills (no `CLAUDE.md`/`README.md` mention) and unregistered hook env toggles (no MANIFEST E-table row); seven previously undocumented toggles got registered.

## 2026-07-14

- `/afk:setup base` — opt-in provisioning of the version-pinned monorepo toolchain (git, JDK, Maven, Node/npm, Python, Docker) plus workstation apps and OS config, for fresh machines and pin bumps.
- `/afk:understand` — post-ship interactive HTML explainer per feature (dual-depth background, seam-ordered diff walkthrough, opt-in quiz); auto-run from preflight's advisory row or standalone; surfaced in `INDEX.md` and a new mission-control panel.
- New `interactive-walkthrough` utils skill (agent-invoked): embeddable HTML flow-slider / branching-simulator / overlap-gantt widgets; `draw-charts` became agent-invoked only.

## 2026-07-13

- `/afk:bug` — mid-task bug pipeline: `capture` (evidence bundle + Jira Bug before anything else), `dispatch` (autonomous fixer in its own worktree → Draft MR you merge), `status` / `retest` / `purge`.
- `/afk:review` rebuilt multi-aspect: 11 book-derived concern checklists, diff-shape triggers for design-level concerns, adversarial skeptic pass before design findings gate, pattern-debt channel.
- Genericity Stop gate: added plugin prose naming a concrete ticket or product symbol blocks the turn (deliberate references go in `hooks/genericity-allow.txt`).
- Verification coverage is exhaustive by default — a subtask declares every applicable tier, not a sample.

## 2026-07-11

- Shared Jira library (`scripts/jira_core.py`): one engine for creds resolution, ADF conversion, and attachment/media upload behind both the PRD and Bug publishers.

## 2026-07-10

- Branch-name gate (git-level, agent-only): an agent creating an off-pattern local branch is refused at ref-update time; branches you create in your own terminal/IDE are never gated.

## 2026-07-09

- Skill-registry Stop gate: a skill dir missing from `plugin.json` blocks the turn — the drift that had silently hidden `/afk:setup` and `/afk:retro` (both re-registered).
- Lavish artifacts render dark-mode deterministically (PreToolUse hook).
- Delegation routing: mechanical slices route to Sonnet (Haiku tier dropped).

## 2026-07-08

- `/afk:setup` — the workflow doctor: probes every entry of the new dependency register (`skills/afk/setup/MANIFEST.md`), fixes what it can, guides the rest; idempotent for first install and post-pull repair.
- `/afk:retro` — cross-feature retrospective mining journals, review rollups, and gate metrics into evidence-cited plugin-edit proposals.
- Code Stop gates: maven-compile, ui-lint, java-format — with a content-hash pass cache so unchanged trees cost nothing.
- `/afk:to-ticket` meeting mode: publish collapsible Meeting Summaries onto any ticket, disjoint from the PRD block.
- The design chain went purely offline: the SDD is no longer published to Jira.
- CLAUDE.md steward: role-scoped sidecars (`IMPL.md`/`TESTING.md`/`DEBUG.md`) keep CLAUDE.md decision-only.
- Lavish render is mandatory at grill render points when a human is present.

## 2026-07-07

- `/afk:mission-control` — read-only per-feature dashboard (watch mode or `--once` retroactive render).
- `/afk:preflight` — feature-level ship gate: merges master behind an ancestry guard, re-validates, integrated review, babysits CI, flips the Draft MR to Ready; chained from autopilot after smoke-green.
- `LAVISH.md` + render points: human-present visualizations woven into the grill/design skills.

## 2026-07-06

- Wiring gate ships with the plugin: a new artifact with no consumer and no anchored IOU blocks the turn; `verify-seams` (agent-invoked) is the judgment tier.
- Chain-wide skill audit shipped behavior fixes: park-on-timeout autopilot semantics, bounded adversary respawns, lockstep drift repairs.
- `tdd` and `verify-seams` hidden from the `/` menu (agent-invoked only).

## 2026-07-05

- `/afk:autopilot` — hands-off plan driver: fresh subagent per subtask, parks failures + dependents while independent work continues, ends at the smoke gate.
- `/afk:adversary` — live-app execution gate probing the running app under an information diet, wired into execute as Step 10.5.
- Human-followability layer: `REPORTING.md` plain-terms protocol, plugin `GLOSSARY.md`, ticket `INDEX.md` dashboard, append-only `plan/JOURNAL.md`, review rollup, `TRACE.md` matrix, grill-log checkpoints.
- Delegation doctrine (`DELEGATION.md`) + named `afk-reader`/`afk-runner` subagents woven through the chain.
- `writing-great-skills` adopted as the skill-authoring reference (`create-skill` retired).

## 2026-07-03

- Staples registry: per-service `STAPLES.md` (stewarded by `/afk:claude-md`) with consult/capture loops threaded through grill → PRD → SDD → subtasks → review.

## 2026-06-30

- `/afk:review` — independent post-verification review gate (findings contract, severity rubric), wired into execute Step 10.

## 2026-06-29

- Verification doctrine: persistence must be proven by API refetch, never by UI echo alone.

## 2026-06-23

- Plugin lands at `tools/payable/ai-agents/plugins/workflow`: core chain (grill-requirements → to-prd → to-ticket → grill-solution → to-sdd → to-subtasks → execute → smoke-test) plus `prototype`, `design-system`, the `claude-md` steward, and the `tdd` doctrine.
- `/afk:fix` — disciplined bug-fix orchestration: diagnose wrap, proportional test coverage, escape analysis of the test that should have caught it.
