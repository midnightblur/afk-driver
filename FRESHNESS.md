# FRESHNESS.md — no artifact goes stale

Binding on every change to this plugin. A stale artifact is worse than a
missing one — an agent trusts what it reads. This file owns the rule keeping
the plugin's *source* artifacts true; *runtime* artifacts (plan/, INDEX.md,
journal…) are governed by `CLAUDE.md` "Section ownership invariants", not
re-registered here.

## The same-commit rule

Staleness is prevented at write time, not discovered later:

1. **Dependency change** — a commit that adds, removes, or changes how any
   skill/script/hook invokes an external tool, MCP server, env var, secret, or
   sibling path updates `skills/afk/setup/MANIFEST.md` **in the same commit**.
2. **Surface change** — a commit that adds, renames, or removes a skill, root
   doc, hook, agent, or bundled script updates every surface the registry row
   below names **in the same commit**.
3. **Contract change** — lockstep pairs (plan grammar, gate shapes, verdict
   sets) follow `CLAUDE.md` "Lockstep" — same-commit there too; this file does
   not restate which pairs exist.

## The safety net

The rule can be missed; the catcher is **`/afk-toolkit:setup audit`**
(`skills/afk/setup/AUDIT.md` enumerates its checks). Run it after any batch of
workflow edits and always before shipping plugin changes. The wiring gate
(`hooks/wiring-gate.sh` + the `verify-seams` skill) complements it: freshness
guards what *exists*, wiring guards what's *consumed*.

## Artifact registry

What must be touched when a given kind of change lands. Stewards write;
everyone else points.

