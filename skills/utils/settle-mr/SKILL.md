---
name: settle-mr
description: Review a GitLab MR and settle it through the review settle loop, using the MR itself as the ledger. Use when the user drops an MR URL/IID for review, wants an MR made ready, or asks to re-check one after fixes landed. Outside the AFK chain; explanatory tours go to /afk:understand.
---

> **Language:** read `LANGUAGE.md` (plugin root) first — it binds every word this skill produces.

# settle-mr — review a GitLab MR until it settles

Reviews an MR of the current repo against a real checkout of its head and settles it through the settle loop (`skills/afk/review/SETTLEMENT.md`) — this skill is the loop's **referee**, and **the MR is the ledger**: findings live as inline discussions, every fix, dispute, and adjudication verdict is a reply on its finding's thread, and a managed summary comment carries the round accounting. Any later session — or another dev — resumes from the MR alone; local files are scratch, never load-bearing.

Two modes:

- **Settle (default)** — reviewer subagents find → findings post inline → fixer subagents fix or dispute, each reading its finding from the MR thread → commit + push per round → repeat until nothing actionable remains — never merging (full never-list: Hard rules).
- **Review-only** — post findings and stop. Each later invocation is one more settle round, paced by the MR author: new commits are the round's delta, thread replies are the fix claims and disputes.

Mode resolution: explicit flag wins; otherwise **settle** when the authenticated `glab` user is the MR author and the MR isn't cross-fork, **review-only** otherwise — announce which mode ran and why. `--settle` on someone else's MR pushes to their branch: stop and get the human's go-ahead first.

## Argument

MR URL or bare IID. Optional:

- `--settle` / `--review-only` — force the mode (resolution above).
- `--skip-build` — skip Phase 2 except the orphan hunt. A **draft** MR implies it.
- `--only <concerns>` / `--skip <concerns>` — narrow the roster (overrides triggers).

## Constants

- `MAIN` = the invoking checkout's root — run from the target repo's main checkout, never from inside an MR worktree. Checklists and plugin files are read from `MAIN`; code under review from the worktree (`WT`).
- Scratch (fetched MR data, `spec.md`, diff files, per-round report drafts): provider scratch directory (`CAPABILITIES.md`), else a session-temp `mr-<iid>` directory.

## The MR as ledger

