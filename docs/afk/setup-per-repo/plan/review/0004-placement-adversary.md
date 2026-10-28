# Adversarial gate — 0004-placement

- Date: 2026-10-28 · branch `feat/setup-per-repo` at `320fcf6`
- Target: `scripts/placement.py`, run in-process with `afk-python` (CPython 3.14.8, Windows 11). There is no app (`plan/DECISIONS.md` D-2).
- Diet: contract `plan/0004-placement.md`, its cited PRD and SDD rows, `plan/DECISIONS.md` (D-14, D-16, D-18, D-31 to D-36), the prior report `plan/review/0003-repository-list-adversary.md` (format only), and the public signatures and docstrings of `placement.py`, `repo_list.py` and `afk-config.py` `parse_single_file` (read by `ast`, with no function bodies). I did not read the slice diff, `scripts/tests/`, review findings, or this branch's commits.
- Isolation: each probe set `HOME` and `USERPROFILE` to a fresh folder under `C:/t/adv4/runs/` before the import. A hash snapshot of `C:/Users/mvu/.afk` (16 files) was the same before and after. Every repository was a real `git init`, `git clone` or `git worktree add` under `C:/t/adv4/`. Links were real junctions and symbolic links. The race used separate `afk-python` processes.
- Side effect: the import wrote the ignored bytecode file `scripts/__pycache__/placement.cpython-314.pyc` (`.gitignore` line 2). `git status` shows no other change.
- Linux pass: run in WSL (Python 3.12.3) on a copy of the 4 modules under `/tmp`: 9 scenarios, all pass (case, symbolic links both ways, `~`, R-01, R-04, a far worktree).
- Probe scripts: `C:/t/adv4/p1_root.py` … `C:/t/adv4/p12_x1.py`, `C:/t/adv4/lin.py`, helpers in `C:/t/adv4/h.py`.

## Verdict

`findings` — 219 scenarios probed: 5 findings (0 critical, 0 high, 0 medium, 5 low).

## Findings

### F1 — correctness · low — a folder is matched to the entry by path text when its git repository is a different one

- Promise: SDD §6 invariant "an agent's worktree of a listed repository sits at `<root>/<short name>/<name>`". Acceptance "starts git only for unusual layouts (… a submodule)" with SDD §14 accepted finding "a text-only check there would misjudge the target". PRD AC-055 "A worktree of a repository that is not in the list is not checked".
- Repro A (`C:/t/adv4/p9_cross.py` X1 to X3, `C:/t/adv4/p12_x1.py`):
  1. List `alpha` and `gamma` under one root.
  2. From `gamma`, run `git worktree add <root>/alpha/gamma-stray -b gs` (a developer can do this from a terminal, AC-056).
  3. Call `target_for(<root>/alpha/gamma-stray, 'next')` and `check_target(<root>/gamma/next, <root>/alpha/gamma-stray)`.
  - Expected: the folder belongs to `gamma`, so the target is `<root>/gamma/next`.
  - Actual: `Verdict(state='inside', target='<root>\alpha\next', folder='<root>\alpha')`. The check of `<root>/gamma/next` is refused as `outside <root>\alpha`. No git starts.
  - Same cause: a worktree of an unlisted repository under `<root>/alpha` answers `refused` (`outside <root>\alpha`) for any target outside, instead of `not listed`.
- Repro B (`C:/t/adv4/p5_gitdir.py` D7, D8):
  1. List `alpha`. Add a submodule `sm` to `alpha`, so its git folder is `<alpha>/.git/modules/sm`.
  2. Call `check_target(<root>/alpha/smwt, <alpha>/.git/modules/sm)`. git run there works on the submodule repository.
  - Expected: `not listed` (the submodule is not listed).
  - Actual: `inside`, with `folder='<root>\alpha'`. When the submodule is listed as `smod`, `check_target(<root>/smod/w, <alpha>/.git/modules/sm)` is refused as `outside <root>\alpha`.
- Holds: a submodule working folder, a nested clone in a checkout or in a short-name folder, a far worktree and a `GIT_DIR` variable all start git and get the right entry (p4 L1, L2; p9 X4; p2 T7; p4 G1 to G8).

### F2 — correctness · low — the separate git folder of a listed repository answers "not listed"

