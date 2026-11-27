---
name: dogfood
description: /afkv2:dogfood — opens 1 afkv2 pane beside the main pane in herdr, where an afkv2 agent builds an afkv2 change for an ask while the developer works on. Sends each new ask and each feedback to that agent, applies each milestone note at once by APPLY.md, and at the end asks for the wrap-up and closes the pane. Use when the developer asks for an afkv2 change during other work, gives feedback on a trial, or says the main work is done.
---

# /afkv2:dogfood

You are the main agent. The afkv2 agent builds the change in its own pane and plugin worktree. You apply each change it reports, for this session only. Write no plugin file.

## The commands

Run each command from any folder. `<python>` is the Python in the setup install record (line `python`). Write each input file (the ask, the feedback, the wrap-up request) in scratch, outside every repository. Every answer is 1 JSON object: `{"ok": true, ...}` or `{"ok": false, "error": {"code", "reason"}}`; exit 0 is ok, 1 is refused, 2 is unreadable input. dogfood.py knows both panes, so no command takes a pane id.

An ok answer can still hold a prompt that the afkv2 agent did not take: `submitted` `false` with `prompt_error` from `start`, or `sent` `unconfirmed` from `tell`. Then send nothing again. Tell the developer to look at the afkv2 pane.

## Steps

1. **Start.** Write the ask of the developer to a file, then run:

   ```sh step=start
   <python> "<this skill's folder>/scripts/dogfood.py" start --ask-file "<ask file>"
   ```

   `status` `opened`: a new afkv2 pane runs the ask. `status` `existing`: the live afkv2 agent of this session got the ask; no second pane opens. Tell the developer which, and go on with the main work. A refusal: see Refusals. Read the session state at any time with:

   ```sh step=status
   <python> "<this skill's folder>/scripts/dogfood.py" status
   ```

2. **A new ask.** The developer gives another afkv2 ask: run step 1 again. The afkv2 agent queues it.

3. **A note.** A prompt `A note from the afkv2 pane: <path>` arrives. Check the note first:

   ```sh step=check-note
   <python> "<this skill's folder>/scripts/dogfood.py" check-note --note-file "<note file>"
   ```

   `note-check-failed`: apply nothing. Send the `failures` as feedback (step 4) and ask for a complete note. `kind` `milestone`: apply it at once by [APPLY.md](APPLY.md), with no question to the developer. `kind` `wrap`: step 6.

4. **Feedback.** The developer gives feedback on a trial in this pane. Write the feedback and the evidence you saw to 1 file: the command, the error and the output, verbatim. Then run:

   ```sh step=feedback
   <python> "<this skill's folder>/scripts/dogfood.py" tell --kind feedback --text-file "<text file>"
   ```

   Feedback that the developer gives in the afkv2 pane needs no step from you.

5. **Wrap-up.** The developer says that the main work is done. Write the wrap-up request to a file, then run:

   ```sh step=wrap
   <python> "<this skill's folder>/scripts/dogfood.py" tell --kind wrap --text-file "<text file>"
   ```

   Your turn ends here. The wrap note arrives later as a prompt; check it by step 3. Do not poll and do not wait in a loop. The afkv2 pane is dead (`no-pane` at the wrap request): run `close --force` of step 6.

6. **The wrap note.** Show the developer each Draft change and each open ask of the note. Then close the session:

   ```sh step=close
   <python> "<this skill's folder>/scripts/dogfood.py" close
   ```

   Tell the developer that the answered `worktrees` and `branches` stay. A dead afkv2 pane after step 5: close with `--force`. Both forms delete the session state and the notes folder; only the worktrees and branches stay.

   ```sh step=close-force
   <python> "<this skill's folder>/scripts/dogfood.py" close --force
   ```

## The 1 exception to rule H-8

Rule H-8 of the [herdr playbook](../herdr-playbook/SKILL.md) closes each pane once its result is read. In this skill, the afkv2 pane stays open after each milestone and each result until the wrap-up. Only `close` of step 6 closes it.

## Refusals

A refusal of `start` starts nothing. Tell the developer the reason and the repair.

| Code | Meaning | Next action |
|------|---------|-------------|
| `outside-herdr` | this session is not in a herdr pane, or herdr is not on the path | tell the developer: start herdr, then run the skill again from a pane in it |
| `no-source` | the install record has no source line | tell the developer: run `/afkv2:setup`, then run the skill again |
| `source-broken` | the source line names no main checkout of the plugin source | tell the developer: run `/afkv2:setup` to record the main checkout again, then run the skill again |
| `auto-approval-banned` | a managed setting turns off the full auto-approval that the afkv2 agent needs | tell the developer the reason; no pane opens |
| `in-afkv2-pane` | this pane is the afkv2 pane of a session | run the skill from the main pane |
| `agent-not-ready` | the afkv2 agent shows a dialog at its start, or did not get ready | tell the developer to look at herdr, then run the skill again |
| `herdr-failed` | a herdr command failed; `reason` names it | tell the developer the reason |
| `state-unreadable` | the session state file is broken | tell the developer the path in `reason`; the developer deletes it after a look |
| `ask-unreadable`, `text-unreadable` | the input file is absent, not UTF-8, empty or over 8000 characters | fix the file, then run the command again |
| `no-pane` | this pane has no live afkv2 pane | run step 1 for an ask; at the wrap-up, `close --force` of step 6 |
| `prompt-blocked` | the afkv2 agent shows a dialog, so nothing was typed | tell the developer to look at the afkv2 pane |
| `note-unreadable` | the note file is absent, not UTF-8 or over 16 KiB | send feedback: the note did not arrive |
| `note-check-failed` | the note breaks a rule of [NOTE-FORMAT.md](NOTE-FORMAT.md) | step 3: apply nothing, ask for a complete note |
| `no-wrap-report` | the afkv2 agent sent no wrap note, or `--force` met a live agent | run the wrap request of step 5; the note arrives as a prompt |
| `cleanup-failed` | close could not delete the notes folder or the state; the state stays | run `close` again; still failing: tell the developer the path in `reason` |
| `io-failed` | a file read or write failed; `reason` names the file | tell the developer the reason |
| `usage` | a command line is wrong | fix the command against its block |
