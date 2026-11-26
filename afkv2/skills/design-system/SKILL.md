---
name: design-system
description: /afkv2:design-system — builds or refreshes the design catalog of 1 frontend in the repository: its tokens and 1 card per repeating shape (shell, components, page types), each card measured and checked side by side against the running app or marked unchecked; a catalog with an unchecked card is a draft. Adds the frontend to the repository config on its first run. Writes only inside the catalog folder and sends nothing to any host. Use to create or refresh a catalog, before a prototype copies the look of the app.
---

# /afkv2:design-system

1 run builds or refreshes the catalog of 1 frontend: its tokens and 1 card per repeating shape. Write the catalog by [CATALOG-FORMAT.md](CATALOG-FORMAT.md). The run writes only inside the catalog folder of the frontend; `add-frontend` alone writes the `frontends` entry of the repository config. The run sends nothing to any host.

## Hands-off

A hands-off subagent, such as an autopilot executor, has no developer at the keyboard. It opens no page, writes no file, and parks with the reason that a developer must run the design-system, to compare each card with the live app.

## The commands

Run each command from the repository root, in the worktree of the branch. `<python>` is the Python in the setup install record (line `python`). Every answer is 1 JSON object: `{"ok": true, ...}` or `{"ok": false, "error": {"code", "reason"}}`; exit 0 is ok, 1 is refused, 2 is unreadable input.

```sh step=start
<python> "<this skill's folder>/scripts/catalog_files.py" start --frontend "<name>"
```

```sh step=add-frontend
<python> "<this skill's folder>/scripts/catalog_files.py" add-frontend --name "<name>" --source "<source folder>" --catalog "<catalog folder>"
```

```sh step=check
<python> "<this skill's folder>/scripts/catalog_files.py" check --frontend "<name>"
```

## Steps

`<afkv2 data folder>` is `%LOCALAPPDATA%\afkv2`. `<run>` is the frontend name and the start time of the run, such as `web-20260101T0930`.

1. **Start.** Run `start`. Leave out `--frontend` when the developer names no frontend. Keep `frontend`, `catalog_dir`, `catalog_exists`, `cards` and `live` of the answer. On a refusal:

   | Code | Next action |
   |------|-------------|
   | `no-frontend` | ask the developer once for the name, the source folder and the catalog folder of the frontend, each relative to the repository root. Run `add-frontend`, then `start` again. `add-frontend` refuses `bad-value`: give the developer its reason, and ask again |
   | `pick-frontend` | ask the developer which of the listed names, and run `start` again with `--frontend` |
   | any other code | the repository config is missing or broken: stop, and give the developer the reason |

2. **Inventory.** List the tokens and the repeating shapes of the frontend: the shell, the components and the page types. Start at the style entry points of the build: each stylesheet, component-library style, font and icon set that the build config loads, in cascade order, and the default styles of the UI framework at its installed version. An entry point that is not on disk, such as a package that is not installed: name it in the README Scope, because only the running app shows what it styles. Read them in `frontend.source` and the installed packages; delegate the read to a subagent, and take back a digest with a file citation for each item. `catalog_exists` true: read the README and each card of `cards` first, and refresh them in place. A card whose shape is gone from the source: remove it only after the developer's yes.

3. **Start the app.** With a `live` block in the answer:
   1. Probe the `address` of the block. It already answers before the start: start no app, because another server holds the address. Go on with no app, and record the cause for the report.
   2. Check that each variable that `needs` names is set. A variable is missing: start no app, go on with no app, and name the missing variables for the report.
   3. Run the `start` command of the block as a background command the harness tracks, in `/bin/sh`, or in Git Bash on Windows: the block holds POSIX shell syntax.
   4. Wait until the `address` answers, at most `ready_seconds`.
   5. Take 1 screenshot of each shape with the browser driver into `<afkv2 data folder>/shots/<run>/`: walk the shell, each page type, and each component on a screen that shows it.
   6. The app does not answer, or the browser driver fails: go on with no app, and record the cause for the report.

   With no `live` block, or when the steps above start no app: ask the developer once for the address of a running app that the run may screenshot, such as a dev server they run or a shared test environment, and whether they sign in to it in the browser of the driver. An address the developer gives is their app: start no app and stop none there, and take the screenshots by step 5. With no address, go on with no app: every card stays unchecked, and the run ends `draft`.

4. **Write the cards.** Write `tokens.css` and 1 card per shape into `catalog_dir`, by [CATALOG-FORMAT.md](CATALOG-FORMAT.md), with made-up data only: copy the look of the app, and never copy a record from a screenshot, the live screen or its database.

5. **Check each card.** Measure first: with the browser driver, read the computed styles of the main elements of each shape on the live screen and on the card: the font family, size, weight and letter case, the line height, the colours, the padding, the height, the border and the radius. Fix each value that differs. Then put each card side by side with the live screenshot of its shape, and fix each difference in the spacing, the type, the colours and the layout. Then mark the card `checked`, with the screenshot it was compared with. A card with no screenshot, because no app ran or the shape did not show, stays `unchecked`.

6. **Write the README** by [CATALOG-FORMAT.md](CATALOG-FORMAT.md): its Scope, 1 Cards row per card and its Refresh section.

7. **Run `check`.** On a refusal, fix each named file or problem, and run `check` again. Never report done before `check` answers ok: its secret scan covers every file of the catalog folder.

8. **Close the run.** At the end of each run, also after a stop or a refusal:
   1. Stop only an app that step 3 of this run started. Run the `stop` command of the `live` block in the same shell, else stop the background command of step 3. Then probe the `address`. While it still answers and its host is `localhost`, `127.0.0.1`, `::1` or `0.0.0.0`, stop the process that listens on its port. Report an address that still answers.
   2. Delete the screenshots.

9. **Report.** End with 1 line: `design-system: <state> — <checked> checked, <unchecked> unchecked; <1-line summary>`. Name the cause of each unchecked card.

   | State | When |
   |-------|------|
   | `done` | `check` answered ok with `unchecked` 0 |
   | `draft` | `check` answered ok with an unchecked card. A draft is not the look of the app: a prototype copies only its checked cards |
   | `stopped` | the developer stopped the run before `check` answered ok |
   | `refused` | a refusal stopped the run; the line names its code |
   | `parked` | a hands-off subagent parked by "Hands-off" |
