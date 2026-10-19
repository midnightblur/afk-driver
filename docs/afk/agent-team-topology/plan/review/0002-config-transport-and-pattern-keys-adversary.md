# Adversary report — 0002-config-transport-and-pattern-keys

- Date: 2026-10-19
- Running system: a copy of the working tree (no `.git`) at `C:/Users/mvu/AppData/Local/Temp/claude/C--Users-mvu-PersonalProjects-afk-driver-agent-teams/96c58aef-58cc-4e51-8bc9-2259fed7dd71/scratchpad/adversary-0002/repo`, driven through `afk-python scripts/afk-config.py` (`validate FILE`, `validate` by discovery, `export-shell`, `effective --json`, `get`), `hooks/lib/adapter.sh`, `hooks/lib/adapter_registry_check.py` and `skills/utils/report-issue/scripts/collect_env.sh`. `HOME` and `USERPROFILE` pointed at an empty folder.
- Baseline: the `main` reader, extracted with `git archive main` and run as a black box (source not read).
- Verdict: `findings` — probed=126, crit=0 high=0 med=1 low=0.

## Findings

### F1 — medium · correctness · an empty `transport:` block erases the kind the probe hands in

Promise: D-43 ("with B no configuration ever sets AFK_CFG_TRANSPORT, so the probe's handed-in kind is never overwritten by a config load"); ADR-0001 ("A probe … resolves the best available kind and hands it to the dispatcher as if configured").

The reader accepts `transport:` with no children (null value) and exports `AFK_CFG_TRANSPORT=''`. The dispatcher reads `AFK_CFG_TRANSPORT`, so a config load after the probe replaces the handed-in kind with an empty string. A file whose `transport` children are all commented out reaches this state. `transport: ""` is refused with "must be a mapping"; the null form is not.

Repro (config file `.afk/config.yaml` in a git repository):

```yaml
schema: 1
transport:
  # kind: multiplexer
```

| Step | Command | Actual | Expected |
|---|---|---|---|
| 1 | `afk-python scripts/afk-config.py validate` | exit 0, `configuration is valid` | exit 0 is acceptable |
| 2 | `afk-python scripts/afk-config.py export-shell \| grep TRANSPORT` | `AFK_CFG_TRANSPORT=''` | no `AFK_CFG_TRANSPORT` line |
| 3 | `bash -c '. hooks/lib/adapter.sh; export AFK_CFG_TRANSPORT=multiplexer; afk_adapter_kind transport'` | empty line | `multiplexer` |
| control | step 3 with `schema: 1` only | `multiplexer` | `multiplexer` |

The same null-export pattern gives `AFK_CFG_TRANSPORT_KIND=''` for `kind:` and `AFK_CFG_TRANSPORT_PANE_SWITCH=''` for `pane-switch:`. No consumer of those 2 names exists yet; recorded here for the subtask that adds one.

Lift as a permanent scenario: a reader case asserting that `export-shell` on `schema: 1` + `transport:` (null) prints no line that starts with `AFK_CFG_TRANSPORT=`, or that `validate` refuses the null block the way it refuses `transport: ""`.

## Promises that held

