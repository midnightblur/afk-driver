# LEDGER-FORMAT.md — the coverage ledger

The one home for the ledger grammar. Completion doctrine — question types,
boundary catalog, dispositions, verdicts, closure — is `INVESTIGATION.md`
(plugin root); this file owns only how the record is written.

## Files and location

One directory per investigation, holding exactly two files:

- `COVERAGE.json` — the complete record. Every table below.
- `REPORT.md` — the short human-readable answer.

Directory: `{spec-dir}/investigations/INV-NNN-slug/` when a spec folder exists,
else `<provider scratch>/investigations/INV-{timestamp}-{slug}/`. `NNN` is a
zero-padded sequence within that `investigations/` directory: the highest
existing number plus one, starting at `001`. `slug` is 2-4 words of the
question, lower case, hyphen-joined.

## COVERAGE.json

One JSON object with six keys. `run` is a single object; the other five are
arrays of row objects.

### `run`

| Field | Value |
|---|---|
| `repository` | the repository root path, or its remote URL when one is configured |
| `head` | the commit sha the investigation ran against |
| `question` | the question as asked |
| `type` | `Q1`-`Q5` |
| `roots` | the subject symbols the investigation started from |
| `aliases` | every name form searched (simple, fully qualified, import alias, wire or serialized) |
| `inventory_hash` | sha256 over the tracked-file list |
| `inventory_count` | how many files that list held |
| `design_phase` | `true` when the caller is a design step; drives the counter-search requirement |
| `started`, `finished` | ISO-8601 timestamps |

### `boundaries` — one row per class

| Field | Value |
|---|---|
| `class` | `B1`-`B14` |
| `mechanism` | the repository instance's `name`, or `default` |
| `method` | the pattern or the command that enumerated it, or the site read |
| `hits` | how many hits the method returned |
| `status` | `closed` · `n/a` · `frontier` · `unverified` |
| `reason` | required for every status but `closed` |

Every class B1-B14 carries a row. A class with no enumeration method is
`unverified` with reason `no enumeration method`.

### `nodes` — one row per discovered site

| Field | Value |
|---|---|
| `id` | stable within the run |
| `class` | the boundary class that found it |
| `site` | `file:line` |
| `disposition` | `traced` · `terminal` · `irrelevant` · `frontier` · `unverified` |
| `verdict` | Q3: `breaks` · `unchanged` · `unverified`. Q4: `code` · `test` · `gap`. Omitted for other types |
| `pinned_by` | the test site that pins this node, or `unguarded` |
| `evidence` | the quoted line, or a path to the evidence file |
| `parent` | the node id this one was reached from; `null` for a root |

### `queries` — one row per search

`command` (the command or pattern run) · `universe` (what it searched — paths,
file kinds) · `count` (hits returned) · `evidence` (path to the raw output when
it was kept).

### `claims` — one row per claim the answer makes

`text` · `kind` (`fact` · `inference` · `unverified`) · `load_bearing` (boolean:
the reader acts on it) · `supporting_nodes` (node ids) · `citations`
(`file:line`, or command and exit code).

### `counter_checks` — one row per counter-search

`method` (the different method used) · `targeted_claims` (claim ids it tried to
break) · `new_nodes` (node ids it discovered; an empty list is the passing
result) · `state` (`pending` · `complete`).

A run whose type requires a counter-search publishes only with every row
`complete` (requirement: `INVESTIGATION.md` § "Counter-search").

## REPORT.md

Read `LANGUAGE.md` (plugin root) §3 before writing it. Body 40 lines or fewer;
the bulk stays in `COVERAGE.json`.

Header line, one line:

```
{repository}@{head} · {closed|closed-with-frontier|partial} · boundaries {n}/{m} · unverified {k} (load-bearing {j}) · ledger: {path}
```

Then: the answer · the site list (never a count) · the frontier list with
reasons · the unverified list with reasons.

## Reply shape

A reply carrying an investigation's result has one fixed shape:

1. the answer;
2. facts (each cited) separated from inferences (each labelled);
3. the `unverified` list, with reasons;
4. the `frontier` list, with reasons;
5. the ledger path;
6. the `OUTCOME:` line (default grammar, `DELEGATION.md` § "Return contract").
