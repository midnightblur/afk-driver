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

The rule can be missed; the catcher is **`/afk:setup audit`**
(`skills/afk/setup/AUDIT.md`): structural consistency, dependency drift,
pointer integrity, registry compliance. Run it after any batch of workflow
edits and always before shipping plugin changes. The wiring gate
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
| `CLAUDE.md` | plugin author | doctrine changes (DRY, delegation, followability, freshness); a skill is added/removed; a lockstep pair changes; the Reference list's targets move |
| `GLOSSARY.md` (root) | plugin author | a methodology term is minted, renamed, or retired |
| `REPORTING.md` | plugin author | any status-line / notification protocol change |
| `DELEGATION.md` | plugin author | any delegation-doctrine change |
| `LAVISH.md` | plugin author | the pin bumps; a render point (RP row) is added/removed; a playbook id changes; the fallback/forbid rules change — update the woven skill(s) in step |
| `FRESHNESS.md` (this file) | plugin author | a new artifact class appears, or enforcement changes |
| `skills/afk/setup/MANIFEST.md` | `/afk:setup` | any external-dependency change (rule 1) |
| `skills/afk/setup/AUDIT.md` | `/afk:setup` | an artifact surface worth auditing appears/disappears |
| `skills/afk/setup/scripts/setup_secrets.py` | `/afk:setup` | the set of entries it fixes, a prompt, or a written key/shape changes — update every `MANIFEST.md` entry whose `Fix` names it in the same commit (it writes the H2 registration, the S1 env block, and the H6 key set — those three own their shapes; this script only places them) |
| `hooks/` — **every** file in the dir (`hooks.json`, all `*.sh` gates/helpers/installers incl. `lib/`, `genericity-allow.txt`, `README.md`); deliberately not enumerated, an enumeration here goes stale the moment a gate is added | plugin author | gate semantics change — update `hooks/README.md` + `CLAUDE.md` Reference (wiring gate also: `skills/utils/verify-seams`; app-start gate also: autopilot/execute skills that invoke it; metrics line shape also: `gate-metrics-report.sh` parser + any reader skill) in step |
| `agents/*.md` | plugin author | an agent's tools/model/purpose change — update the skills that spawn it |
| `PROVIDERS.md` | plugin author | a provider-specific construct (invocation, spawn vocabulary, model tier, env var, cred source, Claude-only capability) is added/changed on either provider — the ONE home for the mapping; skills never carry provider names inline |
| `tools/payable/ai-agents/codex-sync/` (`generate.py`, `README.md`, `config-fragment.toml`, `tests/`) + generated trees (`.agents/skills/`, `.codex/`, AGENTS.md block, harness `hooks/lib/provider.sh` sync) | plugin author | skill/agent frontmatter, either plugin's `hooks.json`, project skills, or `hooks/lib/provider.sh` change → rerun the generator same-commit (enforced by `hooks/codex-drift-gate.sh`); a NEW provider-facing artifact class appears → extend `generate.py` + its README table |
| `skills/afk/bug/SKILL.md` + `FIXER-PROMPT.md` + `RETEST-PROMPT.md` | `/afk:bug` | the subcommand set, the `BUGFIX:`/`RETEST:` result grammars, or the S1-S10 ledger machine's allowed edges change — update both prompt siblings + `LEDGER-FORMAT.md` in the same commit |
| `skills/afk/bug/LEDGER-FORMAT.md` + `BUNDLE-FORMAT.md` + `CONFIG.md` | `/afk:bug` | the ledger schema/state machine, the bundle grammar, or the `afk.local.json` key set (K1-K4) changes — update `SKILL.md`'s pointers in step |
| `skills/afk/bug/scripts/create-worktree` + `scripts/publish_bug.py` | `/afk:bug` | the `WORKTREE_PATH=`/`ERROR=` contract or the Jira create/transition/comment/backfill payloads change — update `SKILL.md` §`dispatch`/§`capture` in step |
| `mcp-servers/jira/server.py` (Jira MCP server) | plugin author | the tool set, a tool's signature, or the env-var contract changes — update `skills/afk/setup/MANIFEST.md` H2/P3 in the same commit; registration stays user-scoped (key `jira`), never plugin-bundled (H2 Notes own the why) |
| `scripts/jira_core.py` (shared Jira lib) | plugin author | creds resolution, ADF conversion, or attachment/media-UUID upload behavior changes — update both callers (`skills/afk/to-ticket/scripts/publish_prd.py`, `skills/afk/bug/scripts/publish_bug.py`) in the same commit |
| `skills/afk/understand/SKILL.md` + `UNDERSTANDING-FORMAT.md` + `shell-template.html` | `/afk:understand` | the section model / predicates / quiz rules / **meta-header grammar** change — update the mission-control understanding parser (`skills/afk/mission-control/scripts/mc/sections/understanding.py`) in the same commit (lockstep pair); a journal event token is added/renamed — update `skills/afk/to-subtasks/JOURNAL-FORMAT.md` (writer row `understand`/subject `understanding`) same-commit; the skill dir is added/renamed/removed — update `plugin.json` skills array, `README.md` (§3 chain map, §7 artifact tree, §10 skill reference), `CLAUDE.md` skills catalog + journal writer list, and the marketplace description |
| `skills/afk/mission-control/DIGEST-FORMAT.md` + `scripts/mc/digests.py` + `scripts/mc/assets/shell.html` | `/afk:mission-control` | a digest schema, the manifest grammar, or a section's data shape changes — the three move in the same commit (emitter contract ↔ parser/validator ↔ shell renderer), plus the A-suite fixture digests |
| `skills/afk/lessons/SKILL.md` + `LEDGER-FORMAT.md` + `CAPTURE.md` | `/afk:lessons` | the ledger event grammar, class enum, status set, escalation ladder, or capture rule changes — update `hooks/lesson-append.sh` + `hooks/lesson-digest.sh` + every detection-point pointer (`CLAUDE.md` "Lockstep") in the same commit |
| `skills/**/SKILL.md` + siblings | that skill | its behavior changes; per-skill lockstep partners per `CLAUDE.md` "Lockstep" |
| AFK pitch artifact — `https://claude.ai/code/artifact/fc1c59af-7779-4e26-a174-0c9e396cc017` (internal stakeholder pitch/field guide; owner: mvu) | artifact owner | the skill set, chain map, gate set, or a limitation/WIP item changes — re-digest the plugin, patch stale facts + the footer snapshot date, republish to the **same URL** (Artifact tool with `url:`; only the owner's account can republish). Manually maintained — deliberately no automatic trigger |
