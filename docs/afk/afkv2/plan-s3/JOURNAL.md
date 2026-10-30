# Journal — append-only event log (format: skills/afk/to-subtasks/JOURNAL-FORMAT.md). Newest last.
2026-10-30 00:41 | autopilot | run | run start (5 runnable) — five slices to build in order; 0011 and 0012 have no prerequisites, 0013-0015 wait on 0012; no app to boot because this repository declares no build gate
2026-10-30 00:41 | autopilot | run | heartbeat 0/5 done, starting 0011-setup-skill — first slice starts
2026-10-30 00:49 | execute | 0011-setup-skill | designing — setup slice started; ground check: no v1 code changed since the takeover investigation (only spec files moved)
2026-10-30 00:53 | execute | 0011-setup-skill | developing — design settled; writing the setup script and its tests
2026-10-30 01:14 | execute | 0011-setup-skill | decision(D-1) — ground check accepted: no v1 code changed
2026-10-30 01:14 | execute | 0011-setup-skill | decision(D-2) — hook proof covers every provider still on v1
2026-10-30 01:14 | execute | 0011-setup-skill | decision(D-3) — fired record file name chosen
2026-10-30 01:14 | execute | 0011-setup-skill | decision(D-4) — expected marker hash read from shipped files
2026-10-30 01:14 | execute | 0011-setup-skill | decision(D-5) — Jira values kept where v1 keeps them
2026-10-30 01:14 | execute | 0011-setup-skill | decision(D-6) — repository config file name and shape chosen
2026-10-30 01:14 | execute | 0011-setup-skill | decision(D-7) — Codex plugin switch is a config edit
2026-10-30 01:14 | execute | 0011-setup-skill | decision(D-8) — both plugins stay on until the proof passes
2026-10-30 01:14 | execute | 0011-setup-skill | decision(D-9) — switch-back leaves only v1 on
2026-10-30 01:17 | execute | 0011-setup-skill | gate-skip native-contract — v1 gate reads the v2 layout as v1: setup must name both harnesses and must start through plain Python 3 (SDD 8), so committed with the skip switch. Output: afkv2/skills/setup/SKILL.md:25 interpreter;afkv2/skills/setup/SKILL.md:35 harness-name;afkv2/skills/setup/SKILL.md:36 harness-name;afkv2/skills/setup/SKILL.md:37 harness-name;afkv2/skills/setup/SKILL.md:38 harness-name;afkv2/skills/setup/SKILL.md:3 harness-name;afkv2/skills/setup/SKILL.md:45 harness-name;afkv2/skills/setup/SKILL.md:8 harness-name;afkv2/tests/setup/live/CODEX-SETUP-LIVE-CHECKS.md:10 harness-name;afkv2/tests/setup/live/CODEX-SETUP-LIVE-CHECKS.md:11 harness-name;afkv2/tests/setup/live/CODEX-SETUP-LIVE-CHECKS.md:16 harness-name;afkv2/tests/setup/live/CODEX-SETUP-LIVE-CHECKS.md:18 harness-name;afkv2/tests/setup/live/CODEX-SETUP-LIVE-CHECKS.md:1 harness-name;afkv2/tests/setup/live/CODEX-SETUP-LIVE-CHECKS.md:24 harness-name;afkv2/tests/setup/live/CODEX-SETUP-LIVE-CHECKS.md:32 harness-name;afkv2/tests/setup/live/CODEX-SETUP-LIVE-CHECKS.md:3 harness-name;afkv2/tests/setup/live/CODEX-SETUP-LIVE-CHECKS.md:9 harness-name;
2026-10-30 01:18 | execute | 0011-setup-skill | pushed 66e3ede8..5bddfa52 (3 commits) — first slice code on the shared branch and a Draft change opened into feat/afkv2
2026-10-30 01:21 | execute | 0011-setup-skill | verifying — running the static, unit and integration checks
2026-10-30 01:25 | execute | 0011-setup-skill | decision(D-10) — switch-back keeps the settings file that holds the off value, and its ignore line
2026-10-30 01:25 | execute | 0011-setup-skill | gate-skip native-contract — same v1-layout refusal as the 01:17 entry on commit 0dc38a30 (plugin-source gates blocked: native-contract; rows are harness-name and interpreter on afkv2 files); comment gate passed before it
2026-10-30 01:26 | execute | 0011-setup-skill | reviewing — independent review loop started on the slice
2026-10-30 01:45 | execute | 0011-setup-skill | review r1 — blocking: crit=0 high=3 med=14 low=8; 3 high bugs in the restore and removal paths. One low finding deferred to the feature gate, one disputed, the rest fixed
2026-10-30 01:50 | execute | 0011-setup-skill | decision(D-11) — the ignore line for the personal settings file has its own decision
2026-10-30 01:50 | execute | 0011-setup-skill | decision(D-12) — switch-back keeps what the harness wrote since the takeover
2026-10-30 01:55 | execute | 0011-setup-skill | gate-skip native-contract — same v1-layout refusal on commit ce4b2932 (harness-name and interpreter rows on afkv2 files)
2026-10-30 02:54 | autopilot | 0015-autopilot-execute | decision(D-13) — the plan author corrected the 0015 contract before it starts; the check input from another session stays an acceptance line because the plan check refuses a producer outside this plan
2026-10-30 02:20 | execute | 0011-setup-skill | review r2 — blocking: crit=0 high=1 med=6 low=6; a git failure on a live repository was read as a deleted one. All 13 are fixed in 1fe1c293.
2026-10-30 02:25 | execute | 0011-setup-skill | gate-skip native-contract — same v1-layout refusal on commit 1fe1c293 (harness-name rows on spec files of this feature)
2026-10-30 02:50 | execute | 0011-setup-skill | review r3 — blocking: crit=0 high=0 med=3 low=2; writes to a read-only file failed after the round 2 fix. All 5 are fixed in 2f8e32c7.
2026-10-30 02:50 | execute | 0011-setup-skill | gate-skip native-contract — same v1-layout refusal on commit 2f8e32c7 (harness-name rows and provider-helper names on spec files of this feature)
2026-10-30 03:15 | execute | 0011-setup-skill | decision(D-14) — a settings file whose enabledPlugins is not an object stops the takeover
2026-10-30 03:25 | execute | 0011-setup-skill | review r4 — blocking: crit=0 high=0 med=2 low=3; a read-only file could not be replaced on Windows. All 5 are fixed in 2f79aedc.
2026-10-30 03:25 | execute | 0011-setup-skill | gate-skip native-contract — same v1-layout refusal on commit 2f79aedc
2026-10-30 03:45 | execute | 0011-setup-skill | review r5 — blocking: crit=0 high=0 med=0 low=2; the failure path of the file write could skip restoring a read-only mode. Both are fixed in 9c3cd097.
2026-10-30 03:45 | execute | 0011-setup-skill | gate-skip native-contract — same v1-layout refusal on commit 9c3cd097
