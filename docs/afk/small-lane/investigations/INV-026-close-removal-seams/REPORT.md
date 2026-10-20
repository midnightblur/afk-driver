midnightblur/afk-driver@d346cfb5b3957f410119b4199dc2184f890d341a · closed-with-frontier · boundaries 13/14 · unverified 0 (load-bearing 0) · ledger: docs/afk/small-lane/investigations/INV-026-close-removal-seams/COVERAGE.json

Untracked universe excluded docs/afk/small-lane/ (process-scoped core.excludesFile); that spec folder is one irrelevant node (B13:docs/afk/small-lane/PRD.md).

| Seam | Existing contract | Planned change (SDD §14) | Impacted | Verdict |
|---|---|---|---|---|
| developer settings | bug/CONFIG.md:37-41 K1-K5, fail-closed rows :59-61 are bug-only operations; DEVELOPER_KEYS afk-config.py:73, unknown key refused :626-637; only mrAssignee maps `none` to unset (:830) | move to CONFIG.md; `none` = unset | test_afk_config_init.py:206 pins mrReviewer `none` literal (breaks); test_afk_config.py:356-380 pins CONFIG.md:136 backticked words; K-ids MANIFEST.md:40,53,213-216 defined only in bug/CONFIG.md; pointers afk-config.py:69, create-worktree:63, CONFIG.md:136, README.md:340, MANIFEST.md:126-127,913-914 | extends |
| skill removed | manifests .claude-plugin/plugin.json:19, .codex-plugin/plugin.json:9; skill-registry-gate.sh:113-119, native-contract-gate.sh:200-208; test_publish_bug.py:30,43 | one commit | gates pass only with folder + both entries gone (pins test_skill_registry_gate.py:57, test_native_contract_events.py:57); test left behind interrupts whole pytest collection (tests.yml:64, exit 2); catalog check B never flags a stale row (AGENTS.md:118) | reworked |
| tracker-writer rule | prose only: AGENTS.md:9,195, README.md:108,117-121, MANIFEST.md:858, GLOSSARY.md:262, SPINOFF-TICKET.md:20, CAPABILITIES.md:65; server.py:96-176 no caller check | one writer, adr/0008 | report-issue writes via gh (publish.sh:267,287) to report-issue.repository | extends |
| registries | FRESHNESS.md:77-80,86 (row 79 also owns scripts/create-worktree; row 78 says K1-K4); MANIFEST H2 :66-67, H6 :126-132, S1 :741, W2 :913-914 | delete or edit rows | H2, S1 must be edited (jira/adapter.json:27-30, check E); deleting H6 heading reds test_setup_h6_probe.py (12 tests, :24) | reworked |
| commit check | GATES plugin-source-gates.sh:97, dispatch :269-271, control list :186-188; check M native-contract-gate.sh:738-760 forces bounded_scan.py | new gate, excludes CHANGELOG + spec folders | GATES string pinned test_plugin_source_gates.py:33,313-314, test_behavior_registry_gate.py:70; hooks/README.md:82, AGENTS.md:228; residual mentions glossary_usage.py:28-31, test_glossary_usage.py:96,132, test_tracker_create_assignee.py:3 | extends |
| release gate | release-gate.sh:91-95 checks version agreement only; MAJOR is the human's (CHANGELOG.md:23-27); update-notice.sh:123-150 surfaces Migration (no test) | major + Migration line | .claude/bugs and fixer worktrees lose their purge owner (gc/SKILL.md:89-90) | fits |

Dependents the first-pass forms missed (claim c-0a48d0f3): providers/PARITY.md:18,20,47; README.md:108,117,120,778; agents/afk-implementor.md:3,9; gc/SKILL.md:89; GLOSSARY.md:252,261,264,271; MANIFEST.md:40,53,213,215; test_publish_bug.py:30.

Landmines
- mrReviewer and change-reviewers lose their only reader (bug/SKILL.md:68, FIXER-PROMPT.md:13,33); setup still requires a reviewer (developer_values.py:148, MANIFEST.md:156).
- K3/K4 surviving reader create-worktree:239,251 runs only in --branch/--dir mode and falls back (:241-247), never fails closed.
- Glossary pin (test_glossary_usage.py:160) guards only GLOSSARY.md:255,258,267 (S1-S10, Evidence bundle, Retester): keeping those entries after the folder goes turns it red; the other Bug pipeline lines are unguarded.
- Glossary test already red on the tracked tree: 5 small-lane terms used only in the untracked spec folder (glossary_usage.py:108-121 walks the filesystem).
- tracker_api.load loses its only test (test_publish_bug.py:43); publish_bug-only behaviours unguarded until bug mode has tests.
- SDD row 565 "8 terms + One-live-fixer": the section has 8 headings, One-live-fixer included. GLOSSARY-FORMAT.md:35 uses it as its example.
- A check forbidding ADR-0001 hits docs/afk/protected-branch-guard (own ADR-0001). PARITY.md:18 totals already disagree with its table. skills/afk/AGENTS.md:7 points at a missing tasks/afk-bug/.

Frontier (B14): harness loaders, installed caches, consuming repositories' .claude/bugs, developers' user config, live tracker items.