| Promise | Scenarios | Result |
|---|---|---|
| Transport family key, kind choice, kind blocks (AC C1, ADR-0001, SDD §5) | `kind` each of 4 kinds; `tmux`, `Multiplexer`, `''`, `3`, a list; `transport: multiplexer` scalar; unknown child; `multiplexer.socket`; kind block as scalar or list; null kind block | valid kinds accepted; every bad value refused at exit 2 with the dotted path |
| Pane switch (AC-041, SDD §4) | `pane`, `subagent`, quoted forms, absent, `panes`, `Pane`, `true`, `pane_switch` spelling | only `pane` and `subagent` pass; `get transport.pane-switch` returns the value, exit 1 when absent |
| Saved pattern with a built-in name (AC-062) | all 5 built-in names, plus `SOLO`, `build_verify`, `review_panel`, `AFK.LITE`, `Debate`, and the same names in a local overlay; control `solo-2` | each refused; control accepted |
| 2 saved patterns with one name (AC-062) | `adv-x` + `adv_x`; `adv-x` + `ADV-X`; one in the repository file and one in the local overlay | each refused |
| Include or stage-map entry naming no pattern (AC-062) | missing name as scalar, inside a list, in `includes`; case or separator variants of real names (`Solo`, `build_verify`, `ADV_X`, `Debate`) | each refused; references resolve to built-ins, same-file patterns, overlay patterns and machine-layer patterns |
| Stage-map shape (AC-032) | one name; list; null; `""`; list of an integer; map value; scalar `stage-map: x` | only one name or a non-empty list passes |
| Saved pattern as data, every field (AC-003, Q54) | all 9 pattern fields and all 6 role fields together; unknown pattern field; unknown role field (`modle`); roles as a list; wrong types for every typed field; `name` differing from its key | full pattern accepted and exported; each defect refused with its dotted path |
| Keys that fold to one shell name (C9) | stage `review` list + stage `review-count` or `review-0`; `adv-a.roles.x.charter` + pattern `adv-a-roles-x`; `adv-a.edges.0.name` + pattern `adv-a-edges-0`; roles `lead` + `LEAD`; stages `execute` + `Execute`; edge keys `from` + `FROM` | each refused, naming both paths and the shared `AFK_CFG_*` name |
| Roles as a map (SDD §14) | local overlay changes `lead.model` and `includes` | `helper` role survives; `includes` list replaced whole; `stage-map` entry replaced |
| Topology and per-role model independent (AC-002) | patterns only; stage-map only; patterns with role models; neither | each reads |
| Unknown top-level keys still refused | `bogus-top`, `Transport` | refused at exit 2 |
| Old configuration reads as before (S-246) | rich old file (tracker, forge, build gates, jira, git, maven, npm, verification, review, report-issue, developer) | `validate` passes; `export-shell` and `effective --json` byte-identical to the `main` reader |
| Shell safety of chosen names | keys with space, `;`, `$(…)`, backticks, quotes, non-ASCII | refused by the YAML subset; edge values with `;` exported quoted |
| Registry check reads the transport family (C2, C3) | fake `adapters/transport/multiplexer` and `adapters/transport/adv-bogus` | in-enum kind: no drift; bogus kind: drift line listing the 4 kinds; `main` checker offers no transport kind |
| Collector lists the transport family (C8), issue template row (D-46) | `kind: desktop`; no key; `pane-switch` only; null block; `AFK_CONFIG` file | `transport` field reads `desktop`, `auto`, `auto`, `auto`, `multiplexer`; `ISSUE-TEMPLATE.md:42` carries `transport <transport>` |
| Family-count text (C4, C5) | search outside tests and spec folders for "four adapter families" | only a `CHANGELOG.md` history line; `ADAPTERS.md` has "Adding a family"; `AGENTS.md:224` lists 5 families; `CLAUDE.md` is `@AGENTS.md` |

## Observations outside the verdict

- `export-shell` and `effective --json` do not validate: a configuration with a saved pattern named `solo` exports at exit 0. The `main` reader behaves the same for an unknown top-level key, so this is the existing contract (`CONFIG.md`: "`validate` fails only on schema problems"). The SDD §14 rollback text "a refused configuration leaves every plugin setting empty" does not match it: the `main` reader exports a configuration with `transport.kind` at exit 0.
- A pattern key with a dot (`adv.x`) is accepted and folds correctly, but `get patterns.adv.x.name` exits 1 because `get` splits on dots. `effective --json` carries it.
- Not probed: native check M on `hooks/lib/adapter_registry_check.py` (a static gate, not a runtime behaviour).

## Information diet

- Read: the contract, `DECISIONS.md` D-43 to D-46, `CONFIG.md`, `ADAPTERS.md`, `AGENTS.md`, the reader's usage text, the header comment of `collect_env.sh` and the docstring head of `adapter_registry_check.py` (neither has `--help`), and `afk_adapter_kind` in `hooks/lib/adapter.sh` (dispatcher, outside Scope).
- Read in passing: `DECISIONS.md` D-47 printed with the requested entries. It names a withdrawn review finding id and a test name about `redact.py`, outside every promise probed here. No review file, test file, diff or branch commit was read. Verdict judged not tainted.
