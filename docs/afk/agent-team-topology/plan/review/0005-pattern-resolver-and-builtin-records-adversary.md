# Adversary report: 0005-pattern-resolver-and-builtin-records

- Verdict: `findings` — probed=278, crit=0 high=0 med=3 low=6
- Target: `cli:C:/Users/mvu/PersonalProjects/afk-driver-agent-teams` (plan decision D-40). Probed a scratch copy of `scripts/team` taken with `git archive HEAD`, through `team.resolver` by import and `scripts/team/resolver.py` on the command line. Host: Windows 11, `afk-python`.
- Diet: contract `## Goal / Scope / Acceptance / Seams / Produces / Context excerpts`, SDD §4 (resolved pattern table), `GLOSSARY.md`, `CONFIG.md`, the shipped files under `scripts/team/patterns/`, `--help`, `inspect.signature` and docstrings. The resolver source, its tests, the branch history and other review files were not read.

## Findings (most severe first)

Repros are pytest-ready Python against `team.resolver`. Shared setup:

```python
from team.resolver import resolve_pattern, ABILITIES
kw = dict(session="adv-s", can_fill=lambda m: True,
          abilities=list(ABILITIES), moderator_model="frontier@claude")
```

### A-1 (medium, spec): a stage-map list writes a source and record version outside the declared contract

- Promise: the resolved pattern file carries a record version that is "empty only for a one-off pattern" and a source that is "one of built-in, saved, one-off" (contract Acceptance, SDD §4 resolved pattern table, `SDD.md:399-401`).
- Repro: `p = resolve_pattern(tmp, "adv-f1", ["debate", "review-panel"], **kw).pattern`
- Expected: `p["source"]` in `{"built-in", "saved", "one-off"}`; `p["record-version"]` is a whole number, since no one-off pattern is involved.
- Actual: `p["source"] == "combined"`, `p["record-version"] is None`. The `sources` list is correct (2 built-in entries, version 1). Any combination of 2 or more names from the command line (`--pattern debate --pattern review-panel`) gives the same result.
- Effect (inferred): a reader that rebuilds the team from this file and trusts the SDD §4 enum gets a value it does not know.

### A-2 (medium, correctness): a pattern with no roles can start a moderator agent with no charter pattern part

- Promise: "A record with no roles, such as BP-1 solo, starts no agent, carries no charter, and the resolver checks no charter part on it" (PRD AC-066). Every pattern that starts agents carries a charter with a pattern part (SDD §4 pattern record, charter rows).
- Repro: `r = resolve_pattern(tmp, "adv-f2", {"name": "adv-noroles", "schema-version": 1, "roles": {}, "edges": [], "steps": [{"name": "d", "roles": [], "debate": True}], "includes": []}, **kw)`
- Expected: refused with `PatternRefused` (a debate step in a pattern that starts no agent), or no agent in the team.
- Actual: success. `r.pattern["team"]["roles"] == ["moderator"]`, and step `d` starts `moderator`. `r.charters["moderator"]` is only the text of `moderator.md`, with no pattern part. The same result comes from a saved record (`saved={"x": {...}}`). A pattern with roles whose debate step lists 0 or 1 roles also resolves, and the added moderator is its only member or one of 2 members.

### A-3 (medium, robustness): a feature identifier with a trailing dot or a case change overwrites another run's resolved pattern

- Promise: the resolved pattern is one per run (SDD §4, "Identity: one per run"); the run keeps one resolved copy in its run directory (PRD AC-004). The resolver refuses unsafe feature identifiers (it refuses `..`, `a/b`, `a\b`, `adv:ads`, an empty name).
- Repro:
  ```python
  resolve_pattern(tmp, "adv-f3", "debate", **kw)
  resolve_pattern(tmp, "adv-f3.", "afk-lite", **kw)   # also "ADV-F3"
  json.load(open(tmp / "adv-f3" / "pattern.json"))["pattern-name"]
  ```
- Expected: the second call is refused as an unsafe identifier, or writes a separate file.
- Actual: both calls succeed. The second returns path `adv-f3.\pattern.json`, but Windows removes the trailing dot, so `adv-f3\pattern.json` now holds `afk-lite`. The run directory has only 1 file. `ADV-F3` overwrites it the same way on the case-insensitive file system. A leading space (`" adv-x"`) is also accepted.

### A-4 (low, spec): a hub that moderates a debate step is not added to the step that it moderates

- Promise: "Every debate has a moderator: the pattern's hub, else one the resolver adds" (PRD AC-036, SDD §6 I15). A step lists the roles it starts (requirement ADR-0020).
- Repro: one-off pattern with roles `h` (`hub: true`), `a`, `b` (both report to `h`), and one step `{"name": "d", "roles": ["a", "b"], "debate": true}`.
- Actual: success. The step is `{"roles": ["a", "b"], "moderator": "h"}`, and no step starts `h`. An added moderator is put into the step's roles (A-2 output). BP-5 is not affected, because its `design` step lists `orchestrator`.
- Effect (inferred, since launch is another subtask): the named moderator is started by no step, so the debate runs with no moderator.

### A-5 (low, robustness): Windows-invalid feature identifiers crash instead of a refusal

- Promise: every refusal exits with code 2 and names its cause (contract Acceptance; SDD §6 I6).
- Repro: `resolver.py --root <tmp> --feature "adv*x" --session s --pattern solo --moderator-model m` (also `adv?x`, `adv|x`, `adv<x`, `nul`, a name with a newline, `adv..`).
- Expected: exit 2 with `unsafe feature identifier ...`, as for `adv:ads`.
- Actual: exit 1 with a raw OS error (`[WinError 123] The filename, directory name, or volume label syntax is incorrect`, or `[Errno 2] No such file or directory` for `nul`). By import the error is `OSError` or `FileNotFoundError`, not `PatternRefused`. No leftover file is created.

