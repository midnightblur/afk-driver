# Adversary report — 0004-knowledge-store

- Date: 2026-10-19
- Target: `cli:C:/Users/mvu/PersonalProjects/afk-driver-agent-teams` (plan decision D-40), commit `c4df4b7`, module `scripts/team/knowledge.py` imported as `team.knowledge` from a `git archive` scratch copy.
- Host: Windows 11, NTFS, `afk-python`. WSL not run.
- Diet: contract `## Goal / Scope / Acceptance / Seams / Produces / Context excerpts`, SDD §4 knowledge-store entry table, `GLOSSARY.md`, D-40, `inspect.signature` and `help()`. No source, tests, diff, branch history or review files read.
- Verdict: **findings** — 161 scenarios probed; 2 medium, 5 low.

## Findings (most severe first)

| ID | Severity | Class | Promise broken | Gist |
|----|----------|-------|----------------|------|
| A-1 | medium | correctness | AC-016; SDD §4 identity "author and time together" | Authors that differ only in letter case share one entry file on Windows |
| A-2 | medium | robustness | AC-016; SDD §6 K1 to K2 | The finished stamp fails with a raw `PermissionError` when another process holds the entry file open for about 2 s |
| A-3 | low | correctness | SDD §4 "keyed by feature" | Feature ids that differ in case or a trailing dot share one store on Windows |
| A-4 | low | robustness | `help(team.knowledge.KnowledgeError)`: "an unsafe name" | Some names that Windows refuses raise a raw `OSError`, not `KnowledgeError` |
| A-5 | low | spec | AC-016 "a verdict always carries its reason"; AC-018 | Text of only spaces counts as a present reason, author, role, model, ground or stage |
| A-6 | low | spec | AC-017 "across stages, a later stage reads earlier stages' finished entries" | A later-stage read with no debater map hides finished debate drafts, but returns the revision and verdicts of the same work item |
| A-7 | low | spec | Acceptance "the store's location is excluded from version control"; AC-019 | The module writes under any root it gets; an entry under a tracked folder shows in `git status` |

### A-1 — case-insensitive author identity (medium, correctness)

The entry file name carries the author. NTFS ignores letter case, so `Adv-Alice` and `adv-alice` at one time map to one file. The second author's write is refused as a duplicate. The stamp call for `adv-alice` marks the entry of `Adv-Alice` finished and returns that other author's entry.

Repro:

```python
from team import knowledge as k
T = "2026-10-19T10:00:00Z"
k.write_entry(R, "adv-feat", author="Adv-Alice", role="r", model="m", ground="g", stage="plan", body="from Alice", time=T)
k.write_entry(R, "adv-feat", author="adv-alice", role="r", model="m", ground="g", stage="plan", body="from alice", time=T)
# actual: KnowledgeError "an entry by adv-alice at 2026-10-19T10:00:00Z already exists"; expected: a second entry
k.mark_finished(R, "adv-feat", "adv-alice", T)
# actual: returns {"author": "Adv-Alice", ..., "finished": true}; expected: KnowledgeError, no entry by adv-alice
```

Consequence: one agent's clean exit can stamp a different agent's entry, so an entry from an agent that ended early can become readable.

### A-2 — stamp lost when the entry file is held open (medium, robustness)

`mark_finished` retries for about 2 s, then raises `PermissionError [WinError 5]` from the rename of its temporary file. The entry stays unfinished, and nothing repairs it (SDD §6 K1). In a debate, the release rule then never fires for that work item. The temporary file is removed; the store holds only the original entry.

Repro (one process holds the file; another stamps it):

```python
# process 1
f = open(k.store_path(R, "adv-feat") / "20261019T100000Z-adv-held.json", "rb"); time.sleep(3)
# process 2, after process 1 opened the file
k.mark_finished(R, "adv-feat", "adv-held", "2026-10-19T10:00:00Z")
# actual: PermissionError [WinError 5] after 2.11 s; the file keeps "finished": false
# expected: the stamp lands, or a KnowledgeError that names the held file
```

Measured window: a hold of 1.0 s or 1.8 s succeeds; a hold of 3 s or 30 s fails at 2.1 s. A virus scanner or file indexer can hold a file this long (inferred, not measured on this host).

### A-3 — feature key collapses on Windows (low, correctness)

`store_path(R, "adv-f1.")` names folder `adv-f1.`, which Windows opens as `adv-f1`. Case is ignored as well.

Repro:

```python
k.write_entry(R, "adv-f1", author="adv-x", role="r", model="m", ground="g", stage="plan", body="feature f1 secret", time=T)
k.mark_finished(R, "adv-f1", "adv-x", T)
k.read_finished(R, "adv-f1.", ["plan"])   # actual: [adv-x "feature f1 secret"]; expected: []
k.read_finished(R, "ADV-F1", ["plan"])    # actual: [adv-x "feature f1 secret"]; expected: []
k.write_entry(R, "adv-f1.", author="adv-x", ..., time=T)  # actual: KnowledgeError "already exists"
```

### A-4 — raw `OSError` for some unsafe names (low, robustness)

