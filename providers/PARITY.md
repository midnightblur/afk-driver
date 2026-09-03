# Parity ledger

The extraction plan set 96 parity rows — one per skill, agent, hook script,
repository hook, MCP server and doctrine file — and asked for each to be proven
before the toolkit could be called finished. This file is the answer, row by
row, and it is written to be checked rather than believed.

Three verdicts are used, and only three:

- **proven** — something was run and its result observed. The evidence column
  says what.
- **covered** — the row's claim is exactly what an automated gate asserts, and
  that gate is green. No separate run was made, and none is needed: the gate
  would fail the release if the claim stopped holding.
- **not proven** — no run, and no gate that asserts it. Named here rather than
  quietly counted as green.

**Totals: 96 rows — 25 proven, 45 covered, 26 not proven.**

The twenty-six are almost all of one kind, and it is worth saying plainly what
kind: they are fixture runs that were never made. Nineteen are skills. Six are
gates or probes whose behaviour needs a seeded input to demonstrate — a
surviving mutant, a missing translation key, a rule violation, a stalled child,
an application that starts, a search counter driven past its threshold. The
last is the render doctrine, which needs a grill session to exercise. Every one
of these items loads, registers, and passes the registry
and contract gates on both harnesses. What has not been shown is that its output
or its refusal is what the plan's row describes. That is the honest boundary of
this evidence, and the last section says what would close it.

## What each source of evidence is

| Tag | What it means |
|---|---|
| `ledger` | The probe ledger in `CONFORMANCE.md` — rounds 1-4, both harnesses |
| `round5` | The adapter proof round in `CONFORMANCE.md` — every adapter kind against its real service |
| `cutover` | The install and uninstall record in `CONFORMANCE.md`, on the owner's own two harnesses |
| `gate` | An automated gate asserts exactly this, and the gate is green: the four Stop gates, `precommit-gates.sh`, `release-gate.sh`, `hooks/tests/hook-smoke.sh`, the 80-test suite, `claude plugin validate .` |
| `release` | Observed during the v1.0.1 / v1.0.2 release and reinstall on both harnesses |

## Skills

| Row | Verdict | Evidence |
|---|---|---|
| afk/adversary | not proven | Loads and registers on both harnesses; no fixture contract was probed |
| afk/autopilot | not proven | Loads and registers; no fixture plan was driven |
| afk/bug | not proven | Its tracker calls are proven through `round5`; the dossier shape was not rendered |
| afk/claude-md | not proven | Loads and registers; no fixture delta was produced |
| afk/design-system | not proven | Loads and registers; the design-system tool is main-session-only and was not driven |
| afk/execute | not proven | Its build gates are proven through `round5`; no driven slice was run |
| afk/fix | not proven | Its gate behaviour is proven through `round5` (blocked then passed); the loop was not run |
| afk/gc | not proven | Loads and registers; no worktree collection was run |
| afk/grill-requirements | not proven | Loads and registers; no grill round was rendered |
| afk/grill-solution | not proven | Loads and registers |
| afk/grill-verification | not proven | Loads and registers |
| afk/lessons | covered | `gate` — the append and digest scripts are exercised by `hook-smoke.sh` and the test suite |
| afk/mission-control | not proven | Its renderer's own unit suite is part of the 80 tests; no board was rendered from a live tracker |
| afk/preflight | not proven | Its forge verbs are all proven through `round5`, including `ci-wait` on a live pull request; the chain was not run end to end |
| afk/prototype | not proven | Loads and registers |
| afk/retro | not proven | Loads and registers |
| afk/review | not proven | Loads and registers; its eleven checklists are gate-checked, no review was run |
| afk/setup | proven | `release` — run on the second harness's real installation: it wrote all four agent stubs with the plugin root substituted and reported its own failed rows honestly |
| afk/smoke-test | not proven | Loads and registers |
| afk/tdd | not proven | Loads and registers |
| afk/to-demo-plan | covered | `gate` + `round5` — its notes writes go through the proven `notes` adapter |
| afk/to-design-brief | covered | `gate` + `round5` — obsidian variant proven at the adapter |
| afk/to-prd | covered | `gate` + `round5` — repo-files, obsidian and notion all proven at the adapter |
| afk/to-sdd | covered | `gate` + `round5` |
| afk/to-subtasks | covered | `gate` + `round5` — `tracker_create` with parent proven on both tracker kinds |
| afk/to-ticket | covered | `gate` + `round5` — creation proven on both tracker kinds |
| afk/to-verification-plan | covered | `gate` — the tier-key rule is asserted by the genericity and config gates |
| afk/understand | not proven | Loads and registers |
| utils/caveman | covered | `gate` — harness-neutral, no adapter; the contract gates assert the only claim |
| utils/diagnose | covered | `gate`; its absence from one harness's model-visible listing is a known open item in `CONFORMANCE.md` |
| utils/draw-charts | covered | `gate` |
| utils/glossary | covered | `gate` — config resolution asserted by the config tests |
| utils/handoff | covered | `gate` — the `/afk:` prefix rule is asserted by the registry gate |
| utils/harvest | covered | `gate` |
| utils/interactive-walkthrough | covered | `gate` |
| utils/review-qa-tests | covered | `gate` |
| utils/settle-change | covered | `round5` — every forge verb it uses was driven against a live merge request and two live pull requests |
| utils/settle-mr | covered | `gate` — the registry gate accepts the alias and resolves its forward |
| utils/todo | covered | `gate` |
| utils/verify-seams | covered | `gate` — the wiring gate is the same machinery, green on this tree |
| utils/writing-for-agents | covered | `gate` — the genericity gate asserts the no-monorepo-vocabulary claim |

