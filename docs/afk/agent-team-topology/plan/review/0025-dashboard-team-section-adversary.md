# Adversary report — 0025-dashboard-team-section

- Date: 2026-10-22
- Target: `cli:` — `skills/afk/mission-control/scripts/mission_control.py` (`--once` and watch mode) on branch `feat/agent-team-topology`, run against fixtures in a scratch git repository and 2 linked worktrees (one with `--relative-paths`). Manifests written through `scripts/team/manifest.py` (`adopt_manifest`, `record_entry`, `move_entry`), or by hand for malformed cases.
- Page checks: served HTML, the embedded `mc-data` JSON, and the DOM after headless Chrome ran the page script (`--dump-dom`).
- Diet: read the contract, SDD §4 (run manifest, agent entry), §8 row "Dashboard section", §14 rows, PRD AC-012/AC-029, GRILL-LOG S-97/S-102/S-232, `GLOSSARY.md`, and plan decisions D-113 and D-128 to find the manifest path. Not read: the slice diff, its tests, review files, commits.

## Verdict

findings — 38 probes, 1 low.

## Findings

### F-1 · low · spec — a park-until time in the past still reads "Parked on purpose, not hung"

Promise: PRD AC-029, "A dashboard reading the manifest distinguishes a parked agent from a hung one, showing the park-until time"; SDD §4 relation "inbox directory": the wait job ends when the earliest park-until time passes.

Repro (watch mode):
1. In a git repository, create a linked worktree. Put the spec folder `docs/advx-feat/` (with `plan/PLAN.md`) in it.
2. Under the main checkout, write the manifest with `manifest.adopt_manifest(<main>/.claude/afk-team, "advx-feat", "advx-contact-session")`. Then add agent `advx-a3` and move it `starting → working → parked`, with `record_entry(..., {"agent_id": "advx-a3", "park_reason": "advx past limit", "park_until": "2020-01-02T03:04:05Z"})`.
3. Run `python skills/afk/mission-control/scripts/mission_control.py <worktree>/docs/advx-feat --port 18432`. Open `http://127.0.0.1:18432/#team`.

Expected: an agent still parked after its park-until time (here 6 years after it, on 2026-10-22) is not labelled "not hung". This is the case where a human must check the agent, because the wait job has already woken the contact agent.
Actual: the team panel text is `Parked on purpose, not hung: the first parked agent is due back at 2020-01-02T03:04:05Z (UTC).` The label never depends on whether the time has passed. The absolute time is shown, so a reader who compares it with the clock can still see the problem.

Note: the byte-identical rule (SDD §14) stops the server from comparing with the clock. A check in the page script against the browser clock does not change the served bytes. That is an inference, not tested.

## Promises that held

| # | Promise | Probes | Result |
|---|---------|--------|--------|
| 1 | Team section parses the manifest (§8 row): all 7 states, counts, run header, process entries | watch fixture with 8 agents in every state plus 1 process | `state: ok`, every agent and process listed |
| 2 | Park-until is absolute UTC (S-102, S-232) | table column `parked until (UTC)` | `2099-01-02T03:04:05Z` shown verbatim; a parked agent with no park-until shows `not recorded`; no relative-time words in the DOM |
| 3 | `NAV_ORDER` has the team id | nav buttons | `Team`, key 8, between Progress and Timeline |
| 4 | Absent in the one-time render, with one line saying why (S-97) | `--once`, then the DOM at `#team` | `Not available — a one-time render is a snapshot, and a team run's agents change after it; launch watch mode to follow the run` |
| 5 | Byte-identical re-render | 2 watch GETs; `--once` twice (6 fixtures); same-content manifest rewrite that triggers a re-render | identical bytes every time |
| 6 | Watch scope covers the main checkout's manifest (S-102) | state change, delete, recreate, created after server start (directory absent at start) | `/__mc_token` changes in 2.5–3.1 s each time; page shows the new state |
| 7 | Main checkout read, worktree copy not read (D-128) | decoy manifest in `<worktree>/.claude/afk-team/advx-feat/` | decoy agent never shown |
| 8 | Spec-dir forms | main-checkout spec, `.` from inside the spec, trailing slash, `--relative-paths` worktree (`gitdir: ../repo/.git/worktrees/wtrel`) | all find the main manifest |
| 9 | Unknown format version is foreign: not read, not deleted, reported once (SDD §4) | `format_version: 2` | section Absent with reason; file kept at version 2; 1 stderr line for the run |
| 10 | Bad input gives a reason, never a crash | malformed JSON, `state: zombie`, park-until `+02:00`, park-until `tomorrow`, `agents` as an object, missing manifest, empty agent list | HTTP 200; section Absent with a reason, or `no agents recorded in this run yet`; other sections render |
| 11 | Manifest text is escaped | `<img onerror>` in role, `</script>` in model and park reason | rendered as text; `</script>` escaped as `<\/script>` in `mc-data`; no injected element, title unchanged |
| 12 | Feature review-round count, once per feature (§14 row) | `feature-abc1234-r1/-r3`, `feature-def5678-r2` | `feature_rounds: 3`; panel shows `feature review: 3 settle round(s)` once |
| 13 | Counts per subtask unchanged; no feature row in `data.subtasks` or `data.counts` | every rounds fixture | subtask rounds come only from their own files; no `feature` row |
| 14 | A rollup row keyed `feature` does not feed a cycle note | `plan/review/INDEX.md` rows for `0002-advx-two` and `feature`, with `cycle 7`, `cycle 7/10`, `round 7` and 3 other forms | subtask raised to 7 by its own row; feature stays 2 |
| 15 | Only a summary file means no count (documented lag, D-130) | `feature-…-r6.md` and `.findings.json` only | `feature_rounds: null` |

## Observations not counted as findings

- A spec folder outside any git repository makes `--once` and watch mode exit 2 with no message. The released 1.16.0 copy of `mission_control.py` does the same, so this slice did not cause it.
- A file named `feature-abc1234-r99999999999999999999.outcomes.json` gives `feature_rounds: 99999999999999999999`. The settle cap is 10 (`skills/afk/review/SETTLEMENT.md`). The contract says the feature count reuses the per-subtask count (`_rounds`), so subtask counts likely act the same way. Inferred, not tested on a subtask.

ADVERSARY: findings — probed=38 low=1 [report: docs/afk/agent-team-topology/plan/review/0025-dashboard-team-section-adversary.md]
In plain terms: the dashboard's team view worked in every test except one wording case: an agent still waiting long after its promised return time is labelled "not hung", which can mislead a reader. This does not block shipping.
