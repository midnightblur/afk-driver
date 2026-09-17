# INV-001 — debate_card field set: dependents and change impact

C:/Users/mvu/PersonalProjects/afk-driver-research-enhancement@d8ca9b44ea2275ac04ca61f6dc05b715f892c5f0 · closed-with-frontier · boundaries 13/14 · unverified 0 (load-bearing 0) · ledger: docs/afk/research-enhancement/investigations/INV-001-round-schema/COVERAGE.json

Question types: Q2 + Q3. Subject: `debate_card` (forms: simple, `"debate_card"`, component, wire, import-alias; declared field forms `exhausted`, `postpone_cost`).

## Answer

Adding `exhausted` and `postpone_cost` as optional `debate_card` fields needs 1 schema edit and 1 renderer edit, plus 1 document row; nothing else reads card fields by name.

- Today an unlisted key is a hard exit: `scripts/lavish/schema.py:253-260` builds the known set from `REQUIRED` + `OPTIONAL`, `:105-109` raises `ContractError`, `scripts/lavish_render.py:117-122` returns exit 1 (markdown fallback). Edit: `schema.py:69` (`OPTIONAL["debate_card"]`).
- The fields render nowhere until `scripts/lavish/components.py:423-475` (`debate_card`) emits them; `:462-464` (`third_paradigm`) is the optional-field pattern.
- Unchanged: `RENDERERS` (`components.py:658-664`), `required_mark` (`schema.py:178`), `runtime.js:5` (attribute contract only), `kit.css:108`, response tokens (`LAVISH-KIT.md:395`), fixture `scripts/tests/samples/lavish-round.json`, every test in `scripts/tests/test_lavish_render.py`.
- Documents: `LAVISH-KIT.md:129` (component table) goes stale without the same-commit edit; `LAVISH-KIT.md:300` (lede table) stays true — `SDD.draft.md:484` places the fields beside `third_paradigm`, in the detail block (`components.py:462-464`); `CLAUDE.md:135` states the four-file lockstep. `GRILL-LOG-FORMAT.md` carries no card-field reference (`:53` appends the response verbatim) — unchanged unless the design logs the fields. `ROUND.md:74` already asks for the cost of resolving an indecision in prose.
- Deployment order: renderer first or same commit; old renderer + new JSON exits 1, new renderer + old JSON renders. No persistence or migration effect.
- Tests: `test_lavish_render.py:715` pins only the unknown-key refusal; no test pins the `OPTIONAL` tuple or an optional field's output — `unguarded` until AC-009's test lands.

## Findings on the design anchors

- `SIGNED-PACKETS.md:163` names `schema.py:46-48` — that is `REQUIRED`; the optional set is at `schema.py:69`.
- `ROUND.md:308-313` is the decided-card contract C-1..C-6; the debate-card lines are `ROUND.md:42-48` and `:68-75`.

## Sites (breaks)

`schema.py:69`, `schema.py:255`, `schema.py:107`, `schema.py:260`, `components.py:423`, `lavish_render.py:120`, `LAVISH-KIT.md:129`.

## Frontier

- B14 — other repositories, deployment manifests, live consumers: round JSON authored by consuming repositories at runtime, `lavish-axi` host.

## Unverified

- none.
- Re-dispositioned 2026-09-15 against the `investigation:` block now in `.afk/config.yaml` (`run.config.sha256` restamped): B3 closed by reading `hooks/lib/provider.sh:7` and `hooks/lib/adapter.sh:146` (neither dispatch reaches `scripts/lavish`); B5 closed by reading `scripts/afk-config.py:208` (codec for `.afk/config.yaml` only) plus the `json-jsonl-artifacts` pattern as a counter-search (159 lines, no new reader/writer); B10 closed by reading `mcp-servers/tracker/server.py:26` plus the `http-and-cli-callers` pattern as a counter-search (7 lines, none reaches the round document); B6, B7 `n/a` — no build step, no aggregator manifest (`BOUNDARY-EVIDENCE.md`); `LAVISH-KIT.md:300` verdict `unchanged` — `SDD.draft.md:484` places the fields beside `third_paradigm`, in the detail block (`components.py:462-464`). Ledger edited directly: the fold refuses a fragment whose `run.config.sha256` differs from the staging ledger's (`merge_fragments.py` `identity`).

## Run notes

- Fold workaround: `merge_fragments.py` reads the seed's placeholder `unverified` as a tracer verdict and marks every dispositioned node `conflict: unverified vs terminal` (122 nodes on the literal fold). The published ledger folded against the seed minus its 122 untriaged node rows; every other seed row is intact. Plugin defect to report.
- Counter-search: deterministic by sibling field names (`third_paradigm`, `undecided_because`, `criteria_order`; 24 new nodes) and agent-driven by registration sites (16 read nodes).
