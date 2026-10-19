# Adversary report — 0001-glossary-terms

Verdict: `findings` — probed=18, crit=0 high=0 med=1 low=2.

Running system: the plugin's command-line surface in the worktree. Probes ran on copies of `GLOSSARY.md`, `docs/afk/agent-team-topology/LAVISH-TIPS.md` and `scripts/lavish/` in the scratch folder `adversary-0001/`. The tooltip wrap step was replayed in Node (`wrap.js`) with the exact regex and `tipFor` logic from the `tips_block` runtime in `scripts/lavish/inject.py:222-245`.

Diet held: the contract, its cited PRD and SDD passages, the SDD term table, `GLOSSARY.md`, `LAVISH-TIPS.md` and `scripts/lavish/inject.py`. No diff, no branch history, no implementor tests, no review files.

## Findings (worst first)

### A-1 (generic words get team-topology tooltips) — medium, class `spec`

Promise: `GLOSSARY.md:29` (Team topology) says "with no configuration the plugin behaves as it always has". `GLOSSARY.md:244` (Tooltip dictionary) says every lavish artifact inherits this glossary's entries. `LANGUAGE.md` §1 says "One term, one meaning".

Observed: the new single-word entries, such as Run, Role, Stage, Helper, Builder, Hub, Inbox, Envelope and Recipe, become case-insensitive tooltip keys that also match plurals. Every lavish page in every repository now attaches the team-topology meaning to these everyday words, whether or not a team topology is configured. The glossary itself uses "run" with a second meaning: one invocation of a skill (`GLOSSARY.md:351` "an `execute` run", `GLOSSARY.md:445` "`Run history` lines keep every run").

Repro (inject, then replay the wrap):
```
python adversary-0001/run_inject.py adversary-0001/repo adversary-0001/dict.json
node adversary-0001/wrap.js adversary-0001/dict.json adversary-0001/lines.txt
```
Input text → tooltip shown:
| Page text | Matched | Tooltip | Expected |
|---|---|---|---|
| `Run the build before you commit.` | `Run` (verb) | All work on one feature under a team topology. | no tooltip |
| `The smoke test run failed on stage 2 of the deploy pipeline.` | `run`, `stage` | team-topology run; "One step of the workflow chain." | no tooltip |
| `The user role needs admin rights; the helper script parses the envelope header.` | `role`, `helper`, `envelope` | team-topology meanings | no tooltip |
| `The structured result tokens of an execute run.` (glossary's own text) | `run` | team-topology run | a skill run, not a team run |
| `afk-lite is the built-in pattern the bug-fix skill runs.` | `runs` (verb) | team-topology run | no tooltip |

The contract requires these terms (Acceptance bullet 1, SDD §13 Q1), so the executor followed the spec. The term choice in the spec causes the collision. Possible remedy (inferred, not tested): qualify the term names, for example "Team run", or leave the tooltip key set out for these entries. The choice belongs to the caller.

Lift as a permanent check: a lavish-inject test that injects a page holding `Run the build` and asserts the dictionary gives no team-topology tooltip for the verb.

### A-2 (Afk-lite names its skill vaguely) — low, class `spec`

Promise: the SDD term table, `SDD.md:33`, says "The built-in pattern that /afk:fix runs (BP-5)". `LANGUAGE.md` §2 says to write every workflow skill reference as literal `/afk:<x>`.

Observed: `GLOSSARY.md:112` says "The built-in pattern the bug-fix skill runs." The same glossary defines two bug skills: `/afk:bug` ("autonomous fix pipeline", `GLOSSARY.md:367`) and `/afk:fix`. The tooltip does not say which skill runs afk-lite.

Repro: `parse_glossary(GLOSSARY.md)["afk-lite"]` returns `The built-in pattern the bug-fix skill runs.`. Expected: text that names `/afk:fix`.

### A-3 (Builder entry leaves out the autopilot case) — low, class `spec`

Promise: the SDD term table, `SDD.md:22`, says "The one role that commits and pushes, one active at a time (S-135); under /afk:autopilot, the subtask agent (S-227)".

Observed: `GLOSSARY.md:82` keeps only the first clause. The tooltip and the glossary do not say who the builder is under `/afk:autopilot`.

Repro: `parse_glossary(GLOSSARY.md)["builder"]` returns `The one role that commits and pushes, one active at a time.`. Expected: the definition also says that under `/afk:autopilot` the builder is the subtask agent.

## Scenarios that held

| # | Promise | Probe | Result |
|---|---|---|---|
| 1 | Produces anchors exist | Verification row 1 grep chain | exit 0; lines 69, 72, 162, 165, 168 |
| 2 | No "relays through the contact agent" wording | Verification row 2 | exit 0 |
| 3 | Glossary usage check passes | `afk-python -m pytest scripts/tests/test_glossary_usage.py -q` | 15 passed |
| 4 | All 36 listed terms plus pane transport present (AC bullet 1) | `inject.parse_glossary` key lookup | 0 missing of 37 |
| 5 | No term added twice | `keys_for` key counts over every `GLOSSARY.md` entry | 0 duplicate keys |
| 6 | Charter text (AC-066) | parsed entry | never empty, pattern part plus one part per role |
| 7 | Charter file text (SDD §4) | parsed entry | one per role per run, run directory, pattern part then role part, only copy for a one-off pattern |
| 8 | One-off pattern text (AC-066) | parsed entry | no record, pattern-record fields, charter and record check when it has roles; no charter when it has none |
| 9 | Team pattern carries the charter | parsed entry | "for a pattern that starts agents, its charter" |
| 10 | Talk edges text (AC-035, AC-069) | parsed entry | off-edge refusal names the edge; 4 no-edge paths; report target both ways; siblings only along declared edges |
| 11 | LAVISH-TIPS copy matches | parsed `talk edges` from both files | identical strings |
| 12 | No relay claim in either file | Python scan for "relay" | only `GLOSSARY.md:25` (contact agent relays instructions) and `LAVISH-TIPS.md:15` (relayer); neither is the removed claim |
| 13 | New entries reach the page dictionary | `inject_file` on a sample page | dictionary holds all new keys |
| 14 | Compound terms win over their head word | wrap replay | "charter file", "role agent", "pane transport", "stage map" match whole; "Pane agents" plural resolves |
| 15 | Seed tips not overridden | `tips.json` key search for the new single words | no collision |
| 16 | Role agent text agrees with the pane switch (AC-041; SDD pane switch row) | parsed entry | conditioned on pane transport and pane switch |
| 17 | Generic-word matching | wrap replay | see A-1 |
| 18 | Definitions agree with the SDD term table | row-by-row comparison, `SDD.md:15-50` | agree except A-2 and A-3 |

ADVERSARY: findings — probed=18 crit=0 high=0 med=1 low=2 report: docs/afk/agent-team-topology/plan/review/0001-glossary-terms-adversary.md
In plain terms: the new glossary entries are present and correct, but common words such as "run" and "role" now show team-setup explanations on every interactive page, and two entries are vaguer than the design. These are wording fixes, not blockers.
