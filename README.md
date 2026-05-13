# afk-driver

Async-from-keyboard driver for the Nakisa core-services platform. Drains
`afk-agents`-labelled Jira SubTasks under their parent Enhancement, opens a
Draft MR, spawns a fresh Claude Code session per SubTask via the `/afk:execute`
skill, transitions tickets through `Dev-Pending → Dev-Designing →
Dev-Developing → Dev-CR/Merge`, and produces a morning digest.

Bootstrapped under [P2P-1220](https://nakisa.atlassian.net/browse/P2P-1220).
Design rationale lives in [`PRD.md`](./PRD.md).

## Quick start

Prerequisites: `glab`, `mvn`, `node`, `claude` (≥ the version supporting
`--print --dangerously-skip-permissions`), `git`, `python` (≥ 3.11).

```powershell
# from this repo's root
pip install -e .

# env (one-shot per shell session)
$j = (Get-Content $env:USERPROFILE\.claude.json -Raw | ConvertFrom-Json).mcpServers.jira.env
$env:JIRA_BASE_URL  = $j.JIRA_BASE_URL
$env:JIRA_EMAIL     = $j.JIRA_EMAIL
$env:JIRA_API_TOKEN = $j.JIRA_API_TOKEN
$env:GITLAB_TOKEN   = (glab auth status -t 2>&1 | Select-String 'Token found:\s*(\S+)').Matches.Groups[1].Value

# drain one pass
python -m afk_driver --label afk-agents --project P2P --digest-out auto
```

End-to-end smoke procedure: [`SMOKE.md`](./SMOKE.md).

## What it does, in one pass

```mermaid
flowchart LR
    A[JQL: label=afk-agents<br/>status=Dev-Pending<br/>type=SubTask] --> B[Group by parent Enhancement]
    B --> C[For each Enhancement]
    C --> D[Ensure worktree off Target Branch]
    D --> E[Push branch + open Draft MR]
    E --> F[Assign + transition Enhancement<br/>Dev-Pending → Dev-Designing → Dev-Developing<br/>Bug parent skips Dev-Designing]
    F --> G[For each SubTask in rank order]
    G --> H[Assign + transition Dev-Pending → Dev-Designing → Dev-Developing]
    H --> I[Spawn claude --print /afk:execute SUBTASK-KEY]
    I --> J{outcome}
    J -->|success| K[Update parent Implementation Notes]
    J -->|test_fail / build_fail| L[retry up to retry_count]
    J -->|timeout / other| M[Comment on SubTask + Request Development]
    K --> N[Last SubTask?]
    N -->|yes| O[Rebase worktree onto target<br/>+ Enhancement → Dev-CR/Merge]
    N -->|no| G
    L --> I
    O --> P[Write digest to ~/.afk-driver/digests/]
```

### Standalone tickets (label on a non-subtask)

A small Enhancement or Bug labelled `afk-agents` with no labelled SubTasks
under it is driven directly: one Draft MR, one `claude --print` invocation
on the ticket key itself, lifecycle transitions on that key. The lifecycle
collapses onto the single ticket — **no MR subtasks checklist** is
maintained, and **no Implementation Notes splice** is written into a
parent (there is no parent). Because `/afk:execute` reads the SubTask Markdown
contract (`## Goal / Scope / Acceptance / Test command / Parent PRD /
Blocked by / Implementation Notes`, plus the cited-mode sections
`## Design refs / Produces / Parent SDD / Consumes / Conflict procedure`
when the standalone is sliced from an SDD), a standalone ticket's
description **must be authored in that shape** for the skill to find
work — the driver does not synthesise it. **Cited-mode contract layers
apply equally to standalones**: `/afk:execute` runs the same Step 2 consumer
preflight on `## Consumes` (a missing upstream `{file}#{anchor}` exits
`contract_mismatch` and the runner comments on the standalone AND on the
named producer ticket — the producer may live outside this drain pass)
and the same Step 10 producer self-preflight on `## Produces` (a missing
own anchor exits `produces_drift`). If a labelled non-subtask also has
labelled SubTasks under it, the SubTask flow wins and the standalone
path is skipped.

## Modules

| Module | Responsibility |
|---|---|
| `subtask_template.py` | Parser/emitter for the SubTask Markdown contract (`## Goal / Scope / Acceptance / Test command / Parent PRD / Blocked by / Implementation Notes`, plus cited-mode `## Design refs / Produces / Parent SDD / Consumes / Conflict procedure`). Round-trip lossless. |
| `scope_enforcer.py` | Pure function `(diff, scope_globs, forbidden, home_module, marker) → list[Violation]`. Catches out-of-scope edits, forbidden patterns (`UpgradeGroup*.java`, `db/changelog/**`, `PreDbMigration*`), and cross-module edits without a JIRA-prefixed marker comment. |
| `config.py` | `DriverConfig` dataclass + TOML override. Defaults: project→service map, `customfield_13706` Target Branch field, `MASTER → master` value map, forbidden patterns, marker template, wall-clock cap (3600s), retry count (3), worktree/log/digest roots under `~/.afk-driver/`, `dev_cr_merge_gate_fields`, `mr_assignee`. |
| `worktree_manager.py` | Per-Enhancement git worktree lifecycle. `ensure / publish_branch / validate_state / rebase_onto_target`. Branch name pattern `mvu/afk/{enh_id_lower}` (GitLab regex `^[a-z0-9][a-z0-9/\-\.]*$`). |
| `jira_client.py` | REST client. `search`, `get_enhancement_fields`, `list_transitions`, `transition` (by name), `update_implementation_notes` (idempotent splice), `set_fields`, `assign`, `get_my_account_id`, `get_issue_description_markdown` (ADF→Markdown for the SubTask parser). |
| `gitlab_client.py` | `glab` CLI wrapper. `find_mr_by_branch / open_draft_mr / update_subtasks_checklist`. Auto-maintained block bracketed by `<!-- afk:subtasks:start/end -->` HTML comments preserves human edits to the rest of the description. |
| `runner.py` | Orchestrator. `Runner.one_pass()` is the entry; `preflight()` validates env. Two flows: `_process_parent` (parent Enhancement + labelled SubTasks) and `_process_standalone` (one labelled non-subtask, collapsed lifecycle — no checklist, no impl-notes splice). Outcomes: `success / test_fail / build_fail / timeout / design_conflict / contract_mismatch / produces_drift / other`. Retries on `test_fail` / `build_fail` up to `retry_count`. `design_conflict` (cited-mode binding-contract violation flagged by `/afk:execute`) skips retry and routes the SubTask back to Dev-Pending with a comment pointing the human at `/afk:architect-grill`. `contract_mismatch` (cited-mode consumer preflight grep miss against an upstream `## Produces` artifact) also skips retry: posts an explicit comment on the consumer AND a separate comment on the producer SubTask (carried via `ClaudeOutcome.producer_key`). `produces_drift` (cited-mode producer self-preflight: SubTask declared `## Produces` X but its own grep cannot find X) likewise skips retry: posts a single "producer self-check failed" comment routing the human to fix the impl OR re-emit the slice. |
| `digest_writer.py` | Emits `RunRecord` as L4 morning Markdown. |
| `cli.py` | `python -m afk_driver` entry. Wires real clients into Runner. Spawns `claude --print --dangerously-skip-permissions "/afk:execute SUBTASK"` per SubTask. |

All I/O is dependency-injected so the runner integration tests (31) drive
fakes in <0.2s. Real-client wiring lives only in `cli.py`.

### Skill ↔ runner contract

Each spawned `claude --print` session returns a `ClaudeOutcome` to the
runner: one of `success / test_fail / build_fail / timeout / design_conflict / contract_mismatch / produces_drift / other`.

The seam is a **structured outcome marker** the `/afk:execute` skill emits as
the last thing in its log (Step 13 of the skill spec):

```
<<<AFK_OUTCOME>>>
{"status": "<status>", "detail": "<one-line summary>", "producer_key": <"PRODUCER-KEY" | null>}
<<<END>>>
```

`cli._parse_outcome_marker` regex-scans the per-SubTask log for the LAST
occurrence (so a session that retried internally and re-emitted wins),
parses the JSON payload, and returns a fully-typed `ClaudeOutcome`. The
marker is the source of truth — when present, it beats the subprocess
exit code, including on timeout: `claude --print` exits 0 on clean
termination regardless of narrative outcome, so without the marker the
runner would collapse every structured failure status (`test_fail`,
`contract_mismatch`, `design_conflict`, `produces_drift`) into
`success`. When the marker is missing or malformed the runner reports
`other` with detail `"no AFK_OUTCOME marker emitted (...)"` so the loss
is loud — silent demotion is the bug this seam fixes.

The ownership split between the two sides is load-bearing:

- **Skill (`/afk:execute`) owns**: in-flight transitions (`Dev-Designing`,
  `Dev-Developing`), TDD loop, code edits, commits, push, MR checklist
  update, parent Implementation Notes splice.
- **Runner owns** (only when outcome is `success`): the boundary
  transition `Dev-CR/Merge`, gate-field writes, parent rebase, parent
  Enhancement → `Dev-CR/Merge`, acceptance-checkbox flips. On
  `test_fail` / `build_fail` it retries; on `timeout` / `other` it
  comments and transitions back to `Dev-Pending`.

The boundary transition is **runner-only** by design — if the skill also
fires `Request CR & Merge` from inside the session, the runner's
follow-up call will fail because the SubTask has already left
`Dev-Developing`. Keep this split when changing either side.

### Section ownership invariants

Mixed human + automated edits live in three Markdown surfaces. Don't let
them collide:

- **Parent Enhancement description**: `## PRD` is owned by `/afk:to-prd`;
  `## SDD` (when present) is owned by `/afk:to-sdd`;
  `## Design Brief` (when present) is owned by `/afk:to-design-brief`;
  `## Implementation Notes (auto-maintained)` is owned by this driver
  (idempotent splice via `update_implementation_notes`); other prose
  belongs to the human.
- **MR description**: the block bracketed by `<!-- afk:subtasks:start -->`
  / `<!-- afk:subtasks:end -->` is auto-maintained; everything outside is
  preserved verbatim.
- **SubTask description**: parsed by `subtask_template.py` and must
  round-trip losslessly. Adding a section requires updating both parser
  and emitter together.

## Configuration

Defaults are in `config.defaults()`. Override via `~/.afk-driver/config.toml`:

```toml
wall_clock_cap_seconds = 1800
retry_count = 2
mr_assignee = "your.gitlab.handle"

[project_service_map]
P2P = "11700-payable"

[target_branch_value_map]
MASTER = "master"
FINCORE_RELEASE = "fin-core/release"

[dev_cr_merge_gate_fields]
merge_request_link = "customfield_12700"
sred_eligibility = "customfield_14005"
time_estimation = "customfield_14006"
sred_rationale = "customfield_14003"
```

## Skills

The driver depends on a chain of Claude Code skills that **ship in this
repo** as the `afk` Claude Code plugin. The plugin lives at
`.claude-plugin/plugin.json` (manifest) + `.claude-plugin/marketplace.json`
(local marketplace) + `skills/<name>/SKILL.md` (one dir per skill). It
ships in lockstep with the Python driver — single git tag, both move
together.

### Plugin install (one-time per machine)

```
# inside Claude Code, from any session
/plugin marketplace add C:\Users\mvu\PersonalProjects\afk    # or your local path
/plugin install afk@afk-marketplace
```

To auto-load on every Claude Code launch, add to `~/.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "afk-marketplace": {
      "source": { "source": "directory", "path": "C:\\Users\\mvu\\PersonalProjects\\afk" }
    }
  },
  "enabledPlugins": {
    "afk@afk-marketplace": true
  }
}
```

After editing any `SKILL.md`, run `/reload-plugins` to pick up changes
without restarting. After `git pull`, same.

For teammate install (private repo, collaborator access required):
`/plugin marketplace add midnightblur/afk-driver` → `/plugin install
afk@afk-marketplace`. Auto-update for private repos requires
`GITHUB_TOKEN` in env.

### The 9 skills

Use `/afk:start` first if you're not sure where to begin — it prints the
pipeline map and routes you to the right entry skill.

**Mandatory chain** (`/afk:to-prd` → `/afk:to-subtasks` → `/afk:execute`):

- **`/afk:to-prd`** — turns conversation context into a PRD. AFK adaptation:
  writes to `{service}/src/main/resources/specs/{year}r{release}/{ENH-ID}/PRD.md`
  (or `tools/{group}/{tool}/PRD.md` for tooling work). Owns the `## PRD`
  section of the parent Enhancement description; AFK driver owns
  `## Implementation Notes (auto-maintained)`.
- **`/afk:to-subtasks`** — slices a PRD (and the accompanying SDD + ADRs,
  when present) into Jira SubTasks under the parent Enhancement, each
  with the structured Markdown contract and the `afk-agents` label.
  **Cited mode** (default when an SDD exists) emits `## Design refs`,
  `## Parent SDD`, and `## Conflict procedure` blocks per SubTask, so
  the implementing agent inherits a binding contract — not just a
  feature ask. **Uncited mode** is human-gated for small features /
  bugs / refactors / tooling: when no SDD is present, the skill asks
  before slicing without one.
- **`/afk:execute`** — invoked by the driver in the spawned session; takes one
  SubTask from `Dev-Pending` through `Dev-Designing` → `Dev-Developing`, gets
  the test command green, pushes commits, then exits with a structured
  outcome. The **runner** — not this skill — performs the final
  `Dev-CR/Merge` transition and the gate-field writes (SRED Eligibility,
  Time, Rationale, MR link), and only when the skill exits `success`. This
  split avoids the double-transition that occurs if both sides try to fire
  `Request CR & Merge`.

**Optional design layer** (recommended for new complex features touching
≥2 modules / introducing patterns / non-trivial transactions or data;
skip for small enhancements, bugs, refactors, tooling):

- **`/afk:grill-me`** — interviews the user about a raw idea or plan
  until the requirements decision tree is exhausted. Does NOT produce
  documents. Pair with `/afk:to-prd` afterward to synthesize.
- **`/afk:architect-grill`** — interviews the user top-down across 8 layers
  (L1 system topology → L8 tactical patterns) until every non-trivial
  decision has a rationale and ≥2 alternatives weighed. Does NOT produce
  documents.
- **`/afk:to-sdd`** — synthesizes the conversation into `SDD.md` plus
  per-decision ADRs, sibling to the PRD:
  `{service}/src/main/resources/specs/{year}r{release}/{ENH-ID}/SDD.md`
  and `.../adr/NNNN-*.md`. Owns the `## SDD` section of the parent
  Enhancement description. Mandates visualizations (Mermaid diagrams,
  tables) per layer so reviewers can scan vertically.
- **`/afk:to-design-brief`** — synthesizes PRD + SDD + ADRs into a tight
  1-2 page `DESIGN-BRIEF.md` sibling to the PRD/SDD. One money-shot
  diagram, 5-10 row decision digest, stakeholder-impact table. Owns the
  `## Design Brief` section of the parent Enhancement description.
  Strict synthesis: refuses to invent decisions and refuses to emit when
  the SDD has executor-blocking open questions. Use for stakeholder
  reviews and as a map before reading the full SDD.

> **Cited-mode contract.** When `/afk:to-subtasks` slices in cited mode it
> emits five additional SubTask sections — `## Design refs`,
> `## Produces`, `## Consumes` (when `Blocked by` is non-empty),
> `## Parent SDD`, `## Conflict procedure`. `subtask_template.py` parses
> all five losslessly. The contract is enforced at three checkpoints:
>
> 1. **Slicing time** (`/afk:to-subtasks` Step 7): graph validation
>    (every `## Consumes` line resolves to a prior `## Produces`) +
>    anchor quality (forbidden-token check, ≥12-char length, trial
>    grep against `{file}` at HEAD must return ≤1 match — refuse on
>    ambiguity). Catches contract drift at declaration time.
> 2. **Consumer preflight** (`/afk:execute` Step 2): before any work, grep
>    every `## Consumes` line `{PRODUCER-KEY} {file}#{anchor}` on the
>    branch — a missing artifact or signature-divergent anchor exits
>    `contract_mismatch` (no retry; runner comments on consumer AND on
>    producer SubTask).
> 3. **Producer self-preflight** (`/afk:execute` Step 10): right before
>    declaring success, grep every own `## Produces` anchor on the
>    branch. Missing or signature-divergent anchor exits
>    `produces_drift` (no retry; runner comments on the SubTask
>    framing it as "I declared X but did not deliver X" and routes the
>    human to impl-vs-slice fix).
>
> On a binding-decision break (SDD §8 mandate is wrong/infeasible),
> `/afk:execute` exits `design_conflict` and routes to `/afk:architect-grill` for
> a superseding ADR. `## Produces` is mandatory on every cited SubTask,
> even leaves with no consumer — it doubles as the reviewer's
> cheat-sheet AND the next SubTask's preflight target. Cited and uncited
> SubTasks both round-trip through the driver — `/afk:to-subtasks` decides
> which to emit based on whether an SDD is present (human-gated).

## Tests

```
python -m pytest -v
```

197 tests covering: subtask_template parser/emitter (round-trip,
including cited-mode `## Produces` / `## Consumes`), scope_enforcer,
config (defaults + TOML override), worktree_manager (real temp-repo
integration), jira_client (HTTP fake), gitlab_client (subprocess fake),
runner (31 integration tests against in-memory fakes — incl.
`design_conflict`, `contract_mismatch`, and `produces_drift` no-retry
semantics with producer-side comment routing — plus phase / standalone
scenario suites), digest_writer, cli (subprocess invocation contract).

## Limitations / known gaps

- **No system-wide install.** Run from a checkout that has `pip install -e
  .` applied; the spawned `/afk:execute` session needs `afk_driver`
  importable from its cwd.
- **No CI / scheduled run.** `python -m afk_driver` is invoked manually
  (cron / Task Scheduler is up to the operator).
- **Failure paths only unit-tested.** `test_fail` retry, `build_fail`,
  `timeout`, `rebase conflict`, mid-run aborts — fakes only.

## Failure modes & recovery

- **Preflight hard-fail** (missing tool / token / PRD path) → fix env, rerun.
- **Parent not in `Dev-Pending` / `Dev-Developing`** → driver skips the
  Enhancement. Transition the parent into a runnable state first.
- **Rebase conflict on the post-last-SubTask rebase** → driver posts a
  comment on the Enhancement and exits clean; resolve manually.
- **Claude session timeout (1h cap)** → recorded as `timeout` in the digest;
  the SubTask returns to `Dev-Pending`.
- **Worktree dirty on resume** (prior session killed mid-edit) → before
  spawning each SubTask the runner does a hard reset to `HEAD`,
  discarding uncommitted leftovers. Resuming partial edits is unsafe
  (claude has no notion of "pick up where the dead session left off"), so
  the deterministic recovery is to start from `HEAD`. Logged as
  `discarded uncommitted leftovers from prior interruption`.
- **Claude reports `success` but didn't commit** (observed during the
  P2P-1233/4/5 smoke run) → the runner auto-stages and commits any dirty
  tree under a `[KEY] AFK auto-commit` message so the work lands on the
  branch. If both claude *and* the auto-commit pass produce no commits
  (branch tip unchanged), the SubTask is failed — refusing to transition
  a SubTask that didn't change any code.

If a run hangs and Jira state is partially advanced, the smoke runbook in
[`SMOKE.md`](./SMOKE.md) (§ "Failure modes to watch for") covers manual
recovery.

## Origin

Inspired by Matt Pocock's AFK Claude Code workflow, adapted for the Nakisa
Jira + GitLab + Maven environment on Windows. The driver is a standalone
Python package; the *work* it drives is Java/Maven inside a sibling
core-services checkout. See `PRD.md` § "AFK adaptation (core-services)".
