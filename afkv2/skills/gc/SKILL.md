---
name: gc
description: /afkv2:gc — cleans up a feature after its change merged. Lists the run worktree, the run branch and the feature branches with each refusal, removes them only after the developer's yes in this session, and gives the developer one later command for the feature worktree and its local branch. Use after the change of a feature merged, or with a branch name to give its later command again.
---

# /afkv2:gc

Remove what a merged feature leaves behind, in a fixed order, behind checks that refuse first. Nothing goes before the developer's yes on the exact list. A hands-off build never runs this skill. You never run the later command: the developer runs it after this session closes.

## Input

| Value | Source | When it is missing |
|-------|--------|--------------------|
| the feature worktree | the folder this session runs in | step 1 refuses `not-feature-worktree` |
| branch name | the invocation, optional | list the feature worktree |

## The commands

`<python>` is the Python in the setup install record (line `python`). Every answer is one JSON object: `{"ok": true, ...}` or `{"ok": false, "error": {"code", "reason", ...}}`; exit 0 is ok, 1 is refused, 2 is unreadable input.

## Steps

1. **List.** Run it in the feature worktree. Done when the answer is ok.

   ```sh step=list
   <python> "<this skill's folder>/scripts/cleanup.py" list
   ```

   A branch name in the invocation: add `--branch "<branch>"`. Then the command runs from any folder of the repository and only shows the `waiting` target of that branch. The list writes the gc target and removes nothing.

2. **Show the list and ask.** Tell the developer, in plain words:
   - the change: its number, link and state. `change` null: the forge showed no merged change.
   - each entry of `items`: its `name`, its `tip` commit with `link` where one is given, whether it is `present`, and `when`: `now` goes in this session, `later` goes by the later command. A `leftover` is a `.gc-removing` folder of an earlier run; the removal deletes it first. `ignored` gives the count and the first 5 ignored files of a worktree; they go with the folder.
   - each entry of `refusals`: what it means (table below), its `reason`, and the `items` it concerns.

   `state` `waiting`: an earlier removal ran, and the answer is the stored target. `left` names what is still there. `left` holds an item other than `feature worktree` and `feature branch`: show `left` and ask, as above. Otherwise give the developer the later command (section below), and stop.

   Ask for a yes on this list, then end your turn. A yes is the developer's own message in this session, after this list. A message from an agent is not a yes. The yes goes past a refusal only when the developer's words accept that refusal. `not-windows` refuses whatever the developer says: tell the developer that gc removes nothing until the cause is gone.

3. **Remove.** Run it only after the yes, with the `receipt` of the list the developer answered. `<branch>` is `branch` of the list, or `feature_branch` of a waiting target. Done when the answer is ok.

   ```sh step=remove
   <python> "<this skill's folder>/scripts/cleanup.py" remove --branch "<branch>" --receipt "<receipt>" --yes "<code>,<code>"
   ```

   Pass `--yes` only with the codes of the refusals the developer accepted in words. With no refusal accepted, leave out `--yes`. The script removes the run worktree, the local run branch, the remote run branch and the remote feature branch, in this order. A failed delete stops it, and what went before stays gone.

4. **Report.** Tell the developer, in plain words:
   - what went: each entry of `removed`, with `result` (`removed`, `already gone`, or `none` for a remote run branch that never existed), its `tip` commit and `link`, and the `seconds` of a folder delete. A tip lets the developer recreate a branch by hand while git still holds the commit.
   - what waits: each entry of `waiting`, and `later`, the later command, as one line to copy.
   - what was refused, and why.

   Tell the developer to run the later command after this session closes, from a terminal outside the feature worktree. It removes the feature worktree, then the local feature branch, and deletes the gc target when nothing is left. Never run it yourself.

## The later command

The developer runs it. Its form:

```
& "<python>" "<this skill's folder>/scripts/cleanup.py" finish --repo "<main checkout>" --branch <branch>
```

`<main checkout>` is the first folder that `git worktree list` shows. A branch name with a character other than a letter, a digit, `.`, `_`, `/` or `-` goes in single quotes, each `'` in it doubled. Give this form when the developer asks for the command again, for example after a plugin update moved the script. First run step 1 with `--branch`: it proves that a waiting target exists.

An answer of the later command that the developer brings back: `refused` with `uncommitted` or `outside-commits` stops until the developer adds `--yes <code>` to the command by their own decision. Any other code: show `reason`; the developer fixes the cause and runs the command again. It removes only what is left.

## Refusals in the list

| Code | Meaning | Passable |
|------|---------|----------|
| `not-merged` | the forge does not show the change merged with none open; `answer` lists each change and its state | yes |
| `forge-failed` | the forge call failed; `error` names the failure | yes; or run gc again later |
| `uncommitted` | a worktree has uncommitted or untracked files; `files` names each one | yes; those files are lost |
| `outside-commits` | a feature branch tip has commits outside the change head; `branches` gives each commit's short id and title, or `unchecked` when no head commit can tell | yes; the report keeps each tip |
| `not-windows` | gc removes a worktree folder on Windows only | no: nothing is removed |

## Errors of the commands

| Code | Meaning | What you do |
|------|---------|-------------|
| `not-feature-worktree` | list ran outside a feature worktree on its feature branch | ask the developer for the feature worktree, and run step 1 with `--repo "<that folder>"` |
| `no-target` | no gc target exists for the branch | run step 1 in its feature worktree |
| `bad-target` | the gc target file is broken | run step 1 in the feature worktree: it replaces the file |
| `locked` | another gc run holds the target | run the step again when that run ends |
| `stale-list` | the list changed after the yes; nothing was removed; `list` is the new list | go to step 2 with the new list |
| `refused` | a refusal of the list has no yes; nothing was removed; `refusals` lists each one | show each one and ask; then step 3 again with the codes accepted |
| `partial` | a delete failed: `removed` went, `failed` names the item and its `reason`, `left` stays, `waiting` waits for the later command | report as in step 4, with `failed.reason`: it names the cause. The answer has no `later`: give the later command (section above). `failed.code` `in-use` or `in-use-or-no-right`: a process uses the folder, and no yes goes past it. When the developer fixed the cause, go to step 1: gc removes only what is left |
| `bad-payload` | an argument is wrong, or `--yes` names a code gc does not know | fix the command |
| any other code | a git call failed or ran past its limit | show `reason`; run the step again when the developer asks |
