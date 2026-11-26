# Prototype live checks

The plugin owner runs these checks by hand, before the change is marked Ready. An agent does not run them. Each check proves what no script can see: what the agent does in a real Claude or Codex session. The hands-off tests in CI cover the script side of each row.

Each check has a session, its data, and its given, when and then. The pass rule is the then. On fail, write what you saw in the table at the end; the owner decides before Ready.

## Before you start

1. Use a test repository, not a repository with real work.
2. Install lavish-axi 0.1.86 globally. `mockup_show.py show` refuses any other version.
3. Install the browser driver with `/afkv2:setup`. The checks that take screenshots need it.
4. For VR-016, install the Codex Stop hook with `/afkv2:setup`, and trust it as in check 1 of [CODEX-LIVE-CHECKS.md](CODEX-LIVE-CHECKS.md).
5. The data names the worked examples WE-01 to WE-04 of the PRD of ticket 207. Every row is made up.
6. Some checks start from the end state of an earlier check. Run them in this order.

## Owner live checks — the real-session checks the owner runs before Ready

### VR-001 — a note on the mockup reaches the agent with its element

- Session: a real Claude session on Windows, lavish 0.1.86 and the browser driver from setup
- Data: WE-01: 2 stories, 12 made-up orders, 1 catalog with tokens and 3 cards
- Given: a scratch frontend repository with a catalog, a live block and a settled PRD with 2 stories that add an orders screen
- When: the developer runs /afkv2:prototype, pins the note 'filter too far right' on the filter bar in lavish and sends it
- Then: lavish shows the mockup file itself with no grill cards; the agent receives the note with its selector, moves the filter bar and shows the mockup again

### VR-002 — settle writes PROTOTYPE.md and the INDEX row

- Session: a real Claude session on Windows, lavish 0.1.86 and the browser driver from setup
- Data: WE-01
- Given: the mockup of VR-001 after the notes loop
- When: the developer settles the direction
- Then: PROTOTYPE.md holds a Coverage table with 2 rows, both reachable from the nav entry, the fidelity mark live-verified with the compared screenshots named, and the INDEX Prototype row reads 'chosen <date>'

### VR-003 — no live app, no catalog and no lavish host

- Session: a real Claude session on Windows, lavish 0.1.86 and the browser driver from setup
- Data: WE-02: the same 2 stories, frontend source only
- Given: a scratch repository with no live block, no catalog and the lavish host stopped
- When: the developer runs /afkv2:prototype
- Then: the agent gives the file:// path of the mockup, takes notes in chat, and PROTOTYPE.md marks the fidelity source-only

### VR-018 — the design catalog of a frontend

- Session: a real Claude session and the browser driver from setup
- Data: a small static frontend served by the live block
- Given: a scratch frontend with a live block and 3 repeating shapes: shell, button, list page
- When: the developer runs /afkv2:design-system for it
- Then: the catalog folder holds tokens.css, 3 card files and a README whose Cards table marks each card checked against a named screenshot

### VR-004 — no live record lands in a written file

- Session: a real Claude session on Windows, lavish 0.1.86 and the browser driver from setup
- Data: WE-03: a seeded app page with 5 named customers; you compare the written files with the 5 names
- Given: a live app whose page shows real customer names
- When: the developer runs /afkv2:prototype and settles
- Then: the mockup and PROTOTYPE.md hold none of the live names, only made-up ones, and the settle reports the secret scan of every written file

### VR-005 — a feature with no screen stops with no_ui

- Session: a real Claude session on Windows, lavish 0.1.86 and the browser driver from setup
- Data: WE-04
- Given: a settled PRD whose 2 stories describe an API export job and no screen
- When: the developer runs /afkv2:prototype
- Then: the run stops with no_ui, no file is written in the spec folder, and the INDEX Prototype row stays '—'

### VR-006 — 'chat only' ends the lavish session

- Session: a real Claude session on Windows, lavish 0.1.86 and the browser driver from setup
- Data: WE-01
- Given: a prototype run with the lavish host running and the mockup shown
- When: the developer writes 'chat only' in chat
- Then: the agent ends the lavish session and takes every later note in chat for the rest of the run

### VR-016 — a note reaches Codex with its element

- Session: a real Codex session on Windows, lavish 0.1.86
- Data: WE-01
- Given: a real Codex session with the Stop hook installed by setup
- When: the developer runs /afkv2:prototype, pins 1 note and sends it
- Then: the next Codex prompt holds the note with its tag and selector, and the agent edits that element

### VR-022 — a hands-off subagent parks

- Session: a real Claude session on Windows, lavish 0.1.86 and the browser driver from setup
- Data: WE-01 spec folder
- Given: a real Claude session
- When: a hands-off subagent is told to run /afkv2:prototype on a ticket
- Then: the subagent opens no page, writes no file and parks with the reason that a developer must run it

### VR-025 — the design cites the prototype

- Session: a real Claude session on Windows, lavish 0.1.86 and the browser driver from setup
- Data: WE-01
- Given: the spec folder of VR-002 with a settled PROTOTYPE.md
- When: the developer runs /afkv2:propose-solution
- Then: the SDD cites the filter-bar decision of PROTOTYPE.md in an existing section, and the design gate passes with no new heading

### VR-026 — the verification plan traces to the prototype

- Session: a real Claude session on Windows, lavish 0.1.86 and the browser driver from setup
- Data: WE-01
- Given: the spec folder of VR-025 with SDD.md
- When: the developer runs /afkv2:propose-verification
- Then: the plan holds ui-e2e or acceptance rows whose story column names stories 1 and 2 of the Coverage table of PROTOTYPE.md

## Results

| Check | Date | Harness version | Result | Notes |
|-------|------|-----------------|--------|-------|
| VR-001 | | | | |
| VR-002 | | | | |
| VR-003 | | | | |
| VR-018 | | | | |
| VR-004 | | | | |
| VR-005 | | | | |
| VR-006 | | | | |
| VR-016 | | | | |
| VR-022 | | | | |
| VR-025 | | | | |
| VR-026 | | | | |
