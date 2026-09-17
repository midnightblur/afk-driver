C:\Users\mvu\PersonalProjects\afk-driver-research-enhancement@d8ca9b44ea2275ac04ca61f6dc05b715f892c5f0 · closed-with-frontier · boundaries 13/14 · unverified 1 (load-bearing 0) · ledger: docs/afk/research-enhancement/investigations/INV-008-registry-gates-and-pointers/COVERAGE.json

Question: Q1 + Q2 + Q3 — what the manifests, the four Stop gates, the root-doctrine pointer contract and the six caller skills' step lists are; what reaches them; what breaks when the plugin adds a skill dir, an agent file, a root doctrine file, a glossary term, a capability row, or a pointer line in a caller skill.

## Answer

**Q1.** Stop entry `hooks/hooks.json:59` → `stop-gates.sh` (twin `hooks.codex.json:59`). Dispatch: wiring every Stop (`stop-gates.sh:108`); skill-registry when a plugin path moved (`:125`); native-contract when plugin/.agents/.codex moved (`:130`); genericity when a plugin `*.md` moved (`:133`); native-contract again at commit (`precommit-gates.sh:154`). Registries read: `.claude-plugin/plugin.json` `skills[]`+`agents[]` (check A `skill-registry-gate.sh:70-77,88,107-117`), `CLAUDE.md`+`README.md` text (check B `:124-135`), `MANIFEST.md` E-table (check C `:142-177`), `LANGUAGE.md` token in `skills/*/*/SKILL.md` + `agents/*.md` (check D `:183-185`), frontmatter name==dir (check F `:203`, `lib/skill_frontmatter_check.py:82`); `.codex-plugin/plugin.json` `skills[]` (rule C `native-contract-gate.sh:188-196`), `providers/codex/agents/afk-<stem>.toml` (rule D `:200-203`), `CAPABILITIES.md` `Shared hook events/matchers:` lines only (rule E `:208-226`), prose scan of every plugin `.md` (rule A `:79-134`); genericity added-line scan (`genericity-gate.sh:152-160,246-251,290`); wiring referrer scan (`wiring-gate.sh:32-61,155,199`). Pointer contract: `LANGUAGE.md:10-15`, `CLAUDE.md:48`; gate = check D, scope = SKILL.md + agents only. `DECISIONS.md:3`, `INVESTIGATION.md:7` are pointer-by-convention, no gate. Six caller skills each carry the LANGUAGE.md pointer at `SKILL.md:6`; a utility pointer line lands at grill-requirements `:46`, grill-solution `:76`, grill-verification `:55`, review `:38`, adversary `:25`, fix `:28`/`:70`.

**Q2.** Reached by: `hooks.json:59`, `hooks.codex.json:59`, `precommit-gates.sh:154`; `FRESHNESS.md:38-66` rows; `/afk:setup audit` checks 1/4/5/6 (`AUDIT.md:12,62,70,78`); `hooks/README.md:62-64,104`. Tests pin only check F (`scripts/tests/test_skill_frontmatter.py:86`), the hooks twin (`hooks/tests/hook-smoke.sh:243`) and genericity cache/pattern paths (`:269-324`); checks A–E, every native-contract rule, wiring and stop-gates dispatch are unguarded.

