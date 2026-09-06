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
arrays of row objects. `scripts/validate_coverage.py` beside this file is the
one checker of everything below.

### `run`

| Field | Value |
|---|---|
| `repository` | the repository root path, or its remote URL when one is configured |
| `head` | the commit sha the investigation ran against |
| `question` | the question as asked |
| `type` | a list of `Q1`-`Q5`; a question matching two types carries both |
| `roots` | the subject symbols the investigation started from |
| `aliases` | every name form, each `enumerated` true or false with its reason |
| `inventory_hash` | sha256 over the tracked-file list |
| `inventory_count` | how many files that list held |
| `design_phase` | `true` when the caller is a design step; drives the counter-search requirement |
| `verdict` | `closed` · `closed-with-frontier` · `partial` — stamped from the validator's `VERDICT:` line, never by hand |
| `started`, `finished` | ISO-8601 timestamps |

### `boundaries` — one row per class

| Field | Value |
|---|---|
| `class` | `B1`-`B14` |
| `mechanism` | the repository instance's `name`, or `default` |
| `method` | the pattern or the command that enumerated it, or the site read |
| `hits` | how many the method returned — a count, never a list |
| `hit_ids` | the node ids those hits became; capped, with `truncated: true` above the cap |
| `status` | `closed` · `partial` · `n/a` · `frontier` · `unverified`, plus `judgment-only` at the seed and fragment stage |
| `reason` | required for every status but `closed` |

Every class B1-B14 carries a row. A class with no enumeration method is
`unverified` with reason `no enumeration method`. `partial` is the status of a
class searched by a method that could not reach all of it — a name form nobody
enumerated, a subset of its sites.

`judgment-only` says a declared site still has to be read. It is a **seed and
fragment status only**: a tracer resolves it to `closed` or `unverified` before
the ledger is published, and the validator rejects it in a published ledger.

### `nodes` — one row per discovered site

| Field | Value |
|---|---|
| `id` | `{class}:{file}:{line}` — the merge key across fragments |
| `class` | the boundary class that found it |
| `site` | `file:line` |
| `disposition` | `traced` · `terminal` · `irrelevant` · `frontier` · `unverified` |
| `reason` | required for `frontier` and `unverified` |
| `verdict` | Q3: `breaks` · `unchanged` · `unverified`. Q4: `code` · `test` · `gap`. Required once the node is dispositioned to anything but `unverified` |
| `pinned_by` | the test site that pins this node, or `unguarded`; required on a dispositioned Q3 node |
| `evidence` | the quoted line, or a path to the evidence file |
| `parent` | the node id this one was reached from; `null` for a root |

### `queries` — one row per search

`command` (the command or pattern run) · `universe` (what it searched — paths,
file kinds) · `count` (hits returned) · `evidence` (path to the raw output when
it was kept).

### `claims` — one row per claim the answer makes

`id` (stable within the run; a counter-search points at it) · `text` · `kind`
(`fact` · `inference` · `unverified`) · `load_bearing` (boolean: the reader acts
on it) · `supporting_nodes` (node ids) · `citations` (`file:line`, or command
and exit code). A load-bearing `fact` **or** `inference` carries at least one
citation — an inference names what it rests on.

### `counter_checks` — one row per counter-search

`method` (the different method used) · `kind` (`deterministic` · `agent`) ·
`targeted_claims` (claim ids) · `new_nodes` (node ids it discovered; an empty
list is the passing result) · `state` (`pending` · `complete`) · `reason`
(required when `pending`).

A method that cannot return anything the first pass missed is not a
counter-search. Every run carries at least one `complete` row; Q2, Q3, Q5 and
design-phase runs additionally carry a `complete` row of kind `agent`
(`INVESTIGATION.md` § "Counter-search"). A `pending` row is legal and makes the
verdict `partial`.

## Verdict

The validator computes it; nothing else does.

- `closed` — every class `closed` or `n/a`, every node dispositioned, no
  frontier, no pending counter-search.
- `closed-with-frontier` — the only remaining gaps are `frontier`.
- `partial` — any `unverified` or `partial` class, any `judgment-only` left,
  any node still `unverified`, any pending counter-search, or any structural
  defect.

## Tracer fragments

A tracer writes one fragment per partition, never the ledger. A fragment is
this same document scoped to its partition, plus:

| Field | Value |
|---|---|
| `partition.id` | the cluster id the caller assigned |
| `partition.classes` | the boundary classes this fragment is answerable for |
| `partition.seed` | path to the slice of the seed map it worked from |

Rows for classes outside `partition.classes` are omitted, not stubbed. Merging
is by key: node `id`, claim `id`, and query order. Same node id from two
fragments with **different** dispositions merges to `unverified` with reason
`conflict: <a> vs <b>`, and reopens the queue for that node.

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
5. the ledger path and its verdict;
6. the `OUTCOME:` line (default grammar, `DELEGATION.md` § "Return contract").