| Artifact | Steward | Must be updated when… |
|---|---|---|
| `.claude-plugin/plugin.json` | plugin author | a skill or agent is added/renamed/removed; the chain's shape changes (description) |
| `.claude-plugin/marketplace.json` | plugin author | the chain's shape changes (description) |
| `CHANGELOG.md` | plugin author | a dev-visible feature/enhancement/behavior change ships — add its dated one-liner **in the same commit** (audience + exclusions self-documented in its header; internal refactors and wording sweeps get no entry) |
| `README.md` | plugin author | a skill is added/renamed/removed (§10); install/bootstrap flow changes (§4); the chain map changes (§3); a contract/lockstep rule changes (§11) |
| `CLAUDE.md` | plugin author | doctrine changes (DRY, delegation, followability, freshness); a skill is added/removed; a lockstep pair changes; the Reference list's targets move; renaming the "How to write these skill files" section also updates the pointer in `tools/payable/ai-agents/CLAUDE.md` |
| `GLOSSARY.md` (root) | plugin author | a methodology term is minted, renamed, or retired |
| `REPORTING.md` | plugin author | any status-line / notification protocol change |
| `DELEGATION.md` | plugin author | any delegation-doctrine change |
| `DECISIONS.md` | plugin author | the two-way-door classification or the `plan/DECISIONS.md` ledger grammar changes — update the pointing surfaces in the same commit: `skills/afk/execute/SKILL.md` (Driven mode, Steps 1/11/13, ownership hard rule), `skills/afk/execute/CITED-MODE.md` (conflict procedure, `design_conflict`), `skills/afk/to-subtasks/SUBTASK-CONTRACT.md` + `skills/afk/to-sdd/SDD-TEMPLATE.md` (conflict blocks), `skills/afk/to-subtasks/JOURNAL-FORMAT.md` (`decision` event), `skills/afk/autopilot/SKILL.md` (`decisions:` report line) |
| `LANGUAGE.md` | plugin author | the writing doctrine (language rules, ubiquitous-language rules, concision bar incl. its steering-notes section, scope/exceptions) changes — the pointing files stay pointers; specialized bars (`PRD-TEMPLATE.md`, `REPORTING.md`) move in step; a §1 sentence-rule change also updates the synchronized install block in `skills/afk/setup/PLAIN-LANGUAGE.md` same-commit; a skill or agent is **added** → its file opens with the pointer line (`hooks/skill-registry-gate.sh` check D refuses the commit turn otherwise) |
| `LAVISH.md` | plugin author | the pin bumps; a render point (RP row) is added/removed; a playbook id changes; the fallback/forbid/opt-out rules change — update the woven surface(s) in step (skills; RP-10's weave is the install block `skills/afk/setup/LAVISH-SESSIONS.md`); the tooltip-dictionary, tab-title, or page-anatomy contract (paths, matching, injection, backfill, `data-afk-*` grammar) changes — `hooks/lavish-tips.sh` + `hooks/lavish-tips.json` + `hooks/README.md` move in step; the set of `lavish-axi` subcommands that inject changes — the two hooks parse it with identical blocks, so `hooks/lavish-tips.sh` **and** `hooks/lavish-dark.sh` move together, never one alone |
| `SPINOFF-TICKET.md` | plugin author | the spinoff protocol changes (kind set, candidate-row fields, link-debt, dedup) — update the woven grills, `to-ticket` spinoff mode, and `GRILL-LOG-FORMAT.md`'s spinoff-row grammar in step |
| `FRESHNESS.md` (this file) | plugin author | a new artifact class appears, or enforcement changes |
| `skills/afk/setup/MANIFEST.md` | `/afk-toolkit:setup` | any external-dependency change (rule 1) |
| `skills/afk/setup/AUDIT.md` | `/afk-toolkit:setup` | an artifact surface worth auditing appears/disappears |
| `skills/afk/setup/scripts/setup_secrets.py` | `/afk-toolkit:setup` | the set of entries it fixes, a prompt, or a written key/shape changes — update every `MANIFEST.md` entry whose `Fix` names it in the same commit (it writes the H2 registration, the S1 env block, and the H6 key set — those three own their shapes; this script only places them) |
| `hooks/` — **every** file in the dir (`hooks.json`, all `*.sh` gates/helpers/installers incl. `lib/`, `genericity-allow.txt`, `README.md`); deliberately not enumerated, an enumeration here goes stale the moment a gate is added | plugin author | gate semantics change — update `hooks/README.md` + `CLAUDE.md` Reference (wiring gate also: `skills/utils/verify-seams`; app-start gate also: autopilot/execute skills that invoke it; metrics line shape also: `gate-metrics-report.sh` parser + any reader skill) in step |
| `agents/*.md` | plugin author | an agent's tools/model/purpose change — update the skills that spawn it |
| `CAPABILITIES.md` + `PROVIDERS.md` | plugin author | a capability, provider mapping, model tier, environment source, credential source, or distribution class changes — skills point here and never carry provider branches inline |
| `.claude-plugin/plugin.json` + `.codex-plugin/plugin.json` + `.mcp.json` | plugin author | a skill, hook registry, MCP server, or plugin identity changes — both native manifests and shared registration move together |
| `hooks/run-hook.py` + `hooks/hooks.json` | plugin author | a hook is added, removed, or re-pointed, or the launcher's shell/root lookup changes — the command shape is fixed (`hooks/README.md` "Every hook entry goes through one launcher", enforced by `hooks/native-contract-gate.sh` rule J) and `hooks/tests/hook-smoke.sh` gains the case that would have caught it |
| `hooks/lib/providers/*.sh` + `hooks/tests/envelopes/*/` + `providers/CONFORMANCE.md` | plugin author | provider detection/envelopes change, a harness is added, or a live probe changes — update its adapter, fixtures, capability/provider columns, setup section, and conformance row in the same commit |
| `providers/codex/agents/*.toml` | plugin author | an `agents/*.md` role is added, removed, renamed, or changes model/sandbox needs — keep pointer-only stubs; `/afk-toolkit:setup` copies them and resolves `{{PLUGIN_ROOT}}` |
| `skills/afk/bug/SKILL.md` + `FIXER-PROMPT.md` + `RETEST-PROMPT.md` | `/afk-toolkit:bug` | the subcommand set, the `BUGFIX:`/`RETEST:` result grammars, or the S1-S10 ledger machine's allowed edges change — update both prompt siblings + `LEDGER-FORMAT.md` in the same commit |
| `skills/afk/bug/LEDGER-FORMAT.md` + `BUNDLE-FORMAT.md` + `CONFIG.md` | `/afk-toolkit:bug` | the ledger schema/state machine, the bundle grammar, or the `afk.local.json` key set (K1-K4) changes — update `SKILL.md`'s pointers in step |
| `skills/afk/bug/scripts/create-worktree` + `scripts/publish_bug.py` | `/afk-toolkit:bug` | the `WORKTREE_PATH=`/`ERROR=` contract or the Jira create/transition/comment/backfill payloads change — update `SKILL.md` §`dispatch`/§`capture` in step |
| `skills/afk/execute/scripts/` (`verify-contract.sh`, `plan-status.sh` + smoke tests) | `/afk-toolkit:execute` | the `## Produces`/`## Consumes` bullet grammar or `[materialized]` marker (`skills/afk/to-subtasks/SUBTASK-CONTRACT.md`), the progress-tracker table shape (`PLAN-TEMPLATE.md`), or the status enum changes — scripts + `CITED-MODE.md`/`SKILL.md` invocations move in the same commit |
| `skills/afk/to-subtasks/scripts/validate_plan.py` (+ smoke test) | `/afk-toolkit:to-subtasks` | a mechanical validation rule (graph, anchor incl. its forbidden-token list, tier-mandate glob table, gate shape, review policy incl. its deferrable-concern copy) changes — script is the owning home; `VALIDATION.md` carries only the residual judgment checks + exit-code contract |
| `skills/afk/gc/scripts/gc-check.sh` (+ smoke test) | `/afk-toolkit:gc` | a refusal guard, worktree verify-safe check, exit code, or the `AFK_DRIVEN` hands-off contract changes — update `SKILL.md`'s exit-code→action table in step |
| `mcp-servers/tracker/server.py` (Jira MCP server) | plugin author | the tool set, a tool's signature, or the env-var contract changes — update `.mcp.json` and `skills/afk/setup/MANIFEST.md` H2/P3 in the same commit |
| `adapters/tracker/jira/api.py` (shared Jira lib) | plugin author | creds resolution, ADF conversion, or attachment/media-UUID upload behavior changes — update both callers (`skills/afk/to-ticket/scripts/publish_prd.py`, `skills/afk/bug/scripts/publish_bug.py`) in the same commit |
| `skills/afk/understand/SKILL.md` + `UNDERSTANDING-FORMAT.md` + `shell-template.html` | `/afk-toolkit:understand` | the subject families / section model / predicates / quiz rules / **meta-header grammar** change — update the mission-control understanding parser (`skills/afk/mission-control/scripts/mc/sections/understanding.py`) in the same commit (lockstep pair); a journal event token is added/renamed — update `skills/afk/to-subtasks/JOURNAL-FORMAT.md` (writer row `understand`/subject `understanding`) same-commit; the skill dir is added/renamed/removed — update `plugin.json` skills array, `README.md` (§3 chain map, §7 artifact tree, §10 skill reference), `CLAUDE.md` skills catalog + journal writer list, and the marketplace description |
| `skills/afk/mission-control/DIGEST-FORMAT.md` + `scripts/mc/digests.py` + `scripts/mc/assets/shell.html` | `/afk-toolkit:mission-control` | a digest schema, the manifest grammar, or a section's data shape changes — the three move in the same commit (emitter contract ↔ parser/validator ↔ shell renderer), plus the A-suite fixture digests |
| `skills/afk/lessons/SKILL.md` + `LEDGER-FORMAT.md` + `CAPTURE.md` | `/afk-toolkit:lessons` | the ledger event grammar, class enum, status set, escalation ladder, or capture rule changes — update `hooks/lesson-append.sh` + `hooks/lesson-digest.sh` + every detection-point pointer (`CLAUDE.md` "Lockstep") in the same commit |
| `skills/afk/grill-solution/HUMAN-SIGNOFF.md` | `/afk-toolkit:grill-solution` | the human-locked aspect set, a contract grade, or the signing protocol changes — update the signoff-row grammar in `skills/afk/grill-requirements/GRILL-LOG-FORMAT.md`, the SDD §0 register + the aspects' sections in `skills/afk/to-sdd/SDD-TEMPLATE.md`, and `/afk-toolkit:to-sdd`'s sign-off gate in the same commit |
| `skills/**/SKILL.md` + siblings | that skill | its behavior changes; per-skill lockstep partners per `CLAUDE.md` "Lockstep" |
| AFK pitch artifact — `https://claude.ai/code/artifact/fc1c59af-7779-4e26-a174-0c9e396cc017` (internal stakeholder pitch/field guide; owner: mvu) | artifact owner | the skill set, chain map, gate set, or a limitation/WIP item changes — re-digest the plugin, patch stale facts + the footer snapshot date, republish to the **same URL** (Artifact tool with `url:`; only the owner's account can republish). Manually maintained — deliberately no automatic trigger |
