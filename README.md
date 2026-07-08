# afk — the away-from-keyboard workflow

A Claude Code **plugin** that turns a raw feature idea into shipped, verified
code through a chain of skills — **human-heavy at the edges, autonomous in the
middle**. You drive the design stages interactively; the implementation middle
can run hands-off via `/afk:autopilot` (or by hand, one `/afk:execute` per
subtask). Each stage leaves a durable artifact on disk, so the next stage (and
the next human) inherits a written contract instead of a verbal hand-off.

> **New here? Read this top to bottom once.** It explains *why* the workflow is
> shaped this way, the handful of concepts you must hold in your head, and then
> walks one feature end to end. The per-skill catalog and the install snippet are
> further down as reference.

**Credit & inspiration.** This repo is directly inspired by and built upon
[Matt Pocock's AFK Claude Code workflow and skills](https://github.com/mattpocock/skills).
The original idea, the AFK framing, and several skill patterns come from his work
— this repo adapts and extends them for a specific environment. If you find this
useful, go read the upstream source first.

Here it is adapted for the Nakisa **Jira + GitLab + Maven** environment on
Windows. The *work* the chain drives is Java/Maven inside a sibling core-services
checkout; **this repo contains only the skills** (the AFK chain under
`skills/afk/<name>/SKILL.md`, plus a few standalone utility skills under
`skills/utils/<name>/SKILL.md`) and the plugin manifests.

---

## Table of contents

1. [Why AFK](#1-why-afk) — the problem it solves
2. [The mental model](#2-the-mental-model) — five ideas to internalize
3. [The chain at a glance](#3-the-chain-at-a-glance) — the map
4. [Install](#4-install) — one-time setup
5. [Walkthrough: your first feature](#5-walkthrough-your-first-feature) — end to end
6. [Choosing your path](#6-choosing-your-path) — full chain vs. the lean path
7. [Where everything lives](#7-where-everything-lives) — the artifact map
8. [The subtask lifecycle](#8-the-subtask-lifecycle) — how `/afk:execute` works
9. [The cited-mode contract](#9-the-cited-mode-contract) — how drift is caught
10. [Skill reference](#10-skill-reference) — every skill, one paragraph each
11. [Section-ownership invariants](#11-section-ownership-invariants) — don't let edits collide
12. [Conventions & gotchas](#12-conventions--gotchas)

---

## 1. Why AFK (and what the name really means)

**AFK = "away from keyboard."** The idea: spend the expensive, focused effort
**up front** — exploring requirements and designing the solution thoroughly —
and then let agents implement autonomously. You settle the *what* and the *why*,
walk away from the keyboard, and come back to pushed, verified, review-gated
Draft MRs.

Today the middle **is** hands-off: `/afk:autopilot` walks the whole plan in
dependency order, one fresh subagent per subtask (driven-mode `/afk:execute`),
self-provisions the live app for `api`/`e2e`/adversarial verification, parks
failures (and their dependents) while independent work continues, and ends at
the feature smoke gate. The edges stay human: you approve the requirements and
the design before the run, and you review + merge the Draft MRs and read the
smoke verdict after it. Every stage can still be run interactively by hand —
autopilot is the default for the middle, not the only way.

What makes it trustworthy while you're away:

- **The hand-off is a file, not a memory.** Every stage emits an artifact (PRD,
  SDD, ADRs, a plan, a verification plan). The next agent reads the contract; it doesn't
  re-derive intent from a chat log.
- **Drift is caught mechanically, not in review.** When the design is settled
  (an SDD exists), the plan slices in *cited mode*: each subtask carries typed
  `Produces`/`Consumes` anchors, and `/afk:execute` greps them before and after
  it works. A signature that drifts from its contract halts the run — it never
  reaches a human reviewer as a surprise.
- **The human stays in the loop at the load-bearing seams.** The skills design,
  draft, implement, and verify; **you** approve the requirements, approve the
  design, review the Draft MR, and merge. Auto-merge is deliberately outside the
  skills' lane.
- **You can always catch up from disk.** The ticket's `INDEX.md` is the
  read-this-first dashboard; `plan/JOURNAL.md` is the append-only event log of
  everything that happened while you were away; every status line a skill
  reports is followed by one jargon-free `In plain terms:` sentence
  (`REPORTING.md`), and every piece of workflow vocabulary has one definition
  (`GLOSSARY.md` at the plugin root — domain vocabulary stays in the target
  repo's glossaries).
- **The orchestrator keeps conclusions, not inputs.** Context-heavy work — bulk
  reads, repo-wide searches, suite runs, big diffs, tracker pulls — runs in
  fresh subagents that return terse cited digests (`DELEGATION.md` at the
  plugin root). The driving agent stays lean for the decisions only it can
  make, and every heavy judgment gets a fresh pair of eyes.

---

## 2. The mental model

Five ideas. Hold these and the rest follows.

**① You invoke the stages; autopilot may drive the middle.** Each skill is a
`/afk:<name>` slash command you run in a Claude Code session. The design and
acceptance stages are interactive; the implementation middle runs hands-off via
`/afk:autopilot` (one fresh subagent per subtask) or by hand, one
`/afk:execute` per subtask. The map in [§3](#3-the-chain-at-a-glance) shows
where each stage fits.

**② Artifacts on disk are the source of truth.** The PRD, SDD, ADRs, the
`VERIFICATION-PLAN.md`, and the execution plan all live as files next to the code
they describe. Jira holds **only** the parent Enhancement/Bug — and only two skills
ever write to it (see ④).

**③ The plan is a local contract, not Jira issues.** `/afk:to-subtasks` emits a
`plan/` directory: a `PLAN.md` index (solution map, seam register, live progress
tracker) plus one `NNNN-slug.md` contract per subtask. A subtask's *id* is its
filename stem. `/afk:execute` parses these files and writes back progress. No
subtask ever becomes a Jira issue.

**④ Only one skill touches the tracker.** `/afk:to-ticket` publishes the PRD body
into the parent ticket. **Everything else stops at disk or GitLab** — including
`/afk:to-sdd`, whose `SDD.md` + design ADRs are local artifacts only. `/afk:execute`
pushes branches + Draft MRs to GitLab but writes no Jira.

**⑤ The human owns the merge.** `/afk:execute` takes a subtask all the way to a
pushed, verified, Draft MR — then **stops**. You review and merge out of band.
Same for the feature gate: `/afk:smoke-test` stamps a feature complete on green
but merges nothing.

```mermaid
graph LR
    subgraph disk_store [On disk - source of truth]
        PRD[PRD.md]
        SDD[SDD.md]
        ADR[ADRs]
        PROTO[PROTOTYPE.md + mockup HTML]
        E2E[VERIFICATION-PLAN.md]
        PLAN["plan/: PLAN.md + NNNN-slug.md"]
    end
    subgraph jira_store [Jira - parent ticket only]
        TICKET["Enhancement or Bug: PRD body + SDD pointer"]
    end
    subgraph gl_store [GitLab]
        MR[Branch + Draft MR]
    end
    PRD -->|/afk:to-ticket| TICKET
    SDD -->|/afk:to-sdd| TICKET
    PLAN -->|/afk:execute| MR
    classDef disk fill:#e8f0fe,stroke:#4285f4;
    classDef jira fill:#fff4e5,stroke:#fb8c00;
    classDef gl fill:#fde7f3,stroke:#e91e63;
    class PRD,SDD,ADR,PROTO,E2E,PLAN disk;
    class TICKET jira;
    class MR gl;
```

---

## 3. The chain at a glance

```mermaid
graph LR
    Grill[/afk:grill-requirements/] --> Prd[/afk:to-prd/] --> Ticket[/afk:to-ticket/] --> AG[/afk:grill-solution/] --> Sdd[/afk:to-sdd/]
    Sdd -->|optional digest| Brief[/afk:to-design-brief/]

    Prd -.->|optional UI mockup| Proto[/afk:prototype/]
    Proto -.->|PROTOTYPE.md feeds design| AG

    Prd -.->|optional verification design| E2E[/afk:grill-verification/]
    Sdd -.->|optional verification design| E2E
    E2E -->|interview settled| VPlan[/afk:to-verification-plan/]

    Sdd --> Sub
    Brief --> Sub
    VPlan -->|VERIFICATION-PLAN.md| Sub

    Sub -->|hands-off driver| Auto[/afk:autopilot/]
    Auto -->|one fresh subagent per subtask| Exec[/afk:execute/]
    Sub -.->|or run once per subtask by hand| Exec
    Exec -->|all subtasks done · gate iff verification plan| Smoke[/afk:smoke-test/]
    Exec -.->|uses| Tdd[/tdd skill/]
    Exec -.->|review gate| Rev[/afk:review/]
    Exec -.->|adversarial gate| Adv[/afk:adversary/]

    classDef mand fill:#d7f3e3,stroke:#1b9e58,stroke-width:2px;
    classDef opt fill:#eef1f5,stroke:#90a4ae;
    class Prd,Ticket,Sub,Auto,Exec mand;
    class Grill,Proto,AG,Sdd,Brief,E2E,VPlan,Smoke,Tdd,Rev,Adv opt;
```

The **green** path is the mandatory spine: `/afk:to-prd` → `/afk:to-ticket` →
`/afk:to-subtasks` → `/afk:autopilot` (or `/afk:execute` per subtask by hand).
Everything in grey is optional design depth you add for complex features and
skip for small ones (see [§6](#6-choosing-your-path)).

Every plan `/afk:to-subtasks` emits ends with a terminal `NNNN-sync-harness` doc
subtask (blocked by all others) that `/afk:execute` runs last to sync the
CLAUDE.md harness for the shipped feature **and settle the staples registry**
(`{service}/STAPLES.md`), delegating the write to `/afk:claude-md`.

**Staples.** A *staple* is a delivered capability that became a standing
expectation (e.g. deep-linking, Excel import/export). Once one exists, every future
feature whose work matches its trigger must **consider** adopting it. The chain wires this as two loops around a
per-service `STAPLES.md` registry (stewarded solely by `/afk:claude-md`): the design
side **consults** it — `/afk:grill-requirements` matches each active staple's trigger
and grills *in-or-out*, `/afk:to-prd` records the call + carries any new-staple
candidate, `/afk:grill-solution` designs the accepted ones; the delivery side
**captures** — the `NNNN-sync-harness` subtask makes the final call on candidates, and
`/afk:review` (spec-fidelity) checks accepted staples were honoured, not stubbed.

Start where your inputs land: a raw idea enters at `/afk:grill-requirements`; an
existing PRD at `/afk:grill-solution`; an SDD already in hand at `/afk:to-subtasks`.

---

## 4. Install

```text
# inside Claude Code, from the core-services repo root
/plugin marketplace add ./tools/payable/ai-agents/plugins/workflow
/plugin install afk@nak-marketplace
```

To auto-load on every Claude Code launch, add to `~/.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "nak-marketplace": {
      "source": { "source": "directory", "path": "./tools/payable/ai-agents/plugins/workflow" }
    }
  },
  "enabledPlugins": {
    "afk@nak-marketplace": true
  }
}
```

That snippet is the only manual part — it can't be a skill because the plugin
isn't loaded yet. **Then run `/afk:setup`** — the workflow doctor: it probes
every external dependency the chain needs (CLIs, MCP servers, secrets, sibling
checkouts) against `skills/afk/setup/MANIFEST.md`, installs what it can, and
walks you through the rest (Jira token, `glab auth login`). Prefer doing it by
hand? `MANIFEST.md` is human-followable — every probe and fix is a
copy-pasteable command.

After editing any `SKILL.md`, run **`/reload-plugins`** to pick up changes
without restarting. Same after `git pull` — and if the pull changed the
workflow itself (new deps, new tools), re-run **`/afk:setup`**: it's
idempotent, so it fixes exactly what the update broke and touches nothing else.

**Teammate install**: the plugin ships inside `core-services`, so a `git pull`
delivers it. Each developer enables it once at **local** scope with the snippet
above (`/plugin marketplace add ./tools/payable/ai-agents/plugins/workflow` →
`/plugin install afk@nak-marketplace`). Directory-source installs are
snapshotted — after a `git pull` that changes a `SKILL.md`, run
`/reload-plugins` (or re-add the marketplace) to refresh.

The dev loop for *this* repo is just: edit a `SKILL.md` → `/reload-plugins`.
There's no build step, no test suite, no Python package.

---

## 5. Walkthrough: your first feature

Here is a complete pass for a **complex** feature (one needing real design). The
commands are slash commands you type in a Claude Code session; the files are what
appears on disk as a result.

```mermaid
sequenceDiagram
    autonumber
    actor Dev
    participant CC as Claude Code (skills)
    participant Disk as Disk
    participant Jira as Jira
    participant GL as GitLab

    Dev->>CC: /afk:grill-requirements
    CC-->>Dev: interview → exhausts requirement tree
    CC->>Disk: GLOSSARY.md
    Dev->>CC: /afk:to-prd
    CC->>Disk: PRD.md + adr/requirements ADRs
    Dev->>CC: /afk:to-ticket (parent_key)
    CC->>Jira: PRD body (ADF, diagrams as PNGs)
    Dev->>CC: /afk:prototype (optional, if net-new UI)
    CC-->>Dev: live HTML mockup loop (refresh + react)
    CC->>Disk: PROTOTYPE.md + chosen HTML
    Dev->>CC: /afk:grill-solution
    CC-->>Dev: L1→L9 design interview
    Dev->>CC: /afk:to-sdd
    CC->>Disk: SDD.md + adr/design ADRs
    CC->>Jira: SDD pointer section
    Dev->>CC: /afk:grill-verification (optional)
    CC-->>Dev: two-modality scenario interview
    Dev->>CC: /afk:to-verification-plan
    CC->>Disk: VERIFICATION-PLAN.md (+ gap notes)
    Dev->>CC: /afk:to-subtasks
    CC->>Disk: plan/PLAN.md + plan/NNNN-slug.md (cited)
    loop once per subtask, in dependency order
        Dev->>CC: /afk:execute {NNNN-slug}
        CC->>GL: commit + push + Draft MR checklist
        CC->>Disk: tracker row → done
        Dev->>GL: review + merge (out of band)
    end
    Dev->>CC: /afk:smoke-test (iff gate exists)
    CC->>GL: run integrated browser suite vs running app
    CC->>Disk: Feature: complete (on green)
```

**Step by step:**

1. **`/afk:grill-requirements`** — Claude interviews you about the idea,
   challenging it against the domain glossary until the requirements decision
   tree is exhausted. Maintains `GLOSSARY.md`; emits no decision records yet.
2. **`/afk:to-prd`** — synthesizes the conversation into `PRD.md` plus
   requirement-level ADRs. **Local only** — nothing in Jira yet.
3. **`/afk:to-ticket`** — publishes the PRD *content* into the **existing**
   parent ticket as native Jira formatting (ADF), rendering any Mermaid diagrams
   to attached PNGs. Idempotent — re-run when the PRD changes.
4. **`/afk:prototype`** *(optional — only if the feature has net-new UI)* — crafts
   the screens with you interactively, anchored to the **real frontend's**
   components and tokens. Writes self-contained HTML you open and refresh while you
   reshape it in plain language; on settle it captures `PROTOTYPE.md` + the chosen
   HTML sibling to the PRD. Self-gates `no_ui` for backend-only features. The won
   design feeds the next two steps and gives the verification UI journeys a concrete
   screen to trace to. Local-first; an opt-in push mirrors the mockup to
   `claude.ai/design` for stakeholder review.
5. **`/afk:grill-solution`** — top-down design interview across 9 layers (L1
   system topology → L8 tactical patterns); every non-trivial decision gets a
   rationale and ≥2 weighed alternatives.
6. **`/afk:to-sdd`** — synthesizes the design into `SDD.md` + per-decision design
   ADRs, and writes the parent ticket's `## SDD` pointer section.
7. **`/afk:grill-verification`** *(optional but recommended)* — designs the
   feature's verification scenarios with you: the real end-user **browser
   journeys**, plus (once the SDD exists) the **API scenarios** that prove the
   backend contract for API/MCP callers who bypass the UI. It **interviews only** —
   walking them concretely routinely surfaces PRD/SDD gaps, surfacing them is a
   feature, not a side effect.
8. **`/afk:to-verification-plan`** — synthesizes that conversation into
   `VERIFICATION-PLAN.md` (UI journeys now; API scenarios too once the SDD exists,
   else deferred and appended on a re-run).
9. **`/afk:to-subtasks`** — slices everything into `plan/`. Because an SDD exists
   it slices in **cited mode** (typed contracts). Because a `VERIFICATION-PLAN.md`
   exists it also seeds a `## Feature smoke gate` and a terminal build subtask per
   modality (`NNNN-smoke-e2e` for the UI journeys, `NNNN-smoke-api` for the API
   scenarios).
10. **`/afk:autopilot`** — the hands-off default for the middle: walks the whole
    plan in dependency order, one fresh subagent per subtask (driven-mode
    `/afk:execute`), self-provisions the live app, parks failures + their
    dependents while independent work continues (push notification on every
    park), journals every event to `plan/JOURNAL.md`, and ends at the smoke
    gate. Prefer this when the plan is approved; or run
    **`/afk:execute {NNNN-slug}`** yourself once per subtask, in dependency
    order, from a worktree on the parent branch — it designs, develops under
    TDD, turns every verification tier green, pushes, updates the Draft MR,
    advances the tracker — then stops. Either way, you review and merge each MR.
11. **`/afk:smoke-test`** — after every subtask is `done`, runs the integrated
    verification suites — browser journeys **and** API contracts — against a running
    app and stamps `Feature: complete` on green across both.

For a **small** feature you collapse this to the lean path — see next section.

---

## 6. Choosing your path

The optional design layer earns its cost on complex work and is pure overhead on
trivial work. Decide up front:

```mermaid
graph TD
    A{New work} --> B{2+ modules, a new pattern, or non-trivial txn or data?}
    B -->|No: bug, refactor, tooling, small enh| LEAN[Lean path]
    B -->|Yes| FULL[Full path]

    LEAN --> L1["/afk:to-prd"]
    L1 --> L2["/afk:to-ticket"]
    L2 --> L3["/afk:to-subtasks - uncited mode"]
    L3 --> L4["/afk:execute - once per subtask"]

    FULL --> F1["grill-requirements, to-prd, to-ticket"]
    F1 --> FP["prototype - optional, iff net-new UI"]
    FP --> F2["grill-solution, to-sdd"]
    F2 --> F3["grill-verification, to-verification-plan - optional"]
    F3 --> F4["to-design-brief - default, skip only on explicit call"]
    F4 --> F5["to-subtasks - cited mode"]
    F5 --> F6["autopilot - or execute per subtask by hand"]
    F6 --> F7["smoke-test - iff verification plan"]

    classDef lean fill:#d7f3e3,stroke:#1b9e58;
    classDef full fill:#e8f0fe,stroke:#4285f4;
    class LEAN,L1,L2,L3,L4 lean;
    class FULL,F1,FP,F2,F3,F4,F5,F6,F7 full;
```

| | **Lean path** | **Full path** |
|---|---|---|
| When | bug / refactor / tooling / small enhancement | new complex feature, new pattern, multi-module |
| Design docs | none | SDD + ADRs |
| UI prototype | none | optional via `/afk:prototype` (iff net-new UI) |
| Slice mode | **uncited** (PRD-only, human-gated) | **cited** (typed `Produces`/`Consumes`, mechanically enforced) |
| verification gate | usually none | optional via `/afk:grill-verification` → `/afk:to-verification-plan` (UI + API) |

**Mode is set by what's upstream**, not by a flag: a PRD **with** an SDD slices
cited; a PRD **alone** slices uncited.

---

## 7. Where everything lives

Every design artifact sits next to the code it describes, under the ticket's
spec folder (or `tasks/{TICKET-ID}/` for tooling work that has no service home):

```text
{service}/src/main/resources/specs/{year}r{release}/{TICKET-ID}/
├── INDEX.md                   ← /afk:to-prd creates; each skill upserts its row (read this first)
├── PRD.md                     ← /afk:to-prd        (published to Jira by /afk:to-ticket)
├── PROTOTYPE.md               ← /afk:prototype     (local; optional; canonical record of the won UI)
├── prototype/                 ← /afk:prototype     (the chosen self-contained mockup HTML)
├── SDD.md                     ← /afk:to-sdd        (local only; not published to Jira)
├── VERIFICATION-PLAN.md       ← /afk:to-verification-plan (local only; UI journeys + API scenarios)
├── DESIGN-BRIEF.md            ← /afk:to-design-brief (local only; default on the full path)
├── GRILL-LOG.md               ← the grills          (on-disk checkpoint of settled decisions)
├── GLOSSARY.md                ← /afk:grill-requirements
├── walkthroughs/              ← /afk:to-code-walkthrough (optional durable copies)
├── adr/
│   ├── requirements/NNNN-*.md ← /afk:to-prd   (what / why)
│   └── design/NNNN-*.md       ← /afk:to-sdd   (how)
└── plan/                      ← /afk:to-subtasks
    ├── PLAN.md                  (index: solution map, seam register, progress tracker, smoke gate)
    ├── JOURNAL.md               (append-only event log — the "what happened while you were gone" file)
    ├── TRACE.md                 (end-of-feature rollup: acceptance criterion → subtask → commits → tests)
    ├── review/                  (review + adversary reports, INDEX.md rollup per subtask)
    └── NNNN-slug.md             (one contract per subtask)
```

**Catching up on a feature you didn't watch:** open `INDEX.md` (summary, artifact
states, reading order), then the tail of `plan/JOURNAL.md` (what happened, in
order, with plain-terms sentences), then `plan/review/INDEX.md` (what the gates
found). Six months later, add `plan/TRACE.md` (which commit satisfied which
acceptance criterion) and the ADR folders (why it's shaped this way).

**Two ADR tiers, separate subfolders, separate numbering** — requirement ADRs
(`adr/requirements/`, owned by `/afk:to-prd`) never share numbering with design
ADRs (`adr/design/`, owned by `/afk:to-sdd`).

Two artifacts live at the **service root**, not the per-ticket spec folder, because
the whole service shares them: `GLOSSARY.md` (vocabulary, stewarded by `/afk:glossary`)
and `STAPLES.md` (the cross-cutting staples registry, stewarded by `/afk:claude-md`).
Every design/plan/review stage reads `STAPLES.md`; only `/afk:claude-md` writes it.

The verification suites themselves are **not** in this repo — they live in the
core-services tree under `11700-payable/verification`, a multi-modal tree:
`ui-e2e/` (the Cucumber + Playwright browser module), `api/` (direct-REST
`node:test` contracts), and `core/` (shared, dependency-free auth/base-URL/poll
primitives both import; `api → core`, `ui-e2e → core`, `core → nothing`). The
authoring recipes are canonical at **`11700-payable/verification/ui-e2e/AUTHORING.md`**
and **`11700-payable/verification/api/AUTHORING.md`** (versioned with the
verification code so they can't drift). AFK skills only *point* at those recipes —
they never embed a copy.

---

## 8. The subtask lifecycle

`/afk:execute` runs **one** subtask per invocation. It owns exactly one cell of
the `PLAN.md` progress tracker (the row it's working) — and nothing else. The states:

```mermaid
stateDiagram-v2
    [*] --> pending
    pending --> designing: contract read, blocked-by satisfied
    designing --> developing: plan within scope
    developing --> verifying: code + TDD done, pushed
    verifying --> reviewing: every tier green
    reviewing --> done: review gate clean/advisory
    done --> [*]

    pending --> blocked: blocked_by or contract_mismatch
    designing --> blocked: design_conflict
    verifying --> blocked: test_fail, build_fail or produces_drift
    reviewing --> blocked: review_fail (blocking after 2 cycles)
    blocked --> [*]

    note right of reviewing
        /afk:review fans out fresh subagents,
        one per concern; blocking findings route
        to /afk:fix (correctness/spec) or an
        inline fix, capped at 2 cycles
    end note
```

The happy path is `pending → designing → developing → verifying → reviewing → done`. Any
structured failure parks the row at `blocked(<reason>)` and reports a matching
`OUTCOME:` line. The reasons:

| Outcome | Meaning | Where you go next |
|---|---|---|
| `success` | every tier green, pushed, MR updated, row `done` | review + merge the MR |
| `blocked_by` | a `## Blocked by` prerequisite isn't `done` yet | run the prerequisites first |
| `test_fail` / `build_fail` | a verification tier stayed red after one retry | fix the impl |
| `review_fail` | the Step 10 review gate stayed `blocking` after two remediation cycles | address the surviving critical/high findings |
| `adversary_fail` | the Step 10.5 adversarial gate's blocking findings survived the remediation cap | read the adversary report in `plan/review/`, fix what it proved broken |
| `contract_mismatch` | a consumed upstream `Produces` is missing/drifted | fix the **producer** subtask |
| `produces_drift` | this subtask didn't deliver its own declared `Produces` | fix impl or re-slice |
| `design_conflict` | a binding SDD/ADR decision is wrong/infeasible | `/afk:grill-solution` → superseding ADR |
| `timeout` / `other` | wall-clock cap / unexpected | inspect and re-run |

Every `OUTCOME:` line arrives with one jargon-free `In plain terms:` sentence and
a pointer to the full story (`REPORTING.md` at the plugin root), and every status
change, park, push, and verdict lands as a timestamped line in the append-only
`plan/JOURNAL.md` — read its tail to reconstruct a run you didn't watch.

Then **it stops at CR/Merge** — reviewing and merging the Draft MR is yours.

---

## 9. The cited-mode contract

When an SDD is present, the plan slices in **cited mode** and each subtask
carries a typed contract. The point: a producer/consumer signature mismatch is
caught by a `grep`, at a precise checkpoint, on the *right* subtask — never as a
silent integration surprise.

```mermaid
graph TD
    subgraph slice [1 - Slicing time, to-subtasks Validation]
        a["graph: every Consumes resolves to a prior Produces"]
        b["anchor quality: no generic tokens, min 12 chars, max 1 grep hit at HEAD"]
        c["acceptance citations + every SDD seam has a named implementer + seam-test"]
    end
    subgraph pre [2 - Consumer preflight, execute Step 2]
        d["grep each Consumes line PRODUCER-ID file anchor on the branch"]
        d -->|miss| dm["contract_mismatch: no retry, both rows blocked"]
    end
    subgraph post [3 - Producer self-preflight, execute Step 9]
        e["grep each own Produces anchor right before success"]
        e -->|miss| em["produces_drift: no retry"]
    end
    slice --> pre --> post
```

`## Produces` is mandatory on **every** cited subtask — even a leaf with no
consumer — because it quadruples as: the reviewer's cheat-sheet, the `static`-tier
grep target, the producer self-preflight target, and the next subtask's consumer
preflight target.

On a binding-decision break (an SDD §8 mandate that's wrong or infeasible),
`/afk:execute` exits `design_conflict` and routes you to `/afk:grill-solution`
for a superseding ADR — it never silently substitutes a different interface.

**Optional upgrade — materialized seams.** Run `/afk:to-subtasks` with
`materialize_seams=true` and each **new-Java** seam is pre-created on the branch
at slicing time: the interface stub (SDD §8 signatures verbatim) plus a
`@Disabled` contract-shape test that pins the signature by compiling. Those
`Produces`/`Consumes` bullets carry a `[materialized]` marker, and the grep
checkpoints above gain the compiler: consumer preflight `test-compile`s the seam
module, and the implementer must enable the contract test and turn it green as
its seam-test. You review and commit the stubs together with the plan.
Existing-file and non-Java seams keep grep-anchors — the fallback never goes away.

---

## 10. Skill reference

### Mandatory chain

- **`/afk:to-prd`** — turns conversation context into a `PRD.md`, plus
  requirement-level ADRs (decisions clearing the *hard-to-reverse + surprising +
  real-trade-off* bar) under `.../{TICKET-ID}/adr/requirements/`. **Local artifacts
  only** — does not touch the tracker.
- **`/afk:to-ticket`** — publishes the full PRD **content** into its **existing**
  parent ticket as native Jira ADF (headings, tables, code, Mermaid → attached
  PNGs embedded inline). **Idempotent**: re-run on PRD change, updates in place,
  preserves product-owner prose outside the managed block. Publishes PRD content
  only — never the SDD/Brief. Refuses without `parent_key`; sets no label,
  creates no branch. Driven by `skills/afk/to-ticket/scripts/publish_prd.py`.
- **`/afk:to-subtasks`** — slices the PRD (+ SDD + ADRs when present) into the
  local `plan/`. **Cited mode** (SDD present) emits `## Design refs`, `## Seams`,
  typed `## Produces`/`## Consumes`, and a `## Conflict procedure` per subtask.
  **Uncited mode** (PRD only) is human-gated. Every subtask declares tiered
  verification (static → unit → integration → api → e2e/browser). A
  `VERIFICATION-PLAN.md` also makes it seed the `## Feature smoke gate` + a
  terminal build subtask per modality (`NNNN-smoke-e2e` for UI journeys,
  `NNNN-smoke-api` for API scenarios). It always seeds one terminal
  `NNNN-sync-harness` doc subtask — blocked by every other subtask, run last —
  that syncs the CLAUDE.md harness for the shipped feature via `/afk:claude-md`.
  **No Jira.**
- **`/afk:execute`** — one subtask per run, in a worktree on the parent branch
  (`kapteyn/development/{username}/{enh_id_lower}`). Reads the contract, advances
  the tracker (`designing → developing → verifying → reviewing → done`), turns
  every verification tier green under TDD, runs the independent `/afk:review`
  gate and the `/afk:adversary` gate, commits + pushes, updates the Draft MR,
  journals every step, then **stops at CR/Merge**. Touches GitLab + the local
  plan, **not Jira**. Reports a structured outcome (see
  [§8](#8-the-subtask-lifecycle)). Run by `/afk:autopilot` in driven mode, or by
  hand.
- **`/afk:autopilot`** — the hands-off driver for the middle. Walks the plan in
  rank order (Blocked-by respected), one fresh subagent per subtask running
  `/afk:execute` in driven mode — **sized by the contract's `## Complexity`**
  (`mechanical` slices get a fast/cheap agent, `complex` ones the strongest;
  a parked `mechanical` is retried once at `standard` before the park stands) —
  self-provisions the live app per slice, parks
  failed subtasks + their dependents while independent subtasks continue (push
  notification with a plain-terms sentence on **every** park), appends run
  events + a per-subtask heartbeat to `plan/JOURNAL.md`, then runs
  `/afk:smoke-test`. Sequential v1 — no parallel subtasks. Writes no PLAN.md
  cell; owns only the run report, the journal's run-level lines, and
  notifications.

### Optional design layer

*(Recommended for new complex features touching ≥2 modules / introducing patterns
/ non-trivial transactions or data; skip for small enhancements, bugs, refactors,
tooling.)*

- **`/afk:grill-requirements`** — interviews you about a raw idea until the
  requirements decision tree is exhausted, challenging it against the domain
  glossary **and the staples registry** (for each `active` staple whose trigger
  the feature matches, grills *in-or-out-and-why*; also raises whether the feature
  mints a new staple). Maintains `GLOSSARY.md`; emits **no** decision records and
  never writes `STAPLES.md` (those come from `/afk:to-prd` and `/afk:claude-md`).
- **`/afk:prototype`** *(after `/afk:to-prd`; only if net-new UI)* — an interactive
  UI-crafting loop, neither a grill nor a one-shot producer. Reads the PRD User
  Stories, anchors to the **real frontend's** components + tokens, and writes
  self-contained HTML you open in a browser and **refresh** while you reshape it in
  plain language. Converges from optional divergent sketches to one design.
  **Self-gates `no_ui`** for backend/API/refactor features. **Durable-lite**: the
  won direction becomes `PROTOTYPE.md` + the chosen HTML sibling to the PRD
  (traceable to User Stories, so `/afk:grill-verification`'s UI journeys trace to
  it); losing scaffolding is discarded. **Local-first** — the in-repo files are
  canonical; a **frictionless opt-in** push mirrors the mockup to a persistent,
  team-shareable `claude.ai/design` project (share-only, never the source of
  truth). Touches no tracker. Feeds `/afk:grill-solution` (UX decisions) and
  `/afk:grill-verification` (the screen its journeys trace to).
- **`/afk:grill-solution`** — top-down design interview across 9 layers (L1
  topology → L8 tactical patterns); every non-trivial decision gets a rationale +
  ≥2 alternatives. Produces **no** documents — feeds `/afk:to-sdd`.
- **`/afk:to-sdd`** — synthesizes the design into `SDD.md` + per-decision design
  ADRs under `adr/design/`, **local artifacts only — does not touch the tracker**.
  Mandates per-layer visualizations (Mermaid, tables) so reviewers can
  scan vertically.
- **`/afk:to-design-brief`** — synthesizes PRD + SDD + ADRs into a tight 1-2 page
  `DESIGN-BRIEF.md` (one money-shot diagram, a decision digest, a
  stakeholder-impact table). **Repo-only**; shared with stakeholders out of band.
  Refuses to invent decisions or to emit while the SDD has executor-blocking open
  questions.
- **`/afk:grill-verification`** — interviews you to design the feature's
  verification scenarios across two modalities: **UI journeys** (the real browser
  flows that decide "this feature works", traced to User Stories) and **API
  scenarios** (direct-REST checks that prove the backend contract for API/MCP
  callers who bypass the UI, traced to SDD §3 endpoints). A grilling skill like
  `/afk:grill-requirements` and `/afk:grill-solution` — it **writes no file**;
  walking the scenarios concretely surfaces PRD/SDD gaps. UI journeys can be
  designed after `/afk:to-prd`; API scenarios need the SDD's endpoint contracts,
  so they're added after `/afk:to-sdd` (a pre-SDD run defers them).
- **`/afk:to-verification-plan`** — synthesizes that conversation into
  `VERIFICATION-PLAN.md` sibling to the PRD (no interview — writes what the grill
  settled). UI journeys now; API scenarios too once the SDD exists, else a deferred
  placeholder that a post-SDD re-run **appends** to (preserving the UI section).
  Its plan is what makes `/afk:to-subtasks` emit the smoke gate + the per-modality
  build subtasks. **Repo-only.** The build recipes are **not** here — they're
  canonical at `11700-payable/verification/ui-e2e/AUTHORING.md` and
  `11700-payable/verification/api/AUTHORING.md`, only pointed at.

### Optional feature gate

- **`/afk:smoke-test`** — the **feature-level** completion gate, distinct from the
  per-subtask `api` / `e2e/browser` tiers. It **only executes** already-built
  scenarios — it authors nothing. Present only when the feature has a `## Feature
  smoke gate` (a `VERIFICATION-PLAN.md` drove build subtasks). After **every**
  subtask is `done`, it runs the integrated suites — the browser UI journeys
  (`npm run smoke`) **and** the API contracts (`node --test`) — against a
  **running app** and, only on green across both, stamps `Feature: complete` in
  `PLAN.md`. The specs are built reuse-first into the existing
  `11700-payable/verification` tree (`ui-e2e` Cucumber + Playwright module; `api`
  `node:test` files) by the terminal `NNNN-smoke-e2e` / `NNNN-smoke-api` subtasks
  (reviewed as code). Env-limited scenarios (e.g. `@sap`) are tagged and excluded
  from the green verdict. The same suites are reused by CI / scheduled / manual
  runs. Merges nothing, touches no Jira. Reports `smoke_green` / `smoke_fail` /
  `env_unreachable` / `preconditions_unmet` / `no_gate`.
- **`/afk:preflight`** — the **feature-level ship gate**, chained by
  `/afk:autopilot` once the smoke gate is green, or run by hand to resume a
  parked feature. Refuses outright (writing nothing) without a green smoke
  gate. A resumable, table-driven PF-1..7 ladder (`PLAN.md`'s `## Preflight`
  section, its sole writer; green rows skipped on re-run): merge
  `origin/master` behind an ancestry guard (never rebase, never
  force-push), re-run validations, a fresh review of the integrated feature
  diff, and a final `/afk:verify-seams final` check — a shared 2-cycle fix
  cap across those three steps — then commit the mission-control end-state
  snapshot, update the MR's own evidence marker block (sibling to
  `/afk:execute`'s checklist block; each writer touches only its own), and
  background-babysit CI (bundled `ci-wait.sh`: exit 0 green / 1 red / 2
  budget / 3 glab-flake) to flip the Draft MR to Ready. CI-only test
  failures and secret-detection hits always park — never auto-fixed. Never
  merges the MR.

### Tooling

- **`tdd`** (agent-invoked, not in the `/` menu) — red-green-refactor
  doctrine, invoked from `/afk:execute` Step 5. Not run standalone.
- **`/afk:review`** — the **independent post-verification review gate**. Fresh,
  parallel subagents — one per concern (CLAUDE.md-compliance, spec-fidelity,
  logic-correctness, code-quality, test-veracity, scope-and-impact,
  refactor-safety) — check the slice diff against the applicable CLAUDE.md
  chain, the spec/acceptance contract, and senior-engineer code-quality +
  refactor bars. **Read-only**: it returns a ranked findings report + a
  `clean`/`advisory`/`blocking` verdict and never edits or commits. The
  reviewers never see the implementor's reasoning — independence is the point.
  Invoked from `/afk:execute` Step 10 (the gate before `done`); also runnable
  standalone as `/afk:review {NNNN-slug}` to audit any slice.
- **`/afk:adversary`** — the adversarial execution gate (`/afk:execute`
  Step 10.5). A fresh session probes the **running app** with scenarios derived
  from the contract + specs under a hard information diet (never the diff or the
  implementor's tests). Verdict `clean` / `findings` (classed + severity-counted)
  / `tainted` / `env_unreachable`; reports land in `plan/review/`. Blocking
  findings route by class like review findings, sharing the remediation cap.
- **`/afk:fix`** — thin orchestrator for fixing a verification-phase or reported
  bug: pulls ticket/repro context, delegates root-cause + regression test to
  `/afk:diagnose`, adds proportional `api`/`e2e` coverage, and — in a
  feature-building session — reconciles the load-bearing artifacts (PRD / SDD /
  ADRs / VERIFICATION-PLAN) so the source of truth stays true. Commits nothing.
  Run standalone for ad-hoc bugs, routed from `/afk:execute` Step 8 when a
  verification tier stays red, or from the Step 10 review gate on a
  `correctness`/`spec` blocking finding.

- **`/afk:retro`** — the cross-feature retrospective: mines delivered plans'
  exhaust (journals, review rollups, adversary verdicts, park reasons, the
  harness `gate-latency.jsonl` metrics, open wiring IOUs) into recurring
  signals — what the chain keeps getting wrong, where it stalls, what it costs
  — and writes a dated `RETRO-*.md` report whose Proposals section contains at
  most 5 evidence-cited, lockstep-aware plugin edits for a human to apply.
  Read-only over everything it mines; the systemic counterpart of `/afk:fix`'s
  per-bug escape analysis. Run it after a release's features ship, or
  periodically.
- **`/afk:claude-md`** — steward of the three steering artifacts: `CLAUDE.md`
  files / `.claude/rules` across a project hierarchy, and the per-service
  `STAPLES.md` registry (its **sole** writer). Creates, audits, dedups, and
  reorganizes project memory; the plan's terminal `NNNN-sync-harness` subtask
  delegates its writes here.
- **`/afk:design-system`** — per-service setup, not a per-feature stage: builds
  (or refreshes) a team-shareable `claude.ai/design` catalog that mirrors the
  service's **live frontend** — real design tokens as ground truth,
  archetype-complete standalone HTML cards, fidelity-checked against the
  running app — so `/afk:prototype` crafts against the real app instead of
  generic defaults. Re-run when the frontend's tokens/components drift.
- **`/afk:mission-control`** — launches the read-only mission-control dashboard
  for one feature's spec folder: watch mode (default) re-renders on artifact
  change and serves the page on `127.0.0.1`; `--once` renders a retroactive
  page for an already-finished feature and exits, no server. Fronts the
  bundled renderer CLI (`scripts/mission_control.py`) — a pure function from
  the spec/plan artifacts to a self-contained page; the skill only launches
  it and reports the served URL / output path. No daemonization: a crashed
  watcher's only recovery is relaunching the skill.
- **`/afk:setup`** — the workflow doctor. Probes every external dependency in
  `skills/afk/setup/MANIFEST.md` (CLIs, MCP servers, secrets, sibling
  checkouts), fixes what it can, guides the human through the rest — idempotent,
  so first-time install and post-`git pull` repair are the same run. As
  `/afk:setup audit` it instead hunts drift between the plugin's artifacts and
  reality (structural consistency, unregistered dependencies, dead pointers) —
  run that before shipping plugin changes (see `FRESHNESS.md`).

### Utility skills (not part of the AFK chain)

General-purpose skills that ship in the same plugin for convenience but are
**not** stages of the workflow. They live under `skills/utils/` and can be
invoked any time, in any project.

- **`/afk:caveman`** — ultra-compressed "caveman" response mode; cuts token use
  while keeping technical accuracy.
- **`/afk:diagnose`** — disciplined diagnosis loop for hard bugs / perf
  regressions (build a feedback loop → reproduce → hypothesise → instrument →
  fix → regression-test).
- **`/afk:draw-charts`** — render-safe Mermaid/diagrams; steers around the
  constructs that break renderers and render-checks before shipping.
- **`/afk:glossary`** — domain-vocabulary steward; the vocabulary-only subset of
  `/afk:grill-requirements`. Audits an existing `GLOSSARY.md` for ambiguity,
  synonyms, vague terms, and code drift, or grills new terminology one question
  at a time. Owns the `GLOSSARY-MAP.md` + per-service `GLOSSARY.md` setup and the
  canonical `GLOSSARY-FORMAT.md` (which `/afk:grill-requirements` defers to);
  writes after approval. Does not grill requirements or emit ADRs.
- **`/afk:handoff`** — compact the current conversation into a handoff doc for a
  fresh agent to pick up.
- **`/afk:todo`** — quick per-project todo list at `<cwd>/.claude/TODO.md` that
  survives sessions.
- **`/afk:to-code-walkthrough`** — top-down narrative walkthrough of a GitLab MR
  (`<MR-URL>`) or an existing code area (`path:` / `symbol:`); caveman prose +
  Mermaid, no verdicts. MR mode needs `glab` on PATH (uses the bundled
  `scripts/fetch-mr.sh`); code mode is fully standalone.
- **`writing-great-skills`** — the reference doctrine for authoring and editing
  skills (invocation choice, information hierarchy, progressive disclosure,
  leading words, failure modes); consulted whenever a skill is created,
  audited, or reviewed.
- **`verify-seams`** (agent-invoked, not in the `/` menu) — independent orphan
  hunt over a change: a fresh-context subagent (blind to the author's
  narrative) classifies every produced artifact wired / weak / orphan; `final`
  mode blocks shipping on open wiring IOUs. The agent runs it before declaring
  multi-artifact work done and before push/ship; to trigger it yourself, just
  ask ("verify seams"). Judgment tier above `hooks/wiring-gate.sh`, one of the
  Stop-hook gates the plugin ships (wiring, Maven compile, UI lint, Java
  format — see `hooks/README.md`); the wiring gate blocks any new artifact
  with no consumer and no anchored IOU in the repo's `.claude/wiring-ious.md`.

---

## 11. Section-ownership invariants

Several Markdown surfaces carry mixed human + automated edits. The rule is
strict ownership so edits never collide:

- **Parent Enhancement description** — PRD content (authored on disk by
  `/afk:to-prd`) is published by `/afk:to-ticket` inside an AFK-managed sentinel
  block; `## SDD` (when present) is owned by `/afk:to-sdd`; the Design Brief is
  **not** published to the ticket; other prose is the human's. Subtask progress
  is **not** spliced into the ticket — it lives in `plan/PLAN.md`.
- **MR description** — the block bracketed by `<!-- afk:subtasks:start -->` /
  `<!-- afk:subtasks:end -->` is auto-maintained by `/afk:execute`; everything
  outside is preserved verbatim.
- **Local plan (`plan/`)** — `/afk:execute` owns only the working subtask's
  `Status` cell (+ the `Last updated` date). **`/afk:smoke-test`** owns a *disjoint* slice
  of the same `PLAN.md`: the `## Feature smoke gate` table's `Status` cells, its
  `Last run` line, and the header `Feature:` line — nothing else. All contract
  sections must round-trip losslessly.

> **Freshness rule for contributors.** No plugin artifact may go stale:
> a dependency change updates `skills/afk/setup/MANIFEST.md` in the same
> commit, a skill/doc surface change updates every surface its `FRESHNESS.md`
> registry row names — and `/afk:setup audit` is the drift catcher to run
> before shipping plugin changes. Doctrine: `FRESHNESS.md` (plugin root).

> **Lockstep rule for contributors.** The plan is the load-bearing interface
> between `/afk:to-subtasks` (emitter) and `/afk:execute` (parser). If you add,
> rename, or change a contract section, update **both** skills in the **same
> commit**. A section read by `/afk:smoke-test` (a gate field) must be changed in
> lockstep with that skill too — and a smoke-gate field's shape touches all three
> (`to-verification-plan` emitter, `to-subtasks` seeder, `smoke-test` reader).

---

## 12. Conventions & gotchas

- **Branch names** must match the GitLab regex `^[a-z0-9][a-z0-9/\-\.]*$`. The
  `kapteyn/development/{username}/{enh_id_lower}` pattern is load-bearing for
  `/afk:execute`'s push.
- **`/afk:execute` is the *only* place the agent commits autonomously.** No other
  context auto-commits. No `--no-verify`, no `--force`, no global git config
  changes.
- **Never alter the DB directly.** Add JPA entities and let liquibase-hibernate7
  pick them up; no hand-written `UpgradeGroup` / `db/changelog/*`. `/afk:execute`
  Step 9 enforces this with a pickup-verification run.
- **Cross-module edits need a marker comment** — a ticket-prefixed line like
  `// {TICKET-ID}: shared helper added` in the added hunks of any file outside
  the home module.
- **Re-run `/afk:to-ticket`** after the PRD changes (it's idempotent). It's the
  only design-chain skill that writes to Jira.
- **The dev loop for this repo**: edit a `SKILL.md` → `/reload-plugins`. Nothing
  to build.

---

**Doctrine files at the plugin root:** `GLOSSARY.md`, `REPORTING.md`,
`DELEGATION.md`, `FRESHNESS.md`, and `LAVISH.md` (the lavish-axi pin,
invocation shapes, render-point → playbook map, and fallback/forbid-list —
render-point skills carry only a pointer to it).

**Parent ticket:** P2P-1220 (Jira). For the contributor-facing internals (the
lockstep contract, the three-checkpoint enforcement, the tracker boundary), see
[`CLAUDE.md`](CLAUDE.md).
