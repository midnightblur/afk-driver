> Language: `LANGUAGE.md` (plugin root).

# Adversary report — 0005-bug-mode

- Verdict: **findings** — 94 scenarios probed; 0 critical, 0 high, 3 medium, 4 low.
- Surface probed (decision D-3, no running app): `publish_bug_mode.py` command line and `run_bug_mode`, through the real `adapters/tracker/jira/api.py` and `adapters/tracker/github-issues/api.py`.
- Fakes: a stateful Jira REST server on `127.0.0.1` (every logged request had a `127.0.0.1:<port>` Host header), and a fake `gh.exe` first on PATH with the GitHub CLI folder removed from PATH (argv and stdin logged). Dummy Jira credentials came from `JIRA_BASE_URL` / `JIRA_EMAIL` / `JIRA_API_TOKEN`; `USERPROFILE` and `HOME` pointed at an empty folder.
- Every run used a throwaway git repository under `<temp>/bt/adv5/repos/` with its own `.afk/config.yaml`. Harness: `<temp>/bt/adv5/lib.py`, `fakegh.py`, scenario scripts `s1_discover.py`..`s17_direct.py`.
- Diet: clean. Read only the contract sections allowed, `BUG-MODE.md`, `SKILL.md`, `DIAGNOSIS-FORMAT.md`, `ADAPTERS.md` "## tracker", `CONFIG.md`, the two adapter `CONTRACT.md` files, D-3, and docstrings and signatures. One traceback from importing the module printed a `@dataclass` line; that is runtime output, not a source read.

## Findings (worst first)

