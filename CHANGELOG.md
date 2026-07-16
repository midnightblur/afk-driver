# Changelog

What changed for **devs using the plugin** — one line per feature/enhancement
you'd notice, grouped by date (no versions), newest first. Internal refactors,
wording sweeps, and review-fix churn are deliberately omitted. After a `git
pull`, skim the dates you missed, then `/reload-plugins` (and `/afk:setup` if
an entry says the dependency set changed).

Maintenance: a commit shipping a dev-visible change adds its one-liner under
today's date **in the same commit** — trigger owned by this file's
`FRESHNESS.md` registry row.

## 2026-07-16

- `APP_START_SKIP_UI=false` now actually serves a frontend. It was a silent no-op: the default Maven profile leaves `*-ui` out of the reactor, so the UI never built, the app's `public/` stayed empty, and the instance booted serving nothing — a browser tier would pass against a page that wasn't there. `app-start-gate.sh` now runs the service's own `build_ui.sh` before packaging the leaf, and refuses to boot (exit 2) if the build leaves no `public/index.html`. Reaching for Maven's `-DskipUi=false -DpipelineBuild=true` instead would force every in-house UI lib to rebuild (`skipUi` is global) — needing a vite/rollup native binary that isn't pinned on all dev platforms, to remake a `dist/` that already exists. New env var: `CI_PROJECT_DIR` (optional, defaults to the repo root).

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
