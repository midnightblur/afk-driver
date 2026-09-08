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
| `design_phase` | boolean, never absent: `true` when the caller is a design step; drives the counter-search requirement |
| `config` | the configuration behind the run: `{path, sha256}`, `path` being the repository-relative config file or the literal `defaults` |
| `merged_from` | how many fragments were folded in; absent in an unmerged ledger |
| `verdict` | `closed` · `closed-with-frontier` · `partial` — stamped from the validator's `VERDICT:` line, never by hand |
| `started`, `finished` | ISO-8601 timestamps |

### `boundaries` — one row per class

| Field | Value |
|---|---|
| `class` | `B1`-`B14` |
| `mechanism` | the repository instance's `name`, or `default` |
| `method` | the pattern or the command that enumerated it, or the site read |
| `hits` | how many the method returned — a count, never a list |
| `hit_ids` | the node ids those hits became: the first 200, `truncated: true` above that |
| `truncated` | `true` when `hits` is above the 200-node cap |
| `status` | `closed` · `partial` · `n/a` · `frontier` · `unverified`, plus `judgment-only` at the seed and fragment stage |
| `reason` | required for every status but `closed`; several gaps join with `; ` |
| `universe` | required: what the method searched — paths, file kinds, or another class's hit set |
| `query_ids` | the queries-table ids of the searches behind this row; a class searching another class's hit set points at that class's queries |
| `sites` | the judgment-only sites this class still has to be read at |
| `modules` | B7 only: the parsed module lists, and the manifests that were missing, unsupported, or unparsable |
| `name_forms` | B1 only: every form per subject, each `enumerated` true or false |

`hits` equals `len(hit_ids)` unless `truncated` is true, and then `hits` is
above the cap and `hit_ids` holds exactly the cap. Every id in `hit_ids` is in
the nodes table and carries this row's class. One row per class, never two.

The query rule, in three parts:

- a row that is `closed` or `partial`, **or** that carries any hits under any
  status, names at least one `query_ids` entry — unless it carries `sites`,
  which says an agent closed it by reading rather than by searching;
- every entry resolves in the queries table;
- a row carrying hits cites at least one query that returned something, and the
  counts over its cited queries sum to at least its `hits` — overlap makes the
  sum larger, and nothing makes it smaller. A query of count 0 is the right
  citation for a row of 0 hits: the absence is the result.

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
| `impact_verdict` | Q3: `breaks` · `unchanged` · `unverified`. Required once the node is dispositioned to anything but `unverified` |
| `coverage_verdict` | Q4: `code` · `test` · `gap`. Same requirement. A run carrying both types carries both fields — one field cannot answer two questions |
| `pinned_by` | the test site that pins this node, or `unguarded`; required on a dispositioned Q3 node |
| `evidence` | the quoted line, or a path to the evidence file |
| `parent` | the node id this one was reached from; `null` for a root |
| `query_id` | the query that produced it, never absent; `null` on a node an agent read rather than searched, which then carries `evidence` instead |

### `queries` — one row per search

`id` (see "Stable keys") · `command` (the command or pattern run) · `universe`
(what it searched — paths, file kinds) · `count` (hits returned) · `evidence`
(path to the raw output when it was kept).

### `claims` — one row per claim the answer makes

`id` (see "Stable keys"; a counter-search points at it) · `text` · `kind`
(`fact` · `inference` · `unverified`) · `load_bearing` (boolean, never absent:
the reader acts on it) · `supporting_nodes` (node ids; a `fact` names at least
one) · `citations` (`file:line`, or command and exit code). A load-bearing
`fact` **or** `inference` carries at least one citation — an inference names
what it rests on.

### `counter_checks` — one row per counter-search

`method` (the different method used) · `kind` (`deterministic` · `agent`) ·
`targeted_claims` (claim ids; a `complete` row names at least one — a
counter-search aimed at nothing broke nothing) · `new_nodes` (node ids it
discovered; an empty list is the passing result) · `state` (`pending` ·
`complete`) · `reason` (required when `pending`) · `classes` (the boundary
classes this check covers).

Coverage rule: every class whose status is `closed` or `partial` by a search
names at least one `complete` counter-search listing it in `classes`, and that
check's `method` differs from the class's own `method`. A class whose universe
**is** another class's hit set is covered by that class's check listing it.
A class resolved by judgment, closed by parsing rather than searching, or left
`frontier`, `n/a` or `unverified` owes none.

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
  any node still `unverified`, any node verdict of `unverified`, any pending
  counter-search, or any structural defect.

No table carries a field this file does not define: an undefined key is a field
nobody validates, and the validator refuses it.

## Tracer fragments

A tracer writes one fragment per partition, never the ledger. A fragment is
this same document scoped to its partition, plus:

| Field | Value |
|---|---|
| `partition.id` | the cluster id the caller assigned |
| `partition.classes` | the boundary classes this fragment is answerable for |
| `partition.seed` | path to the slice of the seed map it worked from |

Rows for classes outside `partition.classes` are omitted, not stubbed.

### Stable keys

An ordinal collides the moment two partitions merge, so every key is derived:

- node: `{class}:{file}:{line}`
- claim: `c-<sha1(text)[:8]>`
- query: `q-<sha1(command + universe)[:8]>`

### Merging

| Table | Rule |
|---|---|
| `run` | `head` must match across fragments; a mismatch aborts the merge — two snapshots are two investigations. `merged_from` records how many were folded in |
| `nodes` | by node id. Same id, different disposition → `unverified` with reason `conflict: <a> vs <b>`, and the queue reopens for that node |
| `boundaries` | one row per class: the worst status wins (`unverified` > `judgment-only` > `partial` > `frontier` > `n/a` > `closed`), reasons join with `; `, `hit_ids`, `query_ids` and `universe` union. `hits` is `len(hit_ids)` after the union, except that a row any fragment marked `truncated` sums instead — capped lists cannot be unioned back into a count |
| `claims` | by claim id; the id is the digest of the text, so equal ids are equal claims. `supporting_nodes` and `citations` union |
| `queries` | by query id; duplicates dropped, identical by construction |
| `counter_checks` | by (`method`, `classes`): `new_nodes` and `targeted_claims` union, and `pending` beats `complete` |

Fragment identity is `partition.id` plus `run.head`: the same partition of the
same snapshot folded twice is one fragment, not two.

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
