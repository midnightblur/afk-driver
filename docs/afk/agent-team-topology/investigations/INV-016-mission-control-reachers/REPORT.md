C:\Users\mvu\PersonalProjects\afk-driver-agent-teams@7e9c87a · closed-with-frontier · boundaries 13/14 · unverified 2 (load-bearing 0) · ledger: docs/afk/agent-team-topology/investigations/INV-016-mission-control-reachers/COVERAGE.json

## Answer

Paths below are relative to skills/afk/mission-control/scripts/ unless stated.

- Two code entry points reach the registry: mission_control.main `--once` (mission_control.py:112) and watch mode (:115). Both pass SECTION_PARSERS to mc/server.py, which runs compose.build through render_once (mc/server.py:22); watch mode runs it again from the watcher thread (mc/server.py:99, :105). The script entry is mission_control.py:125. PANEL_PARSERS (mission_control.py:52) is an alias with no reader.
- NAV_ORDER and SECTION_META are read only inside compose.build (mc/compose.py:52, :57). compose.build has one caller, render_once (mc/server.py:22).
- Two skills invoke the build path: /afk:mission-control watch and retro modes (skills/afk/mission-control/SKILL.md:54-55, relaunch :77) and /afk:preflight PF-5 through `--once` (skills/afk/preflight/SKILL.md:174-178).
- Tests call main at tests/test_contract.py:290, :378, :391, :430, :432, :501.
- No hook, gate, adapter, MCP server, CI workflow or script outside skills/afk/mission-control invokes mission_control.py or imports mc. The importer search returns only mission_control.py:28-29, mc/server.py:15 and test_contract.py (c-5b181744, c-69ca6110).
- Output: render_once writes {spec_dir}/plan/mission-control/index.html (mission_control.py:105, mc/server.py:25). The page shell parses the data slot (mc/assets/shell.html:251), builds the nav in section order (:1157), dispatches RENDER by section id (:1179) and has 12 number keys (:1152). PF-5 copies the `--once` page to a tracked SHIP-SNAPSHOT.html and commits it (skills/afk/preflight/SKILL.md:179-181).
- `--check-digests` and a path-fence rejection exit before the registry is used (mission_control.py:104, :107-109).

## For the design

- Section ids are string keys shared by NAV_ORDER, each parser's SECTION_ID or make_parser call, and the shell RENDER table. An id missing from NAV_ORDER is dropped with no error (mc/compose.py:53-54). mc/sections/overview.py:35 lists the digest ids by hand, a second list beside NAV_ORDER.
- Tests pin the registry by membership only: test_contract.py:294-297 checks 12 ids are present. NAV_ORDER order, an extra section and the Absent-card titles in SECTION_META are unguarded; no test names NAV_ORDER or SECTION_META.
- Stale documents: skills/afk/CLAUDE.md:3 (the add-a-section recipe omits NAV_ORDER and SECTION_META); mc/__init__.py:6 (names panels/ and 5 parsers; the registry holds 11 from mc/sections/, mission_control.py:39-51).
- GRILL-LOG.md:283 (watch the .claude run manifest) is not in code at head: the watch snapshot covers only spec_dir (mc/server.py:50-63). GRILL-LOG.md:278 depends on `--once` rendering the team section Absent.
- plan/mission-control/ is not ignored in this repository (`git check-ignore` exit 1), although SKILL.md:70 and preflight SKILL.md:177 call it gitignored. No file in skills, hooks or scripts writes such an ignore entry (inferred, c-75c31cfa).

## Sites

