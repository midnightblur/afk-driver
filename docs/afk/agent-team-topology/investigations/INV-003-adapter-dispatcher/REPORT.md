C:\Users\mvu\PersonalProjects\afk-driver-agent-teams@9d9fce6 · closed-with-frontier · boundaries 13/14 · unverified 0 (load-bearing 0) · ledger: docs/afk/agent-team-topology/investigations/INV-003-adapter-dispatcher/COVERAGE.json

## Answer

No existing caller changes behaviour. Each existing caller of `afk_adapter*` runs in its own process. The kind is resolved in a subshell (hooks/lib/adapter.sh:39), and `AFK_CFG_*` values are never exported. A new caller's own kind is overwritten by its first `afk_config_load`: scripts/afk-config.py:127-131 always emits the three family keys, and hooks/lib/config.sh:30 evals them. This affects only the new caller.

## Callers

- skills/afk/gc/scripts/gc-check.sh:136 — the only code call of `afk_adapter`. Runs in its own process; gc-check.sh:87-89 loads config first. Pinned by skills/afk/gc/scripts/tests/gc-check-smoke.sh:134. Unchanged.
- hooks/stop-gates.sh:40 and hooks/precommit-gates.sh:57 — source adapter.sh, never call the dispatcher. Unchanged, unguarded.
- hooks/lib/provider.sh:7 and :15 — `afk_adapter` is a loop variable there; `unset` removes only the variable. Unchanged, unguarded.
- hooks/hooks.json:59 and hooks/run-hook.py:319 — only exported variables cross the subprocess. Unchanged, unguarded.
- scripts/tracker_api.py:33 — the Python loader reads YAML, not `AFK_CFG_*`. Pinned by scripts/tests/test_publish_bug.py:43. Unchanged.
- 16 documented dispatch lines, each run from an agent's own shell (inference): ADAPTERS.md:16, adapters/notes/notion/CONTRACT.md:9, docs/afk/agent-team-topology/research/FACTS-claude.md:12, skills/afk/bug/FIXER-PROMPT.md:31, skills/afk/execute/SKILL.md:17,61, skills/afk/preflight/SKILL.md:58,185,199,217,230, skills/afk/understand/SKILL.md:87, skills/utils/settle-change/SKILL.md:17,37,64,103.

## Frontier

B14: other repositories and live consumers.

## Unverified

None. The 16 documented callers rest on the inference that the harness gives each shell call its own process.
