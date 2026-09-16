C:\Users\mvu\PersonalProjects\afk-driver-research-enhancement@d8ca9b44ea2275ac04ca61f6dc05b715f892c5f0 · closed-with-frontier · boundaries 13/14 · unverified 1 (load-bearing 0) · ledger: docs/afk/research-enhancement/investigations/INV-004-manifests-gates/COVERAGE.json

Question: Q3 + Q5 — which gates, scripts and registry files must change in the same commit when the plugin adds skills `research` + `consult`, agent `afk-researcher`, root doc `RESEARCH.md`, capability `web_access`, and pointer sections in DECISIONS.md / DELEGATION.md / INVESTIGATION.md; what breaks if one is missed. Design-phase run.

## Answer

Gate-enforced (Stop exit 2, or a silent loader drop) — same commit:
- `.claude-plugin/plugin.json` `skills[]` + `agents[]` — `hooks/skill-registry-gate.sh:70-77,107-117` (check A). Missed: orphan, exit 2; without the gate the loader never registers the skill/agent.
- `.codex-plugin/plugin.json` `skills[]` — `hooks/native-contract-gate.sh:188-196` (rule C; no agents array there).
- `providers/codex/agents/afk-afk-researcher.toml` — `hooks/native-contract-gate.sh:200-203` (rule D); shape: `providers/codex/agents/afk-afk-tracer.toml`.
- `/afk:research` and `/afk:consult` mention in BOTH `CLAUDE.md` and `README.md` — `hooks/skill-registry-gate.sh:124-135` (check B). No pre-existing `research`/`consult` mention, so no false pass.
- `LANGUAGE.md` pointer line in each new `SKILL.md` and in `agents/afk-researcher.md` — `hooks/skill-registry-gate.sh:183-185` (check D).
- Frontmatter: `name` == directory, only Agent-Skills/Claude keys — `hooks/lib/skill_frontmatter_check.py:82`, `hooks/native-contract-gate.sh:139-162`; pinned by `scripts/tests/test_skill_frontmatter.py:86`.
- Prose scans every new `.md` must pass: `hooks/native-contract-gate.sh:79-134` (harness names, `mcp__`, SendMessage/subagent_type, bare PLUGIN_ROOT; WebSearch/WebFetch not in the regex), `hooks/genericity-gate.sh:156` (ticket ids, product files, person names), `hooks/wiring-gate.sh:34,155` (`RESEARCH.md`, the agent file, and non-SKILL siblings need a referrer token or an IOU; the CLAUDE.md Reference line wires `RESEARCH.md`, the plugin.json entry wires the agent).

Registry-required, not gate-enforced (only `/afk:setup audit` or a human catches it):
- `skills/afk/setup/MANIFEST.md:536-543` O5 — "exactly these five" stub list + "all five stubs" prose.
- `PROVIDERS.md:23` Spawn-AFK-role roster; `DELEGATION.md:26` named types + `:45` tier for the new role.
- `providers/CONFORMANCE.md:18` skill count (40 → 46 manifest entries) and a per-agent probe row (`:26` precedent).
- `CHANGELOG.md` `[Unreleased]` line (`FRESHNESS.md:40`); `FRESHNESS.md` gains a row for `RESEARCH.md` (`:56`); `CLAUDE.md:183-199` Reference list + `README.md:829` root-doc list; `GLOSSARY.md` entries for minted terms (`FRESHNESS.md:44`, audit check 6); `CAPABILITIES.md:7-22` `web_access` row + `:37-44` Skill-requirements row (`FRESHNESS.md:62`); the skills that spawn the agent (`FRESHNESS.md:61`).

Unchanged: `.claude-plugin/marketplace.json` (version/description until release or chain-shape change), `.agents/plugins/marketplace.json`, `hooks/release-gate.sh` + `.github/workflows/release-gate.yml` (version equality only), `hooks/hooks.json`, MANIFEST E-table (no new hook env var), `INVESTIGATION.md` lockstep partners (`FRESHNESS.md:47`; a pointer-only section changes no class/checklist), `DECISIONS.md` pointing surfaces (`FRESHNESS.md:51`; classification + grammar intact).

Q5: none of `research`, `consult`, `afk-researcher`, `afk-afk-researcher`, `web_access`, `RESEARCH.md` exists in plugin source — absent over B1–B13 (tracked + untracked, docs/ excluded; counter query `q-*` in the ledger, 0 lines). Only the feature's own `docs/afk/research-enhancement/` artifacts name them.

## Sites (breaks)
`hooks/skill-registry-gate.sh:70,74,129,183,203` · `hooks/lib/skill_frontmatter_check.py:82` · `hooks/native-contract-gate.sh:79,139,188,201` · `hooks/wiring-gate.sh:34,155` · `hooks/genericity-gate.sh:156` · `.claude-plugin/plugin.json:9,16,17` · `.codex-plugin/plugin.json:6,7` · `providers/codex/agents/afk-afk-tracer.toml:1` · `FRESHNESS.md:38,40,42,43,44,46,52,56,61,62,63,66` · `skills/afk/setup/MANIFEST.md:538` · `PROVIDERS.md:23` · `providers/CONFORMANCE.md:18,26` · `DELEGATION.md:26,45` · `CLAUDE.md:116,195` · `README.md:765,829` · `CAPABILITIES.md:21,44` · `GLOSSARY.md:228` · `CHANGELOG.md:14`

## Frontier
- B14: harness plugin loaders and marketplaces consume the manifests outside this repository; live behaviour on an unregistered dir is recorded only in `providers/CONFORMANCE.md`.

## Unverified
- Re-dispositioned 2026-09-15 against the `investigation:` block now in `.afk/config.yaml` (`run.config.sha256` restamped): B3 closed by reading — the five gates plus `hooks/lib/provider.sh:7` and `hooks/lib/adapter.sh:146` (neither walks `skills/` or `agents/`); B5 closed by reading — the six manifest/stub sites plus `scripts/afk-config.py:51` (the add declares no config key) and the `json-jsonl-artifacts` pattern as a counter-search (159 lines, nothing beyond the manifests); B10 closed by reading `mcp-servers/tracker/server.py:26` plus the `http-and-cli-callers` pattern as a counter-search (7 lines, none reads a registry); B6, B7 `n/a` — no build step, no aggregator manifest (`BOUNDARY-EVIDENCE.md`; the manifests' `skills[]` arrays stay B5 sites). Ledger edited directly: the fold refuses a fragment whose `run.config.sha256` differs from the staging ledger's (`merge_fragments.py` `identity`).
- Claim: whether a harness loader errors or stays silent on an unparsable SKILL.md (live B14 behaviour; `hooks/skill-registry-gate.sh:30-34` records one silent drop).
- Process note: folding `seed.json` as the staging ledger turns every seed node into `unverified(conflict: unverified vs <verdict>)` (`merge_fragments.py:116-134` has no placeholder rule); this ledger was folded against a nodes-stripped copy of the seed. Raw fold kept beside the scratch seed as `COVERAGE.raw-merge.json`.
