# INV-005 — what the `debate_card` component is

C:/Users/mvu/PersonalProjects/afk-driver-research-enhancement@d8ca9b44ea2275ac04ca61f6dc05b715f892c5f0 · closed-with-frontier · boundaries 13/14 · unverified 1 (load-bearing 0) · ledger: docs/afk/research-enhancement/investigations/INV-005-debate-card-definition/COVERAGE.json

Question type: Q1. Subject: `debate_card` (forms: simple, `"debate_card"`, component, wire, import-alias; field forms `undecided_because`, `third_paradigm`, `criteria_order` as counter-search).

## Answer

`debate_card` is one of the six round-document components: a recorded indecision (`skills/afk/grill-requirements/ROUND.md:42`) rendered as a criteria grid with a recommendation and a pick-plus-note answer.

| Site | What it defines | Cite |
|---|---|---|
| registry | `COMPONENTS` entry; unknown component is `ContractError` | `scripts/lavish/schema.py:22-29`, `:228-230` |
| required set | `question`, `options`, `criteria_order`, `recommended`, `why`, `undecided_because` | `schema.py:46-47`; enforced `:211-221` |
| optional set | `context`, `third_paradigm` | `schema.py:69` |
| common keys | `component`, `id`, `state`, `fresh`, `group` (`:77`); `depends_on` (`:256-257`) | known-set builder `:253-260`, refusal `:105-109` |
| debate guards | options are objects with ids, ≥2, unique; `recommended` names an option; `depends_on` ids resolve; refused in a table-layout group | `schema.py:268-279`, `:293-296`, `:405-409` |
| dispatch | `RENDERERS["debate_card"]` → `debate_card()` via `render_item` | `scripts/lavish/components.py:658-664`, `:672-673` |
| renderer | `def debate_card(item, states, level)` | `components.py:423-471` |
| contract | component row, `context` placement, lede, choice tokens | `LAVISH-KIT.md:129`, `:164`, `:300`, `:395` |
| fixture | Q-1 (context, `third_paradigm`, 3 options); Q-2 (blocked, `depends_on`, 2 options) | `scripts/tests/samples/lavish-round.json:87-131`, `:238-269` |
| tests | `IndecisionIsStated`, `HardFailures`, `NoCaps`, `Navigability`, `TableLayoutGroups` | `scripts/tests/test_lavish_render.py:604-617`, `:713-716`, `:739-740`, `:779-803`, `:977-985`, `:1314-1331` |

Where each field is emitted (`components.py`): `question` → card heading (`:469`, `_card` `:101`) · `recommended` → lede line `afk-rec-line` with `why` (`:450-453`) and the `afk-rec` badge on that option's column head (`:432-436`) · `undecided_because` → lede line `afk-undecided` (`:454-455`) · `depends_on` → chips strip (`:456`, `:145-171`) · `context` → first paragraphs of the `<details>` block (`:459-460`, `:179-182`) · `criteria_order` × `options[].criteria` → grid rows × columns, `—` when a criterion is missing (`:431-444`) · `third_paradigm` → optional `afk-third` paragraph (`:462-464`) · `options[].id` → one radio each plus `write-in`, with the note textarea (`:466-468`, `:41-60`). Element: `article.afk-card--debate` (`:113`), styled `scripts/lavish/assets/kit.css:108`.

Path: `python scripts/lavish_render.py <round.json>` (`LAVISH-KIT.md:16-17`) → `json.load` (`lavish_render.py:107-114`, exit 2 on unreadable or invalid JSON) → `schema.load` (`:117`) → `page.build` (`:118`; answerable only for current-round unsettled items, `page.py:127`; five render sites `page.py:79,95,113,203,204`) → write (`:130-131`) unless `--check` (`:127-128`). Any `ContractError` → one stderr line, exit 1 (`:120-122`); no degrade path for this component (`schema.py:12-16`). No config key, environment variable, persistence, or async work on the path (B8, B9, B11 closed). Downstream: the runtime sends the checked radio value (`runtime.js:61-66`) as `{item-id} {choice-token} | {note}` (`LAVISH-KIT.md:378-386`), appended verbatim to the grill log (`GRILL-LOG-FORMAT.md:53`).

## Findings

- `LAVISH-KIT.md:129` lists `depends_on[]` as optional; the code admits it as a common key (`schema.py:256-257`), not in `OPTIONAL` (`:69`) — same admitted set (inference: the table folds the common key in for the author).
- `docs/afk/research-enhancement/SIGNED-PACKETS.md:163` anchors the optional fields at `schema.py:46-48`; that is `REQUIRED`, the optional set is `:69` (already corrected in `GRILL-LOG.md:33`).
- Unguarded: no test reads `OPTIONAL["debate_card"]`, asserts `third_paradigm` output (`git grep third_paradigm -- scripts/tests/test_lavish_render.py`: 0 lines), or names the ≥2-options guard.

## Frontier

- B14 — the round JSON is authored at runtime by the consuming repository's grill session and hosted by `lavish-axi` (`LAVISH-KIT.md:16`); neither is in this repository.

## Unverified

- `c-2e6b8ee3` (seed, not load-bearing): "the hit set holds every reference"; targeted by 11 complete counter-searches, none found a node outside the ledger.

## Run notes

- Config: `.afk/config.yaml` `investigation:` block picked up (`run.config.sha256` 360476c8…, not the empty-string digest). Declared-pattern universes (B4/B5/B8/B10) yield 546 hits off the render path, each dispositioned `irrelevant` with a shared cited reason.
- One tracer for the whole run (Q1, not design-phase; subject hits in one module). No `afk-tracer` agent type is registered in this harness; the orchestrator traced.
- Tooling defect (disclose): `merge_fragments.py` folds the seed's placeholder rows as tracer verdicts — every dispositioned node reads `conflict: unverified vs <verdict>`, and the seed's `judgment-only`/`unverified` boundary statuses win the worst-status fold. Workaround: fold against a staging copy of the seed whose node rows and boundary rows are replaced by the fragment's (ids, `line_hash`, `query_id` unchanged). Builder: scratchpad `inv005/build_fragment.py`.
