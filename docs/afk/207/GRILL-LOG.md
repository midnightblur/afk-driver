# Grill log — 207

## Requirements grill

- Round 0: "use lavish natively, without afkv2's own engine to use lavish for grilling. this is a different use case\nbring in design-system as well\nof course PROTOTYPE.MD should be consumed by propose-solution and propose-verification (for e2e, uat tests)\n"
- Ledger: Lavish can host a self-contained drivable HTML mockup natively, outside the afkv2 page engine, with element annotations returned to the agent → verified (afkv2/engine/launcher.py:61-99 takes any .html; lavish-axi 0.1.86 dist/cli.mjs:5708-5744 returns selector, tag, text per note)
- Ledger: v1 design-system can be ported to afkv2 alongside prototype → verified (skills/afk/design-system/SKILL.md:41-99; afkv2 browser driver afkv2/skills/setup/scripts/tools.py:42-45; publish needs claude.ai/design tools afkv2 does not provision)
- Ledger: propose-solution and propose-verification can consume PROTOTYPE.md (verification: e2e and UAT tests) → verified (afkv2/skills/propose-solution/SKILL.md:35-43; afkv2/skills/propose-verification/SKILL.md:36; levels ui-e2e and acceptance afkv2/skills/propose-verification/VERIFICATION-FORMAT.md:30)
- Ledger: afkv2 has no PreToolUse guard against a direct lavish-axi call → verified (afkv2/hooks/hooks.json: SessionStart, Stop, SubagentStart only)
- Ledger: The afkv2 SDD has no UI or UX section; its headings are fixed and gated → verified (afkv2/skills/propose-solution/SDD-FORMAT.md:4,22-138)
- Ledger: The INDEX.md template already holds a Prototype row with no writer → verified (afkv2/skills/to-prd/INDEX-FORMAT.md:24)
- Ledger: A page document's session.skill is a frozen enum without prototype → verified (afkv2/engine/schema/page-v2.schema.json:5,67-68)
- Ledger: No STAPLES.md exists in this repository → verified (rg --files for STAPLES.md under repo root: none)
- Staples: none
- Term: Mockup → verified (afkv2/GLOSSARY.md)
- Term: Design catalog → verified (afkv2/GLOSSARY.md)
- Term: Anchor → verified (afkv2/GLOSSARY.md)
- Term: Capability walk → verified (afkv2/GLOSSARY.md)
- Spinoff: afkv2 chain order omits propose-verification (afkv2/GLOSSARY.md:8; propose-solution SKILL.md:184 names to-subtasks next) → readers follow a wrong order; out because it is not part of the prototype port
- Policy: Developer runs prototype (us-1 to us-4, us-8) → permitted developer at the keyboard; denied hands-off subagent (opens no page, parks); scope unscoped; validation synthetic fixtures only, mockup opens as file:// with no network call, repo file free of lavish runtime
- Policy: Developer runs design-system (us-5) → permitted developer at the keyboard; denied hands-off subagent; scope one frontend per run, named in repo config; validation synthetic data only, secret scan on every written file
- Policy: propose-solution and propose-verification read PROTOTYPE.md (us-6, us-7) → permitted the skill in its own run; denied any writer of PROTOTYPE.md other than prototype; scope the ticket spec folder; validation input optional, absent file changes nothing
- Examples: ex-1 frequent: new list screen, catalog and live block present, 2 stories, 12 synthetic orders, live-verified; ex-2 edge: no live block, no catalog, no lavish host, source-only, notes in chat; ex-3 risky: live page shows real customer names, fixtures stay synthetic, secret scan before commit; ex-4 edge: backend-only feature, prototype stops no_ui, writes nothing
- Devil: pass ran (provider codex, model gpt-6-luna); open-pain: stakeholder review of a chosen mockup not settled → resolved R3 card i-devil-share: sharing out of scope, the committed HTML file opens in any browser
- Session: s-20261120-211919 · page document pages/grill-s-20261120-211919.json
- Settled: **Verdict:** two pains. (1) afkv2 cannot settle new UI before the design, so screen choices are redone late. (2) Notes in chat lose which element you meant; a note pinned on the mockup keeps it. Is this the pain, or is there more (for example, sharing with stakeholders)? · settled by mark accept R1 · card i-pain
- Settled: Is anyone missing, such as a designer who drives the mockup? · settled by mark accept R1 · card i-actors
- Settled: **My reading:** lavish shows the **mockup HTML file itself**, with no page document, no cards, no rounds. Your notes come back pinned to elements. The lavish **pin and host-safety checks still apply**, through the existing launcher or a thin command beside it. Is that what you meant? · settled by mark accept R1 · card i-native
- Settled: **My reading:** lavish is the **default** when its host runs. You can say "chat only" at any time. When the host is not available, the skill gives you the file path to open in a browser and takes your notes in chat. The file always opens as a plain `file://` page. Or do you want lavish **off by default**, turned on per run? · settled by mark accept R1 · card i-optional
- Settled: Where does the design-system catalog live, which the prototype reads first? · settled by mark b R1 · card i-ds-home
- Settled: v1 let you push the chosen mockup to claude.ai/design for a shareable link. Holds if the catalog card picks B. · settled by mark b R1 · card i-share
- Carried: You decided earlier to add a logic and state-model branch from LOGIC.md to the prototype. Does it ship with this port? · card i-logic
  owner note on i-logic (N-1-i-logic-1): "skip"
