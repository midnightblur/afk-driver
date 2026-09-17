# Plugin defect candidates found while planning research-enhancement

Found at commit d8ca9b4 while running the design chain on this repository. None filed; the PR description carries the list. Each entry: evidence, effect, workaround used.

## 1. `merge_fragments.py` folds seed placeholders as conflicts

- Evidence: every seed node arrives as `unverified: seed map hit, not yet triaged` and every class without a method as a `no enumeration method` boundary row; the fold treats a fragment's disposition of the same node as `conflict: unverified vs <verdict>` (45 conflicts on a literal fold of INV-005). Seed `judgment-only` and `unverified` boundary statuses also win the worst-status fold, so a verdict stays `partial` after every row is dispositioned.
- Effect: no fragment can fold onto its own seed without hand work.
- Workaround: fold a staging copy of the seed with the placeholder nodes and boundary rows replaced by the fragment's rows; every node id, `line_hash` and `query_id` carried unchanged. Disclosed in each `investigations/INV-00N-*/REPORT.md`.

## 2. `seed_map.py` splits a dotted subject on `.`

- Evidence: `skills/utils/investigate/scripts/seed_map.py:315` takes the last dotted segment as the simple name, so the root `provider.sh` searches bare `sh` (14,950 B1 hits, 47-minute run for INV-007; the first INV-008 run was killed after an hour).
- Effect: a file-name root is unusable as a subject.
- Workaround: extension-less subjects with the file name declared as a `wire=` alias (`--alias file=provider.sh`).

## 3. `validate_coverage.py` and `LEDGER-FORMAT.md` disagree on `sites` rows

- Evidence: `skills/utils/investigate/scripts/validate_coverage.py:351-357` counts only `traced` and `terminal` read nodes toward a `sites` row; `skills/utils/investigate/LEDGER-FORMAT.md:80-82` also admits `irrelevant`. A row cannot carry both `sites` and hits (`:414-436`).
- Effect: a declared-scan site read as irrelevant does not close its class.
- Workaround: declared-scan sites dispositioned `terminal`; B5 and B10 in INV-006 closed by search with their sites read under the agent counter-check.

## 4. `run.config.sha256` anomaly in INV-003

- Evidence: `investigations/INV-003-provider-library/COVERAGE.json` carries `run.config.sha256` = sha256 of `{}` (an empty block) although `.afk/config.yaml` carried the `investigation:` block on disk at seed time; INV-005..008, seeded later against the same file, carry the block's digest `360476c8…`. INV-001/002/004 were restamped by hand from `seed_map.load_config`.
- Effect: a ledger may record a config it did not read; `merge_fragments.py identity()` then refuses a fragment whose digest differs from the staging ledger's.
- Cause: not verified (unconfirmed). Candidate: the seed read the main checkout's config, not the worktree's.
- Workaround: none applied to INV-003; the block's B3 instance was closed at the same site by judgment.

## 5. `merge_fragments.py identity()` blocks a re-seed after a config change

- Evidence: `identity()` refuses a fragment whose `run.config.sha256` differs from the staging ledger's, so the surviving INV-001/002/004 fragments could not fold onto a re-seed under the new block.
- Effect: adding an `investigation:` block invalidates every fragment already traced.
- Workaround: ledgers edited directly; pattern instances recorded as tracer counter-search queries (`lines` set, `count` 0); config digest restamped; validated afterwards.

## 6. Seed re-indexes untracked spec artifacts

- Evidence: `--untracked` indexes prior ledgers and reports under `docs/` (1,509 irrelevant nodes in INV-007); a scratch folder written inside the spec folder re-indexed itself (537 self-hits in the first INV-003 run).
- Effect: run time and node count grow with every ledger published.
- Workaround: scratch kept outside the repository; irrelevant nodes dispositioned by path rule.

## 7. `check_sdd_investigations.py` requirements not stated in the to-sdd skill

- Evidence: `skills/afk/to-sdd/scripts/check_sdd_investigations.py:119` globs `INV-{number}-*/COVERAGE.json` (a slug suffix is mandatory); `:44` and `:276-281` require a seam row's cited ledgers to cover `Q1`, `Q2` and `Q3` together; `:150-161` requires a ledger subject to appear as whole words in the row name. `skills/afk/to-sdd/SKILL.md` step 7c states none of the three.
- Effect: four extra investigations (INV-005..008) and one folder rename after the first gate run.
- Workaround: folders renamed; supplementary ledgers run; seam-row names rewritten to carry the symbols.

## 8. `validate_plan.py` parses only a lone `(INV-NNN)` citation

- Evidence: `skills/afk/to-subtasks/scripts/validate_plan.py:249` `INV_RE = r"\(INV-(\d{3,})\)"`; SDD §14 rows cite `(INV-006, INV-002)` (`SDD.md:516-521`), which the SDD gate accepts (`check_sdd_investigations.py` `CITATION.findall`). Check (i) flagged 10 `I-SEAM-UNGROUNDED` for INV-005..008.
- Effect: the two validators disagree on the citation grammar.
- Workaround: each `## Seams` row cites the id its §14 row also cites in lone form (INV-001..004).

## 9. INV-005 reported `partial` through the library call (unconfirmed)

- Evidence: the to-subtasks agent reported `validate_coverage.validate()` computing `partial` for INV-005 ("2 claim ids not recomputable"). The CLI `validate_coverage.py --ledger` on the same file reports `valid · 13/14 classes closed, 1012 nodes, 12 claims`, and `check_sdd_investigations.py` accepted it.
- Effect: none observed; not reproduced.
- Status: unconfirmed.

## 10. `/afk:investigate` and `afk-tracer` absent from the installed plugin

- Evidence: the installed plugin (1.0.18) answers `Unknown skill`; the repository (1.3.0) ships both.
- Effect: every ledger was produced by an agent following `skills/utils/investigate/SKILL.md` by hand, single tracer.
- Workaround: none needed after a plugin refresh per `PROVIDERS.md`.
