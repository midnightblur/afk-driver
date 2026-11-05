# Grill log — #159

## Requirements grill

- Ledger: The rendered tooltip dictionary currently merges seed terms, plugin glossary terms, repository glossary terms and PAGE-TIPS.md → verified (afkv2/engine/shell/inject.py:127-136)
- Ledger: afkv2.page/0 has no page-owned tips field and its schema is frozen → verified (afkv2/engine/schema/page-v0.schema.json:5-13)
- Ledger: A card renders its title and id as separate plain spans, so its id does not inherit the title as a tip → verified (afkv2/engine/components/base_card.py:89-100)
- Ledger: The browser promotes authored title or data-tip text and can propagate a tipped single-token id to later text occurrences → verified (afkv2/engine/shell/tips.js:63-87)
- Ledger: The prior requirements choice makes page-owned feature-term and id tips in scope and leaves the missing-tip coverage audit out → verified (docs/afk/158/GRILL-LOG.md:41)
- Ledger: PAGE-TIPS.md has no repository writer and is referenced only by the loader and one test fixture → verified (afkv2/engine/shell/inject.py:4,21,135; afkv2/tests/engine/test_engine_core.py:917-927)
- Staples: none
- Term: Page feature term → verified (GLOSSARY.md)
- Term: Page id tip → verified (GLOSSARY.md)
- Policy: page reader resolving a term or id → permitted people with page access; denied people without page access; scope page-owned tips first and shared glossary fallback second; validation exact ids beat term matches, unmatched text stays plain, no hover-time fetch
- Policy: page author supplying tips → permitted page-document writers; denied readers and people without page write access; scope this page document; validation one non-empty key and one non-empty plain-text value per entry, same-catalog match collisions name the field
- Policy: legacy page/0 rendering → permitted existing page/0 documents and adjacent PAGE-TIPS.md; denied new page-owned-tip documents from reading the sidecar; scope legacy page/0 only; validation current rendering meaning stays unchanged and needs no migration
- Examples: frequent: `settle loop` maps to its definition and every visible term shows it; edge: `AC-001` in a card and summary shows one title while `ac-001` stays plain; risky: an exact id `card` beats a same-token feature term, the page definition beats the shared glossary, and `<b>unsafe</b>` displays as text
- Session: s-20261104-160923 · page document pages/grill-s-20261104-160923.json
- Settled: What compatibility result must this feature preserve? Recommended: A. The schema explicitly freezes page/0, so old documents should keep rendering with their current meaning. · settled by mark a R1 · card r1-compatibility
- Settled: Confirm this definition: A page feature term is a term whose meaning is specific to this page's feature. The page document carries the term and its plain-language definition. Repository and plugin glossary tips remain available as shared context. · settled by mark accept R1 · card r1-feature-term
- Settled: Confirm this definition: A page id tip maps one page identifier, such as a card, acceptance criterion or worked-example id, to the title of the thing it names. Every visible occurrence of that identifier can show the same title on hover. · settled by mark accept R1 · card r1-id-tip
- Settled: Recommended: the page still renders, and an unmatched term or id stays plain. Refusing pages with missing tips remains the later coverage-audit work that #159 excludes. · settled by mark accept R1 · card r1-missing-tip
- Settled: Recommended policy: anyone already permitted to open the page sees its authored tips. A person denied access to the page gets no tip data. Tips do not fetch another page, repository file or external system at hover time. · settled by mark accept R1 · card r1-access
- Settled: The reader outcome follows the binding choice from #158. · decided-by agent R1 · accepted 2026-11-04 · repo: docs/afk/158/GRILL-LOG.md:41 · reverse: Reopen the accepted #158 scope and remove both page-owned tip requirements. · card r1-reader-outcome
- Settled: The page document is the source for feature-local meanings. · decided-by agent R1 · accepted 2026-11-04 · repo: docs/afk/158/GRILL-LOG.md:41; afkv2/engine/shell/inject.py:127-136 · reverse: Restore an external feature-tip artifact and define a reachable writer and lifecycle for it. · card r1-data-boundary
- Settled: The ticket and prior decision already place two items outside this change. · decided-by agent R1 · accepted 2026-11-04 · spec: #159 description; docs/afk/158/GRILL-LOG.md:41 · reverse: Expand #159 and re-grill the added behavior, failure paths and acceptance criteria. · card r1-out-of-scope
- Settled: Recommended validity walk: an existing page/0 document and its adjacent PAGE-TIPS.md keep the current rendered tips. It needs no migration. New page-owned tips replace the sidecar as the authoring path for the new capability. · settled by mark accept R2 · card r2-legacy-sidecar
- Settled: Recommended: each authored term or id has one non-empty key and one non-empty plain-text tip. A malformed or duplicate entry fails page validation and names the field to repair. A term or id with no authored entry is not malformed in #159; it stays plain. · settled by mark accept R2 · card r2-validation
- Settled: Recommended: a page id matches its complete identifier with the same case, so AC-001 does not rename ac-001. A page feature term follows the existing term-tip behavior, including safe word boundaries and the current lowercase/plural handling. · settled by mark accept R2 · card r2-matching
- Settled: Confirm the repair policy: old page/0 documents require no repair; an author repairs a malformed new tip entry in the page document named by validation; a missing tip needs no repair until the later coverage-audit work. · settled by mark accept R2 · card r2-repair-paths
- Settled: Confirm these end-to-end examples. · settled by mark accept R2 · card r2-examples
- Settled: The page-specific source resolves a same-key conflict. · decided-by agent R2 · accepted 2026-11-04 · spec: The accepted R-1 data boundary makes the page document the source for feature-local meanings; afkv2/engine/shell/inject.py:127-136 already gives the feature source last precedence. · reverse: Reverse the dictionary merge order and document that shared terms cannot be specialized by a page. · card r2-precedence
- Settled: The current tooltip box writes its value through textContent. · decided-by agent R2 · accepted 2026-11-04 · repo: afkv2/engine/shell/tips.js:94-105 · reverse: Define an allowed rich-text format, sanitizer and security tests before enabling markup. · card r2-display-safety
- Settled: Devil finding: the accepted rules could make one omitted page term both tipped by a shared glossary and plain. · decided-by agent R3 · accepted 2026-11-04 · spec: Accepted cards r1-feature-term, r1-missing-tip and r1-access retain shared glossary fallback while excluding a missing-tip gate. · reverse: Remove shared fallback from pages and state that page documents must repeat every wanted tip. · card r3-shared-fallback
- Settled: Devil finding: separate term and id entries can match the same visible token, and 2 term entries can overlap under term matching. · decided-by agent R3 · accepted 2026-11-04 · spec: Accepted cards r1-id-tip and r2-matching give ids exact identity; r2-validation requires malformed or duplicate entries to fail with a repair field. · reverse: Choose another explicit precedence rule and update the collision examples and validation contract. · card r3-collision-rule
- Settled: Devil finding: a retained PAGE-TIPS.md beside a new document could otherwise override or add stale feature meanings. · decided-by agent R3 · accepted 2026-11-04 · spec: Accepted card r2-legacy-sidecar preserves the sidecar for page/0 only; r1-data-boundary makes the new page document authoritative. · reverse: Define a merge order and lifecycle for sidecars on new documents. · card r3-sidecar-boundary
- Devil: pass ran; shared fallback now applies before unmatched text stays plain; same-catalog collisions fail and an exact id beats a term; PAGE-TIPS.md is limited to legacy page/0
- Settled: exit gate passed 2026-11-04 · session s-20261104-160923

