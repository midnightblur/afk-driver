# 0001-skeleton-manifests-hooks

## Goal
Create the afkv2 plugin skeleton in folder `afkv2/`: the Claude and Codex
manifests (plugin name `afkv2`), the marketplace entry, the `.afkv2` config
reader, the afkv2 data folder, and the session-start and subagent-start `.cmd`
hooks. Each hook prints a prebuilt core-behaviors file between the begin and end
marker lines and writes the fired record. The plugin check builds the provider
variants and enforces the size limit, the marker hash and the no-v1-name rule.
Run the day-1 live check that a harness accepts a `.cmd` hook (Claude here; the
Codex part is an owner-run step, PLAN.md "Owner-run live checks").

## Complexity
complex

## Design refs
- SDD: SDD.md#§8 L7 — Module Decomposition — rows config reader, session-start hook; "Frozen on day 1"
- SDD: SDD.md#§9b External Seams & Failure Affordance — 3 hook rows
- SDD: SDD.md#§7 L6 — Process & Coordination — failure row ".cmd hook refused"; v1 defect table row 1
- ADR: adr/design/0005-session-start-hook-cmd-and-markers.md — .cmd hook, markers, build check
- ADR: adr/requirements/0003-core-behaviors-from-plugin-hook.md — rules from the plugin hook only

## Scope
- afkv2/.claude-plugin/plugin.json
- afkv2/.codex-plugin/plugin.json
- .claude-plugin/marketplace.json   # add the afkv2 entry only; v1 entry byte-identical
- afkv2/hooks/hooks.json
- afkv2/hooks/session-start.cmd
- afkv2/hooks/subagent-start.cmd
- afkv2/scripts/afkv2_config.py
- afkv2/scripts/plugin_check.py
- afkv2/tests/test_config.py
- afkv2/tests/test_hooks.py
- afkv2/tests/test_plugin_check.py
- afkv2/tests/live/CODEX-LIVE-CHECKS.md
- afkv2/core/CORE-BEHAVIORS.md   # seed only; 0002 owns the content
- afkv2/hooks/built/afkv2-core-behaviors.txt   # seed only; 0002 owns the content
- afkv2/hooks/built/afkv2-core-behaviors.claude-subagent.json   # seed only; 0002 owns the content
- .gitattributes   # afkv2 lines only; v1 lines byte-identical

