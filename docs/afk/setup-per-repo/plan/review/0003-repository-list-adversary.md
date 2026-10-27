# Adversarial gate — 0003-repository-list

- Date: 2026-10-27 · branch `feat/setup-per-repo` at `5db975fa`
- Target: `scripts/repo_list.py`, run in-process with `afk-python` (CPython 3.14.8, Windows 11). There is no app (`plan/DECISIONS.md` D-2).
- Diet: contract `plan/0003-repository-list.md`, its cited PRD/SDD rows, `plan/DECISIONS.md`, and the module's public signatures and docstrings (read by `ast`, with no function bodies). I did not read the slice diff, `scripts/tests/`, review findings, or this branch's commits.
- Isolation: each run set `HOME` and `USERPROFILE` to a fresh folder under `C:/t/adv3/runs/`. Before and after, `C:/Users/mvu/.afk` held only `config.yaml` and `data`. All repositories were real `git init`/`git clone` repositories under `C:/t/adv3/`. Concurrency used separate `afk-python` processes.
- Linux pass: not run. `unverified: the protected-branch guard refuses every wsl command (inline and as a script file); I did not route around it.`
- Probe scripts: `C:/t/adv3/p1_add.py` … `C:/t/adv3/p10_misc.py`, helpers in `C:/t/adv3/h.py`.

## Verdict

`findings` — 147 scenarios probed: 4 findings (0 critical, 0 high, 2 medium, 2 low).

## Findings

### F1 — robustness · medium — a read raises a raw `PermissionError` while a writer replaces the list file (Windows)

- Promise: Acceptance "Finding the entry for a path reads only the list file" (PRD AC-080; SDD §8 row "repository list (new)" "find entry for a path"). Module error contract: "A refusal raises `RepositoryListError`; a refused write raises the safe writer's `SafeWriteError`."
- Repro (`C:/t/adv3/p7_reader_race.py`, helpers `reader.py`, `churn.py`):
  1. Add one repository `stable`.
  2. Start 3 processes that loop `find_entry(<stable>/x)` and 1 process that loops `all_entries()`, all for 8 s.
  3. In the same 8 s, run 1 process that loops `add_repository(churn, root)` then `remove_repository('churn', root)`.
- Expected: every read returns the `stable` entry, or a documented error.
- Actual: 582 of 92,381 reads raised `PermissionError: [Errno 13] Permission denied: '...\home\.afk\repositories.json'`. Spread: 461 + 346 + 359 from the `find_entry` processes, 582 from the `all_entries` process. The earlier mixed run `C:/t/adv3/p6_concurrency.py` C4 hit it in 2 of 2 `find_entry` processes.
- Effect: the reader that every session calls fails with an exception type outside the documented set whenever setup writes the list at the same time.

### F2 — spec · medium — an entry whose main checkout folder is gone is not reported missing

- Promise: Acceptance "An entry whose main checkout folder is gone is reported missing and is removed only on an explicit remove call" (PRD AC-006). SDD §7 failure row "main checkout folder gone | path check | reported missing | … | list module". SDD §6 state diagram `Listed --> Missing`.
- Repro (`C:/t/adv3/p4_remove_repoint.py` G1):
  1. `add_repository(<src>/g1, root)`.
  2. Delete the `<src>/g1` folder.
  3. Call `all_entries()` and `find_entry(<src>/g1)`.
- Expected: the result marks the `g1` entry as missing.
- Actual: both calls return `Entry(path='...\src\5\g1', short_name='g1')`. That is the same shape and value as a live entry. `Entry._fields == ('path', 'short_name')`. No call of the SDD §8 interface tells a gone entry from a live one. The only signal is indirect: `repoint_repository` on a live entry refuses with "still exists".
- Holds: the gone entry stays listed through other adds and is removed only by `remove_repository` (G1, R5 pass).

### F3 — robustness · low — an empty or whitespace-only path lists the current folder's repository

- Promise: PRD AC-004 "a folder that is not a git repository … refused, each with its reason". Module docstring: add and repoint resolve the given path. The `root` argument already refuses `''` with "the worktree root is not an absolute path".
- Repro (`C:/t/adv3/p10_misc.py` X2, `C:/t/adv3/p1_add.py` A5-empty-string): set the current folder to any git repository `cwdrepo`, then call `add_repository('', root)`.
- Expected: `RepositoryListError` that names the empty path.
- Actual: returns `Entry(path='...\src\cwdrepo', short_name='cwdrepo')` and writes its marker. `add_repository('   ', root)` and `repoint_repository('gone', '', root)` resolve to the same current folder too: they were refused only because `cwdrepo` was already listed. In the first run the current folder was the plugin worktree, so the real afk-driver main checkout was listed (in the probe HOME only).
- Effect (inferred): if setup passes an empty pasted answer through, it silently lists the repository the session runs in.

