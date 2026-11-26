---
name: prototype
description: /afkv2:prototype — turns a settled PRD that adds or changes a screen into 1 clickable HTML mockup per screen that looks like the app, with made-up data. Anchors on the design catalog, the live app or the frontend source, shows the mockup file in lavish or by its file:// path, edits it for each note, and settles PROTOTYPE.md and the INDEX row. Stops with no_ui when no story adds or changes a screen. Use after the PRD is settled, before the design.
---

# /afkv2:prototype

1 run turns the screen stories of a settled PRD into 1 clickable mockup per screen, takes the developer's notes on it, and settles `PROTOTYPE.md`. Write each mockup by [MOCKUP.md](MOCKUP.md), and `PROTOTYPE.md` by [PROTOTYPE-FORMAT.md](PROTOTYPE-FORMAT.md). Only this skill writes `PROTOTYPE.md` and the `INDEX.md` Prototype row.

## Hands-off

A hands-off subagent, such as an autopilot executor, has no developer at the keyboard. It opens no page, writes no file, and parks with the reason that a developer must run the prototype.

## The commands

Run each command from the repository root, in the worktree of the branch. `<python>` is the Python in the setup install record (line `python`). Every answer is 1 JSON object: `{"ok": true, ...}` or `{"ok": false, "error": {"code", "reason"}}`; exit 0 is ok, 1 is refused, 2 is unreadable input.

```sh step=start
<python> "<this skill's folder>/scripts/prototype_files.py" start --ticket "<ticket key>"
```

```sh step=check
<python> "<this skill's folder>/scripts/prototype_files.py" check --mockup "<mockup>"
```

```sh step=settle
<python> "<this skill's folder>/scripts/prototype_files.py" settle --ticket "<ticket key>"
```

```sh step=show
<python> "<this skill's folder>/scripts/mockup_show.py" show --mockup "<mockup>"
```

```sh step=wait
<python> "<this skill's folder>/scripts/mockup_show.py" wait --mockup "<mockup>" --notes-file "<notes file>"
```

```sh step=reply
<python> "<this skill's folder>/scripts/mockup_show.py" reply --mockup "<mockup>" --reply-file "<reply file>"
```

```sh step=end
<python> "<this skill's folder>/scripts/mockup_show.py" end --mockup "<mockup>"
```

## No screen, no mockup

Read the `## User Stories` and `## Acceptance Criteria` of the PRD. When no story adds or changes a screen, stop with `no_ui`: the run writes no file, shows no mockup, starts no app and leaves the `INDEX.md` Prototype row as it is. Tell the developer that the feature has no screen to draw.

## Steps

`<afkv2 data folder>` is `%LOCALAPPDATA%\afkv2`. `<run>` is the ticket key and the start time of the run, such as `ABC-12-20260101T0930`.

1. **Start.** Run `start`. Add `--frontend "<name>"` when the developer names the frontend. Keep `spec_dir`, `prd`, `prototype_md`, `mockup_dir`, `frontend`, `anchor`, `live` and `resume` of the answer. Then check for a screen by "No screen, no mockup". On a refusal:

   | Code | Next action |
   |------|-------------|
   | `missing-input` | the ticket has no PRD: stop, and name `/afkv2:to-prd` |
   | `no-frontend` | the PRD exists: first check for a screen by "No screen, no mockup", in the `PRD.md` of the ticket folder under the `spec_folder` of `.afkv2/config.json`. Then stop, and give the developer the command of the reason |
   | `pick-frontend` | first check for a screen in the same way. Then ask the developer which of the listed names, and run `start` again with `--frontend` |
   | any other code | the repository config is missing or broken: stop, and give the developer the reason |

   `resume` true: read `PROTOTYPE.md` and the mockups it names, and run `check` on each mockup; fix each line it names, as in step 3. Run step 2, then go to step 4.

2. **Anchor.** Copy the look of the app from the source that `anchor` names:

   | `anchor` | Read |
   |----------|------|
   | `catalog` | the catalog README and its cards in `frontend.catalog`: copy their tokens and card markup as they are |
   | `live` | screenshots of the live app: its shell and the screen type nearest each new screen |
   | `source` | the tokens, the components and the shell in `frontend.source`; delegate the read to a subagent, and take back a digest with a file citation for each item |

   With a `live` block in the answer, also on the `catalog` anchor, start the app:
   1. Probe the `address` of the block. It already answers before the start: start no app, because another server holds the address. Use the next anchor, and record the cause for the Fidelity section.
   2. Check that each variable that `needs` names is set. A variable is missing: start no app, use the next anchor, and name the missing variables for the Fidelity section.
   3. Run the `start` command of the block as a background command the harness tracks, in `/bin/sh`, or in Git Bash on Windows: the block holds POSIX shell syntax.
   4. Wait until the `address` answers, at most `ready_seconds`.
   5. Take the screenshots with the browser driver into `<afkv2 data folder>/shots/<run>/`.
   6. The app does not answer, or the browser driver fails: use the next anchor (`catalog`, else `source`), and record the cause for the Fidelity section.

   Also map the neighbours of each screen: the screens a story enters from, and the screens the new screen links to.

3. **Draft.** Write 1 mockup per screen into `mockup_dir`, by [MOCKUP.md](MOCKUP.md), with made-up data only: copy the look of the app, and never copy a record from a screenshot, the live screen or its database. A mockup of an earlier run is already in `mockup_dir`: keep it and its edits, and change it instead of a new draft. The direction is unclear: give 2 to 3 variants in the file. Run `check` on each mockup, and fix each line it names. Done when `check` answers ok for every mockup.

