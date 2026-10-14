## Goal
Teach the configuration reader scripts/afk-config.py the keys this feature adds: the transport family key with one settings block per kind, the pane switch under the transport settings, the stage map and the saved patterns, each with its own validator, and the charter fields of a saved pattern. The same commit adds the matching schema rows to CONFIG.md, the transport family to the adapter registry's family enum and to the issue-report environment collector, and replaces the "four adapter families" text in ADAPTERS.md with add-a-family instructions. The slice ends at reading and validating configuration: resolving patterns, probing the machine and running a transport are other subtasks.

## Complexity
standard

## Design refs
- SDD: SDD.md#§14 L9 — Implementation Seams & Change Impact — rows on the configuration reader, the schema table parity and the issue-report collector bind changes C1 to C5, C8 and C9
- SDD: SDD.md#§4 L3 — Data Architecture — the pane switch field
- SDD: SDD.md#§5 L4 — Cross-Cutting & Quality Attributes — the feature-flag rows for the stage map, saved patterns, pane switch and transport kind override
- SDD: SDD.md#§13 Open Questions — Q54 (4): the charter fields of a saved pattern; V40
- ADR: adr/design/0001-transport-as-fifth-adapter-family.md — the transport is a fifth adapter family; a configuration key can force a kind
- ADR: adr/design/0015-a-change-that-only-adds-keeps-the-contract.md — a change that only adds keeps the contract and states its rollback

## Scope
- scripts/afk-config.py
- CONFIG.md
- ADAPTERS.md
- hooks/lib/adapter_registry_check.py
- skills/utils/report-issue/scripts/collect_env.sh
- scripts/tests/test_afk_config*.py
- AGENTS.md (the "four adapter families" text at :9 and :224)

