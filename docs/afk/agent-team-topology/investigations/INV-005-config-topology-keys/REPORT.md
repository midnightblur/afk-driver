C:\Users\mvu\PersonalProjects\afk-driver-agent-teams@7e9c87a · closed-with-frontier · boundaries 13/14 · unverified 1 (load-bearing 0) · ledger: docs/afk/agent-team-topology/investigations/INV-005-config-topology-keys/COVERAGE.json

## Answer

Two new top-level keys — a topology map (stage name → pattern name) and a saved-pattern block (pattern → roles, model, lifespan, talk edges) — need growth of the recognised top-level set, a validator of their own, a rule against keys that collide in the shell view, 2 CONFIG.md schema rows and 2 carve-outs. Three strict validators refuse a configuration that carries the keys before the reader knows them, so the reader change ships first or with the first configuration that uses them.

## Sites that change or break

- scripts/afk-config.py:51 `TOP_LEVEL`, refused at :541 ("unknown top-level key", exit 2) — both keys must be added. Breaks. Pinned by scripts/tests/test_afk_config.py:134.
- scripts/afk-config.py:105 `CHILD_KEYS`, loop :586 — a fixed child set refuses free stage and pattern names; left out, nothing below the keys is checked (a misspelled role field, a list as a stage value, a stage naming a missing pattern all validate clean). Each key needs its own validator, as `investigation` has at :465 and :637-667. Unguarded.
- scripts/afk-config.py:975 `shell_name`, from `export_shell` :1001-1005 — free keys fold `-`, `.`, `_` and letter case into one variable; `to-sdd`, `to_sdd` and `to.sdd` all emit the same name and eval keeps the last with no error; a key ending `-count` overwrites a list's `_COUNT` line. Breaks. Unguarded.
- scripts/afk-config.py:1009 `get()` — a stage key holding a dot is unreachable (None, exit 1). Unguarded.
- scripts/afk-config.py:316 `deep_merge` — a list overlay replaces the whole list: a local layer that changes one role's model drops every other role. Maps merge key by key. Existing behaviour, confirmed by a probe. Unguarded for the new keys.
- hooks/lib/config.sh:45-57 `afk_config_list` — prints one empty line per role map (flatten :986 writes `prefix.i.key`); role readers need `get` or the Python reader. Unguarded.
- scripts/afk-config.py:150, :261-287 parser — accepts a stage→pattern map, a pattern→record map, `- name:` role lists with sibling keys, and scalar lists; refuses flow style, lists of lists, and keys outside `[A-Za-z0-9_.-]`. Talk edges must be maps or strings. CONFIG.md:71-76 (YAML subset) unchanged. Pinned by test_afk_config.py:87.
- scripts/tests/test_afk_config.py:267-291 parity test — walks `CHILD_KEYS` → CONFIG.md only, so new rows pass unpinned. New tests needed: the TYPOS table (:237), shell-name collisions, a stage naming a missing pattern. Unguarded.
- CONFIG.md:83-107 — 2 new schema rows. Unguarded.
- CONFIG.md:113-116, :228-230 — "every map is validated one level down" becomes false; both need a carve-out. Unguarded.
- CONFIG.md:234-244 shell view — document the nested and list export shapes and the collision rule. Unguarded.
- CHANGELOG.md:19 — an Unreleased line in the same commit (FRESHNESS.md:40).

## Deployment order

Strict validators that break when a configuration carries the keys before the reader knows them:

- skills/utils/investigate/scripts/seed_map.py:301-303 raises `ConfigError`; the investigation refuses the repository. Pinned by test_seed_map_binding.py:455, :466.
- skills/utils/report-issue/scripts/publish.sh:104 sets `cfg_ok=0`; an agent run queues as config-invalid, the machine-wide configuration included. Pinned by publish-smoke.sh:151.
- scripts/tests/test_afk_config.py:123-125 `test_self_config_validates` goes red.

## Unchanged

- `export-shell` (:1084-1090) never validates; with or without the grown set it exits 0 and every line evals. Output shapes: `AFK_CFG_TOPOLOGY_<STAGE>`, `AFK_CFG_TEAM_PATTERNS_<P>_ROLES_COUNT`, `…_ROLES_0_MODEL`, `…_TALK_0_FROM`. No existing reader name collides with these prefixes. worktree-provision:62 forwards them to adapter subprocesses; harmless because adapters read fixed names only (inference).
- Load-only readers of their own key: server.py:62, tracker_api.py:32, api.py:71, run-hook.py:163, setup_secrets.py:44, :106, create-worktree:126, collect_env.sh:29. `normalize` :407. 65 tests pass before and after growing `TOP_LEVEL` in a scratch copy.

## For the design

- A parse error in the new blocks makes `export-shell` exit 2; config.sh:29 swallows it, so every `AFK_CFG_*` variable is unset for every gate. Existing behaviour; the new blocks make it likelier.
- Keys that fold to one shell name collide silently: validate must refuse them, or the design forbids them.
- A local override of one role replaces the whole role list.
- Recorded document errors: GRILL-LOG.md:237 calls the parity test two-way (it is one-way); research/PROPOSAL-claude.md:159 assumes `export-shell` can cache a probe result (it renders only the loaded configuration); INV-001 REPORT.md:19 puts TYPOS in afk-config.py (it is test_afk_config.py:237).

## Frontier

B14: other repositories and live readers of `AFK_CFG_*`.

## Unverified

One claim, not load-bearing: the hit set holds every reference over the name forms searched. Not run: publish-smoke and worktree-provision-smoke against a patched copy. Not read: hook-smoke and adapter-dispatch tests. hooks/lib/adapter_registry_check.py:131-146 parses the CONFIG.md table but matches adapter-family names only (inference).