## Agents

| Row | Verdict | Evidence |
|---|---|---|
| afk-implementor | proven | `ledger` both harnesses; `release` — the second harness's stub was reinstalled under its new name |
| afk-reader | proven | `ledger` both harnesses; `release` — spawned on a real session of the second harness, returned a cited answer verbatim |
| afk-runner | proven | `ledger` both harnesses |
| afk-runner-lite | proven | `ledger` both harnesses |

## Hooks and scripts

| Row | Verdict | Evidence |
|---|---|---|
| run-hook.py | proven | `ledger` — both root variables honoured; repo kind resolves from `.afk/hooks.json` |
| hooks.json | covered | `gate` — `claude plugin validate .` and the registry gate |
| hooks.codex.json | covered | `gate` — the native-contract gate diffs the twin modulo the root variable |
| stop-gates.sh | proven | `ledger` — real Stop blocks observed on both harnesses |
| precommit-gates.sh | proven | `round5` — dispatched maven on a monorepo worktree and npm on a fixture |
| gate-context.sh | covered | `gate` |
| gate-cache.sh | covered | `gate` |
| gate-metrics.sh | proven | `round5` — metrics lines observed on every build-gate run |
| gate-metrics-report.sh | covered | `gate` |
| wiring-gate.sh | covered | `gate` — green on this tree, and it is the gate that would fail |
| skill-registry-gate.sh | covered | `gate` — validates every skill, agent and `adapter.json` on each run |
| native-contract-gate.sh | proven | `ledger` — negative probe returned exit 2 naming all six findings; it blocked three real changes during this release |
| genericity-gate.sh | proven | `release` — it caught a real ticket key in new prose and was answered by rewriting, not allow-listing |
| branch-name-gate.sh | covered | `gate` |
| install-git-hooks.sh | covered | `gate` |
| stall-watchdog.sh | not proven | No timing probe was run |
| lesson-append.sh | covered | `gate` — `hook-smoke.sh` |
| lesson-digest.sh | covered | `gate` — `hook-smoke.sh` |
| lavish-dark.sh | covered | `gate` |
| lavish-tips.sh | covered | `gate` |
| maven-lock.sh | covered | `gate` |
| maven-compile-gate.sh | proven | `round5` — exit 0 in 148 s on a monorepo worktree, with `--also-make` in the invocation |
| java-format-gate.sh | proven | `round5` — exit 2 on an unformatted file, exit 0 once formatted |
| mutation-probe.sh | not proven | No seeded mutant was run |
| ui-lint-gate.sh | proven | `round5` — exit 0 clean, exit 2 on a lint error; this is the row whose bug the round found |
| app-start-gate.sh | not proven | No fixture application was started in this programme |
| release-gate.sh | proven | `release` — exit 0 at v1.0.1 and v1.0.2; it is what forced the four-way version agreement |
| update-notice.sh | covered | `gate` |
| hooks/lib/provider.sh | proven | `ledger` — auto-detection returned the right adapter on both harnesses |
| providers/claude.sh | proven | `ledger` |
| providers/codex.sh | proven | `ledger` round 4 |
| hooks/lib/config.sh | covered | `gate` — the config tests compare the shell view against `effective --json` key by key |
| scripts/afk-config.py | covered | `gate` — its own test directory is inside the 80 |
| hooks/lib/adapter.sh | proven | `round5` — dispatched every family and kind; the round found and fixed two dispatch defects here |

