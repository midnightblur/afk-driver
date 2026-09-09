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
| `config_warnings` | the declared mechanisms whose pattern matches every occurrence in the repository, so their hits are not about the subject; absent when there are none |
| `verdict` | `closed` · `closed-with-frontier` · `partial` — stamped from the validator's `VERDICT:` line, never by hand |
| `started`, `finished` | ISO-8601 timestamps |

### `boundaries` — one row per class

| Field | Value |
|---|---|
| `class` | `B1`-`B14` |
| `mechanism` | the repository instance's `name`, or `default` |
| `method` | the pattern or the command that enumerated it, or the site read |
| `hits` | how many the method returned — a count, never a list |
| `hit_ids` | the node ids those hits became — every one of them, so the row and the nodes table hold the same set |
| `status` | `closed` · `partial` · `n/a` · `frontier` · `unverified`, plus `judgment-only` at the seed and fragment stage |
| `reason` | required for every status but `closed`; several gaps join with `; ` |
| `universe` | required: what the method searched — paths, file kinds, or another class's hit set |
| `query_ids` | the queries-table ids of the searches behind this row; a class searching another class's hit set points at that class's queries |
| `sites` | the judgment-only sites this class still has to be read at |
| `modules` | B7 only: the parsed module lists, and the manifests that were missing, unsupported, or unparsable |
| `name_forms` | B1 only: every form per subject, each `enumerated` true or false |

`hits` equals `len(hit_ids)`, always: a row carries every hit it found, so the
count and the list are one number, and the nodes table is what both are checked
against. Every id in `hit_ids` is in the nodes table and carries this row's
class, and every searched node of a class is in its row's `hit_ids` — a node no
row counts is a line the answer lost. A class returning more hits than a ledger
can carry as whole nodes (20000) is a subject too generic to answer: the seed
stops and writes nothing rather than publishing a sample, the validator refuses
a row past it, and so does a fold. The ceiling is per class, never a sum. One row per class,
never two.

The query rule, in three parts:

- a row that is `closed` or `partial`, **or** that carries any hits under any
  status, names at least one `query_ids` entry — unless it carries `sites`,
  which says an agent closed it by reading rather than by searching;
- `sites` and `query_ids` are exclusive: a row carrying both claims a read and
  a search for one class, and the reading claim is dropped. A `closed` or
  `partial` row carrying `sites` states a `method` that names the read (it
  begins `read` or `judgment`), and every one of its sites carries at least one
  node under that path whose `query_id` is null, whose `disposition` is
  `traced`, `terminal` or `irrelevant`, and whose `evidence` is non-null. A
  site with no such node leaves the row `judgment-only`, so the verdict is
  `partial`;
- every entry resolves in the queries table;
- a row's `hits` is the number of nodes of its class that a search produced,
  counting only nodes whose `query_id` the row names or a counter-search
  covering the class ran. A node of the class citing any other query is a hit
  the row does not account for, and a defect. A row of 0 hits cites the query
  that found nothing: the absence is the result.

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
| `site` | `path:line`, or `path` alone where the class is the file itself; `line` is a positive integer. A site with no line keys to its path, never to its last segment. The separator is the one git writes, so a site holding a backslash is a defect, in `sites` as in `site` |
| `disposition` | `traced` · `terminal` · `irrelevant` · `frontier` · `unverified` |
| `reason` | required for `frontier` and `unverified` |
| `impact_verdict` | Q3: `breaks` · `unchanged` · `unverified`. Required once the node is dispositioned to anything but `unverified` |
| `coverage_verdict` | Q4: `code` · `test` · `gap`. Same requirement. A run carrying both types carries both fields — one field cannot answer two questions |
| `pinned_by` | the test site that pins this node, or `unguarded`; required on a dispositioned Q3 node |
| `evidence` | the quoted line, or a path to the evidence file |
| `line_hash` | the identity of the matched line — 12 lowercase hex characters, the first 12 characters of the SHA1 digest of the exact bytes of the line, its own line break aside, indentation and inner spacing included — so a node survives an edit above it: two runs are compared on (`class`, file, `line_hash`), never on ids alone. Required wherever `query_id` names a search; a node an agent read has no matched line and omits it |
| `parent` | the node id this one was reached from; `null` for a root. A node another node names as its parent is `traced` — a path the run followed further is not one that ended there |
| `query_id` | the query that produced it, never absent; `null` on a node an agent read rather than searched, which then carries `evidence` instead |

