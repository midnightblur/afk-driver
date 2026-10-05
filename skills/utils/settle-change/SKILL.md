---
name: settle-change
description: Review a forge change and settle it through the review loop, using the change as the ledger. Use for a change URL or provider id that needs review or another check after fixes.
---

> **Language:** read `LANGUAGE.md` (plugin root) first — it binds every word this skill produces.

# settle-change — review a forge change until it settles

Reviews a change of the current repository against a real checkout of its head. This skill is the referee for `${AFK_PLUGIN_ROOT}/skills/afk/review/SETTLEMENT.md`. The change is the review record. A later session reconstructs the loop from the forge alone.

Two modes:

- **Settle (default)** — reviewer subagents find → findings post inline → fixer subagents fix or dispute, each reading its finding from the change thread → commit + push per round → repeat until nothing actionable remains — never merging (full never-list: Hard rules).
- **Review-only** — post findings and stop. Each later invocation is one more settle round, paced by the change author: new commits are the round's delta, thread replies are the fix claims and disputes.

Mode resolution: explicit flag wins. Otherwise use **settle** when the authenticated forge user is the author and `cross_fork=false`; use **review-only** otherwise. A cross-fork change is always review-only because no writable push target is modelled. Refuse `--settle` with that reason. `--settle` on another author's change requires the human's approval.

## Argument

Change URL or provider id. Optional:

- `--settle` / `--review-only` — force the mode (resolution above).
- `--skip-build` — skip Phase 2 except the orphan hunt. A draft change implies it.
- `--only <concerns>` / `--skip <concerns>` — narrow the roster (overrides triggers).

## Constants

- `MAIN` = the invoking checkout's root — run from the target repo's main checkout, never from inside a change worktree. Checklists and plugin files are read from `MAIN`; code under review from the worktree (`WT`).
- Scratch (fetched change data, `spec.md`, diff files, per-round report drafts): provider scratch directory (`CAPABILITIES.md`), else a session-temp `change-<id>` directory.

## The change as the review record

Follow `${AFK_PLUGIN_ROOT}/skills/afk/review/SETTLEMENT.md`. Run `${AFK_PLUGIN_ROOT}/skills/afk/review/scripts/forge_ledger.py` for `post`, `reply`, `resolve`, `summary`, `reconstruct`, `trailers`, and both `gate` phases. Do not call the forge adapter directly for these verbs. The script preserves exact inline locations, immutable records, trust, and closure.

## Shared machinery (the DRY seam)

The reviewer machinery is one-home in `skills/afk/review/SKILL.md` — run its "Concerns (11)", "Trigger activation", "Delta-round roster", "Checklists", "Findings contract", "Verify pass", severity rubric, and verdict table exactly, with this substitution map for its plan-anchored inputs:

| review SKILL.md input | here |
|---|---|
| slice / feature diff | round 1: fetched diff; round n≥2: delta since `reconstruct`'s prior `reviewed_head`, with the full change diff as context |
| subtask contract + parent PRD/SDD | `spec.md` (Phase 0) |
| AGENTS.md chain | unchanged — walked from `$WT` |
| artifact dir `plan/review/` | the forge change; no local gate record. `pattern-debt` findings still post before disposition |
| mutation probe | never runs — CI owns test execution |

`scope-and-impact` runs without `## Scope` globs: stray churn + blast radius only. Reviewer prompts: `PRECEDENCE.md` + checklist pasted verbatim from `MAIN`, spawn per `DELEGATION.md` (plugin root).

The loop protocol — round structure, fix-or-dispute, dispute adjudication, termination — is SETTLEMENT.md's. The caller-side pieces it leaves to this skill:

- **Review pass** — the fan-out above; `$WT` stays checked out across rounds.
- **Fix routing (settle mode)** — every class fixes inline in `$WT`. Brief each fixer with the ledger key, active location, `$WT`, `spec.md`, and the `AGENTS.md` chain. A fixer returns a fix or an evidence-cited dispute. Write the dispute record before adjudication. `scope` findings revert stray churn. A fixer that changes a test applies the `test-veracity` checklist and nearest `TESTING.md`.
- **Cheap re-verification per round (settle mode)** — reactor compile of fix-touched modules + the tests covering the fixed code + the Phase-2 checks whose file set the fixes touched. CI runs on each round's push — the loop never waits on it; a red pipeline is the author's signal, not a round gate.
- **Commit/push (settle mode)** — one commit per round in `$WT` (`review r{n}: <what>`), pushed at round close: inline anchors only exist on pushed heads, so posting round n+1's findings requires round n's fixes on the remote. Agent-driven commits run the commit-time code gates (`hooks/precommit-gates.sh`), so a round touching `.java` commits in minutes, not seconds: invoke `git commit` with an explicit **600000 ms tool timeout** — a commit dying on the default timeout is not a signal to retry with `--no-verify`. After the push, post the `Fixed — … (<short-sha>)` replies and resolve those threads. A fixer that adds a comment applies `RATIONALE.md` § Classification test and records each moved reason with `forge_ledger.py rationale-add`. Once the round's push lands, run `rationale-post` and `rationale-verify --clear` (`RATIONALE.md` § Write path). A failed verify blocks `settled`: report the missing IDs.
- **Settled / stalemate** — write a new summary note. Run closure only for a settled result. End with the terminal `SETTLE:` line.

