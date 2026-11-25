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

Read the `## User Stories` and `## Acceptance Criteria` of the PRD. When no story adds or changes a screen, stop with `no_ui`: the run writes no file, opens no page, starts no app and leaves the `INDEX.md` Prototype row as it is. Tell the developer that the feature has no screen to draw.

## Steps

1. **Start.** Run `start`. Add `--frontend "<name>"` when the developer names the frontend. Keep `spec_dir`, `prd`, `prototype_md`, `mockup_dir`, `frontend`, `anchor`, `live` and `resume` of the answer. `resume` true: read `PROTOTYPE.md` and the mockups it names, and go to step 5. Refusals:

   | Code | Next action |
   |------|-------------|
   | `missing-input` | the ticket has no PRD: stop, and name `/afkv2:to-prd` |
   | `no-frontend` | the config names no frontend: stop, and give the developer the command of the reason |
   | `pick-frontend` | ask the developer which of the listed names, and run `start` again with `--frontend` |

2. **Check for a screen.** By "No screen, no mockup". Done when at least 1 story adds or changes a screen.

3. **Anchor.** Copy the look of the app from the source that `anchor` names:

   | `anchor` | Read |
   |----------|------|
   | `catalog` | the catalog README and its cards in `frontend.catalog`: copy their tokens and card markup as they are |
   | `live` | screenshots of the live app: its shell and the page type nearest each new screen |
   | `source` | the tokens, the components and the shell in `frontend.source`; delegate the read to a subagent, and take back a digest with a file citation for each item |

   With a `live` block in the answer, also on the `catalog` anchor, start the app: run the `start` command of the block as a background command the harness tracks, and wait until its `address` answers, at most `ready_seconds`. Take the screenshots with the browser driver into `<afkv2 data folder>/shots/<run>/`. The app does not answer, or the browser driver fails: use the next anchor (`catalog`, else `source`), and record the cause for the Fidelity section. Also map each screen's neighbours: the screens a story enters from, and the screens the new screen links to.

4. **Draft.** Write 1 mockup per screen into `mockup_dir`, by [MOCKUP.md](MOCKUP.md). The direction is unclear: give 2 to 3 variants in the file. Run `check` on each mockup, and fix each line it names. Done when `check` answers ok for every mockup.

5. **Take the notes.** By "Notes loop".

6. **Stop on a PRD gap.** A note or a story needs an answer that the PRD does not hold: stop with `prd_gap`, name the gap, and name `/afkv2:grill-requirements`. Run `end` first when lavish shows the mockup.

7. **Settle.** Only the developer settles a direction. Then:
   1. Delete the losing variants and the switcher bar from the mockup. Run `check` again.
   2. **Capability walk.** Click every story and acceptance criterion of the PRD through the mockup, from its entry screen. Each one is `reachable`, or a `gap` in the Coverage table.
   3. **Fidelity pass.** With the app running, put each mockup side by side with the live screenshots, and fix each difference in the shell, the spacing, the type and the components. Record what you compared and each difference left.
   4. Write `PROTOTYPE.md` by [PROTOTYPE-FORMAT.md](PROTOTYPE-FORMAT.md). The fidelity mark comes from the anchor and the fidelity pass.
   5. Run `settle`. On a refusal, fix each named file or problem, and run `settle` again. Never report done before `settle` answers ok: its secret scan covers every file the run wrote.

8. **Stop the app.** At the end of each run, also after a stop or a refusal: run the `stop` command of the `live` block, else stop the background command of step 3. Delete the screenshots and the notes file.

9. **Report.** End with 1 line: `prototype: <state> — <1-line summary>`, with the state `settled`, `no_ui` or `prd_gap`.