A non-null `query_id` resolves in the queries table, and is a query the
node's own class reached the site through: one the class row names, or one a
counter-search covering the class ran. A node citing any other search is a hit
its class row does not account for.

### `queries` — one row per search

`id` (see "Stable keys") · `command` (the command that ran, written so it runs
again verbatim) · `universe` (what it searched — paths, file kinds) · `count`
(the nodes citing this query) · `lines` (optional integer, zero or more: the
lines the search returned) · `origin` (`seed` · `tracer`) · `evidence` (path to
the raw output when it was kept).

`command`, `universe`, `count` and `origin` are required; `count` is an integer,
zero or more, and is the number of nodes citing this query in this ledger —
two numbers for one search is one of them lying, and the nodes table is the one
a reader can check. Every searched node cites exactly one query. `count` and
`lines` count different things, so they part where one returned line becomes
several nodes — a line two classes each take a node from is one line and two
citations, and `count` runs ahead of `lines`. A pass that wants a narrower and a
wider universe executes both and records both commands; a command a pass
composed in memory is a command nobody can rerun. A pass searching only the
files another class named passes those files to the search as paths, and splits
them across several executed commands where the list is long — each command is
its own row, and a hit cites the one that returned it. `origin` says who ran the search: `seed` for the deterministic
pre-pass, whose queries a later pre-pass runs again, `tracer` for a widening
past it, which it does not. One boundary row never names the same query twice — one execution
counts once — and no two rows in this table share an id.

### `claims` — one row per claim the answer makes

`id` (see "Stable keys"; a counter-search points at it) · `text` · `kind`
(`fact` · `inference` · `unverified`) · `load_bearing` (boolean, never absent:
the reader acts on it) · `supporting_nodes` (node ids; a `fact` names at least
one) · `citations` (`file:line`, or command and exit code). A load-bearing
`fact` **or** `inference` carries at least one citation — an inference names
what it rests on. Every entry of `supporting_nodes` is a node id in the nodes
table; every entry of `citations` is a non-empty string.

### `counter_checks` — one row per counter-search

`method` (the different method used) · `kind` (`deterministic` · `agent`) ·
`targeted_claims` (claim ids; a `complete` row names at least one — a
counter-search aimed at nothing broke nothing) · `new_nodes` (node ids it
discovered; an empty list is the passing result) · `state` (`pending` ·
`complete`) · `reason` (required when `pending`) · `classes` (the boundary
classes this check covers) · `query_ids` (the queries a deterministic method
ran) · `evidence_nodes` (the nodes an agent-driven method read).

Execution rule: `complete` says the method ran, so the row names what ran — a
`deterministic` row names at least one query in the queries table, an `agent`
row a non-empty `classes` and at least one node in the nodes table carrying
evidence, each of a class the row covers. A `complete` row naming neither is a
defect; with the rule in place, an empty `new_nodes` reads as a result rather
than as work nobody did.

Coverage rule: every class whose status is `closed` or `partial` by a search
names at least one `complete` counter-search listing it in `classes`, and that
check's `method` differs from the class's own `method`, and it ran at least one
`command` the class row does not already run — same command under another
universe label is the class's own pass wearing a second name. A class whose
universe **is** another class's hit set is covered by that class's check
listing it.
A class resolved by judgment, closed by parsing rather than searching, or left
`frontier`, `n/a` or `unverified` owes none.