## Repository hooks

| Row | Verdict | Evidence |
|---|---|---|
| crowdstrike-guard.sh | proven | `ledger` both harnesses; it blocked four commands during this release, which is the strongest evidence a guard can offer |
| explore-counter.sh | not proven | The counter was not driven past its threshold after the path fix |
| i18n-parity-gate.sh | not proven | No seeded missing key was run |
| java-rules-gate.sh | not proven | No seeded rule violation was run |

## MCP server

| Row | Verdict | Evidence |
|---|---|---|
| `tracker` server | proven | `round5` for the jira and github-issues kinds, nine tools each; `release` — registered and callable on both harnesses, and the v1.0.1 defect that stopped it starting on one of them is fixed and re-proven there |

## Doctrine

| Row | Verdict | Evidence |
|---|---|---|
| CAPABILITIES.md | covered | `gate` — the native-contract gate cross-checks the table against disk |
| DELEGATION.md | covered | `gate` — agent names checked by the registry gate |
| LAVISH.md | not proven | No grill fixture was rendered on either harness |
| CONFIG.md | covered | `gate` — both sample configurations validate; the literal-grep rule is a gate |
| ADAPTERS.md | covered | `gate` — the registry gate diffs it against every `adapter.json` |
| CHANGELOG.md | proven | `release` — the release gate reads its first released heading, three times |
| README.md | proven | `release` — the install commands were run on both harnesses, and one of them was wrong and is corrected |
| hooks/README.md | covered | `gate` — the registry gate checks it against the `hooks/` listing |
| providers/CONFORMANCE.md | proven | It is the evidence, and it was written from runs |
| review checklists | covered | `gate` — all eleven load and pass the genericity gate |
| adapters CONTRACT.md | covered | `gate` — the registry gate diffs verbs against `operations[]`, empty on every kind |
| LICENSE | proven | Added in this release. It was missing: an owner decision that never landed on disk, and the row that found it |

## What would close the twenty-six

Each is one fixture run, and the fixtures are cheap: a temporary repository, a
seeded input, one invocation, one look at the output. They were skipped because
the programme spent its proof budget on the boundaries between this code and
services it does not own — which is where all twelve of round 5's defects lived,
where the release defect that made the toolkit unusable on one harness lived,
and where none of them would have been visible from a fixture.

That was the right trade for finding defects. It leaves two claims unmade: that
each skill's output matches the shape its row describes, and that each of the
six seeded-input gates refuses what it says it refuses. A gate that has never
been shown to block is the more expensive of the two to leave open, because a
gate that silently stopped working looks exactly like a gate with nothing to
catch — which is precisely the defect round 5 found in the lint gate, and found
only because something was seeded for it to catch.

Anyone continuing this work should run the twenty-six before adding to them, and
should start with the six gates.
