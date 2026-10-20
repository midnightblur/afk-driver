midnightblur/afk-driver@d346cfb5b3957f410119b4199dc2184f890d341a · closed-with-frontier · boundaries 13/14 · unverified 2 (load-bearing 0) · ledger: docs/afk/small-lane/investigations/INV-023-close-caller-seams/COVERAGE.json

Answer: all 5 caller seams traced at d346cfb; 67 nodes `breaks`, none pinned by a test. Fragments P0-P6 + blind CS + deltas D1 (70 conflicts) and D2 (name forms `afk/<skill>`, `name: <skill>`).

| Seam | Existing contract | Planned change | Impacted (breaks unless noted) | Verdict |
|---|---|---|---|---|
| `/afk:execute` fix points + limits | Step 8 retry→`/afk:fix` (`execute/SKILL.md:67`); Step 10 routing `:77-79` (scope→bare `blocked`, not in Step 14 list); 10.5 `:93`; limits `:12,30,142,147,151`; prefix `[{NNNN-slug}]` `:61` | point at shared procedure; out-of-slice sibling; cherry-pick with bug id | `execute/SKILL.md:12,30,61,63,67,77,79,93,123,129,142,147,151`; `CITED-MODE.md:148-151`; `review/SKILL.md:23,33`; `checklists/agents-md-compliance.md:14`; `mc/sections/commitjoin.py:3,21`, `progress.py:7`; `README.md:597,626`; `lavish/tips.json:64` | reworked |
| hands-off: `DECISIONS.md`, autopilot | `DECISIONS.md:23` (external write never two-way), `:25` hard limits; `autopilot/SKILL.md:24,64`; `SUBAGENT-PROMPT.md:28-29` | run start = prior approval for ticket + separate-change writes | `DECISIONS.md:23,25`; autopilot `:24,46,64,66,67`; `SUBAGENT-PROMPT.md:28-29`; `README.md:117,120,122,126,127,860`; `AGENTS.md:9,195` | reworked |
| preflight PF-3/PF-4 + description blocks | PF-3 `:99`, PF-4 `:125` → `/afk:fix`; park reasons closed list `JOURNAL-FORMAT.md:50-55`; `change-update-body` replaces whole body (github `forge.sh:410-418`, gitlab `:428-459`, Draft restore `:454`) | procedure results → PF park reasons; dependency note in `afk:subtasks`; `change-fetch` before rewrite | `preflight/SKILL.md:99,125`; `JOURNAL-FORMAT.md:51-54`; block parsers: none (prose only) | extends |
| smoke red gate with autopilot | `smoke-test/SKILL.md:53` no silent retry, `:80` never patch, `:29,52` stamp rules; autopilot `:67` red ends run | autopilot runs procedure per failing scenario, one re-run | `smoke-test/SKILL.md:53`; autopilot `:67`; stamp readers unchanged (preflight `:26-31`, `gates.py:66-90`, `gc-check.sh:105-108`) | reworked |
| journal events + autopilot report | grammar `JOURNAL-FORMAT.md:21`, writers `:24`, subjects `:25`, events `:31-37`; report `autopilot/SKILL.md:51-58` (no code parses it) | 3 events + 1 report line | `JOURNAL-FORMAT.md:33`; token readers `insights.py:23-24` (closed regexes), `commitjoin.py:65-78` (plan-id subjects), `understand/SKILL.md:80` (`pushed` ranges) | extends |

Landmines:
- `change-fetch` stdout carries no body on either forge; body only in `files.metadata` (`mr.json`): key `body` (github `forge.sh:315`), key `description` (gitlab `:324`); no contract or test names either (`ADAPTERS.md:68-71`, `test_forge_adapters.py:229`).
- Fix commits made at smoke time or in PF-3/PF-4: no commit authorization today (autopilot `:24`, `execute:142`), no slice review (prefix selection `review/SKILL.md:23`), no adversary; settle closure needs `Settles:` trailer (`SETTLEMENT.md:41,86`).
- Mission-control `insights.py:23` flags a park only on `park(`/`parked(`; `:24` exit set is closed (8 tokens).
- `FRESHNESS.md:51` lockstep for two-way-door changes; `BEHAVIORS.md:56,70` headings frozen (`behavior_registry.py:283-317`); `test_execute_step_pointers.py:44-52` scans every `*.md` citing execute steps, the new sibling file included.
- `hooks/README.md:123` long-timeout commit list goes stale; procedure needs its own 600000 ms rule (`execute/SKILL.md:61`).
- Genericity gate rejects example ticket ids outside its allow-list prefixes (`sensitive-patterns.tsv:9`).

SDD §14 citation errors: `review/SKILL.md:22` is blank (rule at `:23`); exit regex is `insights.py:24`; `test_contract.py:306` pins the commit join, journal fixture is `:90-97`; "ready stays forbidden" already false for the feature change (preflight `:215`); smoke row misses `execute:142`.
Existing drift: `JOURNAL-FORMAT.md:51-55` lacks `unhomed_product_debt` (`preflight:169`); `AGENTS.md:179`, `README.md:838-840` omit the preflight-evidence block; `gc-check.sh:151-152` reads `AFK_DRIVEN`, nothing sets it.

Frontier (B14): live `gh pr edit --body` and `glab mr update --description` behaviour, a live GitLab instance, change-description readers in consuming repositories.
Unverified (not load-bearing): seed hit-set completeness claim; live forge behaviour (B14).
