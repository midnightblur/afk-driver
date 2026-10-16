C:\Users\mvu\PersonalProjects\afk-driver-agent-teams@7e9c87a · closed-with-frontier · boundaries 13/14 · unverified 1 (load-bearing 0) · ledger: docs/afk/agent-team-topology/investigations/INV-014-model-tiers-definition/COVERAGE.json

## Answer

The model-tier map is the `## Model tiers` table in PROVIDERS.md (heading :51, table :55-60). Columns: Tier | Claude Code | Codex CLI.

| Tier | Claude Code | Codex CLI | Site |
|---|---|---|---|
| Frontier | `opus` | `gpt-5.6-sol` at high or xhigh effort; `gpt-5.5` fallback | PROVIDERS.md:57 |
| Implementation | pinned `claude-opus-4-8`; `sonnet` for simple slices | `gpt-5.6-terra` at medium effort; lower for simple slices | :58 |
| Digest | `sonnet` | `gpt-5.6-terra` at low effort | :59 |
| Deterministic | `haiku`, carried by `afk-runner-lite` | `gpt-5.6-terra` at low effort; no distinct rung | :60 |

- Fallback: a column is harness configuration; pick the first available model in the active column, else the nearest capability-compatible model that harness can drive (PROVIDERS.md:53). CAPABILITIES.md:16 restates it as the `model_tiers` degrade cell.
- Override direction: callers override per spawn, always upward; never downgrade on a verdict (DELEGATION.md:50). The table states no override rule (PROVIDERS.md:51-65).
- Pin delivery: the implementation pin travels through the agent definition, never as a spawn-model argument (PROVIDERS.md:65).
- A Fable-class or Astra-class model is never a tier (PROVIDERS.md:62).
- All 5 agents/*.md `model:` values and all 5 Codex stub model/effort values match their rows. No mismatch.

## Sites

- The map: PROVIDERS.md:51, :53, :55, :57-60, :62, :65.
- Copies that match (unguarded hand copies): agents/afk-tracer.md:5, afk-implementor.md:4, afk-reader.md:5, afk-runner.md:5, afk-runner-lite.md:5; providers/codex/agents/afk-afk-{tracer,implementor,reader,runner,runner-lite}.toml:3 and :4.
- Restating or dependent: CAPABILITIES.md:16, :41, :46; DELEGATION.md:26, :41, :43, :45-50, :56-57; FRESHNESS.md:62; CLAUDE.md:22, :67, :137, :199; AGENTS.md:22, :199; CHANGELOG.md:256; PROVIDERS.md:23; agents/afk-implementor.md:3; skills/afk/autopilot/SKILL.md:35; skills/afk/autopilot/SUBAGENT-PROMPT.md:3; skills/afk/bug/SKILL.md:68; skills/utils/settle-change/SKILL.md:57; providers/codex/agents/afk-afk-implementor.toml:10.
- Distribution: skills/afk/setup/MANIFEST.md:536-543, :562 (copies stubs to `~/.codex/agents/`, replaces only `{{PLUGIN_ROOT}}`); .claude-plugin/plugin.json:9 (lists the 5 agents); .codex-plugin/plugin.json:6 (no agents key); CLAUDE.md:15.
- Readers that check no value: hooks/native-contract-gate.sh:143 (check B allows a `model` key), :200 (check D pairs agent and stub by filename only); hooks/lib/provider.sh:7; scripts/afk-config.py:51, :105, :541 (no model or tier key, so no config override).

## For the design

- Dangling pointer: DELEGATION.md:46 and skills/afk/autopilot/SKILL.md:35 cite PROVIDERS.md "Pin delivery"; no such heading exists (rule is at PROVIDERS.md:65).
- FRESHNESS.md:62 names only CAPABILITIES.md + PROVIDERS.md as update surfaces; it omits agents/*.md and the Codex stubs.
- No gate or test compares a model value with the map (native-contract-gate.sh:143, :199-203; the 6 test hits are hook-envelope fixtures).
- A stub change reaches a machine only after `/afk:setup` re-copies the stubs (inferred; MANIFEST.md:552, :562).
- CHANGELOG.md:255-256 says one model per column; the Codex frontier cell also names `gpt-5.5` (inferred: a within-cell fallback, not a second model).
- Trial on Claude Code 2.1.282: `--model opus` ran `claude-opus-5-5`, not the pinned `claude-opus-4-8`, so DELEGATION.md:46 holds. One harness version, 2026-09-24.

## Frontier

- B14: installed plugin copies (`~/.claude/plugins`, `~/.codex/agents` stub copies) and other repositories that restate the map. Outside this repository.

## Unverified

- c-7a676672: the hit set holds every reference over the name forms searched. Not load-bearing. 5 deterministic counter-checks ran to completion against it.