- Settled: **Verdict:** afkv2 has no term **UAT**. Its verification levels already hold `ui-e2e` (a user journey through the real screen and backend) and `acceptance` (does what was meant, in business words). I read your "e2e, uat" as these two levels, and add no new term. · settled by mark accept R1 · card i-uat
- Settled: Both readers take PROTOTYPE.md when it exists and run as today when it does not. · decided-by agent R1 · accepted 2026-11-20 · repo: afkv2/skills/to-prd/INDEX-FORMAT.md:24 holds the Prototype row with no writer; v1 prototype self-gates no_ui (skills/afk/prototype/SKILL.md:14). · reverse: Make the input required in both start scripts and their tests. · card i-readers
- Settled: The afkv2 SDD has fixed headings and no UI section. How do the screen decisions of PROTOTYPE.md reach the design? · settled by mark a R1 · card i-sdd
- Settled: Correct any definition with a note on its row. · settled by mark accept R1 · card i-terms
- Settled: **My reading of your note "skip":** the branch is **out of this ticket**, and I file **no spinoff** now. · settled by mark accept R2 · card i-logic-2
- Settled: The catalog option you picked said a push to claude.ai/design stays an **opt-in extra**. The share card you picked **drops** the push. Which holds? · settled by mark a R2 · card i-claude-design
- Settled: Both skills reuse what afkv2 already has to start the app. · decided-by agent R2 · accepted 2026-11-20 · repo: `afkv2/scripts/afkv2_config.py:140-170` reads the `live` block; `afkv2/scripts/live_build.py:83` starts it. · reverse: Add a separate app-address input to both skills. · card i-live
- Settled: **My reading:** one catalog **per frontend**. The repo config names each frontend's **source path** and its **catalog folder**, so neither skill asks each run. The exact keys are a design choice. Today no config key names a frontend path. · settled by mark accept R2 · card i-catalog-find
- Settled: **Verdict:** the 8 stories in the stories block cover prototype, chat fallback, settle, design-system, both readers and the no-UI stop. Note a story to change it; name a missing one. · settled by mark accept R2 · card i-stories
- Settled: `afkv2/skills/use-lavish/SKILL.md:14`; `afkv2/engine/launcher.py:283-287` · settled by mark accept R2 · card i-policy
- Settled: **Verdict:** the examples block holds a new list screen (frequent), no app and no catalog (edge), and real records on the live page (risky). Note an example to change it. · settled by mark accept R2 · card i-examples
- Settled: **Finding from the second-opinion check (Codex):** the pain leaves open whether stakeholders must review a chosen mockup. **My reading:** sharing is **not a pain of this ticket**. The chosen mockup is one self-contained HTML file committed on the branch; anyone opens it in a browser from the change, with no tool. A hosted share link is a later ticket, if a real need shows up. Override if stakeholders must review in this ticket. · settled by mark accept R3 · card i-devil-share
- Settled: **Verdict:** the new edge example (a backend-only feature) covers the last story without one: the prototype stops with `no_ui`, writes nothing and leaves the INDEX row untouched. · settled by mark accept R4 · card i-ex-noui
- Settled: exit gate passed 2026-11-24 · session s-20261120-211919
- Last pass: R4 · session s-20261120-211919

