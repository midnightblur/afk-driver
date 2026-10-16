## Goal
Under the subagent fallback (no pane transport found, or the pane switch set back to subagent), a role child that runs as a subagent returns its report text, and the agent that started it writes the report file. The move covers 3 kinds of role child: the adversary, each /afk:investigate run and each tracer. The starters at the sites the §14 row lists gain the write, and the text that names the old writer changes. Children that edit code or plugin files, review workers and helpers keep their own writes. The slice ends at the fallback path; the pane paths of the review gate, the adversary and the spawn steps are other subtasks.

## Complexity
standard

## Design refs
- SDD: SDD.md#§14 L9 — Implementation Seams & Change Impact — row "Report-file writers under the subagent fallback, including /afk:investigate step 7"
- SDD: SDD.md#§9b External Seams & Failure Affordance — row "Subagent report-file write"
- SDD: SDD.md#§13 Open Questions — V11, V12, V13

## Scope
- skills/afk/execute/SKILL.md
- skills/utils/investigate/SKILL.md
- skills/afk/grill-requirements/SKILL.md
- skills/afk/grill-requirements/ROUND.md
- agents/afk-tracer.md
- skills/afk/adversary/SKILL.md
- skills/afk/grill-solution/SKILL.md (:76)
- skills/afk/grill-solution/GROUNDING-RULE.md (:25, :40)
- skills/utils/investigate/LEDGER-FORMAT.md (:267)
- skills/afk/execute/CITED-MODE.md (:82-83)
- skills/utils/investigate/scripts/ground_diff.py (:7)
- AGENTS.md (:70-71, :180)
- DELEGATION.md (:26, the afk-tracer clause)
- providers/CONFORMANCE.md (:26, :441 and the new probe rows)
- providers/codex/agents/afk-afk-tracer.toml   # the Codex tracer stub

