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
