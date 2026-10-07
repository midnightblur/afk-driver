C:\Users\mvu\PersonalProjects\afk-driver-agent-teams@7e9c87a · closed-with-frontier · boundaries 13/14 · unverified 1 (load-bearing 0) · ledger: docs/afk/agent-team-topology/investigations/INV-008-mission-control-section/COVERAGE.json

## Answer

The section registry is `SECTION_PARSERS` at skills/afk/mission-control/scripts/mission_control.py:39, a static import list at :29. `compose.build` (mc/compose.py:45-68) calls every parser with the spec folder and emits only the ids in `NAV_ORDER` (:15). `SECTION_META` (:30) titles an Absent card. mc/assets/shell.html:1179 renders by an id-keyed `RENDER` table. Every reader resolves its source against the spec folder; none reads the main checkout or `.claude/`. A missing source already renders as an Absent card when the parser returns Absent (mc/vm.py:126). Paths below are under skills/afk/mission-control/scripts/ unless stated.

## Sites that change or break

- mission_control.py:29, :39 — the new parser needs an import and a registry entry. Unguarded; test_contract.py:273 catches only a parser that raises.
- mc/compose.py:15, :52-54 — an id missing from `NAV_ORDER` is dropped with no error. Unguarded.
- mc/compose.py:30, :57 — no `SECTION_META` entry gives a fallback title. Unguarded.
- mc/assets/shell.html:1179-1181 — an id with no `RENDER` entry shows "This section failed to render". Unguarded.
- mc/assets/shell.html:1152 — 12 number keys; a 13th section gets no shortcut. Unguarded.
- mc/assets/shell.html:1160 — a live section always shows a green dot; manifest staleness needs new shell code. Unguarded.
- mc/server.py:53 (loop :99) — watch mode snapshots only the spec folder, so a manifest edit under `.claude/` never re-renders. Unguarded.
- mc/digests.py:83-88 — a digest source outside the spec folder always counts as drifted, so the section must be live, not a digest. Pinned by test_contract.py:475.
- mc/vm.py:33-35 — a park-until time rendered relative to now breaks the byte-identical re-render; emit it absolute. Unguarded for the new section.
- test_contract.py:410 — a client-side fetch of the manifest fails the one-fetch rule. Pinned.
- test_contract.py:374-383 — the renderer stays inline. Pinned.
- test_contract.py:270-274 — the parser must return Absent, never raise, on a missing file. Pinned by :343.
- mc/sections/overview.py:30-35 — the overview lists section ids by hand. Unchanged unless edited.
- skills/afk/preflight/SKILL.md:176-181 — PF-5 commits the `--once` render as SHIP-SNAPSHOT.html, so per-machine data from the ignored `.claude/` file would be committed. Unguarded.
- Stale or contradicted documents, unguarded: skills/afk/CLAUDE.md:3 (the add-a-section recipe omits `NAV_ORDER` and `SECTION_META`), skills/afk/mission-control/SKILL.md:3, :13, :25, :31-33, :77, GLOSSARY.md:158, FRESHNESS.md:78, mc/__init__.py:6.

## For the design

- scripts/afk-config.py:75 copies `.claude` into each new worktree, so worktree and main-checkout copies diverge; the main-checkout recipe is at :725. Which `.claude/` the section reads is a design decision.
- The test fixture runs `git init` at the spec folder (test_contract.py:245), so a repository-root lookup lands inside it (inference).
- The settled row "a dashboard is eventually consistent" (GRILL-LOG.md:188) fails unless the watch scope widens.
- No run-manifest writer exists at this head (inference); the manifest is design work.

## Frontier

B14: live browser tabs polling the reload token, and SHIP-SNAPSHOT copies committed in consuming repositories.

## Unverified

One claim, not load-bearing: the hit set holds every reference over the name forms searched.