## Phase 0 — fetch change + spec

If the selected forge is `none`, refuse with the adapter's reason.

1. Source `${AFK_PLUGIN_ROOT}/hooks/lib/adapter.sh` once. Run `afk_adapter forge change-fetch` in `MAIN`. Read the normalized id, URL, author, `head_sha`, immutable `base_sha`, `head_ref`, `cross_fork`, and `blob_base`.
2. Use the fetched diff. After checkout, `git diff {base_sha}...{head_sha}` is the fallback.
3. Spec: extract the tracker key from title or source branch. Fetch it through the selected tracker adapter and digest acceptance criteria into `spec.md`. Without a key, use the change description as the intent statement.

## Phase 1 — checkout the change head

Never review from diff text alone. Reviewers navigate the checked-out change head.

Fetch the adapter-provided `head_ref` into a local review branch. Create the worktree through `${AFK_PLUGIN_ROOT}/scripts/create-worktree`. Verify its HEAD equals `head_sha`. Fetch the change again when it moved.

`WORKTREE_PATH` from the last line is `WT`. In settle mode, configure the writable source branch as the push target.

Changed-module list (drives Phase 2 and triggers): `git -C "$WT" diff --name-only <base_sha>...HEAD`, mapped to `NNNNN-x/module` via `sed -nE 's|^([0-9]+-[^/]+/[^/]+)/src/.*|\1|p' | sort -u`.

## Phase 2 — local gates

Discover the selected build gates with `afk_build_gate_discover`. Run applicable gates with `afk_build_gate_run`. Skip this work for a draft change or `--skip-build`. Keep the orphan hunt. Run no live application.

Run one orphan hunt. For each new public class, endpoint, or config key, prove a consumer exists at the change head. Unproved reachability is an orphan finding.

## The rounds

Run SETTLEMENT.md's round. Every round reconstructs the forge record, reviews, posts every finding, and passes the progress gate before any fixer. Then the modes diverge:

- **Settle** — fix/dispute → adjudicate → commit → push → reply + resolve → next round, in-session, until settled or stalemate.
- **Review-only** — stop; the round's findings await the author. On the next invocation: nothing new (head equals the summary's reviewed head AND no new thread replies) → report that and stop. Otherwise delete any leftover `review/change-<id>` worktree/branch, re-run Phase 1 at the new head, and run the next round — the delta review (empty delta → skip the fan-out) plus **thread triage**, SETTLEMENT steps 4–6 with the author as implementor:
  - **Fix claim / no reply but code changed** — verify in `$WT` against the finding's evidence (read the file, never trust the claim). Verified → reply confirming + resolve; not fixed → stays open, reply stating what's still wrong.
  - **Pushback** — the author's dispute: adjudicate per SETTLEMENT step 5. `withdrawn` → reply the verdict + resolve (settled); `stands` → stays open, reply the evaluation (concede any partial points).
  - **No reply, no code change** — stays open.

For a verified author fix, write `verified` with the full current head SHA and
exact locator. State `verified at <full-head-sha>`. Name an author commit only
when the forge or git history proves which commit fixed the key.

## Publishing findings

Use `forge_ledger.py post`. It publishes each finding at its exact diff location or as a counted unanchored note. Run `gate --phase progress` before briefing fixers. Use `reply` and `resolve` for later records. Write the final summary, then run `gate --phase closure` before reporting settled. An unanchored key or unresolved thread blocks closure.

## Cleanup

After the terminal report: `git -C "$MAIN" worktree remove <WT>` (`--force` only if the worktree is clean but has untracked scratch) and `git -C "$MAIN" branch -D review/change-<id>`. In review-only mode the worktree never outlives the invocation; keep it only when the user says they want to inspect the checkout.

## Verdict

Every closed round writes a new immutable summary note. The invocation then ends:

```
SETTLE: <settled|stalemate|open> — round={n} fixed={f} settled={s} open={o} posted={p}/{a} anchored={x} unanchored={y} [change: <url>]
In plain terms: <one jargon-free sentence — where the change stands and what happens next>
```

`settled` requires a green closure gate. `stalemate` names each open key. `open` means a review-only round awaits the author.

## Hard rules

- **Review-only mode is read-only on project source.** It writes only scratch and forge comments. Settle mode may edit, commit, and push to the change source branch. It never merges, changes Draft status, or rewrites existing commits.
- Checklists always from `$MAIN`, code always from `$WT`.
- Never boot the app or hit a live environment.
- All fan-outs single-message parallel; the verify pass and adjudications are their own parallel waves.
