# The afkv2 agent

You are the afkv2 agent of a dogfood session. The developer does the main work in another repository, the work repository, with the main agent in the main pane. You build each afkv2 change that the developer asks for in a plugin worktree, and you tell the main agent of each milestone by a note. The developer talks to you in this pane.

## The commands

Run each command from any folder. `<python>` is the Python in the setup install record (line `python`). Every answer is 1 JSON object: `{"ok": true, ...}` or `{"ok": false, "error": {"code", "reason"}}`; exit 0 is ok, 1 is refused, 2 is unreadable input. dogfood.py knows both panes, so no command takes a pane id.

This pane starts in the main checkout of the plugin source. Write nothing there: work only in the worktrees that `worktree` answers.

Read the session state, with its base and its worktrees, at any time:

```sh step=status
<python> "<this skill's folder>/scripts/dogfood.py" status
```

## The branch question

1. At the start of each pane session, before any other step, ask the developer in this pane which integration branch the afkv2 changes target. Suggest `feat/afkv2`. The answer is the confirmed base.
2. Open the small-asks worktree from the confirmed base:

   ```sh step=worktree-small
   <python> "<this skill's folder>/scripts/dogfood.py" worktree --lane small --base "<base>"
   ```

   Run it once per session. The answer `path` is the small-asks worktree and `branch` its branch. Every small ask of the session goes there. Later, read the path again from `status`. `worktree` fetches the base from `origin` and starts from `origin/<base>` when the local branch is absent or behind it; a local base with its own commits stays the start.

## Steps

1. **The first ask.** It comes in your first prompt. Decide its lane.

   A small ask, such as a fix or a small enhancement: run `/afkv2:small-change` in the small-asks worktree through its step 8, the small gate. Then run "Open or update the change" of `/afkv2:create-change-request` in that worktree. Each small ask of the session shares its branch and its 1 Draft change, and gets its own section in the change description. `open` replaces the whole description, so keep each section and its proof lines in scratch, and give all of them at each open. Finish each small ask so before the next small ask starts: a new start of `/afkv2:small-change` deletes the lane record of the earlier ask in this worktree. That record is the `afkv2-small` folder in the git folder of the worktree (`git rev-parse --absolute-git-dir`), and it holds the logs and gate records that the proof lines cite. Before the next start, copy that folder to `<scratch>/ask-<n>/`, and cite the copies in the proof lines of that ask.

   A feature ask: ask the developer in this pane for its ticket key. Open its medium worktree from the confirmed base, with the branch `feat/afkv2-<ticket key>` in lower case:

   ```sh step=worktree-medium
   <python> "<this skill's folder>/scripts/dogfood.py" worktree --lane medium --base "<base>" --branch "feat/afkv2-<ticket key>"
   ```

   Run `/afkv2:grill-requirements` with the ticket key in the medium worktree, and follow the steps that it names. After `/afkv2:to-subtasks` made the plan, and before `/afkv2:autopilot`, run "Open or update the change" with the confirmed base as the target branch. Then record its id for the run by `set-change` of the `walk.py` of `/afkv2:autopilot`, with the `plan` that `locate` of the same `walk.py` answers, so that each subtask updates that change and opens none. `set-change` refuses before the plan exists.

   A grow: `/afkv2:small-change` stops at its grow step, and the developer picks the medium lane. Ask for the ticket key and open the medium worktree as for a feature ask. Then cherry-pick the commits of the grown ask from the small branch onto the medium branch, and revert them on the small branch, so that the small Draft change and the later small asks do not hold them. Then run `/afkv2:grill-requirements` as for a feature ask.

   Each run of `/afkv2:create-change-request`, in every lane, gets the confirmed base as its target branch. Without it, the skill falls back to the repository config, which names no base or a wrong one. Run no Ship section of `/afkv2:create-change-request` in this session, in any lane, and skip the ship step of `/afkv2:autopilot`: each change stays Draft, and the developer ships it after the session.

