probed=174 scenarios crit=0 high=0 med=4 low=8

# Adversary report: 0007-ship-script at c4032334

Verdict: findings, medium and low only, so the gate treats them as advice and the slice proceeds.

Method: `ship.run_ship_step` imported in-process with a fake `ship.Forge` subclass and fake `Tools` fields. Each scenario got its own bare remote, clone and Diagnosis branch in a temp sandbox; each diagnosis passed `check_diagnosis.py`. The command line ran through `ship.main` and as a subprocess. The GitLab adapter ran through `hooks/lib/adapter.sh` with a POSIX `glab` stub first on PATH. After each step the prober read the remote refs, the fake forge's calls and the Outside writes. The worktree's `git status`, `git worktree list` and `git branch` were unchanged afterwards.

## Held up

- **open**: a clean run and a skipped re-run left one change. A create that failed before or after taking effect was read back, so no duplicate opened. Three failed creates gave `blocked`. An existing open change was reused. Several changes on one branch or a lookup error gave `blocked` with no write. A rejected, diverged or racing fix-branch push gave `blocked` and was never forced. A protected fix branch, an empty id, the wrong checked-out branch and a diagnosis with no Outside writes part were refused. CRLF diagnoses and earlier bug-mode entries kept every entry in order.
- **proof**: one comment with P-1, P-2, the evidence link and its marker; a re-run was skipped; a lost entry was read back by marker. A missing evidence link, a missing P-2, missing files and a P-3 were refused before any write. After land the comment went on the feature branch's open change; with none it answered `no-change`.
- **ready**: every `ci-wait` outcome other than success kept the change Draft, also when the exit code and the body disagreed. `mrReviewer: none` added no reviewer. A merged or closed change gave `blocked`.
- **land**: a fast-forward push set the upstream and listed `push:`; a re-run was skipped; a lost entry read back as found. A moved tip gave `not-fast-forward`, exit 2, nothing forced. A protected target and the repository's base branch (tool, `AFK_CONFIG`, committed config, `auto` with main, master, a remote default, or no origin/HEAD) were refused. A missing, unknown or ahead-of-HEAD Base commit was refused.
- **Command line**: refused exits 1; done, skipped, draft and no-change exit 0; not-fast-forward and blocked exit 2; each prints one JSON object.
- **GitLab change-reviewers**: sends `+name` per name in every input shape; empty `reviewers` errors with no `glab` call.

## Findings

| id | severity | class | promise broken (citation) | reproduction | observed versus expected |
|---|---|---|---|---|---|
| A1 | medium | correctness | ship.py docstring "Refused too when HEAD has no commit past the Base commit"; DIAGNOSIS-FORMAT.md:5 the diagnosis is "committed with the failing test on the diagnosis branch"; ADR-0006 | Base `feature/x@tip`; the Diagnosis branch holds only the diagnosis and failing-test commit; land | Observed: `done, how: pushed`; the remote feature branch holds the failing test with no fix. Expected: the no-fix refusal fires. In the documented flow the diagnosis commit is always past Base, so the D-51 range check never refuses. |
| A2 | medium | authz | SDD §5 "Changes \| one per bug \| … lookup … by recorded number after" | `change:` entry names !2, whose source branch is not the Diagnosis branch; green CI; `mrReviewer=bob`; ready | Observed: `change-ready` and `change-reviewers` act on !2. Expected (inferred): refuse a recorded change that is not from the Diagnosis branch. |
| A3 | medium | correctness | Acceptance "opens one Draft change"; docstring "open one Draft change onto the Base branch unless the lookup found one" | the branch already has an open non-Draft change into `release`; Base is main; open, then ready | Observed: open lists that change; ready answers `skipped` "already ready"; no change into main opens. Expected: the lookup accepts only a change into Base. |
| A4 | medium | spec | SDD §4 Proof row "credentials removed by the shared redaction rules" | P-1 holds a private token, a bearer header and a password; proof | Observed: the comment carries all three verbatim. Expected: credentials removed. unverified: whether redaction belongs to the writer of the proof files. |
| A5 | low | robustness | docstring exit codes | `ship.py bogus D`, empty step, `OPEN`, `--proof P-1` with no path | Observed: argparse exit 2, empty stdout. Expected: exit 1 with refused JSON. |
| A6 | low | robustness | docstring "blocked (… re-run the step, which reads back first)" | change-reviewers fails, then re-run ready | Observed: re-run `skipped` "reviewers are not read back"; reviewer never added. |
| A7 | low | spec | Acceptance "no CI (exit 3 at once)" | stub `glab mr view` with no head pipeline; `ci-wait` | Observed: polls until budget, then `unreadable`. unverified: real `glab` answer for a head with no pipeline. |
| A8 | low | robustness | SDD §5 "refuses an empty id" | `change-reviewers {"id":"","reviewers":"bob"}` | Observed: `glab mr update "" --reviewer +bob`, ok. Ship refuses empty ids first, so ship cannot reach it. |
| A9 | low | robustness | docstring: empty change id refused | listed link `…/merge_requests/12/diffs` | Observed: refused "empty change id" though id 12 is present; wrong reason, no write. |
| A10 | low | spec | SDD §3 /afk:fix: a feature-branch diagnosis ends with "no ticket, no change"; ADR-0006 | Base `feature/x`; open | Observed: a Draft change opens into the feature branch. Expected (inferred): open refuses a feature-branch Base. |
| A11 | low | correctness | Acceptance "a re-run opens no duplicate change" | the only change on the branch is merged; no `change:` entry; open | Observed: a second Draft change opens. |
| A12 | low | robustness | docstring refused versus blocked | Base written `refs/heads/main` | Observed: `blocked`, exit 2. Expected: refused, exit 1. Nothing pushed. |