- Promise: PRD AC-053 "An agent's `git worktree add` … for a listed repository whose real target is outside `<root>/<short name>` is refused". D-35 counts "a repository git cannot map to a main checkout" as not listed and names 2 cases: a bare repository and a linked worktree of a separate git folder. This repository is listed.
- Repro (`C:/t/adv4/p5_gitdir.py` D1, D2):
  1. `git init --separate-git-dir <run>/sepgit <run>/sepwork`, commit, then `add_repository(<run>/sepwork, root)`.
  2. Call `check_target(<run>/outside_target/w, <run>/sepgit)`.
  - Expected: `refused`, naming `<root>\sepwork`.
  - Actual: `Verdict(state='not listed', folder=None)`. In that folder, `git worktree add -b proof <run>/proof_wt` exits 0, and `git worktree list` in `sepwork` then shows `proof_wt`: a worktree of the listed repository outside the root.
- Holds: the same check from `<run>/sepwork` is refused (D1).

### F3 — robustness · low — a machine-file read during a file swap raises `PlacementError`

- Promise: catalog R R-07 "checked on every read", and SDD §7 row "file swap busy on Windows". The 0003 disposition of F1 retries a refused list read on Windows. The machine-file read does not retry.
- Repro (`C:/t/adv4/p7_race.py`):
  1. Confirm a root, list `alpha`.
  2. Start 3 processes that loop `target_for(<alpha>, 'w')` for 8 s.
  3. In the same 8 s, run 1 process that writes `config.yaml.tmp` and `os.replace`s it over `~/.afk/config.yaml` with the same text, and 1 process that loops `add_repository` and `remove_repository` of another repository.
  - Expected: every call answers `inside` at `<root>\alpha\w`.
  - Actual: 1,136 of 7,024 calls raised `PlacementError: …config.yaml: cannot read it (Permission denied)`. The other 5,888 answered correctly. The list churn (72 cycles) caused no error. The writer made 3,962 swaps.
- Effect (inferred): while setup writes the machine file, the creator exits 3 and the guard denies a correct target. The error type is the documented one, so the caller sees no crash.

### F4 — correctness · low — R-02 does not refuse a root inside a bare repository

- Promise: catalog R R-02 "the root and none of its parents is inside any git repository".
- Repro (`C:/t/adv4/p1_root.py` R02.7, `C:/t/adv4/p11_confirm.py`):
  1. `git init --bare <run>/bare.git`; make `<run>/bare.git/r`.
  2. Set `developer.worktreeRoot: '<run>/bare.git/r'`; call `root_state()`.
  - Expected: `refused`, rule `R-02`, naming `<run>/bare.git`.
  - Actual: `RootState(state='confirmed', source='developer.worktreeRoot', rule=None)`. In that folder, `git rev-parse --is-inside-git-dir --is-bare-repository` prints `true true`.
- Holds: a root in a checkout, at its top, in or under `.git`, in a linked worktree, under a missing subfolder, through a junction, and the suggestion under a home folder that is a repository are all refused with R-02 and the repository name (R02.1 to R02.8; p8 H1).

### F5 — robustness · low — a machine file that is a folder gives the suggestion

- Promise: module docstring "A file or git failure raises `PlacementError`". PRD AC-042 lets agents use the suggestion only "until the developer confirms a root".
- Repro (`C:/t/adv4/p1_root.py` M5):
  1. Make the suggestion folder `~/repo-worktrees`.
  2. Replace `~/.afk/config.yaml` with a folder of that name. Call `root_state()`.
  - Expected: `PlacementError`, as for an unreadable file (p6 IO5) or a broken file (p1 M1 to M3).
  - Actual: `RootState(state='suggested', source='suggestion')`.

## Held up (no finding)

