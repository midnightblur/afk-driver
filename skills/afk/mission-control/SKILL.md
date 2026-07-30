---
name: mission-control
description: Read-only dashboard for a feature's spec folder (watch / --once / build). Use on /afk:mission-control, to see a feature's progress, or if the watcher crashed.
---

# afk:mission-control — the feature dashboard

Fronts the mission-control renderer CLI (`scripts/mission_control.py`, bundled
in this skill directory). The page has two layers:

- **Live sections** (progress, timeline, gates, insights, diffs) — derived by
  the renderer from the plan artifacts on every render; always current; no
  agent ever writes their content.
- **Digest sections** (architecture, flows, entities, decisions, critical
  logic, legend) — rendered from the committed, hash-stamped
  `plan/digests/*.json` this skill authors in **build mode**
  ([DIGEST-FORMAT.md] — schemas, per-type digestibility rules, build
  protocol). Launching never builds: a missing/stale digest renders an amber
  hint naming this skill's build mode, so a launch costs zero tokens.

## Argument

`spec_dir` — path to the feature's spec folder (the ticket's directory
containing `PRD.md`/`SDD.md`/`plan/`, or the provisional `spec/{slug}/` folder
before a ticket key is minted). Required.

## Three modes

- **Watch mode (default)** — for a feature with a run in progress. Launches
  the renderer without `--once`; watches the spec/plan artifacts (digests
  included) and git refs, re-renders on change, serves on `127.0.0.1`.
- **Retro mode (`--once`)** — for a finished feature, no live run. Renders one
  complete page from the artifacts as they stand and exits — no server, no
  watching.
- **Build mode (`build`)** — the only mode that spends tokens. Rebuilds
  exactly the digests the freshness report calls `stale`/`missing`/`invalid`,
  by the protocol in [DIGEST-FORMAT.md]. Before fanning out, tell the user
  which digests will be rebuilt and from which sources; a fresh set is a
  no-op reported as such.

## Process (watch / retro)

1. **Freshness first.** Run
   `python3 tools/payable/ai-agents/plugins/workflow/skills/afk/mission-control/scripts/mission_control.py {spec_dir} --check-digests`
   (read-only, exit 0) and tell the user which digest sections are fresh,
   stale, or unbuilt — with "run `/afk:mission-control {spec_dir} build` to
   refresh" when any aren't fresh. Never build uninvited.

2. **Invoke the renderer.**
   - Watch mode: `python3 …/scripts/mission_control.py {spec_dir} [--port PORT]`
   - Retro mode: `python3 …/scripts/mission_control.py {spec_dir} --once`

   `--port` defaults to `8420`; pass it only if the user names a different
   port or the default is in use.

3. **Interpret the exit code.** `0` = success. `2` = the path fence rejected
   `spec_dir` (not a directory inside a git checkout) — report to the user
   verbatim; do not retry with a guessed path.

4. **Surface where to look.**
   - Watch mode: the renderer keeps running in the foreground (serving);
     report `http://127.0.0.1:{port}` for the user's browser. The process
     ends with its terminal (Boundary).
   - Retro mode: the renderer writes `{spec_dir}/plan/mission-control/index.html`
     and exits; report that path for the user to open via `file://`, and note
     its directory is gitignored (regenerate any time, never commit it —
     unlike `plan/digests/`, which IS committed).

## Watcher-crash recovery

The watcher has exactly one recovery path: **relaunch this skill** (Boundary,
"No daemonization"). If the page stops updating or the served URL stops
responding, run `/afk:mission-control {spec-folder}` again; the re-render is a
pure function of the current artifacts + digests, so nothing is lost.

## Boundary (hard rules)

- **Status stays derived.** Never edits `PLAN.md`, `JOURNAL.md`, or any other
  artifact the live sections derive from. Digests carry design synthesis
  only — a digest restating status is a defect (requirement ADR-0005: the
  page is never a second home for status).
- **Build mode writes only `{spec_dir}/plan/digests/`** (digest files + the
  manifest). Watch/retro modes write only the gitignored render output.
- **No daemonization** (SDD §11 — the launcher lives as long as its
  terminal). Never background the watch-mode process past the current
  session, register it as a service, or keep it alive after its terminal
  closes. A crashed watcher is relaunched, not revived.
- **Path fence is the renderer's, not this skill's, to relax** — an exit-2
  rejection is handled per step 3, never worked around.

[DIGEST-FORMAT.md]: DIGEST-FORMAT.md
