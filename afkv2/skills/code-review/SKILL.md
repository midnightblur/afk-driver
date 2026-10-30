---
name: code-review
description: /afkv2:code-review — reviews one subtask in at most 3 rounds. Picks the concerns from its contract and diff, fixes critical and high findings, posts medium and low findings on the change. Use when a subtask's tests are green, or to review a subtask by hand.
---

# /afkv2:code-review

A round is: pick the concerns, review, record the findings, fix. The review stops after round 3, whatever is left, and reports what is left.

## Input

| Value | Source |
|-------|--------|
| subtask id | the invocation |
| plan folder, which holds `<subtask id>.md` | the invocation; else `plan` |
| change id | the invocation; none given: stop and ask for it, because the findings have no place to go |
| base commit, where the subtask started | the invocation; else the merge base of `HEAD` and the change's `target` from the forge `change-view` |

## The command

`<python> <this skill's folder>/scripts/review_rounds.py <verb>`, with one JSON object on stdin, from the repository root. `<python>` is the Python in the setup install record (line `python`). Every payload holds `plan` and `subtask`. Every answer is one JSON object; exit 0 is ok, 1 is refused, 2 is unreadable input. The script owns the round count, the severity routing, the posts and the state file `<plan>/review/<subtask>.rounds.json`.

## Steps

1. **Pick the concerns.** Read the contract and `git diff <base>...HEAD`. Write the diff to a scratch file. Pick each concern that this diff can break, with [CONCERNS.md](CONCERNS.md); there is no fixed set. Each concern has one `why` that names what in the contract or diff calls for it. Defer a concern only when its defect costs no more to fix later than now, with one `why`.
2. **Open the round.** `begin` with `change`, `concerns` and optional `deferred`, each a list of `{name, why}`. The answer holds `round`.
3. **Review.** Start one fresh read-only subagent per concern, together when the harness can. Give each one [REVIEWER.md](REVIEWER.md), its concern, the diff path and the contract path. Keep out the author's reasons, earlier findings and the round number.
4. **Record.** Join the arrays into one, with one finding per defect. `record` with `findings`. The script posts the medium and low findings on the change through the forge port. Done when the answer arrives; `post_failed` entries stay in the state and `finish` tries them again.
5. **Fix.** `next` is `stop`: go to step 7. `next` is `fix` or `fix-then-finish`: for each entry of `fix`:
   - Behavior defect: write a failing test first, then the fix. Stay inside the contract's `## Scope`. Commit code and tests only, and push; never force-push.
   - Fixed: `outcome` with `id`, `result: "fixed"`, `sha`.
   - Not fixed, because the fix leaves the scope, needs a human decision or does not work: `outcome` with `id`, `result: "unfixed"`, `reason`.
6. **Next round.** `next` was `fix-then-finish`: go to step 7, because no round reads this fix. `next` was `fix`: go to step 1 with the new diff, and keep each concern that found a critical or high finding.
7. **Finish.** `finish`. Its answer is this skill's result. Show the developer one plain sentence: why the review stopped, and what `left` holds. `not_posted` is not empty: run `finish` once more, then report the entries that remain.

The review is done when `finish` answers `ok: true`.

## Refusals

| Code | Meaning | Next action |
|------|---------|-------------|
| `round-cap` | round 3 is finished | `finish` |
| `no-fix-to-review` | the last round left no fix | `finish` |
| `fix-open` | a critical or high finding has no outcome | `outcome` for each id named |
| `review-owed` | a fix waits for its review round | step 1 |
| `round-open` | a round has no findings yet | step 3 |
| `no-open-round`, `no-review` | no round is open | step 1 |
| `review-over` | this subtask's review has stopped | `finish` repeats the report |
| `change-mismatch` | this review posts on another change | stop and report both ids |
| `no-such-finding` | no critical or high finding has this id | use an id from the `fix` list |
| `bad-state` | the state file is broken or holds another subtask | stop and report the path; the file stays as it is |
| `bad-payload` | exit 2: the payload or a finding is not usable; the reason names it | correct the payload and send it again |

## The result

| Field of `finish` | Holds |
|-------------------|-------|
| `stopped_by` | `clean`: the last round found no critical or high finding, and none stayed unfixed. `cap`: round 3 found one. `unfixed`: every other stop, where a critical or high finding stayed unfixed |
| `fixed` | each fix with its `sha`; `reviewed: false` means no later round read the fix |
| `left.blocking` | critical and high findings not fixed, each also posted on the change; `replaces` is the url of its earlier medium or low comment |
| `left.posted` | medium and low findings on the change |
| `left.not_posted` | findings the forge did not take, with `post_error` |
| `deferred`, `concerns` | what was deferred, and what each round ran |
| `reopened` | findings marked fixed that a later round found again |
