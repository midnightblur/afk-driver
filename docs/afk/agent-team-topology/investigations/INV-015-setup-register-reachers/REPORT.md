C:\Users\mvu\PersonalProjects\afk-driver-agent-teams@7e9c87a · closed-with-frontier · boundaries 13/14 · unverified 1 (load-bearing 0) · ledger: docs/afk/agent-team-topology/investigations/INV-015-setup-register-reachers/COVERAGE.json

## Answer

Three gates read or scan skills/afk/setup/MANIFEST.md, and all three run on Stop. skill-registry-gate check C blocks a hook-read environment variable that the register lacks (hooks/skill-registry-gate.sh:142, :172, :222). adapter_registry_check.py requires each row id in an adapter.json `register` array to exist as a register heading (hooks/lib/adapter_registry_check.py:36, :113-116); its only caller is hooks/skill-registry-gate.sh:194. native-contract-gate check A scans the register with every plugin .md, and hooks/native-contract-allow.txt pins 15 register lines as exceptions (hooks/native-contract-gate.sh:80). Dispatch: hooks/hooks.json:59 and hooks/hooks.codex.json:59 → hooks/stop-gates.sh:125, :130; also hooks/precommit-gates.sh:154, installed by hooks/install-git-hooks.sh:103. /afk:setup reads the register as its whole dependency set (skills/afk/setup/SKILL.md:48); /afk:setup audit diffs references against it (skills/afk/setup/AUDIT.md:33-38, :52-55, :72). install_block.py has one invoker, the H7 fix at skills/afk/setup/MANIFEST.md:146; its default sentinel block is skills/afk/setup/PLAIN-LANGUAGE.md:10-31. Config key `setup.extra` adds register rows (scripts/afk-config.py:121, CONFIG.md:103, MANIFEST.md:610). No test reads the register, runs install_block.py, or runs either register check: all unguarded (c-afcfd00d; c-45be1f34, inferred from a whole-tree search).

## Sites

Traced (the reach path): hooks/hooks.json:59 · hooks/stop-gates.sh:125, :130 · hooks/precommit-gates.sh:154 · hooks/skill-registry-gate.sh:142, :194 · hooks/lib/adapter_registry_check.py:36, :113, :114 · hooks/native-contract-gate.sh:80 · scripts/afk-config.py:121 · skills/afk/setup/MANIFEST.md:146.

Terminal, executable or data:
- hooks/skill-registry-gate.sh:15, 17, 18, 28, 29, 46, 138, 172, 222 · hooks/lib/adapter_registry_check.py:4, 15, 36, 112, 116, 117 · hooks/hooks.codex.json:59 · hooks/install-git-hooks.sh:12, 103 · hooks/branch-name-gate.sh:5 · hooks/genericity-gate.sh:156 (generic .md scan)
- hooks/native-contract-allow.txt:17, 20-28, 33-40, 58
- adapter.json register arrays: adapters/build-gate/maven:26, build-gate/npm:21, forge/github:32, forge/gitlab:32, forge/none:30, notes/notion:21, notes/obsidian:22, notes/repo-files:21, tracker/github-issues:25, tracker/jira:27, tracker/none:23
- skills/afk/setup/SKILL.md:3, 8, 13, 18, 19, 25, 48, 53, 54, 58, 71, 72, 74, 88, 97 · AUDIT.md:1, 33, 36, 37, 49, 52, 70, 72 · MANIFEST.md:1, 5 · PLAIN-LANGUAGE.md:3, 10, 31 · LAVISH-SESSIONS.md:3 · INVESTIGATION-SESSIONS.md:3 · scripts/install_block.py:4, 25 · scripts/setup_secrets.py:4, 14, 240 (P3), 330 (H2)
- scripts/afk-config.py:55, 948 · scripts/tests/test_afk_config.py:250 (pins the key set) · scripts/tests/samples/monorepo-config.yaml:81, 83 · .claude-plugin/plugin.json:34 · .codex-plugin/plugin.json:24

