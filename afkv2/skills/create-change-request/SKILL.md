---
name: create-change-request
description: /afkv2:create-change-request — opens the one Draft change of a branch with its description, one request per person, proofs, mergeability case and one self-critique; watches CI in the background after each push; marks the change Ready at ship. Use to open or update a change, after a push, or at ship.
---

# /afkv2:create-change-request

The skill ends at Ready. A human merges the change.

## Input

| Value | Source |
|-------|--------|
| target branch | the invocation; else the base branch in the repository config |
| change id | the invocation; else the answer of `open` |
| plan folder, which holds the subtask contracts | the invocation; else `plan` |

## The commands

`<python> <this skill's folder>/scripts/change_request.py <verb>` and `<python> <this skill's folder>/scripts/ci_watch.py <verb>`, with one JSON object on stdin, from the worktree of the change's branch. `<python>` is the Python in the setup install record (line `python`). Every answer is one JSON object; exit 0 is ok, 1 is refused, 2 is unreadable input. Every payload can hold `forge` and `repo`, and the scripts pass them to the forge port.

## Open or update the change

Run this when the branch has its first commits, and again at ship.

1. **Push** the branch. Never force-push.
2. **Read the merge facts.** `merge-facts` with `target`. `conflicts` holds a file: merge the target in, resolve, push, and read again. Never rebase a pushed branch. `fetched: false` means the facts rest on the last fetch: say so in the case.
3. **Write the parts.** Write for a reader who has not seen the plan: state the facts, name no plan file, and link no ticket without its summary.

   | Field | Holds |
   |-------|-------|
   | `description` | what changes and why, for this reader |
   | `requests` | a list of `{person, role, request}`: one entry per person, `person` a forge login with no @, `role` `assignee` or `reviewer`. `request` names the one thing this person must do or read |
   | `proofs` | a list of `{claim, evidence}`: each claim the change makes, with the command and result, link or file that shows it |
   | `mergeability` | the case that this change can merge now: the merge facts, what it can break, and how to undo it |
   | `self_critique` | one pass, one text: read `git diff <target>...HEAD` and the parts as the reviewer. Name the weakest point. Fix what costs little, and write what stays |

4. **Open.** `open` with the parts; for a new change also `title` and `target`. Done when the answer holds `id`. `created: true` is a new Draft change. `created: false` wrote the description of the branch's open change.

`open` replaces the whole description. A person's note goes in a comment. The title, the assignee and the reviewers are set only when the change is created.

## After each push

`start` with `id`. The answer comes at once, and `previous` holds what the last watch found. Keep working.

Read `status` with `id` before each push and each new subtask. The watch writes its result to a record; `status` makes no forge call.

| `state` | Meaning | Next action |
|---------|---------|-------------|
| `watching` | CI still runs | keep working |
| `finished` | `status` is `success`, `failed` or `canceled`; `current_head: false` means an older commit | see below |
| `no-verdict` | the watch ended with no final status; `reason` says why | `start` after the next push, or read CI at ship |
| `lost` | the watch process stopped with no result | `start` |
| `none` | no watch has run | `start` |

A red CI does not stop work on the branch. Report it to the developer in one line. Fix a failure in code you own. For a failure in code you do not own, check whether the target branch has the fix, and merge it in when it does.

## Ship

Ship needs each subtask's review finished. `mark-ready` runs the review's `finish` for each subtask contract in the plan folder, so a review that owes no more work stops here.

1. **Update.** Run "Open or update the change" with the final proofs.
2. **Mark.** `mark-ready` with `id` and `plan`. Done when the answer holds `draft: false`. `marked: false` means the change was already Ready.

| Refusal | Meaning | Next action |
|---------|---------|-------------|
| `review-open` | `reviews` names each subtask and why | finish that review, then mark again |
| `head-differs` | the local head is not the head of the change | push and mark again, or run from the branch of the change |
| `ci-running` | checks still run, or wait for a human | run `watch` with `id` as a background shell of the harness: its exit wakes you, then mark again. A harness with no background shell: end the turn and say that CI runs |
| `ci-red` | a check failed or was canceled | fix and push, or report the failure to the developer. The change stays Draft |
| `ci-none` | the change has no checks | report it; the developer marks the change Ready |
| `change-not-open` | the change is merged or closed | report it |
| `not-draft` | `open` created a change that is not Draft | report the url; a human sets the flag |
| `no-branch` | `open` found no branch checked out | pass `id` or `source` |
| `no-target`, `no-merge-answer` | git has no such target, or gave no merge answer | correct `target`, or report the reason |
| `watch-not-started`, `no-repository`, `bad-record` | the watch has no process or no record | `reason` names the fix |
| other codes | the forge port's error codes, with its `reason` | `afkv2/ports/forge/CONTRACT.md` |