### A-6 (low, robustness): an empty root writes the resolved pattern into the current directory

- Promise: `--root` is "the ignored agent directory" (`--help`), and the resolved copy is excluded from version control (PRD AC-004).
- Repro: `resolver.py --root "" --feature adv-empty-root --session s --pattern solo --moderator-model m` from any directory.
- Expected: refused, as an empty `--session` or `--feature` is.
- Actual: exit 0, `{"path": "adv-empty-root\\pattern.json", ...}`. The file is written below the current directory. If that directory is a repository root, the file is not in an ignored path (inferred).

### A-7 (low, spec): a saved pattern with a built-in pattern's name is ignored without a refusal

- Promise: a pattern record's name is unique across built-in and saved patterns (SDD §4 pattern record identity); no silent pattern substitution (ADR-0013).
- Repro: `resolve_pattern(tmp, "adv-f7", "debate", saved={"debate": <valid saved record with role "w">}, **kw)`
- Actual: success with source `built-in` and roles `debater-a`, `debater-b`, `moderator`. The saved record is not used, and no refusal names the clash.
- Note: `CONFIG.md:152-154` says the configuration reader refuses this name before it reaches the resolver, so only an import caller that passes an unchecked map reaches this path (not verified against the reader).

### A-8 (low, robustness): a role listed twice in one step stays listed twice

- Promise: the combined team lists every agent once (PRD AC-033).
- Repro: one-off pattern with roles `a`, `b` and step `{"name": "s", "roles": ["a", "a", "b"]}`.
- Actual: success. The resolved step is `{"roles": ["a", "a", "b"]}`. A role with `count: 2` is the documented way to start 2 agents (`STANDARD.md`, record shape).
- Effect (inferred): a launcher that starts one agent per listed role starts `a` twice.

### A-9 (low, robustness): a usage error and a refusal share exit code 2; a malformed input file exits 1

- Promise: the refusal exit code 2 reaches the team entry script as the sign of a refused pattern (SDD §14 row "Pattern resolver: refuse a pattern with no charter").
- Repro: `resolver.py --root <tmp> --feature f --session s --pattern solo` (no `--moderator-model`) gives exit 2 with an `argparse` usage message. `--one-off <file holding "{not json">` gives exit 1; `--one-off <file holding "[1,2]">` gives exit 2 with `refused: the one-off pattern file must hold one JSON object`.
- Effect (inferred): a caller that reads exit 2 as "pattern refused" also reads a wrong command line as a refusal, and 2 kinds of bad one-off input give 2 exit codes.

## Promises that held

| Promise | Evidence |
|---|---|
| 5 built-in records resolve; BP-1 has no roles and no charters | `solo`, `debate`, `build-verify`, `review-panel`, `afk-lite` all exit 0; `solo` charters `{}` |
| Unknown pattern, unfillable role, missing ability, unfillable moderator refused with exit 2 and the name | `'nope' names no pattern`; `role debater-b cannot be filled (model frontier@codex)`; `needs messaging ability worker-to-worker`; `debate argue: its moderator moderator cannot be filled` |
| Each of the 4 abilities required by every built-in with roles; none by `solo` | 16 runs |
| Unknown record or schema version refused, naming pattern and version | `2, 0, -1, "1", true, 1.0, null, ""` all refused; an included unknown version also refused |
| Charter pattern part or role part absent, null, empty, blank or not text refused for saved and one-off patterns, naming the pattern and the role; tampered built-in charters also refused | 22 runs |
| No charter check on a pattern with no roles | saved and one-off, with and without `charter` |
| Self-include (direct, 2-step, 3-step), pattern reached twice (diamond, repeated include, repeated list name, list name plus its include) refused | 7 runs |
| Included steps follow the includer's, depth first, named `pattern/step`; roles merge by name; 2 definitions of 1 role refused (model or charter difference) | `a[b[d],c]` gives `s1, b/sb, d/sd, c/sc` |
| Edge, step or report target naming an undefined role refused, also across includes; self or looping report target refused | 12 runs |
| Added moderator: name clash refused, charter from `moderator.md`; missing or blank `moderator.md` refused | 4 runs |
| Combined charters: every combined pattern part, includer first, then the role part | `A-PART, debate part, W-PART` |
| 2 implied `message` edges per role, to the report target and back | BP-5: 14 implied edges for 7 roles |
| Resolved file: name, versions, `sources`, flattened team without charter text, `created-at` in UTC to the second, `owning-session`; disk content equals the returned value | `2026-01-01T15:00:30Z` for `10:00:30.9-05:00` |
| One-off pattern: name required, built-in or saved name refused, record version empty, only `pattern.json` written | CLI run with `--saved`; repository `git status` clean |
| Unknown fields (`max-agents`, `spend-limit`, `max-messages`, an edge `limit`) refused | 4 runs |
| Atomic write: a failed replace leaves no temporary file; a refusal creates no run directory and keeps an earlier file | `pattern.json` as a directory; refusal after success |

## Not verified

- An older, known record version read as it is (PRD AC-061): unverified, because version 1 is the only known version (`RECORD_VERSIONS = (1,)`).
- The resolver is never a Stop handler and not a `resolve` subcommand of the configuration reader: unverified, because it is a wiring claim with no runtime surface in this slice.
- Charter content (milestones, the `progress: MILESTONE — SENTENCE` line, no harness or tool named): read in the shipped files and present in every role part and `moderator.md`; no program checks it, by design.

Pointers: contract `docs/afk/agent-team-topology/plan/0005-pattern-resolver-and-builtin-records.md`; resolved-pattern contract `docs/afk/agent-team-topology/SDD.md:394-404`.