| Id | Severity | Class | Promise broken |
|---|---|---|---|
| A-1 (change link never reaches ticket) | medium | correctness | Acceptance: "When the diagnosis's Outside writes list a change link, the evidence comment carries it" (PRD AC-020) |
| A-2 (other repository's issue key swapped) | medium | correctness | Acceptance: "A given ticket key must be one the tracker returns, else the run is refused with no write" (SDD §3) |
| A-3 (absent in-review label found after writes) | medium | robustness | Acceptance: in-review key "must be configured and match ... else the run is refused with no write" (PRD AC-032) |
| A-4 (prior consent needs no approval) | low | spec | Acceptance: "A tracker write runs only with a person present or under a prior approval that covers ticket writes" (PRD AC-036) |
| A-5 (confirmation asked before the plan) | low | correctness | Acceptance: "The run is dry-run first" (SDD §14); `BUG-MODE.md` "How to run" step 3 |
| A-6 (JQL values not escaped) | low | robustness | Acceptance: fix-version check carried from the old publisher (SDD §14) |
| A-7 (server fault reported as unknown type) | low | robustness | Acceptance: "4xx bodies shown, 5xx retried" (SDD §14) |

### A-1 — a change link listed after the first evidence comment never reaches the ticket

Repro (Jira; GitHub Issues gives the same result):

1. Diagnosis with empty Outside writes. Run `publish_bug_mode.py --diagnosis docs/afk/bug-login-crash/DIAGNOSIS.md --consent person --yes`. The fake creates `adv-1`, the folder moves to `docs/afk/adv-1`, and one evidence comment is posted.
2. Append `- change: https://gitlab.example.invalid/g/p/-/merge_requests/88` to `## Outside writes`.
3. Run `--diagnosis docs/afk/adv-1/DIAGNOSIS.md --consent person --yes --in-review`.

- Actual: exit 0. `STEP: evidence — skipped, listed in Outside writes`, `STEP: in-review — moved`. The ticket has 1 comment, and 0 comments carry the link. The ticket is now in review.
- Expected: a comment that carries the listed change link. For example, a step keyed on the change, so that a re-run after a change is listed still posts it.
- Same result on an existing ticket given by `--key adv-9`, and on GitHub Issues (`issue 100`, 0 of 1 comments carry `pull/12`).
- The link reaches the ticket only when it is listed before the first run (observed in the happy path). Inference: filing the ticket before the fix and moving it to review after the change opens is the normal order, so the link is missed in that order.
- Script: `s14_change_later.py`.

### A-2 — a GitHub key from another repository writes to a different issue

Repro: the configured repository is `example-owner/example-repo`, and issue `#7` there is unrelated. Run `--diagnosis … --consent person --yes --key other-owner/other-repo#7`.

- Actual: exit 0. `STEP: ticket — recorded 7 as the ticket key`. The fake `gh` receives `issue comment 7 --repo example-owner/example-repo`, and the output is `TICKET: 7 https://github.com/example-owner/example-repo/issues/7`. The evidence lands on a different issue than the one named, and the diagnosis records `7`. The dry run shows only `ticket 7 (exists)`.
- Expected: the run is refused with no write, because `other-owner/other-repo#7` is not a ticket of the configured tracker.
- Script: `s16_keycase.py` (`g-key-otherrepo2`).

### A-3 — an absent GitHub in-review label is found only after writes

Repro: `github-issues.state-labels.in-review: "status:in-review"` is configured, but the repository has only the labels `bug` and `enhancement`.

- New ticket: `--diagnosis … --consent person --yes --in-review`. Actual: exit 2. The writes `issue create` (#100), the folder move, and `issue comment 100` succeed. Then `issue edit 100 --add-label status:in-review` fails with `'status:in-review' not found`.
- Existing ticket: add `--key 7`. Actual: exit 2. `issue comment 7` is posted, then the label edit fails.
- Expected: refused before any write, like the type-label check (`REFUSED: type 'enhancement': the label 'enhancement' does not exist in the repository`, observed). The existence of the in-review label can be read before writing in the same way.
- A re-run fails at the same step until a person creates the label.
- Script: `s5_refusals_gh.py` (`g-ir-label-missing`, `g-ir-label-missing-existing`).

### A-4 — `--consent prior` writes with an empty Approval part

Repro: diagnosis with an empty `## Approval`. Run `--diagnosis … --consent prior --yes`.

- Actual: exit 0. `adv-1` is created and the evidence comment is posted.
- Expected per AC-036: refused unless a prior approval covers ticket writes.
- Note: `DIAGNOSIS-FORMAT.md` says of Approval "nothing checks it", and `BUG-MODE.md` makes the flag the caller's statement. The routing may accept this as the design. The script trusts the flag with no evidence on disk.
- Script: `s11_stopped_desc.py` (`c-prior-noapproval`).

### A-5 — the confirmation prompt comes before the plan it refers to

Repro: run `--diagnosis … --consent person` without `--yes` and with `PYTHONUNBUFFERED=1`, then answer `y` on stdin.

- Actual stdout starts with `Run the 2 write step(s) above? [y/N] PLAN: work id bug-login-crash; ticket to be created`. Every `PLAN:` line comes after the question, and the writes run.
- Expected: the plan is printed before the question that asks about it.
- `BUG-MODE.md` step 4 passes `--yes` after a dry run, so the skill's documented path does not reach this prompt.
- Script: `s15_prompt.py`.

### A-6 — preflight JQL interpolates values without escaping

Repro: run `--diagnosis … --consent person --yes --fix-version '1.0" OR project = "X'`.

- Observed request to the fake: `jql = project = "ADV" AND fixVersion = "1.0" OR project = "X"`.
- Expected: the value is escaped inside the JQL string literal.
- Inferred, not verified against real Jira: real Jira parses this as a valid query, so the preflight check can pass for a value that is not a version. A real version name that contains `"` would make the query invalid and get refused. The adapter's own fix-version check before `tracker_create` still blocked the write in an earlier run (`fix version 9.9 does not exist in project ADV … nothing was written`), so no bad write was observed.
- Issue-type names from `jira.issue-types` go into the same kind of clause (`issuetype = "Bug"`).
- Script: `s4_types.py` (`t-fixver-quote`).

### A-7 — a server fault during the preflight type check is reported as an unknown type

Repro: the fake answers 503 to every `POST /rest/api/3/search/jql`. Run `--diagnosis … --consent person --yes`.

- Actual: exit 1, `REFUSED: type 'bug': Jira does not accept issuetype 'Bug': HTTP 503: …`, with no retry. A read timeout gives the same wording (`… TimeoutError: timed out`).
- Expected: a 5xx or network failure is not reported as a refusal of the type. Retry it, or report it as a tracker fault. Nothing is written in either case.
- Script: `s15_prompt.py`, `s8_retry.py` (`x-network-down`).

## Promises that held up

| Promise | Observed (Jira and GitHub Issues unless named) |
|---|---|
| Create from a diagnosis, `TICKET: <key> <link>` | `TICKET: adv-1 http://127.0.0.1:<port>/browse/adv-1`; `TICKET: 100 https://github.com/…/issues/100` |
| Description only on a created ticket | Existing ticket: Jira `PUT` body is only `{"fields":{"fixVersions":[…]}}`; GitHub has no body edit; prose, PRD block and Meeting Summaries unchanged |
| Ticket key set only while empty | Recorded `adv-5` kept; a different `--key adv-6` is listed as `- ticket: adv-6`, and its marker step is `evidence-adv-6` |
| Folder move after create | `git mv` to `docs/afk/adv-1`, work id becomes the key; an existing target folder is left alone with a `NOTE:`; untracked files move with the folder |
| In-review configured and matched | Unconfigured → refused, 0 writes; existing ticket with no match → refused, 0 writes (also in a dry run); match by id `"21"`; already in the state → no write; new ticket with no match → exit 2 after the create, as `BUG-MODE.md` states |
| Fix version | Jira: unknown version → refused, 0 writes; an existing ticket keeps `1.0` and gains `2.0`; GitHub: `--fix-version` refused |
| Type check | Unknown Jira type → refused, 0 writes; a missing GitHub label → refused even when `bugfix` and `debug` exist |
| Consent and confirmation | No `--consent` → refused, 0 writes, no request sent; EOF or `n` at the prompt → refused, 0 writes |
| Evidence comments | Marker line on each comment; change link carried when listed before the run; stopped diagnosis (V-4, V-5) posted as one comment |
| Proof files | Named `{key or work id}-p-n-proof-{name}`; a duplicate name gets `-2`; Jira stored-name mismatch named in the comment and a `NOTE:`; GitHub non-image named as not attached |
| Outside writes and re-run | Full re-run → every step skipped, 0 writes; resume after exit 2 posts only the missing step |
| Read-back before retry, no duplicate | 500 after create, an earlier crashed run, and GitHub 502 after create each give "found by its marker, not created again" (1 ticket); the same for comments, transitions and uploads; description-mode re-run gives 1 ticket |
| 4xx shown, 5xx retried | 400 and 422 bodies shown, 1 attempt; 503 → 3 attempts, then `FAILED`, no later write; `sleep` called with `5` in a direct `run_bug_mode` call |
| Refusals before any write | 16 refusal cases in `s3_refusals_jira.py`, 4 in `s4_types.py` and 8 in `s5_refusals_gh.py`, each with 0 writes on the fake |
| Description-file mode | Create with the description as the body; existing ticket → comment only; empty or blank file → refused |
| Dry run | 0 writes; read-only `POST /search/jql` only |

## Unverified

- unverified: GitHub search lag. Read-back after a failed create uses `gh issue list --search "…" in:body`. The fake indexes at once, but real GitHub search is eventually consistent. A new issue that search cannot yet find could be created twice. Not modelled.
- unverified: real Jira JQL validation of `/search/jql`. The fake returns 400 for an unknown `issuetype` or `fixVersion` value, as the script's docstring expects.
- The worktree `git status` shows 3 untracked files that these probes did not write: `plan/review/0005-bug-mode-3f83acf-r9.{md,findings.json,outcomes.json}`. Only their names were seen, not their content.

Repros are written as stub-tracker cases: fake tracker state, then command, then the requests and state observed. They can move into `scripts/tests/test_publish_bug_mode.py`. That file's conventions were not read (diet).
