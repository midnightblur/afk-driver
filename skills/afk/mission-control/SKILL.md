---
name: mission-control
description: Launch (or relaunch) the read-only mission-control dashboard for one feature's spec folder — watch mode for a live run, `--once` for a retroactive render of an already-finished feature. Use when the user runs `/afk:mission-control {spec-folder}`, asks to "see the dashboard" / "view progress" for a feature, or the watcher has crashed and needs relaunching.
---

# afk:mission-control — launch the feature dashboard

Fronts the mission-control renderer CLI (`scripts/mission_control.py`, bundled
in this skill directory): a pure function from a feature's spec folder
(`PRD.md` / `SDD.md` / `plan/`) to a self-contained, read-only HTML dashboard.
This skill's job is only to **launch it correctly and report where to look** —
it authors no page content itself.

## Argument

`spec_dir` — path to the feature's spec folder (the ticket's directory
containing `PRD.md`/`SDD.md`/`plan/`, or the provisional `spec/{slug}/`
folder before a ticket key is minted). Required.

## Two modes

- **Watch mode (default)** — for a feature with a run in progress. Launches
  the renderer without `--once`; it watches the spec/plan artifacts and git
  refs, re-renders on change, and serves the page on `127.0.0.1`.
- **Retro mode (`--once`)** — for a feature that's already finished, with no
  live run happening. Renders one complete page from the artifacts as they
  stand and exits — no server, no watching.

## Process

1. **Invoke the renderer.**
   - Watch mode: `python3 tools/payable/ai-agents/plugins/workflow/skills/afk/mission-control/scripts/mission_control.py {spec_dir} [--port PORT]`
   - Retro mode: `python3 tools/payable/ai-agents/plugins/workflow/skills/afk/mission-control/scripts/mission_control.py {spec_dir} --once`

   `--port` defaults to `8420` if omitted; pass it only if the user names a
   different port or the default is already in use.

2. **Interpret the exit code.** `0` = success. `2` = the path fence rejected
   `spec_dir` (it isn't a directory inside a git checkout) — report this to
   the user verbatim; do not retry with a guessed different path.

3. **Surface where to look.**
   - Watch mode: the renderer keeps running in the foreground (serving);
     report the served URL — `http://127.0.0.1:{port}` — for the user to
     open in a browser. The process stays alive only as long as its terminal
     session; this skill does not background, detach, or daemonize it.
   - Retro mode: the renderer writes `{spec_dir}/plan/mission-control/index.html`
     and exits; report that path for the user to open via `file://` and note
     that the directory it lives in is gitignored (regenerate any time, never
     commit it).

## Watcher-crash recovery

The watcher has exactly one recovery path: **relaunch this skill.** There is
no daemonization, no process supervisor, and no auto-restart (SDD §11 — "no
daemonization/service-manager integration for the launcher; it lives as long
as its terminal"). If the page stops updating or the served URL stops
responding, run `/afk:mission-control {spec-folder}` again; the re-render is
a pure function of the current artifacts, so nothing is lost by relaunching.

## Boundary (hard rules)

- **Read-only launcher.** This skill never edits `PLAN.md`, `JOURNAL.md`, or
  any other artifact the dashboard derives from — it only starts the
  renderer process and reports where to look.
- **No daemonization.** Never background the watch-mode process past the
  current session, register it as a service, or attempt to keep it alive
  after its terminal closes. A crashed watcher is relaunched, not revived.
- **Path fence is the renderer's, not this skill's, to relax.** An exit-2
  path-fence rejection is reported as-is — never silently redirected to a
  different directory.