## Solution design

- Premise: afkv2.page/0 is frozen and rejects a new top-level tips field; a compatible change needs a new schema value, file and reader → verified (afkv2/engine/schema/page-v0.schema.json:3-13; afkv2/engine/engine.py:52-82)
- Premise: The page JSON is persisted source state and generated HTML is replaceable derived state → verified (afkv2/engine/engine.py:231-292; afkv2/engine/shell/page.py:157-178)
- Premise: The shared round builder is the only production page-document constructor; new sessions are v0 and resumes refuse another schema → verified (afkv2/skills/grill/scripts/round_document.py:23,334-361)
- Premise: Grill, propose-solution and to-subtasks share the same page-document constructor → verified (afkv2/skills/propose-solution/scripts/design_round.py:170-183; afkv2/skills/to-subtasks/scripts/plan_files.py:386-409)
- Premise: The engine registry already maps each schema value to a schema file and reader → verified (afkv2/engine/engine.py:52-82; afkv2/tests/engine/test_engine_core.py:393-412)
- Premise: The page builder receives the checked document, but tooltip dictionary loading receives only the HTML path → verified (afkv2/engine/engine.py:284-290; afkv2/engine/shell/page.py:157-178)
- Premise: Opening rendered HTML reinjects the replaceable tooltip block from path-based sources → verified (afkv2/engine/launcher.py:59-82,285-298; afkv2/engine/shell/inject.py:184-194)
- Premise: The engine already inventories every card, component and map-node ID and refuses duplicates with a field location → verified (afkv2/engine/engine.py:118-143)
- Premise: The current flat runtime dictionary cannot keep lowercase page IDs case-sensitive because lowercase keys receive case-insensitive fallback → verified (afkv2/engine/shell/tips.js:8-29)
- Premise: Current dictionary precedence is seed, plugin glossary, repository glossaries, then the legacy sidecar; later sources win → verified (afkv2/engine/shell/inject.py:117-136)
- Premise: Hover reads local DOM data, writes the tip through textContent and makes no network request → verified (afkv2/engine/shell/tips.js:89-105)
- Premise: The tooltip runtime has no total catalog or page-size bound; it skips text nodes over 50000 characters and debounces mutation rescans by 300 ms → verified (afkv2/engine/shell/tips.js:31-34,264-270)
- Premise: No database, service state, new endpoint or separate authorization guard exists for page tips; access stays at the page host boundary → verified (afkv2/engine/engine.py:300-327; afkv2/engine/shell/tips.js:2-6,89-105)
- Premise: The current test suite has no direct DOM behavior coverage for page-tip precedence, exact IDs, wrapping, hover or mutation recovery → verified (counter-search of afkv2/tests for data-afkv2-tip, promote, harvest and tipFor; afkv2/tests/engine/test_engine_core.py:917-931)
- Premise: All likely change surfaces are owned by this repository configuration → verified (.afkv2/config.json:2-5)
- Settled: design gate passed 2026-11-04 · session s-20261104-182229
- Premise: The page-tip resolver and browser fixture use browser-neutral standard DOM APIs → verified (afkv2/engine/shell/tips.js:1-89; afkv2/tests/live/page_tip_browser.html:10-80)
- Premise: Installed Chrome is available at C:/Program Files/Google/Chrome/Application/chrome.exe and Node v24.18.0 is on PATH → verified (Get-Command node; Test-Path chrome.exe, 2026-11-04)
- Premise: The Computer Use browser host is unavailable in this session, so the proof needs a local Chrome DevTools Protocol driver → verified (cua.getState, 2026-11-04)
- Settled: design gate passed 2026-11-05 · session s-20261104-221155