## Seams
- (none — the one §14 row this slice changes is excepted (partial INV-036); listed under ## Acceptance)

## Acceptance
- [ ] Excepted seam §14 row "Report-file writers under the subagent fallback, including /afk:investigate step 7" (partial INV-036, human exception of 2026-10-02, GRILL-LOG.md:711): before this subtask merges, §13 V11, V12, V13 are proven at build as listed in ## Verification, and the change follows the row's Planned change cell (SDD §14 row "Report-file writers under the subagent fallback, including /afk:investigate step 7")
- [ ] With no pane transport or the switch set back, the adversary, each /afk:investigate run and each tracer return their report text as subagents, and their starter writes the file (SDD §14 row "Report-file writers under the subagent fallback, including /afk:investigate step 7")
- [ ] The starters gain the write: execute/SKILL.md:90 (a file outside the writes its ownership rule at :145 lists); investigate/SKILL.md:44 and :53, each returned fragment; grill-requirements/SKILL.md:46, grill-requirements/ROUND.md:52-56, grill-solution/SKILL.md:76 and GROUNDING-RULE.md:25 and :40, each run's COVERAGE.json and REPORT.md (SDD §14 row "Report-file writers under the subagent fallback, including /afk:investigate step 7")
- [ ] The text that names the old writer changes: investigate/SKILL.md:8, :10; AGENTS.md:70-71 and :180; agents/afk-tracer.md:16, :40; investigate/LEDGER-FORMAT.md:267; the Codex tracer stub; DELEGATION.md:26's afk-tracer clause "writes its coverage fragment", after 0014-delegation-doctrine narrows :26 to helpers and the subagent fallback; providers/CONFORMANCE.md:26; adversary/SKILL.md:40; execute/CITED-MODE.md:82-83 and ground_diff.py:7 (SDD §14 row "Report-file writers under the subagent fallback, including /afk:investigate step 7")
- [ ] The delta tracer and the counter-search tracer of /afk:investigate step 5 and the grill-requirements grounding runs follow the same move (SDD §14 row "Report-file writers under the subagent fallback, including /afk:investigate step 7")
- [ ] Readers stay unchanged: mission control, /afk:retro, the review rollup, verify-seams, the drift re-check and /afk:understand read by path or glob and check no writer, so the starter writes the text as it came (SDD §14 row "Report-file writers under the subagent fallback, including /afk:investigate step 7")
- [ ] The starter writes the returned text as it came, before it cites any finding; the `ADVERSARY:` line keeps its shape and names the brief's path, and the starter writes the returned report there (agent-decided, SDD §14 row "Report-file writers under the subagent fallback, including /afk:investigate step 7")
- [ ] Children that edit code or plugin files keep writing (the /afk:autopilot subtask agent, the /afk:bug fixer, the lessons capture writer, the /afk:design-system card builders, the /afk:to-meeting-b page writer); review concern workers already return their findings; helpers keep writing their evidence files; a review worker's mutation-probe output stays with the worker (agent-decided, SDD §14 row "Report-file writers under the subagent fallback, including /afk:investigate step 7")
- [ ] With no pane transport found, or with the switch set back, role agents run as subagents and the run report says so; such a subagent returns its report as text, and the agent that started it writes the report file (PRD AC-044)
- [ ] With the switch set back, a role starts as a subagent and its parent writes its report file (PRD AC-044)
- [ ] Every artifact in ## Produces exists with its declared contract (SDD §14 row "Report-file writers under the subagent fallback, including /afk:investigate step 7")
- [ ] The fallback rests on the §9b subagent-write seam: the extended probe asserts on the harness's real Write refusal and acceptance for the review gate's file names and the bug result file (SDD §9b row "Subagent report-file write")

## Produces
- skills/utils/investigate/SKILL.md#starter writes the file — the starter-writes rule at investigate's spawn

## Consumes
- 0017-spawn-steps skills/afk/autopilot/SKILL.md#pane-agent rule — the spawn steps the fallback reverses
- 0018-review-gate-pane-workers skills/afk/review/SKILL.md#lifespan Turn — the review fallback path
- 0019-adversary-pane-agent skills/afk/adversary/SKILL.md#pane agent per attempt — the adversary fallback path

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `grep -n 'starter writes the file' skills/utils/investigate/SKILL.md`; `grep -n 'pane-agent rule' skills/afk/autopilot/SKILL.md`; `grep -n 'lifespan Turn' skills/afk/review/SKILL.md`; `grep -n 'pane agent per attempt' skills/afk/adversary/SKILL.md` | Produces and consumed anchors present |
| static | `afk-python -m pytest scripts/tests/test_skill_frontmatter.py -q` | skill frontmatter still valid |
| integration | V11, environment-gated on Claude Code: probe providers/CONFORMANCE.md:441 extended with the review gate's file names (the slice report, its findings JSON, plan/review/INDEX.md); recorded as a probe row | V11; seam-test of §9b row "Subagent report-file write" |
| integration | V12, environment-gated on Claude Code: probe providers/CONFORMANCE.md:441 extended with the /afk:bug result file's name; recorded as a probe row | V12; seam-test of §9b row "Subagent report-file write" |
| integration | V13, environment-gated on each harness: a new probe row in which a subagent returns a large report and its starter writes it unchanged | V13 |

## Context excerpts
> (SDD §14 row "Report-file writers under the subagent fallback, including /afk:investigate step 7", Planned change) With no pane transport or the switch set back, the subagent returns its report text and its starter writes the file (S-157, AC-044). The move covers 3 kinds of role child: the adversary, each /afk:investigate run and each tracer. Children that edit code or plugin files keep writing: the /afk:autopilot subtask agent, the /afk:bug fixer, the lessons capture writer, the /afk:design-system card builders and the /afk:to-meeting-b page writer. Review concern workers already return their findings (S-209). Helpers keep writing their evidence files (D-13, which restates S-209 and AC-044). Agent-decided: the ADVERSARY: line keeps its shape and names the brief's path, and the starter writes the returned report there before it cites any finding (D-15); a review worker's mutation-probe output is build output and stays with the worker (D-17)

> (SDD §14 row "Report-file writers under the subagent fallback, including /afk:investigate step 7", Impacted flows) Starters gain a write: execute/SKILL.md:90, a file outside the writes its ownership rule at :151 lists; investigate/SKILL.md:44 and :53, each returned fragment; grill-requirements/SKILL.md:46, grill-requirements/ROUND.md:52-56, grill-solution/SKILL.md:76 and GROUNDING-RULE.md:25 and :40, each run's COVERAGE.json and REPORT.md (INV-036 c-82baecb6, c-fec6258d, inference). Text that names the old writer changes: investigate/SKILL.md:8, :10; AGENTS.md:70-71 and :180; agents/afk-tracer.md:16, :40; investigate/LEDGER-FORMAT.md:267; the Codex tracer stub; DELEGATION.md:26; providers/CONFORMANCE.md:26; adversary/SKILL.md:40 (c-d4330950, inference); execute/CITED-MODE.md:82-83 and ground_diff.py:7 (c-362024d6). Readers stay unchanged when the starter writes the text as it came: mission control, /afk:retro, the review rollup, verify-seams, the drift re-check and /afk:understand read by path or glob and check no writer (c-e8ed64a9, c-6bee9be2, inference; INV-036)

> (SDD §14 row "Report-file writers under the subagent fallback, including /afk:investigate step 7", Conventions / landmines) How a subagent's final text reaches its starter, and how much one reply carries, is unproven (c-80e1da73; §13 V13); ledgers run up to 35,603,954 bytes (c-14a0900a), though mission-control digests already return a whole artifact for the starter to write (c-c6de43ce). … The JSON readers of fragments and ledgers refuse a malformed document loudly, while the adversary verdict parsers read the first 4000 characters and drop a report with no verdict label silently (gates.py:114, insights.py:206), so the starter writes the text as it came (c-b99ad411, inference). The stall watchdog takes a file change under the watched paths as a tracer's only sign of life, so a tracer whose evidence writes move looks stale after 20 minutes (stall-watchdog.sh:13-18; c-c8c603d3, inference). Compatibility: AC-001 gains one difference: a subagent's report file is written by the agent that started it (AC-044).

> (SDD §9b row "Subagent report-file write") Claude Code 2.1.285, probe 2026-09-30 (providers/CONFORMANCE.md:441) | A subagent's Write tool refuses REPORT.md, SUMMARY.md and findings.md; other names and a shell write pass. Codex refuses none | Under the subagent fallback the starter writes the report the child returns (S-157, AC-044) | The probe; extend it with the review gate's file names and the bug result file (§13 rows for INV-036)

> (SDD §13 V11) Whether a Claude Code subagent's Write tool refuses the review gate's own files. Under the subagent fallback the review orchestrator runs inside the subtask subagent and writes the slice report, its findings JSON and the rollup plan/review/INDEX.md (review/SKILL.md:159, :161); the probe tested other names only (providers/CONFORMANCE.md:441). INV-036 c-eafe6df3; §14 row Report-file writers. Proven at build by: the probe 'A subagent's file write is refused, and which paths the refusal covers' (:441), extended with these file names

> (SDD §13 V12) Whether a Claude Code subagent may write the result file through which the /afk:bug publisher and retester return their result line when they run as subagents (S-165); the probe tested other names only (providers/CONFORMANCE.md:441). INV-036 c-86e07f89; §14 row Report-file writers. Proven at build by: probe :441 extended with the bug result file's name

> (SDD §13 V13) How a subagent's final text reaches the agent that started it, and how much text one reply carries. AC-044 routes every report, ledger and fragment through that reply, and no feature document states its bound (INV-026, INV-036 at PRD.md:144). INV-036 c-80e1da73; §14 row Report-file writers. Proven at build by: a new probe row in which a subagent returns a large report on each harness and its starter writes it unchanged

> (PRD AC-044) With no pane transport found, or with the switch set back, role agents run as subagents and the run report says so. Such a subagent returns its report as text, and the agent that started it writes the report file.

> (PRD Testing Decisions) | Role and helper line | With a pane transport, a role agent starts in a pane; with the switch set back it starts as a subagent and its parent writes its report file. On a tool that delivers only by typing into panes, a message to the contact agent lands in its inbox, never in its input box. A start request from an agent not live in the manifest is refused. |

## Parent PRD
docs/afk/agent-team-topology/PRD.md

## Parent SDD
docs/afk/agent-team-topology/SDD.md

## Blocked by
0017-spawn-steps, 0018-review-gate-pane-workers, 0019-adversary-pane-agent

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality
during implementation, classify per the decision protocol (`DECISIONS.md`,
workflow plugin root): a two-way-door correction is recorded in
`plan/DECISIONS.md` and implemented; a one-way door or a tie exits
`design_conflict` quoting the SDD section + the conflict. Never override off
the record. Parked conflicts route back to `/afk:grill-solution` for a
superseding ADR.