Path separators, `.`, `..`, `:` and a NUL character raise `KnowledgeError`. Other names Windows refuses raise `OSError [Errno 22]` or `[WinError 123]`. No partial file is left.

| Input | Actual |
|-------|--------|
| `author="adv*"`, `"adv?"`, `"adv\n"` | `OSError [Errno 22] Invalid argument` |
| `author="a"*300` | `OSError [Errno 22] Invalid argument` |
| `feature="a"*300` | `OSError [WinError 123]` |

Expected: `KnowledgeError`, which `help()` documents for "an unsafe name". A caller that catches only `KnowledgeError` crashes.

### A-5 — text of only spaces counts as present (low, spec)

`reason=""` on a verdict entry is refused, but `reason="   "` is accepted. The same holds for `author`, `role`, `model`, `ground` and `stage`: `""` is refused, `"   "` is stored.

Repro:

```python
k.write_entry(R, "adv-feat", author="adv-a1", role="critic-a", model="m", ground="g:1", stage="review", body="v",
              time="2026-10-19T10:20:02Z", work_item="W1", debate_step="verdict", verdict="AGREE", reason="   ")
# actual: entry stored with reason "   "; expected: KnowledgeError "a verdict entry must carry its reason"
```

### A-6 — later stage cannot read earlier debate drafts without the debater map (low, spec)

All entries below are finished, stage `review`, work item `W1`, roles `critic-a` and `critic-b`.

```python
k.read_finished(R, "adv-feat", ["build", "review"])
# actual: adv-a revision, adv-a verdict, adv-b verdict, adv-p plain note — both drafts missing
k.read_finished(R, "adv-feat", ["build", "review"], {"W1": ["critic-a", "critic-b"]})
# actual: both drafts, revision, both verdicts, plain note
```

`help(read_finished)` documents this: "a draft whose item is not in `debaters` is withheld". The finding is the gap against AC-017: a later-stage reader must know the debater roles of every earlier work item to read earlier finished drafts. It is a `spec` class finding because the right behaviour depends on the reading of AC-017.

### A-7 — the module does not keep the store out of version control (low, spec)

```python
# R = <fresh git repo>/agentdir, not ignored
k.write_entry(R, "adv-feat", author="adv-g", role="r", model="m", ground="g", stage="plan", body="b", time=T)
# git status --porcelain: ?? agentdir/adv-feat/knowledge/20261019T100000Z-adv-g.json
```

`help(team.knowledge)` puts the store "under the caller's ignored agent directory `root`". The module neither picks that folder nor checks it. If the caller owns this promise, the Acceptance bullet is out of this slice's reach; the contract names no caller that owns it (unverified: no later subtask contract was read).

## Promises that held

| Promise | Scenarios | Result |
|---------|-----------|--------|
| AC-018 fields, UTC ISO 8601 to the second (`write_entry`, default time) | 1 happy, 17 time forms | Default time is UTC with `Z`. Offsets, fractions, missing `Z`, lower case, impossible dates, numbers all refused |
| AC-016 created unfinished; stamp is idempotent; unknown entry refused | 6 | Held |
| AC-016 / AC-007 verdict rules | 13 invalid, 2 valid | Missing or empty reason, wrong verdict value, verdict on a non-verdict step, half-set debate fields all refused. Two verdicts read back as two entries; no combined verdict |
| AC-017 per-stage filter | 7 | Unfinished entries hidden; unlisted stage hidden; earlier stage readable when listed; `stages` given as one text or `None` refused |
| AC-017 / SDD §7 release rule | 12 | No draft released while one role has no finished draft. A replacement's finished draft fills the role; the dead debater's unfinished draft is skipped. An empty role list releases nothing |
| SDD §4 foreign file rule | 24 | Unknown format version, missing version, malformed JSON, empty file, non-object, bad field, file name that does not match content, stray file and folder: all skipped, reported once on stderr, never changed |
| Path safety | 13 | `..`, `/`, `\`, `:`, NUL, `.` refused for author and feature |
| ADR-0018 no promotion | public names | Public surface is `write_entry`, `mark_finished`, `read_finished`, `store_path`; no export or copy function |
| Concurrency: 8 writers × 150 entries + 3 readers, 25 s | 1 | 1200 entries, 0 errors, 0 reads that lost an entry seen before, no temporary file left |
| Concurrency: 12 processes write one identity at once, 5 trials | 1 | Exactly 1 success per trial; 11 refusals; file body is the winner's |
| Concurrency: 8 processes stamp one entry 50 times + 2 readers | 1 | 0 errors; entry finished |
| Concurrency: 40 work items stamped role by role + 4 readers, 2850 reads | 1 | 0 partial releases, 0 unfinished drafts returned |

## Limits

- `mark_finished` takes the author as an argument; any process can stamp any author's entry. The module has no caller identity, so "only the author" rests on the caller (unverified: no caller exists in this slice).
- A JSON format version of `1.0` reads as version 1. SDD §4 says the version is an integer. Not raised as a finding: no harm observed.
- WSL and POSIX file systems not probed; A-1, A-2 and A-3 are Windows behaviours.