A method that cannot return anything the first pass missed is not a
counter-search: a case-blind rerun of a primary that already ran case-blind, of
expressions holding no literal letter outside a bracket expression, or of a
search that counts 0 by construction — no expression at all, or one quantified
away — is
recorded `pending` with a reason naming the method as not discriminating — never `complete`. A class covered
only by a `pending` row is not a defect; the `pending` row makes the verdict
`partial`. Every run carries at least one `complete` row; Q2, Q3, Q5 and
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

A fragment carries the `run` block of the ledger it folds into, copied verbatim
from what the caller handed it — the fold reads it to prove the fragment answers
the same question over the same subject, and refuses a fragment that leaves it
out. Rows for classes outside `partition.classes` are omitted, not stubbed.

### Stable keys

An ordinal collides the moment two partitions merge, so every key is derived:

- node: `{class}:{file}:{line}`
- claim: `c-<sha1(text)[:8]>`
- query: `q-<sha1(command + universe)[:8]>`

`command` is the invocation written out, in the order it ran: the tool and
its fixed flags, then the run's extra flags, then one `-e <expression>` per
expression in the order the expressions were passed, then `--` and the
pathspecs when there are any. Reordering the expressions is another
invocation and another id; the same tuple always digests to the same id, so
two fragments that ran one search carry one query row.

### Merging

| Table | Rule |
|---|---|
| `run` | `head`, `question`, `type`, `roots`, `aliases` and `config.sha256` must match across fragments; a mismatch aborts the merge naming the field — two snapshots are two investigations. `merged_from` records how many were folded in |
| `nodes` | by node id. Same id, different disposition → `unverified` with reason `conflict: <a> vs <b>`, and the queue reopens for that node. Two rows under one id that disagree on `class`, `site` or `line_hash` are two different sites under one name, and a fold refuses them. Two rows under one id that disagree on any other field they both fill are two answers under one name, and a fold refuses them rather than keeping the first |
| `boundaries` | one row per class: the worst status wins (`unverified` > `judgment-only` > `partial` > `frontier` > `n/a` > `closed`), reasons join with `; `, `hit_ids`, `query_ids` and `universe` union, and `hits` is `len(hit_ids)` after the union — never a sum, which would count a hit both fragments found twice. A union past the ceiling (20000) refuses the fold |
| `claims` | by claim id; the id is the digest of the text, so two rows under one id must carry the same text and a fold refuses them when they do not. `supporting_nodes` and `citations` union, and the worst `kind` wins (`unverified` > `inference` > `fact`); a fold that lowers a kind says so on stderr |
| `queries` | by query id; two rows under one id must agree on `command`, `universe` and `origin`, and a fold refuses them when they do not. `count` and `lines` are not carried across: each records one execution in the ledger holding it, and the fold reads `count` off the folded nodes table |
| `counter_checks` | by (`method`, `classes`): `new_nodes`, `targeted_claims`, `query_ids` and `evidence_nodes` union, and `pending` beats `complete`; any other field the two rows both fill and fill differently refuses the fold |

A fragment accounts for what it searched: every node it carries that a search produced is in the `hit_ids` of a boundary row the fragment itself carries, and its every query's `count` is the fragment's own nodes citing it.

Every fragment is checked against the rules above — every rule but the ones that read on the whole run: its own fields, the fourteen-class sweep, the counter-search coverage and the verdict. A fragment carrying a defect refuses the fold, naming the fragment and the row; nothing is repaired or filled in on its behalf. A fragment names rows the seed left in the staging ledger, so a reference it cannot resolve alone is not its defect.

A fragment's identity is what it found — the bytes of its `partition` and of
the five tables — never its `run` block: one partition traced twice, in two
worktrees or at two times, is one answer and folds once.
A fragment carries `partition.id`, and a fold refuses one that does not: a
fragment nobody can name cannot be reasoned about. Folding the same bytes twice
folds them once; a second, *different* fragment of one partition is a delta and
folds normally, because a re-trace carries nodes the first pass never had. A
fragment carrying a class outside its `partition.classes` is refused.

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