| Promise (contract Acceptance / SDD) | Scenarios | Result |
|---|---|---|
| AC-040, AC-042 suggestion `~/repo-worktrees`: suggested when it exists; refused R-03 "run /afk:setup" when missing | 4 | pass |
| Confirmed root: forward slashes, lower-case drive, trailing separator; `null` reads as absent | 5 | pass |
| AC-043, D-33 old base value: passing gives suggested, source `developer.worktreeBasePath`; failing refuses (R-01, R-03) with no fallback; `worktreeRoot` wins over it, and a failing `worktreeRoot` never falls back | 6 | pass |
| R-01 relative, `~`, `~/x` (also when it exists), `./`, `..\`, `C:x`, `\x`, `/x`, number, bool, map | 13 | pass |
| R-02 (see F4 for the bare case) | 9 | pass except F4 |
| R-03 missing, a file, deleted between 2 calls | 3 | pass |
| R-04 a space warns and stays confirmed (D-32); R-01 and R-03 come before it; the warning rides on `inside` and on an R-06 refusal | 5 | pass |
| R-05 clash with an earlier entry, case clash on Windows, invalid name, device name, `..`; the earlier entry keeps the name (D-34); R-05 before R-06 | 7 | pass |
| R-06 marker for another path, garbage, a folder, unreadable; folder with content; empty and absent folder pass (D-14); marker case and slash variants pass | 12 | pass |
| Root rules come before short-name rules; `check_target` also applies the root rules | 2 | pass |
| R-07 a changed machine file, list and marker each read again | 4 | pass |
| AC-044 `worktreeRoot` and `worktreeBasePath` in the committed file and in `<git dir>/afk/config.yaml` are not read and not opened, also with the current folder in the repository | 4 | pass |
| AC-050, AC-055 `target_for` from main checkout, subfolder, case and slash variants, `.`, worktree under the root, far worktree; unlisted, not git, missing folder give not listed | 10 | pass |
| `target_for` name: `..`, `.`, `../x`, `x/../../y`, absolute, UNC, `NUL` refused as outside; `a/b`, `C:x`, `~`, trailing space or dot land below `<root>/<short name>`, and `check_target` agrees; empty or `None` raise `PlacementError` | 18 | pass |
| `check_target`: inside, nested, the short-name folder itself, the root, sibling and prefix siblings, `..` out and in, the main checkout, case and slash variants, relative made absolute against `folder` (not the current folder), `~` in and out, trailing separator and dot | 24 | pass |
| Links on both sides: junction and symbolic link from inside to outside refused; from outside to inside allowed; root through a junction; folder through a junction; 8.3 short names on both sides | 11 | pass |
| Unusual layouts start git: `GIT_DIR` (absolute, relative, in `os.environ`), `GIT_WORK_TREE`, worktree admin folder, nested clone, submodule working folder, far worktree; ordinary layouts start no git | 17 | pass except F1, F2 |
| Read budget: a listed `check_target` and `target_for` open only the machine file, the list file and the entry's marker (D-31); unlisted opens 2 files; `root_state` opens 1 | 6 | pass |
| Errors: broken, schema 2, folder-shaped list file raise `PlacementError`; no list file gives not listed; unreadable machine file raises `PlacementError` for a listed repository and gives not listed for an unlisted one | 9 | pass |
| Linux (WSL) | 9 | pass |

## Notes (observed, not findings)

- NFR (SDD §10, informational per the contract): median over 10 fresh interpreters, bytecode cache allowed. Plugin modules import in 19.0 ms and `root_state` takes 0.6 ms, so 19.6 ms when the standard library is already loaded. From a bare interpreter the total is 26.2 ms, because the import also loads `subprocess` and `typing` (6.4 ms). A warm `check_target` takes 1.85 ms. A far worktree, where git starts, takes 50.3 ms (SDD §14 accepts this).
- `worktreeRoot: ''` reads as absent and gives the suggestion. The contract does not say if an empty value is "set".
- R-01 and R-02 reasons do not say to run setup; the R-03 reason does. PRD AC-042 says agents "say to run setup". `unverified: the creator and guard word the agent-facing refusal in later slices`.
- A refused `Verdict` still carries a `target`, which can lie outside the root (short name `..` gives `target='<run>\x'`). A caller must read `state` first.
- A target written as `\\localhost\C$\…` for a folder inside `<root>/<short name>` is refused as outside. git accepts it and records the UNC path. The refusal is on the safe side. A `\\?\` target is also refused, and git itself fails on it.
- A malformed machine file (flow syntax, tab indent) raises `PlacementError` naming the file and line. The docstring documents this.

ADVERSARY: findings — probed=219 crit=0 high=0 med=0 low=5 report: docs/afk/setup-per-repo/plan/review/0004-placement-adversary.md
In plain terms: The worktree placement check gave the right answer in almost every layout tried, but in 5 rare setups it names the wrong repository, misses a repository, briefly fails while setup saves its settings, or accepts a bad root folder; none blocks normal use, and each is worth a small fix or a recorded decision.