## Solution design

- Premise: launcher.run injects the afkv2 tips block into the original HTML file on every open → verified (afkv2/engine/launcher.py:296-300; afkv2/engine/shell/inject.py:206-216,257-267; tests/engine/test_page_tip_injection.py:77-110)
- Premise: launcher opens any existing .html with no page document, checks pin 0.1.86 and refuses LAVISH_AXI_HOST → verified (afkv2/engine/launcher.py:34,61-107,136-154)
- Premise: lavish-axi poll returns prompts with selector (5 parts, cut at nearest id), tag and text (240 chars) → verified (lavish-axi 0.1.86 dist/cli.mjs:5708-5734,9404-9419,13172-13193)
- Premise: engine poll without a page document keeps only the note words in raw; selector, tag and text stay only in prompts → verified (afkv2/engine/engine.py:625-672; afkv2/engine/prompt_lines.py:130-227)
- Premise: Codex Stop hook needs a waiting record, written only by engine show; with no document it returns note words without selectors → verified (afkv2/hooks/codex_stop.py:39-47,81,118-136; afkv2/engine/launcher.py:431-445; afkv2/engine/engine.py:548)
- Premise: No script can tell a hands-off run from a developer at the keyboard; the rule is an instruction → verified (afkv2/skills/use-lavish/SKILL.md:14; afkv2/skills/autopilot/scripts/walk.py:144; tests/engine/fixtures/v0-page-with-notes.json:956)
- Premise: read_config ignores unknown top-level keys and refuses unknown keys inside live; setup repo_config and live_build are the only config writers → verified (afkv2/scripts/afkv2_config.py:97-146; afkv2/skills/setup/scripts/repo_config.py:158-171; afkv2/scripts/live_build.py:407-416)
- Premise: live_build exposes start_live/stop_live for a skill to hold the app up during a run → verified (afkv2/scripts/live_build.py:83-127; pattern afkv2/skills/small-change/scripts/small_lane.py:275-293)
- Premise: engine/notices.py scan_files scans any file list for secrets with stdlib only → verified (afkv2/engine/notices.py:21-24,154-176; precedent afkv2/skills/create-change-request/scripts/ci_watch.py:473-477)
- Premise: design_files.py start and verification_files.py start answer fixed dicts where an optional prototype path can be added; VERIFICATION rows trace by criteria and story columns → verified (propose-solution/scripts/design_files.py:136-140; propose-verification/scripts/verification_files.py:180-207,47; VERIFICATION-FORMAT.md:27-28,53,67)
- Premise: A new afkv2 skill registers by its folder; plugin_check bans v1 names and duplicate module names → verified (afkv2/.claude-plugin/plugin.json; afkv2/scripts/plugin_check.py:88-134; tests/test_module_names.py:22)
- Premise: No afkv2 skill or script calls the chrome-devtools MCP tools by name; setup installs chrome-devtools-mcp 1.10.1 → verified (afkv2/skills/setup/scripts/tools.py:41-47; rg mcp__chrome-devtools afkv2/skills: none)
- Settled: design gate passed 2026-11-24 · session s-20261124-211045
- Last pass: R2 · session s-20261124-211045