## Seams
(none — this slice touches no SDD §14 seam row; its §9b rows are in ## Acceptance and the PLAN.md seam register)

## Acceptance
- [ ] Both manifests name the plugin `afkv2`; the config folder is `.afkv2`; the environment prefix is `AFKV2_`; the data folder is `%LOCALAPPDATA%\afkv2` on both harnesses (SDD §8 row "afkv2 data folder")
- [ ] The config reader is one read command that answers one JSON object (`{"ok": true, ...}` or `{"ok": false, "error": {"code", "reason"}}`) with exit 0, 1 or 2, and resolves spec folder, tracker kind and ownership from `.afkv2` (SDD §8 row "config reader")
- [ ] The session-start hook runs on startup, resume, clear and compact, and the subagent-start hook on subagent start; each prints only the prebuilt text in the wrapper the provider requires: plain stdout on Claude session start and on Codex, JSON `hookSpecificOutput.additionalContext` on Claude subagent start (SDD §9b row "Claude subagent-start hook")
- [ ] The printed text starts with `afkv2-core-behaviors begin <sha12>` and ends with `afkv2-core-behaviors end <sha12>`, where sha12 = the first 12 hex characters of SHA-256 over the text between the marker lines (ADR-0005 design)
- [ ] Each hook run writes the fired record for its provider in the afkv2 data folder, overwritten each session (SDD §4 row "Hook fired record")
- [ ] The hook finishes in under 50 ms, median of 7 runs on Windows, and parses no shell command; a slower hook or extra output fails the test (PRD §AC-013)
- [ ] The plugin check builds the provider variants from one source, refuses a stale prebuilt file, fails at 8,001 characters or more, and fails on a v1 name: `afk` or `AFK_` not followed by `v2` in file names, environment variables, markers, storage keys and CSS classes (PRD §AC-019)
- [ ] The plugin check fails on code that matches an afkv2 or v1 marker by a prefix or substring; markers match only as full lines (SDD §7 "v1 defects afkv2 must not repeat")
- [ ] With afkv2 disabled, a new session holds no afkv2 rule text (PRD §AC-011)
- [ ] Live check on Claude: a non-interactive Claude session with afkv2 loaded from this worktree reports the end marker with the right sha12, also after a compaction (PRD §AC-012). The Codex steps are written to `afkv2/tests/live/CODEX-LIVE-CHECKS.md` for the owner (PLAN.md "Owner-run live checks")
- [ ] If a harness refuses a `.cmd` hook, the subtask stops with `design_conflict`: the fallback (Python hook, 50 ms limit back to the owner) is the owner's call (SDD §7 failure row ".cmd hook refused by a harness")
- [ ] The marketplace entry adds afkv2 and leaves the v1 entry byte-identical (PRD §SK-01)
- [ ] Implements the public interfaces in SDD §8 rows "config reader" and "session-start hook" unmodified (SDD §8)

## Produces
- afkv2/.claude-plugin/plugin.json#"name": "afkv2" — Claude manifest
- afkv2/.codex-plugin/plugin.json#"name": "afkv2" — Codex manifest
- afkv2/hooks/hooks.json#SubagentStart — session-start + subagent-start registration
- afkv2/hooks/session-start.cmd#afkv2-core-behaviors — prints the prebuilt text, writes the fired record
- afkv2/scripts/afkv2_config.py#def read_config( — `.afkv2` reader, JSON answer
- afkv2/scripts/plugin_check.py#def build_hook_outputs( — provider variants from one source
- afkv2/scripts/plugin_check.py#def check_core_size( — 8,000-character limit
- afkv2/scripts/plugin_check.py#def check_no_v1_names( — no-v1-name rule
- afkv2/scripts/plugin_check.py#def marker_hash( — sha12 over the text between the markers
- afkv2/tests/live/CODEX-LIVE-CHECKS.md#Codex live checks — owner-run steps

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `afk-python -m compileall -q afkv2/scripts` + `rg -F` each ## Produces anchor in its file (exactly 1 hit) | code builds; declared symbols present |
| static | `afk-python afkv2/scripts/plugin_check.py` exit 0 on the tree; JSON manifests load | the tree passes its own check |
| unit | `afk-python -m pytest afkv2/tests/test_config.py afkv2/tests/test_hooks.py afkv2/tests/test_plugin_check.py -q` | reader answers, hook output per provider, 8,001-character and v1-name failures, prefix-match failure |
| integration | hook timing: run each `.cmd` 7 times with a sample hook payload on stdin, median < 50 ms; live Claude session (non-interactive) with afkv2 loaded from the worktree reports the end marker, before and after a compaction | the harness accepts the hook and the text reaches context |

## Context excerpts
> (PRD §SK-01) | SK-01 | plugin skeleton | 2 native manifests (Claude, Codex), plugin name `afkv2`, config folder `.afkv2`, environment prefix `AFKV2_`, own plugin data folder | C-2 |

> (PRD §SK-02) | SK-02 | session-start hook | prints the core-behaviors file and stops; under 50 ms; parses no shell command | H-1, H-3 |

> (PRD §AC-011) With afkv2 disabled, a new session holds no afkv2 rule text. (verified: Codex probe 2026-10-29, GRILL-LOG ledger)

> (PRD §AC-012) After a compaction, the session holds the core-behaviors text again. The test includes a compaction on Codex. (verified: Claude docs + probe; Codex docs, root sessions only; GRILL-LOG ledger)

> (PRD §AC-013) The session-start hook finishes in under 50 ms and prints only the core-behaviors text, in the wrapper the provider requires (plain text, or the provider's JSON). A slower hook or extra output fails.

> (PRD §AC-019) No afkv2 file, environment variable or data folder uses a v1 name (`afk`, `.afk`, `AFK_`).

> (SDD §8 row "config reader") | config reader | resolves `.afkv2` values (spec folder, tracker kind, ownership) | one read command, JSON answer | — | S1 (subtask 01) |

> (SDD §8 row "session-start hook") | session-start hook | prints the core-behaviors text, writes the fired record | provider hook output (§9b) | prebuilt files | S1 |

> (SDD §8 "Frozen on day 1") | afkv2 data folder | `%LOCALAPPDATA%\afkv2` on both harnesses | S1 | S3 setup, Stop hook |
> | marker hash | first 12 hex characters of SHA-256 over the text between the marker lines | S1 build check | S3 setup proof |
> | no-v1-name rule | `afk` or `AFK_` not followed by `v2`, over file names, environment variables, markers, storage keys and CSS classes; each ported module renamed in one pass | all | plugin check |

> (SDD §9b rows) | Claude session-start hook | Claude Code hooks (docs) | adds plain stdout to context; above 10,000 characters gives a file path + 2,000-character preview | text cut to a preview | live session finds the end marker (AC-014) |
> | Claude subagent-start hook | Claude Code hooks (docs) | adds context only from JSON `hookSpecificOutput.additionalContext` | no context in subagents | live subagent finds the end marker |
> | Codex session-start / subagent-start hook | Codex hooks (docs) | adds plain stdout; about 2,500 tokens before a file + preview; untrusted hook skipped silently | no rules in the session | live session finds the end marker after the trust review |

> (ADR-0005 design) Per provider, a `.cmd` hook prints a prebuilt file and writes a fired record; it runs on session start (startup, resume, clear, compact) and on subagent start. The text starts and ends with `afkv2-core-behaviors begin|end <sha12>`. A build check makes the provider variants, enforces 8,000 characters and refuses a stale file. Setup proves the hook: the fired record is newer than setup's install record, and the agent finds the end marker. Day 1 opens with a live check that both harnesses accept a `.cmd` hook; if not, a Python hook and the 50 ms limit go back to the owner.

> (SDD §7 v1 defect table) | a git hook file that holds v1's marker string anywhere counts as v1's own, and v1 overwrites it | afkv2 writes no git hook; afkv2 finds its own block or file only by the full begin and end lines, never by a part of a marker | plugin check: no substring or prefix marker match in afkv2 code |

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