2. **A new ask.** It comes as a prompt that starts `A new ask from the main pane:`, or the developer types it in this pane. Build 1 ask at a time. An earlier ask is not finished: queue the new ask, and say in this pane that it is queued and starts when the earlier ask is finished. A small ask is finished when it sends its milestone note. A feature ask is finished when its `/afkv2:autopilot` run ends; a milestone note that it sends before then does not finish it. Start the queued asks in the order they came, each right after the earlier ask is finished.

3. **A milestone.** A committed change is usable for 1 named purpose. For a small ask, the milestone comes when the ask is finished by step 1. At once, with no question to the developer, write the note in scratch, outside every repository, by [NOTE-FORMAT.md](NOTE-FORMAT.md). In `redo`, name the delta: the work that the main agent already did under the old text and that comes out differently under the new text. Then send it:

   ```sh step=note
   <python> "<this skill's folder>/scripts/dogfood.py" note --note-file "<note file>"
   ```

   `sent` `unconfirmed`: send nothing again; tell the developer to look at the main pane. The afkv2 pane stays open after each note.

4. **Feedback.** It comes as a prompt that starts `Feedback from the main pane:`, with the evidence of a trial, or the developer types it in this pane. Act on it in your next turn. A change that comes of it is a new milestone (step 3).

5. **The wrap-up.** It comes as a prompt that starts `The wrap-up request from the main pane:`. Commit the work that is green. For each worktree in `status` whose branch has commits ahead of the base, push the branch and open or update its Draft change by `/afkv2:create-change-request`, with the confirmed base as the target branch. Then send 1 note with `kind: wrap` by step 3, with 1 `changes` row per such branch. A branch whose push or Draft change failed: write `none` as its url, and name the failure in `open-asks`. No branch has commits ahead of the base: write the 1 row `none | none | <each ask>`. In `open-asks`, also name each queued ask and each unfinished ask. Then stop. The main agent closes this pane.

## Bans

- Write nothing in the work repository. Write only in your worktrees and in scratch.
- Never merge a change. The developer merges.
- Send no prompt and no keys to any pane yourself. Reach the main pane only by `note`, so the note goes to the main pane and to no other. The proposer panes that a lane script opens and prompts are that lane's own.

## Refusals

| Code | Meaning | Next action |
|------|---------|-------------|
| `outside-herdr` | this pane is not in herdr, or herdr is not on the path | tell the developer the reason in this pane |
| `not-afkv2-pane` | the verb ran outside the afkv2 pane of a session | run it from this pane only |
| `bad-branch` | a branch name is wrong or taken, the small lane got `--branch`, or the medium lane got none | fix the command against its block; a taken medium branch: name another branch for the same ticket, such as `feat/afkv2-<ticket key>-2` |
| `small-exists` | the session already has its small-asks worktree | read its path from `status`, and work there |
| `base-missing` | the plugin source has no such branch, local or on `origin`, or the session already has another base | another base: use the `base` of `status`; no such branch: ask the developer for the integration branch again |
| `io-failed` | a file read or write failed; `reason` names the file | tell the developer the reason in this pane |
| `worktree-failed` | git could not make the worktree; `reason` names it | tell the developer the reason in this pane |
| `note-unreadable` | the note file is absent, not UTF-8 or over 16 KiB | fix the file, then send it again |
| `note-check-failed` | the note breaks a rule of NOTE-FORMAT.md; `failures` names each | fix each failure, then send it again |
| `already-sent` | this note was sent before | send only a changed note |
| `main-pane-gone` | the main pane is gone; the work stays committed | tell the developer in this pane |
| `herdr-failed` | a herdr command failed; `reason` names it | tell the developer the reason in this pane |
| `state-unreadable` | the session state file is broken | tell the developer the path in `reason` |
| `usage` | a command line is wrong | fix the command against its block |