Terminal, names only (no read, no invocation): scripts/tests/test_skill_frontmatter.py:90 · hooks/tests/envelopes/claude/pretooluse-bash-danger.json:7, -safe.json:7 · hooks/tests/envelopes/codex/pretooluse-bash-danger.json:8, -safe.json:8 · skills/afk/execute/SKILL.md:57 · skills/afk/bug/CONFIG.md:27 · skills/utils/diagnose/SKILL.md:39.

Terminal, documents: ADAPTERS.md:22, 24, 144, 148 · CLAUDE.md:11, 73, 104, 177, 190, 201 · AGENTS.md:73, 104, 177, 190 · CONFIG.md:103, 107 · FRESHNESS.md:15, 25, 26, 47, 52, 53, 57, 58, 59, 66, 74 · GLOSSARY.md:120-122, 333 · PROVIDERS.md:46 · README.md:248, 258, 278, 314, 320-322, 542, 543, 740, 742 · hooks/README.md:62, 81, 104 · providers/CONFORMANCE.md:31, 173, 272, 302 · providers/PARITY.md:62, 111 · skills/afk/to-ticket/SKILL.md:29 · skills/utils/draw-charts/SKILL.md:15 · skills/afk/mission-control/DIGEST-FORMAT.md:98 · CHANGELOG.md:232, 316, 320, 493, 514, 609, 614, 619, 653, 679, 684, 784, 822, 856, 1061, 1133, 1143, 1191, 1301, 1436, 1490, 1491, 1497, 1511, 1512, 1518, 1533, 1539, 1615, 1621, 1652 (historical).

Terminal, feature spec (docs/afk/agent-team-topology/): GRILL-LOG.md:125, 161, 219, 222, 239, 273, 279, 291, 296, 297, 301, 355, 364 · PRD.md:90 · grill-requirements.round.json:385, 386 · grill-solution.round.json:236, 247, 248, 1542, 2359, 2503, 2506, 2588 · grill-solution.html:398, 791 · investigations/INV-007-setup-offer/REPORT.md:7, 17, 38 · research/BRIEF.md:13, 43 · CRITIQUE-claude.md:58 · FACTS-claude.md:18, 45, 46, 47, 49 · PROPOSAL-claude.md:14, 177, 191, 233 · PROPOSAL-codex.md:229 · VERDICT-claude.md:51.

## For the design

- S-64 (GRILL-LOG.md:239, grill-solution.round.json:1542) is refuted in part (c-dfc23055). It says the register changes only for a new environment variable, and that every registration duty is gate-enforced. The gate blocks only a hook-read variable (hooks/skill-registry-gate.sh:142-177). FRESHNESS.md:13-15 also requires rows for new tools, MCP servers, secrets and sibling paths, which no gate enforces. adapter_registry_check.py:112-116 enforces adapter-named rows. The planned multiplexer row (GRILL-LOG.md:279, :291, :297) is not an environment variable. Outside this ledger: S-125 (R-35) corrected S-64's wording in the grill record.
- Confirmed by code: GRILL-LOG.md:222 (check C location), GRILL-LOG.md:359 (the register holds probes, not stored findings; MANIFEST.md:8-12), INV-007 REPORT.md:7, :17, :38 (install_block.py:1-41 only replaces a block; no remove mode; no test).
- The multiplexer row (S-92, S-98, S-108, HL-5 E8, HL-6 C9-C17; PRD.md:90 AC-028) fits the existing [opt-in] row shape at MANIFEST.md:26-31 (c-3237d95f).

## Frontier

- B14: another repository, a deployment manifest, or a live consumer. Nothing in this repository can show it.

## Unverified

- c-e00426cf: the hit set holds every reference over the name forms searched. Not load-bearing. 10 complete counter-searches, 2 of kind agent, widened the forms.