## Seams
- (none in validator form — this slice's 3 seams sit on §14 rows whose grouped citations the plan validator cannot read; they are under ## Acceptance, plan D-9)

## Acceptance
- [ ] Seam §14 row "Configuration reader `TOP_LEVEL`, `CHILD_KEYS`, `export_shell` (scripts/afk-config.py)" (INV-005, closed-with-frontier), carried here and not under ## Seams because the plan validator cannot read this row's grouped citation (plan D-9): the reader gains the transport family key, one settings block per kind, the kinds tuple with its choice check and a child-key entry per block, the pane switch, the stage-map key and the saved-pattern key, each with its own validator, and roles as a map; it refuses keys that fold to one shell name and unknown role fields (SDD §14 row "Configuration reader `TOP_LEVEL`, `CHILD_KEYS`, `export_shell` (scripts/afk-config.py)")
- [ ] Seam §14 row "Schema table rows in CONFIG.md ↔ `CHILD_KEYS` parity, and the adapter registry family enum" (INV-002, closed-with-frontier), carried here and not under ## Seams because the plan validator cannot read this row's grouped citation (plan D-9): CONFIG.md gains one family row and two topology rows in the same commit as the reader's key-map entry, the parity test from the reader's child keys to the schema table passes, and the registry check's family enum reads the transport family (SDD §14 row "Schema table rows in CONFIG.md ↔ `CHILD_KEYS` parity, and the adapter registry family enum")
- [ ] Seam §14 row "Issue-report environment collector family list, mirroring `TOP_LEVEL` families" (INV-001, closed-with-frontier), carried here and not under ## Seams because the plan validator cannot read this row's grouped citation (plan D-9): the collector's hand-written family list gains the transport family (SDD §14 row "Issue-report environment collector family list, mirroring `TOP_LEVEL` families")
- [ ] Reading a configuration refuses a saved pattern that uses a built-in pattern's name (PRD AC-062)
- [ ] Reading a configuration refuses 2 saved patterns with one name (PRD AC-062)
- [ ] Reading a configuration refuses an include or a stage-map entry that names no pattern (PRD AC-062)
- [ ] The pane switch is one key under the transport settings with the values pane or subagent; an absent key means pane when a pane tool is found, and nothing else needs configuring (PRD AC-041)
- [ ] A pane-switch value other than pane or subagent is refused (SDD §4)
- [ ] The reader learns the pane switch in the same commit as the other new keys (SDD §14 row "Configuration reader `TOP_LEVEL`, `CHILD_KEYS`, `export_shell` (scripts/afk-config.py)")
- [ ] The transport kind override is optional: absent, the probe chooses; present, it names one kind of the kinds tuple (SDD §5)
- [ ] A stage-map entry is keyed by stage name and its value is one pattern name or a list of names; the plugin ships no stage map (PRD AC-032)
- [ ] A saved pattern is accepted as data and may declare every field a built-in pattern declares (PRD AC-003)
- [ ] The saved-pattern validator learns the charter fields of a saved pattern in the same commit as the other pattern keys; this is the design's inferred reading (SDD §13 Q54)
- [ ] The topology keys and a per-role model are read independently: a configuration with either, both or neither reads (PRD AC-002)
- [ ] Roles are a map, so a local override of one role replaces that role and not the whole role list (SDD §14)
- [ ] Unknown top-level keys stay refused at afk-config.py:581-582; the transport keys and the pane switch join the known set, so the switch key that sets role agents back to subagents is read, not refused, and scripts/tests/test_afk_config.py:135 still pins the refusal of an unknown key (SDD §14 row "Configuration reader `TOP_LEVEL`, `CHILD_KEYS`, `export_shell` (scripts/afk-config.py)")
- [ ] An old configuration with none of the new keys reads as before (SDD §14 row "Configuration reader `TOP_LEVEL`, `CHILD_KEYS`, `export_shell` (scripts/afk-config.py)")
- [ ] ADAPTERS.md:1 no longer says "four adapter families" and ADAPTERS.md gains add-a-family instructions; the same stale text at AGENTS.md:9 and :224 changes too; CLAUDE.md, the one-line pointer @AGENTS.md, is not edited (SDD §14 row "Schema table rows in CONFIG.md ↔ `CHILD_KEYS` parity, and the adapter registry family enum")
- [ ] Conforms to ADR-0001 — the transport is a fifth adapter family whose kind a configuration key can force; no silent pattern substitution (ADR-0001)
- [ ] Conforms to ADR-0015 — the change only adds keys and rows, and every existing caller keeps its contract (ADR-0015)
- [ ] The changed hooks/lib/adapter_registry_check.py, a Stop-path source, passes native check M: any new scan goes through bounded_scan.py (SDD §13 V40)
- [ ] Every artifact in ## Produces exists with its declared contract (SDD §14 row "Configuration reader `TOP_LEVEL`, `CHILD_KEYS`, `export_shell` (scripts/afk-config.py)")
- [ ] The seam-test for each of the 3 seam rows above asserts on the tool's real output: the reader's refusal text and exit code on a real configuration file, the parity test over the real CONFIG.md, and the collector's real file (SDD §14 row "Schema table rows in CONFIG.md ↔ `CHILD_KEYS` parity, and the adapter registry family enum")

## Produces
- scripts/afk-config.py#_validate_saved_patterns — refuses a saved pattern with a built-in name, 2 saved patterns with one name, an include or stage-map entry naming no pattern; checks charter fields
- scripts/afk-config.py#_validate_transport_block — the transport family key in TOP_LEVEL, its kind settings blocks and the pane switch
- CONFIG.md#transport.kind — schema table row for the transport family and the two topology rows

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `afk-python -m py_compile scripts/afk-config.py hooks/lib/adapter_registry_check.py && bash -n skills/utils/report-issue/scripts/collect_env.sh && grep -n '_validate_saved_patterns' scripts/afk-config.py && grep -n '_validate_transport_block' scripts/afk-config.py && grep -nF 'transport.kind' CONFIG.md` | code builds; the Produces anchors exist |
| static | `grep -n 'transport' skills/utils/report-issue/scripts/collect_env.sh` | seam-test for the issue-report collector row: its family list names transport (no gate or test checks the list) |
| unit | `afk-python -m pytest scripts/tests/test_afk_config.py scripts/tests/test_afk_config_init.py -q`, new cases: each of the 3 refusals; the pane-switch values pane, subagent, absent and another value; the charter-field check; keys that fold to one shell name; an unknown role field; an old configuration reading as before | the reader's refusals and switch values (AC-062, AC-041, Q54 (4)); seam-test for the configuration reader row |
| static | `afk-python -m pytest scripts/tests/test_native_contract_events.py -q`; the native contract gate run on the change (`GATE_CACHE_DISABLE=1 gate_native_contract`, sourced as scripts/tests/test_native_contract_events.py:25-28 does) reports no check M finding | V40 for the changed hooks/lib/adapter_registry_check.py |
| unit | `afk-python -m pytest scripts/tests/test_afk_config.py -q`, parity case: CONFIG.md schema rows ↔ the reader's child keys, including the transport family row and the two topology rows | seam-test for the schema table parity row |

## Context excerpts
> (SDD §14 row "Configuration reader `TOP_LEVEL`, `CHILD_KEYS`, `export_shell` (scripts/afk-config.py)") C1: transport family key, one settings block per kind, kinds tuple with its `_choice` call, child-key entry per block; the pane switch, one key under the transport settings with the values pane or subagent, where no key means pane when a pane tool is found (S-230). C9: stage-map key, keyed by stage name, whose value is one pattern name or a list the resolver combines, and saved-pattern key, each with its own validator; roles as a map; refuse keys that fold to one shell name, unknown role fields, a saved pattern with a built-in name, 2 saved patterns with one name, and an include or stage map entry that names no pattern (S-96, S-229, S-230) … Reader ships first or with the first configuration using the keys, and learns the switch key in the same commit as the other new keys (S-230); a list overlay replaces a whole list; tests for collisions and missing patterns are new. Compatibility: the reader accepts the new keys, and an old configuration reads as before (S-246). Rollback: remove the new keys from the configuration first, then roll back the reader and the schema rows in one commit; an older reader refuses the new keys, and a refused configuration leaves every plugin setting empty (S-246)
> (SDD §14 row "Schema table rows in CONFIG.md ↔ `CHILD_KEYS` parity, and the adapter registry family enum") C2, C3: one family row and two topology rows, landed with the reader's key-map entry in one commit (S-62); two carve-outs from "every map is validated one level down" … "Four adapter families" becomes false in three documents (C4); add-a-family instructions written (C5). Compatibility: only adds (S-246). Rollback: in one commit with the reader, after the new keys leave the configuration (S-246)
> (SDD §14 row "Issue-report environment collector family list, mirroring `TOP_LEVEL` families") C8: the transport family added … No gate or test checks the list. Compatibility: only adds (S-246). Rollback: revert the commit, or install the previous plugin version (S-246)
> (SDD §4) | pane switch | one of pane, subagent | yes: the key may be absent | absent means pane when a pane tool is found | — | One key under the transport settings (S-230) | — | subagent turns role agents back into subagents and returns /afk:fix to one agent (S-230) | S-230, AC-041 |
> (SDD §5) | Stage map entry per stage: key the stage name, value one pattern name or a list the resolver combines (S-230) | absent: the plugin ships no stage map; the contact agent proposes patterns from their descriptions and the human picks (AC-032, S-143). With no entry and no pick, the stage runs as today (AC-001, S-230): today's team shape and model rules (D-09, agent-decided) | the human adds entries per stage | none; permanent configuration |
> (SDD §5) | Saved patterns | absent: only the built-in patterns BP-1 to BP-5 (S-143, AC-034) | the human saves patterns in configuration (§14 C9) | none; permanent configuration |
> (SDD §5) | Pane switch: one key under the transport settings, pane or subagent (S-230) | absent: pane when a pane tool is found; role agents are pane agents wherever the plugin is enabled (AC-041, S-230) | set it to switch role agents back to subagents; it also returns /afk:fix to its old run in one agent (S-201, AC-044) | none |
> (SDD §5) | Transport kind override | absent: the probe chooses (S-55) | optional | none |
> (SDD §13 Q54) (4) A saved pattern's charter fields live in the human's configuration, whose reader refuses an unknown role field (§14 C9): the saved-pattern validator learns the charter fields in the same commit as the other pattern keys (inferred; the §14 configuration-reader row stands under the exception of 2026-10-02 and is not changed here).
> (SDD §14) INV-005: a local override of one role replaces the whole role list. Accepted; roles as a map (S-96) limits it to the map level.
> (PRD AC-002) **AC-002** Team topology and multi-model are independently switchable; all four combinations run.
> (PRD AC-003) **AC-003** A pattern is accepted as data, whether it shipped with the plugin or the user wrote it, and a user-written pattern may declare every field a built-in one declares.
> (PRD AC-032) **AC-032** A pattern carries a description of how and when it is useful and names no workflow stage. The plugin ships no stage map. The human's configuration may map a stage to one pattern, or to a list of patterns combined into one team. With no entry, the contact agent proposes patterns from their descriptions, possibly several combined, and the human picks. With no pattern picked, or no human present, the stage runs as it does today.
> (PRD AC-041) **AC-041** The pane-agent default applies whenever the plugin is enabled and a pane transport is found; nothing needs configuring. One configuration key switches role agents back to subagents. A session without the plugin enabled is unchanged.
> (PRD AC-062) **AC-062** Reading configuration refuses 3 errors: a saved pattern that uses a built-in pattern's name; 2 saved patterns with one name; an include or a stage-map entry that names no pattern.
> (ADR-0001) The transport is a fifth adapter family with one kind per transport, the six verbs of SDD §3, and the house answer shapes (S-4, S-48, S-57). The existing dispatcher selects the kind and is not edited. A probe inside the feature's package resolves the best available kind and hands it to the dispatcher as if configured; a configuration key can force a kind (S-55, S-60). Everything else is a package inside the feature with one top-level entry script (S-48, S-52). The transport and the manifest never depend on each other (S-50).
> (ADR-0015) A change takes extends when every existing caller keeps the contract it has today and the change only adds: a key, a row, a field, a line, a step or a count (S-199). Its §14 row states what an older reader and a session with no team see, and how the change rolls back: revert the commit or install the previous plugin version, after the first step S-246 names for a change that needs one (S-246). The 13 rows cite this record as extends (design ADR-0015). Three later rows cite it too: the row of audit round 14 and the rows for the SessionStart hook and the built-in pattern records (charter C3 and C6); all three are agent-decided. The agent decided this under the human's delegation of 2026-09-30 (`GRILL-LOG.md` row "Agent-decided, 2026-10-05", design-audit open points, L31).

## Parent PRD
docs/afk/agent-team-topology/PRD.md

## Parent SDD
docs/afk/agent-team-topology/SDD.md

## Blocked by
(none)

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality
during implementation, classify per the decision protocol (`DECISIONS.md`,
workflow plugin root): a two-way-door correction is recorded in
`plan/DECISIONS.md` and implemented; a one-way door or a tie exits
`design_conflict` quoting the SDD section + the conflict. Never override off
the record. Parked conflicts route back to `/afk:grill-solution` for a
superseding ADR.