### F4 — robustness · low — some bad inputs escape as raw OS errors instead of `RepositoryListError`

- Promise: module error contract (see F1). Acceptance: a bad short name is "refused so setup can ask for another" (PRD catalog R R-05).
- Repros (`C:/t/adv3/p2_names.py`, `p3_markers.py`, `p5_find_schema.py`):

| Call | Actual | Expected |
|---|---|---|
| `add_repository(repo, root, short_name='b'*300)` | `OSError [WinError 123] … syntax is incorrect` (nothing made under the root) | `RepositoryListError`, pick another |
| `add_repository(repo, <path of a plain file>)` | `FileExistsError [WinError 183]` (list unchanged) | `RepositoryListError` that names the root |
| `all_entries()` when `~/.afk/repositories.json` is a folder | `PermissionError [Errno 13]` | `RepositoryListError` |

- Holds: a 255-character short name is accepted and its marker is written.

## Held up (no finding)

| Promise (contract Acceptance / SDD) | Scenarios | Result |
|---|---|---|
| AC-003 add main checkout, subfolder, worktree, worktree subfolder; absolute path, links resolved, no case on Windows | 22 (`p1`), 14 (`p9`: junction, 8.3 short path, submodule, separate git folder, path inside `.git`) | pass |
| AC-004 refuse bare, not git, missing, file, duplicate (same, case, trailing separator, `..`, subfolder, worktree, other short name, through a link) | 15 | pass, each with its reason |
| AC-005 two clones are two entries; default short-name clash refused | 4 | pass |
| AC-007 `schema` 1 file shape; `schema` 2 refused with "update the plugin" on all 5 calls; 0, "1", missing, true, 1.0, bad JSON, bad entries refused; no byte under the checkout (including `.git`) changes | 14 (`p5`), 2 | pass |
| R-05 short-name set, Windows device names and trailing dot (D-17), unicode letters and digits, case clash on Windows, invalid default name | 33 | pass except F4 |
| SDD §7 run stopped after marker: next add reuses the marker (mtime unchanged); orphan marker blocks another path | 2 | pass |
| R-06 foreign, garbage, empty, folder-shaped marker refused; non-empty folder refused; empty folder claimed (D-14); marker case variant accepted | 9 | pass |
| SDD §4 remove: folder deleted when only the marker is left; marker kept with a worktree or a file; unknown, twice, bad name refused; case-insensitive on Windows; D-19 left marker deleted by a later remove | 9 | pass |
| US 4 repoint: gone entry gets new path and marker; live entry, listed path (also case variant), bare, unknown refused; worktree path stored as main checkout | 7 | pass |
| AC-080 `find_entry` by text: subfolder, missing subfolder, sibling-prefix `foo`/`foobar`, case, slashes, relative path, nested repository returns innermost, `<root>/<shortName>` worktree with `root` only (D-16), works with no git on `PATH`, ignores markers, no list file creates nothing | 18 | pass |
| SDD §6/§7 single lock: 10 parallel distinct adds keep all 10; 8 parallel adds of one repository give 1 ok + 7 refused; 6 repositories racing for one short name give 1 winner whose path the marker holds; mixed add/remove storm keeps every entry; remove vs re-add on one short name: 0 of 30,227 stable snapshots show an entry without its marker | 6 | pass except F1 |
| No lock file under the root | watcher over 3 waves | pass (see notes) |

## Notes (observed, not findings)

- Short-name folders briefly hold safe-writer temp files `..afk-repository.<hex>.tmp` during a marker write. These files are not lock files, and none were left behind. D-13 accepts the safe writer's temp file.
- Under heavy contention, writers failed with `SafeWriteError` "file swap stayed busy" (3 times) and "is locked" (1 time). SDD §7 rows "file swap busy on Windows" and "lock held past 2000 ms" specify this.
- An empty list file reads as an empty list, and the next add overwrites it. A hand-edited list with two equal entries is read without complaint. Only a hand edit makes either state.
- A root inside a repository puts the marker in that repository's working tree (`?? wroot/m11/.afk-repository`). Placement's root rules own this (SDD §7 "root fails a rule"), not this slice.

ADVERSARY: findings — probed=147 crit=0 high=0 med=2 low=2 report: docs/afk/setup-per-repo/plan/review/0003-repository-list-adversary.md
In plain terms: The repository list keeps its data safe under every race tried, but on Windows a lookup can crash while setup saves the list, a repository whose folder was deleted looks the same as a live one, and two kinds of bad input get through without a clear refusal; fix the first two before shipping.