- Traced: .claude-plugin/plugin.json:29; .codex-plugin/plugin.json:19; skills/afk/mission-control/SKILL.md:54, 55; skills/afk/preflight/SKILL.md:174, 176; scripts/: mission_control.py:39, 102, 112, 115; mc/compose.py:15, 30, 45, 47, 48, 52; mc/server.py:21, 22, 25, 66, 70, 78, 87, 99, 105; mc/template.py:38, 46; mc/assets/shell.html:251, 253.
- Terminal, code: scripts/: mission_control.py:28, 29, 52, 105, 107, 117, 125; mc/__init__.py:6; mc/compose.py:57; mc/server.py:15, 36; mc/template.py:20, 29, 40; mc/sections/architecture.py:17, diffs.py:16, digest_sections.py:21-25, gates.py:18, insights.py:14, overview.py:14, 35, progress.py:20, timeline.py:11; mc/assets/shell.html:8, 247, 251, 299, 497, 596, 676, 794, 831, 861, 892, 970, 1009, 1069, 1086, 1115, 1152, 1179; .claude-plugin/plugin.json:29; .codex-plugin/plugin.json:19; .github/workflows/release-gate.yml:37.
- Terminal, tests: scripts/tests/test_contract.py:28, 29, 156, 158, 258, 262, 273, 288, 290, 291, 294-297, 336, 337, 367, 376, 378, 388, 391, 396, 398, 428, 430, 432, 439-441, 443, 444, 478, 501, 502, 504.
- Terminal, documents: AGENTS.md:110, 185; CLAUDE.md:15, 110, 185; FRESHNESS.md:77, 78; GLOSSARY.md:157; README.md:724, 726; providers/PARITY.md:57; skills/afk/CLAUDE.md:3, 15; skills/afk/mission-control/SKILL.md:2, 3, 10, 68, 77, 88; skills/afk/preflight/SKILL.md:38, 39, 177, 178, 179; skills/afk/to-subtasks/PLAN-TEMPLATE.md:51, 52; skills/afk/understand/UNDERSTANDING-FORMAT.md:3, 95; docs/afk/agent-team-topology/GRILL-LOG.md:273, 278, 283, 297; investigations/INV-008-mission-control-section/REPORT.md:1, 5, 9, 10, 11, 23.
- Irrelevant, code: hooks/lib/adapter.sh:45; hooks/skill-registry-gate.sh:70; mcp-servers/tracker/server.py:64, 74; scripts/afk-config.py:208; scripts/tracker_api.py:39; skills/afk/understand/shell-template.html:16, 53, 61, 68; scripts/: mission_control.py:2, 4, 18, 36, 83, 84; mc/__init__.py:1; mc/compose.py:1, 2, 20, 26, 35, 41; mc/digests.py:40, 41, 75; mc/gitio.py:1; mc/mdtable.py:1; mc/sections/__init__.py:1; mc/server.py:1, 75; mc/template.py:1, 18; mc/vm.py:31; mc/assets/shell.html:6, 9, 13, 255, 398, 499, 501, 581, 1155; tests/__init__.py:1; tests/test_contract.py:2, 30, 438, 484, 526.
- Irrelevant, documents: CHANGELOG.md:1460, 1522, 1600, 1626, 1662; CLAUDE.md:11; GLOSSARY.md:162; skills/afk/CLAUDE.md:1; skills/afk/mission-control/DIGEST-FORMAT.md:207; skills/afk/mission-control/SKILL.md:8, 46, 50; docs/afk/agent-team-topology/: GRILL-LOG.md:197, 198, 202, 210, 213, 299, 300; grill-requirements.html:773; grill-solution.html:396, 789; grill-solution.round.json:1261, 1265, 1299, 1323, 2247, 2399, 2653; research/CRITIQUE-codex.md:59; investigations/INV-006-stage-skills/REPORT.md:15, 19.
- Irrelevant: 101 lines of investigations/INV-008-mission-control-section/COVERAGE.json, a prior ledger quoting the names; each line is a node in the ledger.

## Frontier

- B14: another repository, deployment manifest or live consumer. Browser tabs polling /__mc_token, rendered index.html pages and committed SHIP-SNAPSHOT.html copies live only in consuming repositories (c-3e49b9e6).

## Unverified

Neither claim is load-bearing.

- c-7260335c: the hit set holds every reference to the 3 roots over the name forms searched; completeness beyond those forms is not provable. 8 counter-searches found no reader outside the listed sites.
- c-6fbe561e: providers/PARITY.md:57 puts the renderer suite inside "the 80 tests"; the runner that collects those 80 was not enumerated.