**Q3 — same-commit set per artifact kind** (gate → exit 2 unless noted):
- **Skill dir**: `.claude-plugin/plugin.json` `skills[]` (check A `:70`) · `.codex-plugin/plugin.json` `skills[]` (rule C `:188`) · `/afk:<name>` mention in BOTH `CLAUDE.md` + `README.md` (check B `:129`) · LANGUAGE.md pointer line (check D `:183`) · frontmatter name==dir, allowed keys (check F `:203`; rule B `:146`) · prose scans (rule A `:79`; genericity `:156`). Not gated: `CHANGELOG.md` (`FRESHNESS.md:40`), `CAPABILITIES.md:44` row, `CONFORMANCE.md:18` count. SKILL.md is wiring-exempt (`wiring-gate.sh:34`).
- **Agent file**: `plugin.json` `agents[]` (check A `:74`) · `providers/codex/agents/afk-<stem>.toml` (rule D `:200`) · pointer line (check D `:183`) · referrer or IOU (wiring `:34,199`; the manifest entry is the referrer) · prose scans. Not gated: `DELEGATION.md:26,45`, spawning skills (`FRESHNESS.md:61`).
- **Root doctrine file**: referrer or IOU (wiring `:34-35,199`) · rule A + genericity scans. Check D does not cover it. Not gated: `CLAUDE.md:189-201` Reference, `README.md:829`, `FRESHNESS.md:56` row, pointer lines in consuming skills.
- **Glossary term**: no Stop gate (GLOSSARY.md wiring-exempt `:34`; only the two prose scans). Audit check 6 (`AUDIT.md:78`, `scripts/glossary_usage.py:110-130`) needs ≥1 consumer file; `FRESHNESS.md:44`.
- **Capability row**: no gate parses the table (rule E reads `CAPABILITIES.md:26,28` only; file excluded from rule A `:78`); genericity scans the line. Registry-only `FRESHNESS.md:62`.
- **Pointer line in a caller skill**: rule A (`:114` — bare `PLUGIN_ROOT` forbidden), genericity (`:156`), wiring when the target is new (`:155`, the line is the referrer). Audit check 3 requires the path to resolve (`AUDIT.md:40-50`).

## Sites (breaks)
`hooks/skill-registry-gate.sh:70,74,88,113,129,183,203,206` · `hooks/lib/skill_frontmatter_check.py:82` · `hooks/native-contract-gate.sh:79,114,146,188,200,347` · `hooks/genericity-gate.sh:156,251,290,334` · `hooks/wiring-gate.sh:34,155,199` · `.claude-plugin/plugin.json:9,16` · `.codex-plugin/plugin.json:6` · `providers/codex/agents/afk-afk-tracer.toml:1` · `FRESHNESS.md:38,40,42,43,44,52,56,61,62,63,66` · `hooks/README.md:104` · `CLAUDE.md:48,83,189` · `README.md:637,829` · `LANGUAGE.md:12` · `DELEGATION.md:26,45` · `skills/afk/setup/AUDIT.md:12,62,78` · `GLOSSARY.md:9` · `CAPABILITIES.md:21,44`

## Frontier
- B14: harness plugin loaders and marketplaces consume `plugin.json` outside this repository; the configured sites (`hooks/update-notice.sh`, `adapters/forge`, `adapters/tracker/github-issues`) reach the release feed and the live forge/tracker, none reads a registry.

## Unverified
- `c-2d7ed730` (seed claim, not load-bearing): the fold keeps the seed's `unverified` kind over the fragment's `fact` (worst kind wins).

## Inferences
- `c-942e979b`: no cross-commit deployment order exists — every enforced pair is checked on one tree per Stop. `c-7cea50ff`: a regression in check A/B/D or rule C/D fails no suite.

## Tooling notes
- 11,234 of 11,316 nodes were dispositioned by path rule (`reason` starts `rule-classified:`), not read individually; the 82 read nodes carry the answer.
- `merge_fragments.py` folds seed placeholder nodes as conflicts; folded against a staging copy whose nodes were replaced by the fragment's rows (`scratchpad/inv008/staging.json`).
- `seed_map.py` took 60 min for 18 subjects (every declared alias is repeated per subject in one `git grep`, ~19 aliases × 18 subjects); `run.config.sha256` was a real digest, not the empty-string digest.
- Subjects were passed without extensions (`skill-registry-gate`, `README`…) because `name_forms` takes the last dotted segment as the simple name (`seed_map.py:315`); the `.md`/`.sh`/`.json` names went in as `wire=` aliases.