4. **Take the notes.** By "Notes loop".

5. **Stop on a PRD gap.** A note or a story needs an answer that the PRD does not hold: stop with `prd_gap`, name the gap, and name `/afkv2:grill-requirements`.

6. **Settle.** Only the developer settles a direction. Then:
   1. Delete the losing variants and the switcher bar from the mockup. Run `check` again.
   2. **Capability walk.** Click every story and acceptance criterion of the PRD through the mockup, from its entry screen. The Coverage table holds 1 row per story: `reachable`, or `gap` when the story or one of its criteria cannot be reached. Name each criterion that is a gap in the Decisions section.
   3. **Fidelity pass.** With the app running, put each mockup side by side with the live screenshots, and fix each difference in the shell, the spacing, the type and the components. Record what you compared and each difference left. With no app running, mark the fidelity by the anchor: `catalog` or `source-only`.
   4. Write `PROTOTYPE.md` by [PROTOTYPE-FORMAT.md](PROTOTYPE-FORMAT.md). The fidelity mark comes from the anchor and the fidelity pass.
   5. Run `settle`. `missing-input`: the spec folder has no `INDEX.md`; stop, and name `/afkv2:to-prd`. On any other refusal, fix each named file or problem, and run `settle` again. Never report done before `settle` answers ok: its secret scan covers every file the run wrote.

7. **Close the run.** At the end of each run, also after a stop or a refusal:
   1. Run `end` when lavish shows a mockup.
   2. Stop only an app that step 2 of this run started. Run the `stop` command of the `live` block in the same shell, else stop the background command of step 2. Then probe the `address`. While it still answers and its host is `localhost`, `127.0.0.1`, `::1` or `0.0.0.0`, stop the process that listens on its port. Report an address that still answers.
   3. Delete the screenshots and the notes file.

8. **Report.** End with 1 line: `prototype: <state> — <1-line summary>`.

   | State | When |
   |-------|------|
   | `settled` | `settle` answered ok |
   | `no_ui` | no story adds or changes a screen |
   | `prd_gap` | step 5 stopped the run |
   | `stopped` | the developer stopped the run before a settle |
   | `refused` | a refusal stopped the run; the line names its code |
   | `parked` | a hands-off subagent parked by "Hands-off" |

## Notes loop

Show the mockup in lavish only when the developer did not ask for chat only. Else, or when `show` refuses, take the notes in chat. Lavish annotates only the file that `show` opened. A click that loads another file, also a link back to the same screen, shows that file with no annotation, until the developer reloads the lavish tab. With several screens, show 1 screen at a time, starting at the entry screen, and tell the developer this rule once. To take notes on another screen, answer the notes of the shown screen, run `end`, then run `show` with the other screen.

Each note names its element by the `selector`, the `tag` and the `text` that lavish pins on it; a note in chat names it in words. Give each note an edit of the mockup or a reply, never neither. Run `check` after each edit. Repeat the loop until the developer settles a direction or stops.

### In lavish

1. Run `show`. `no-host`: lavish is missing, at another version or on an unsafe host. Its reason holds the `file://` path: go on by "In chat". `status` `user-ended`: the developer ended this session in the browser, and lavish does not open it again: run `end`, and go on by "In chat". `tab` `reused`: lavish opened no new tab, because a tab showed the mockup before. When the developer does not see the mockup, run `end`, then `show`.
2. Wait for the notes. On Claude, run `wait` with `--notes-file "<afkv2 data folder>/notes/<run>.json"` as a background command the harness tracks; its exit tells you the notes are in the notes file. On Codex, run `show` before you end each turn: the Stop hook waits only on the waiting record that `show` writes, and it clears the record after each wait. A later `show` reuses the open tab. Then end your turn, and the Stop hook hands back 1 line per note with its tag, selector and text.
3. Read each note, and give it an edit of the mockup or a reply.
4. Show the edited mockup: lavish reloads the saved file in the open session, so run no `show` for it. Write 1 Markdown line per note to a reply file, the edit made or the answer, and run `reply`.
5. Go to step 2.

| Answer of `wait` | Next action |
|------------------|-------------|
| `count` 0 and `ended` false | run `wait` again |
| `ended` true | first give each note of the notes file an edit of the mockup or a reply. An `end` that you ran to show another screen: run `wait` for that screen. `status` `browser_disconnected`: the developer closed the browser; ask in chat whether to run `show` again or to go on by "In chat". Any other `status`: the developer ended the session, and lavish does not open it again; go on by "In chat" |
| `no-session` | run `show`, then `wait` |
| `notes-unwritten` | the notes are in the `notes` field of the refusal: give each an edit of the mockup or a reply, and fix the notes file path that the reason names |
| `no-host` or `host-error` | go on by "In chat", with the `file://` path of the mockup |

On Codex, the Stop hook can end the wait with no note: the wait timed out, the developer closed the mockup, no session shows it, or lavish fell back. Its message goes to the developer, and your turn ends. At the next chat message of the developer, ask whether to show the mockup again or to go on by "In chat". To show it again, run `end`, then `show`: lavish then opens a new tab.

### In chat

Give the developer the `file://` path of the mockup: they open it in a browser and give their notes in chat. Give each note an edit of the mockup or a reply, and tell the developer to reload the mockup after each edit.

### Chat only

The developer says "chat only", at any time: run `end` when lavish shows a mockup, and take every later note of this run in chat, by "In chat". The run never shows the mockup in lavish again.
