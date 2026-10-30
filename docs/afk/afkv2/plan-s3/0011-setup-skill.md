# 0011-setup-skill

## Goal
Write `/afkv2:setup`: one run in any repository serves Claude and Codex. It asks
for the Jira values and stores them as v1 does, installs rg on every shell path,
asks for the ownership config, offers a copy of v1 config values, guides the
Codex hook trust review, proves the hook, then takes over from v1 (rule block,
git hook stubs, plugin switch, lavish host 0.1.80), each step with a backup.
Switch-back restores all of it.

## Complexity
complex

## Design refs
- SDD: SDD.md#§5 L4 — Cross-Cutting & Quality Attributes — idempotency rows, secrets
- SDD: SDD.md#§7 L6 — Process & Coordination — v1 takeover use case, failure rows hook did not fire / switch back
- SDD: SDD.md#§9b External Seams & Failure Affordance — rows Claude plugin switch, Codex plugin switch
- SDD: SDD.md#§14 L9 — Implementation Seams & Change Impact — rule block and git hook stub rows
- ADR: adr/design/0008-setup-takeover-from-v1.md
- ADR: adr/design/0005-session-start-hook-cmd-and-markers.md — hook proof
- ADR: adr/requirements/0004-one-rule-set-per-session.md

## Scope
- afkv2/skills/setup/**
- afkv2/tests/setup/**

## Seams
- implement: v1 rule block written by install_block — remove the block from both user instruction files in one run after the hook proof, with backup; switch-back restores (INV-004)
- implement: v1 git hook stubs from install-git-hooks — move the pre-commit and reference-transaction stubs aside per repository, with backup; switch-back restores (INV-004)

## Acceptance
- [ ] Setup runs in any repository, the main checkout included, and one run serves Claude and Codex (PRD §SK-04)
- [ ] It asks once for `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN` and stores them as v1 does, never in the repository, and never prints the token (SDD §5 Secrets)
- [ ] It installs rg and puts it on the path of every shell the agent uses (PRD §SK-04)
- [ ] It checks Python 3 on the path and records it (SDD §8 "Frozen on day 1" row "Python")
- [ ] In a repository with no ownership config it asks once; a skip is recorded so the agent asks at its first edit to a file the ticket does not name (PRD §AC-020)
- [ ] In a repository with a v1 config it offers one copy of the needed values into `.afkv2`; the v1 config file is byte-identical after setup (PRD §AC-018)
- [ ] Hook proof: the fired record is newer than setup's install record and the agent reports the end marker with the matching sha12; only then is the v1 block removed. Without the proof setup keeps the block, keeps a backup and reports why, naming the Codex hook trust review (PRD §AC-015; ADR-0005 design)
- [ ] The v1 block is found only by its full begin and end marker lines and removed from both user instruction files in one run; bytes outside the block are unchanged (SDD §14 row "v1 rule block written by install_block")
- [ ] The v1 pre-commit and reference-transaction stubs are moved aside into the backup folder; afkv2 writes no git hook and never copies v1's marker string (SDD §14 row "v1 git hook stubs from install-git-hooks")
- [ ] Plugin switch: on Claude `enabledPlugins` in the project's `.claude/settings.local.json`, never the shared file; on Codex the global config, with backup; setup refuses to leave both `afk` and `afkv2` enabled (PRD §AC-017; ADR-0008 design)
- [ ] It records the installed lavish host version, then installs lavish-axi 0.1.80 machine-wide (ADR-0008 design)
- [ ] Every step is idempotent per SDD §5: absent markers = already removed; a present backup = already moved; an equal settings value = no write (SDD §5 Idempotency)
- [ ] Switch-back restores the block, the git hook stubs, the settings and the host version from the backups, turns v1 on, and lists the tickets in `%LOCALAPPDATA%\afkv2\published-tickets.txt` (PRD §AC-016; SDD §14 accepted findings; PLAN.md decision D-S-3)
- [ ] Seam-tests: the Claude switch reads back the effective `enabledPlugins` value; the Codex switch lists the plugin state after the switch (SDD §9b rows "Claude plugin switch", "Codex plugin switch")
- [ ] Every test runs against a temporary home, data folder and repository; no test touches the real user files

## Produces
- afkv2/skills/setup/SKILL.md#/afkv2:setup — the setup skill
- afkv2/skills/setup/scripts/setup.py#def prove_hook( — fired record + end marker proof
- afkv2/skills/setup/scripts/setup.py#def remove_v1_block( — full-line block removal with backup
- afkv2/skills/setup/scripts/setup.py#def move_v1_git_hooks( — stubs aside with backup
- afkv2/skills/setup/scripts/setup.py#def switch_plugins( — Claude local settings, Codex global
- afkv2/skills/setup/scripts/setup.py#def switch_back( — restore every backup

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | every `afkv2/skills/setup/**/SKILL.md` has Agent Skills frontmatter (`name`, `description`); `afk-python -m compileall -q afkv2/skills/setup`; `rg -F` each ## Produces anchor | skill files parse; declared symbols present |
| unit | `afk-python -m pytest afkv2/tests/setup -q` | each step, its idempotency, its backup and its refusal on a temp home |
| integration | end-to-end on a temp home + temp repository holding a v1 block in both files, v1 stubs and a v1 config: proof missing → block kept; proof present → takeover; switch-back → every file byte-identical to before; Claude switch read back from the effective settings; Codex plugin state listed | the two §14 seams and the two §9b switch seams on real files |

## Context excerpts
> (PRD §SK-04) | SK-04 | `/afkv2:setup` | runs in any repository, main checkout included; one run serves Claude and Codex; asks for the Jira API token and stores it as v1 does; installs ripgrep (`rg`) and puts it on the path of every shell the agent uses; asks for the ownership config; guides the Codex hook trust review; removes the v1 block after the hook proof | K-1, D-2, D-3, H-4 |

> (ADR-0008 design) After the hook proof (ADR-0005), setup removes the v1 rule block, moves the v1 pre-commit and reference-transaction stubs aside, writes the plugin switch on Claude to the project's personal settings file (never the shared one) and globally on Codex, installs lavish host 0.1.80 after recording the installed version, and installs rg. Every write keeps a backup; switch-back restores each one.

> (SDD §14 rows) | v1 rule block written by install_block | (INV-004) | setup removes the block from both user instruction files after the hook proof; backup; switch-back restores | (INV-004): one writer pair (setup install, setup teardown), one reader (session-start drift check, silent when the markers are gone) | bytes outside the block stay unchanged; remove from both files in one run, because a later v1 setup re-adds a block missing from one file only (inferred, INV-004) | reworked |
> | v1 git hook stubs from install-git-hooks | (INV-004) | setup moves the pre-commit and reference-transaction stubs aside in each repository it runs in; switch-back restores | (INV-004): v1 rewrites missing stubs at every v1 session start; a file holding v1's marker string counts as v1's own | afkv2 writes no git hook and never copies v1's marker string; a set `core.hooksPath` stops the stubs anyway | reworked |

> (SDD §5 Idempotency) | v1 rule block removal | the block's begin and end markers | permanent | absent markers = already removed |
> | v1 git hook move | the moved file in the backup folder | until switch-back | a present backup = already moved |
> | plugin switch | the settings key value | permanent | equal value = no write |

> (SDD §9b) | Claude plugin switch | Claude Code settings (docs: project local overrides shared project overrides user) | `enabledPlugins` in `.claude/settings.local.json` | wrong file → team affected | setup test reads back the effective value |
> | Codex plugin switch | Codex config (global) | one switch per machine | not verified: a command-line enable/disable; else config edit with backup | setup test lists the plugin state after the switch |

> (SDD §14 accepted finding) On Claude, the plugin switch is per project, but the v1 rule block lives in the user-level files. Removing it stops v1's rules in every project where v1 is still enabled. Accepted: requirement ADR-0004 makes afkv2 take over the user instruction files; switch-back restores the block.

> (SDD §5 Secrets) Jira: `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`, looked up as v1 does (environment, then the Claude user config's tracker entry, then the Codex config). Setup asks once and stores them with the developer's own tooling, never in the repository. GitHub and GitLab: `gh` and `glab` logins.

> (PRD §AC-015) `/afkv2:setup` removes the v1 block from a user instruction file only after the session shows the afkv2 hook marker. Without the marker, setup leaves the block, keeps a backup, and reports why.

> (PRD §AC-017) On Claude, exactly one of `afk` and `afkv2` is enabled per project. On Codex, exactly one is enabled on the machine. Setup refuses to leave both enabled.

## Parent PRD
docs/afk/afkv2/PRD.md

## Parent SDD
docs/afk/afkv2/SDD.md

## Blocked by
(none)

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality
during implementation, classify per the decision protocol (`DECISIONS.md`,
workflow plugin root): a two-way-door correction is recorded in
`plan/DECISIONS.md` (this plan folder's `DECISIONS.md`) and implemented; a
one-way door or a tie exits `design_conflict` quoting the SDD section + the
conflict. Never override off the record. Parked conflicts route back to
`/afk:grill-solution` for a superseding ADR.
