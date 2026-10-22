# Adversary report: 0023-lesson-ledger-lock

Target: hooks/lesson-append.sh, hooks/native-contract-gate.sh and scripts/create-worktree, run from a scratch copy of the branch tree (git archive of HEAD) and from scratch git repositories. LESSON_LEDGER_FILE always pointed at a scratch path. Hosts: Windows Git Bash (GNU stat 8.32; Python 3.12, 3.13, 3.14 pinned by a PATH shim) and a Linux container `python:3.11-slim` (Python 3.11.17, GNU stat 9.7) for the pre-3.12 walker cases. Diet kept: no slice diff, tests, history or review findings read; the lock folder name was observed at run time, not read from source.

ADVERSARY: clean — probed=35
In plain terms: the lesson writer never handed out the same number twice, gave up cleanly when it had to, and the 2 folder walkers kept working while lessons were written, so the change can ship.

## Findings
None.

## Observed (runtime)
| # | Promise (contract `## Acceptance`) | Scenario | Result |
|---|---|---|---|
| 1 | distinct ids | 8 parallel appends | 8 distinct ids, exit 0, stdout = id only, no lock left |
| 2 | distinct ids | 3 waves of 8, folder polled | 24 distinct; lock = `<ledger dir>/lesson-append.lock/` with an `owner` file |
| 3 | distinct ids | 24 parallel, 2 trials | 24 of 24 distinct each, 30.2–31.9 s wall time |
| 4 | distinct ids | 8 parallel on Linux, Python 3.11 | 8 distinct |
| 5 | stale after 10 s | lock 60 s old, dead owner | taken over in 1.5 s, fresh id, lock freed |
| 6 | V17: lock left with no trap stays until stale | fresh lock, no owner alive | taken over at 10.6 s, fresh id |
| 7 | wait at most 30 s; timeout exit 0 + stderr note | lock touched every 1 s | gave up at 30.2 s: exit 0, empty stdout, `lesson-append: gave up after 30 s …; nothing written`, other lock and owner kept |
| 8 | never take over a lock whose age it cannot read | `stat` shim fails both forms, lock 60 s old | tried `-c %Y` then `-f %m` each poll; no takeover; exit 0 at 30.0 s |
| 9 | BSD `stat -f %m` fallback | shim rejects `-c`, answers `-f %m` | lock taken over in 1.3 s |
| 10 | atomic takeover | 8 parallel on one stale lock | 8 distinct, no lock left |
| 11 | atomic takeover | 24 parallel on one stale lock | 22 distinct ids; 2 hit the 30 s cap (see Notes) |
| 12 | trap frees on exit | holder killed (TERM ×3, HUP ×3), 200k-line ledger | 4 killed while holding: lock removed, no partial line |
| 13 | waiter does not free another's lock | waiter killed by TERM, HUP; INT | other lock and owner kept (INT ignored by a background job; ran to the cap) |
| 14 | acquire-or-bail | ledger path under a regular file | exit 0 in 0.5 s, `cannot create ledger dir` |
| 15 | lock path derived from ledger path | lock held on ledger A, append to ledger B | B done in 0.7 s |
| 16 | lock path derived from ledger path | path with spaces, folder missing | folder made, id L-0001 |
| 17 | id step and append under the lock | `applied --id` under a fresh foreign lock | waited 10.6 s, took over, wrote transition line |
| 18 | id step and append under the lock | holder paused (SIGSTOP) inside the lock over 10 s, 18 pause points, Linux | other append took over and minted N; resumed holder minted N+1; 0 duplicates, 0 bad lines |
| 19 | id format and grammar unchanged | ledger past 9999 ids | `L-200001`, `L-1000001`; line fields per LEDGER-FORMAT.md |
| 20 | create-worktree skips the lock folder | held lock in `.claude/lessons/`, Windows | exit 0; ledger copied, lock not copied |
| 21 | V18 create-worktree | 6 runs, 4 looping writers, Windows | 6 of 6 exit 0, lock never copied, 175 distinct ids |
| 22 | V18 create-worktree | 3 runs, 4 writers, Python 3.11 Linux | 3 of 3 exit 0 |
| 23 | V18 create-worktree | 3 runs, writers + churn of a non-lock folder | 2 of 3 exit 0; 1 failed on the non-lock folder (see Notes) |
| 24 | walkers skip the takeover's moved-aside folder `lesson-append.lock.<pid>.<n>.<n>` | leftover folder, static | gate exit 0; create-worktree exit 0, folder not copied |
| 25 | same | 8 create-worktree runs during back-to-back takeovers | 8 of 8 exit 0, only LEDGER.jsonl copied |
| 26 | same | 6 gate runs during back-to-back takeovers | 6 of 6 exit 0, 0 crash lines |
| 27 | V40: changed gate passes check M | gate on its own tree, Windows | exit 0 in 4.6 s |
| 28 | V40 | same, Python 3.11 Linux | exit 0 |
| 29 | V18 gate walk | 5 runs, 4 writers, Python 3.12 | 5 of 5 exit 0 |
| 30 | V18 gate walk | 5 runs, Python 3.13 | 5 of 5 exit 0 |
| 31 | V18 gate walk | 5 runs, Python 3.14 | 5 of 5 exit 0 |
| 32 | V18 gate walk | 15 runs, 4 writers, Python 3.11 | 15 of 15 with 0 crash lines |
| 33 | V18 gate walk | 15 runs, writers + non-lock folder churn, Python 3.11 | 15 of 15 with 0 crash lines |
| 34 | ledger integrity under the walker races | all race ledgers | 176, 1171, 810, 2248, 391 lines; every id distinct |
| 35 | stdout stays silent | every timeout and bail case | stdout empty; only the minted id on success |

Controls (main's `hooks/native-contract-gate.sh` and `scripts/create-worktree`, run unread on the same harness, Python 3.11): main's gate raised a traceback in `pathlib.rglob` → `os.scandir` in 1 of 10 churn runs; main's create-worktree failed twice with `cp: cannot stat '…/lesson-append.lock/owner'` and `ERROR=unexpected failure near line 317`. So the race reaches the window the slice fixes.

## Notes (not findings)
- At 24 appends started together on a stale lock (Windows, about 1.25 s per hold), 2 of 24 hit the 30 s cap and wrote nothing. This follows the stated timeout rule; the SDD measured 8 of 8.
- create-worktree still exits 1 (`near line 317`) when a folder other than the lesson lock vanishes in `.claude/` during the copy (scenario 23). The contract scopes the fix to the lock folder, so this is outside the slice.
- A waiter or holder killed by a signal exits 143 or 129, not 0. The best-effort exit-0 rule covers normal ends only.
- Gate exit 2 in some harness runs came from probe files in the scanned tree (scratch worktrees under `.claude/worktrees/`, a control copy in `hooks/`). Each was re-run clean or judged on crash lines only.
- Not probed: the "no new upper-case setting" bullet (static, no runtime signal); Python 3.8–3.10; Windows with Python before 3.12 (none installed).