- **One inline discussion per finding**, body carrying its id (`r-NNN`), finding/why/fix, evidence in a `<details>`, and a trailing AI-review attribution line.
- **Thread replies** record the rest: `Fixed — <what> (<short-sha>)`, dispute rationales, adjudication verdicts. `fixed` and `settled` threads get **resolved**; open findings stay unresolved.
- **Summary comment** — one managed note, first line sentinel `<!-- afk:settle-mr:summary -->`, upserted every round (find by sentinel, `PUT` the note; `POST` when absent): round number, reviewed head, `REVIEW:` verdict line, fixed/settled/open counts. This is the referee's durable accounting — the next round's `--base` and the SETTLEMENT round cap read from here.
- **Ledger reconstruction** (any invocation): fetch the summary comment + discussions (`glab api "projects/:id/merge_requests/<iid>/discussions?per_page=100"`, paginate); settle-mr threads are identified by the attribution line. Unresolved = the open set; resolved via an accepted dispute = the settled set for SETTLEMENT step 2's filter.
- **Information diet** (SETTLEMENT's hard rule) applied here: reviewer and adjudicator prompts never contain the summary comment, the round count, or thread contents beyond what SETTLEMENT step 5 grants the adjudicator; fixers read their own finding's thread — the implementor side may see its dispute history, never the round accounting.

## Shared machinery (the DRY seam)

The reviewer machinery is one-home in `skills/afk/review/SKILL.md` — run its "Concerns (11)", "Trigger activation", "Delta-round roster", "Checklists", "Findings contract", "Verify pass", severity rubric, and verdict table exactly, with this substitution map for its plan-anchored inputs:

| review SKILL.md input | here |
|---|---|
| slice / feature diff | round 1: `mr.diff`; round n≥2: the delta since the summary comment's reviewed head, full MR diff as the context-only sibling (its "Delta rounds" + delta roster apply) |
| subtask contract + parent PRD/SDD | `spec.md` (Phase 0) |
| CLAUDE.md chain | unchanged — walked from `$WT` |
| artifact dir `plan/review/` | the MR: findings post inline, accounting in the summary comment; no `INDEX.md` rollup, no outcomes files. `pattern-debt` findings post as regular (non-blocking) threads, noted as such |
| mutation probe | never runs — CI owns test execution; the summary comment notes "no signal" |

`scope-and-impact` runs without `## Scope` globs: stray churn + blast radius only. Reviewer prompts: `PRECEDENCE.md` + checklist pasted verbatim from `MAIN`, spawn per `DELEGATION.md` (plugin root).

The loop protocol — round structure, fix-or-dispute, dispute adjudication, termination — is SETTLEMENT.md's. The caller-side pieces it leaves to this skill:

- **Review pass** — the fan-out above; `$WT` stays checked out across rounds.
- **Fix routing (settle mode)** — every class fixes inline in `$WT`: one fixer subagent per finding, spawned as `afk-implementor` (it writes product code against the finding's brief — `DELEGATION.md` named types; parallel when files don't overlap), briefed with its finding's **discussion id** — it reads the finding and thread from the MR — plus `$WT`, `spec.md`, and the CLAUDE.md-chain paths. It fixes, or returns an evidence-cited dispute rationale (the implementor side of SETTLEMENT step 4), which the referee posts as the thread reply before adjudicating. Adjudicators (SETTLEMENT step 5) are briefed with the discussion id (the thread carries finding + rationale) plus the diff and spec/CLAUDE.md paths. `scope` findings fix by reverting the stray churn. A fixer whose fix adds or modifies a test self-applies the `test-veracity` checklist and the nearest `TESTING.md` antipattern list to the code it adds before returning — the fix is next round's delta and will be reviewed at that bar. Unfixable within the MR's stated intent → thread stays open, named in the summary as deferred.
- **Cheap re-verification per round (settle mode)** — reactor compile of fix-touched modules + the tests covering the fixed code + the Phase-2 checks whose file set the fixes touched. CI runs on each round's push — the loop never waits on it; a red pipeline is the author's signal, not a round gate.
- **Commit/push (settle mode)** — one commit per round in `$WT` (`review r{n}: <what>`), pushed at round close: inline anchors only exist on pushed heads, so posting round n+1's findings requires round n's fixes on the remote. Agent-driven commits run the commit-time code gates (`hooks/precommit-gates.sh`), so a round touching `.java` commits in minutes, not seconds: invoke `git commit` with an explicit **600000 ms tool timeout** — a commit dying on the default timeout is not a signal to retry with `--no-verify`. After the push, post the `Fixed — … (<short-sha>)` replies and resolve those threads.
- **Settled / stalemate** — update the summary comment and end with the terminal `SETTLE:` line (Verdict below); no park states.

## Phase 0 — fetch MR + spec

1. `glab api "projects/:id/merge_requests/<iid>"` (run in `MAIN`; `glab` fills `:id` from the repo) → title, description, author, draft flag, `diff_refs` (base/start/head_sha), source/target branch. Save as `mr.json`.
2. Raw diff: `glab api "projects/:id/merge_requests/<iid>/raw_diffs"` (fallback: `git diff base_sha...head_sha` after Phase 1) → `mr.diff`.
3. Spec: extract the tracker key from title/source branch (`[A-Z][A-Z0-9]+-\d+`); `jira_get` with full fields (summary, description, comments) → digest acceptance criteria into `spec.md`. No key → **no-spec mode**: the MR description is the only intent statement; `spec-fidelity` reviews scope-creep + description-vs-diff instead of acceptance bullets.

## Phase 1 — checkout the MR head

Never review from diff text alone — reviewers must navigate real MR-head code (new files exist, modified files post-MR, surrounding/similar code greppable).

```bash
git -C "$MAIN" fetch origin "merge-requests/<iid>/head:review/mr-<iid>"
"$MAIN/tools/payable/ai-agents/plugins/workflow/skills/afk/bug/scripts/create-worktree" --branch "review/mr-<iid>" --dir "mr-<iid>-review" --no-npm --no-open
```

`WORKTREE_PATH` from the last line = `WT`. The fetch-into-local-branch works for cross-fork MRs too (the MR ref always exists on origin). Verify `git -C "$WT" rev-parse HEAD` == `diff_refs.head_sha`; if the MR moved since Phase 0, re-fetch `mr.json` + `mr.diff` so anchors match. Settle mode additionally sets the worktree branch to track the MR's **source branch**, the push target.

Changed-module list (drives Phase 2 and triggers): `git -C "$WT" diff --name-only <base_sha>...HEAD`, mapped to `NNNNN-x/module` via `sed -nE 's|^([0-9]+-[^/]+/[^/]+)/src/.*|\1|p' | sort -u`.

## Phase 2 — local gates (only what CI does NOT catch)

No double work with the MR pipeline: **never compile, run unit tests, or anything the CI build already enforces**; nothing that boots the app. Run in `$WT`, in parallel; failures become findings merged into the round-1 pool. Round n≥2 re-runs only the checks whose file set the delta touches.

1. **Java format** (`class: compliance`) — per changed module: `./mvnw -f all-modules-pom.xml -pl <mod> net.revelc.code.formatter:formatter-maven-plugin:2.28.0:validate -Dconfigfile=$WT/eclipse-code-formatter.xml -Dformatter.includes=<changed files relative to module source roots>` (harness convention CI doesn't enforce). One `afk:afk-runner-lite` subagent (exit-code verdict — `DELEGATION.md` "Runner split").
2. **UI lint** (`class: compliance`) — only if the diff touches files under a dir with an ancestor `.eslintrc.*` (vite builds don't lint): `npm ci` at `$WT` root, then `npx --no-install eslint <changed ui files>` from the nearest eslintrc dir. eslint unresolvable → record "skipped (infra absent)", don't fail. One `afk:afk-runner-lite` subagent (exit-code verdict — `DELEGATION.md` "Runner split").
3. **Orphan hunt (wiring)** (`class: design`, medium) — one `afk:afk-reader` subagent: for each NEW public class/endpoint/config key in the diff, prove a consumer exists at MR head (grep `$WT`); default to "orphan" when reachability can't be proven.

## The rounds

Run rounds per SETTLEMENT.md "The round", with the substitutions above. Every round, both modes: reconstruct the ledger from the MR → review pass → filter against the settled set → **post every new finding inline** (Posting below) → update the summary comment. Then the modes diverge:

- **Settle** — fix/dispute → adjudicate → commit → push → reply + resolve → next round, in-session, until settled or stalemate.
- **Review-only** — stop; the round's findings await the author. On the next invocation: nothing new (head equals the summary's reviewed head AND no new thread replies) → report that and stop. Otherwise delete any leftover `review/mr-<iid>` worktree/branch, re-run Phase 1 at the new head, and run the next round — the delta review (empty delta → skip the fan-out) plus **thread triage**, SETTLEMENT steps 4–6 with the author as implementor:
  - **Fix claim / no reply but code changed** — verify in `$WT` against the finding's evidence (read the file, never trust the claim). Verified → reply confirming + resolve; not fixed → stays open, reply stating what's still wrong.
  - **Pushback** — the author's dispute: adjudicate per SETTLEMENT step 5. `withdrawn` → reply the verdict + resolve (settled); `stands` → stays open, reply the evaluation (concede any partial points).
  - **No reply, no code change** — stays open.

## Posting inline comments (every round, both modes)

Script it (parse the diff → anchor → POST per finding). Rules that bite:

- JSON body via `glab api -X POST -H "Content-Type: application/json" "projects/:id/merge_requests/<iid>/discussions" --input <file>`; `-f position[…]` form params silently degrade to a plain note.
- `position` = `{position_type: "text", base_sha, start_sha, head_sha}` from the current `diff_refs` + `old_path, new_path` + line: added lines `new_line` only; context lines BOTH `old_line`+`new_line`; deleted lines `old_line` only.
- **New files: `old_path` must equal `new_path`** (not `/dev/null`) or GitLab 500s.
- Anchor fallback: exact line → nearest added line within 60 → context line. File not in diff → general note (no `position`) prefixed `file:line`.
- Verify each created note's `type` is `DiffNote`; delete bad notes via `… /notes/<id> -X DELETE`.
- Replies go inside the finding's existing discussion (`POST …/discussions/<id>/notes`); resolving is `PUT …/discussions/<id>?resolved=true`.

## Cleanup

After the terminal report: `git -C "$MAIN" worktree remove <WT>` (`--force` only if the worktree is clean but has untracked scratch) and `git -C "$MAIN" branch -D review/mr-<iid>`. In review-only mode the worktree never outlives the invocation; keep it only when the user says they want to poke at the checkout.

## Verdict

Every round stamps its `REVIEW:` line (grammar: review SKILL.md "Verdict & output") into the summary comment. The invocation then ends:

```
SETTLE: <settled|stalemate|open> — round={n} fixed={f} settled={s} open={o} [MR: <url>]
In plain terms: <one jargon-free sentence — where the MR stands and what happens next>
```

`settled` / `stalemate` per SETTLEMENT "Termination" (stalemate leftovers = the threads still open, the human's worklist — named in the summary comment); `open` = a review-only round finished with findings awaiting the author. Layered per `REPORTING.md` (plugin root).

## Hard rules

- **Review-only mode is read-only on project source** (main + worktree); it writes only scratch and GitLab notes. Settle mode may edit/commit in `$WT` and push to the MR source branch — never merge, never touch Draft/Ready, never rewrite the author's existing commits.
- Checklists always from `$MAIN`, code always from `$WT`.
- Never boot the app or hit a live environment.
- All fan-outs single-message parallel; the verify pass and adjudications are their own parallel waves.
