# 0007-grill-skill

## Goal
Write `/afkv2:grill`: read a ticket with its comments and links through the
tracker port, an optional round 0, requirement rounds on the page (page document
written by the agent, rendered and shown by the engine), the claim ledger, the
exit gate, `GRILL-LOG.md` and glossary terms. One page document per session.

## Complexity
complex

## Design refs
- SDD: SDD.md#§3 L2 — Service Boundaries & Integration — engine verbs, tracker verbs
- SDD: SDD.md#§4 L3 — Data Architecture — page document path
- SDD: SDD.md#§7 L6 — Process & Coordination — page round, Codex page wake
- ADR: adr/design/0001-page-engine-verbs-and-schema-v0.md
- ADR: adr/design/0006-codex-page-wake-through-stop-hook.md

## Scope
- afkv2/skills/grill/**
- afkv2/tests/skills/test_grill.py
- afkv2/tests/skills/fakes/*

## Seams
(none — this slice touches no SDD §14 seam row; its §9b rows are in ## Acceptance and the PLAN.md seam register)

## Acceptance
- [ ] The grill reads the ticket with its comments and linked tickets through the tracker verbs issue-get (Jira) or issue-get / issue-search (GitHub issues) (PRD §SK-07)
- [ ] Round 0 is optional; each round is one page document `pages/grill-<session id>.json` in the spec folder, written by the agent and rendered and shown by the engine; the agent never writes HTML (SDD §4; ADR-0001 requirements)
- [ ] On Claude the grill waits for the answer with a tracked background poll; on Codex it ends its turn after show and the Stop hook hands the answer back (ADR-0006 design)
- [ ] The grill reads the answer through ingest and settles only what the §6 rules settle; it writes its reading for every note-settled point (PRD §AC-036)
- [ ] The claim ledger, settled rows and verbatim owner notes go to `GRILL-LOG.md`; resolved terms go to the glossary as they settle (PRD §WE-01 grill row)
- [ ] Run without its required input, the skill stops and names the missing file and the skill that writes it; it reads only what is on disk (PRD §AC-002, §AC-003)
- [ ] No step asks for a lane or chooses one (PRD §AC-004)
- [ ] A picture of the current state comes before a critical-aspect question (PRD §AC-043)

## Produces
- afkv2/skills/grill/SKILL.md#description: /afkv2:grill — the grill skill
- afkv2/skills/grill/scripts/round_document.py#def build_round_document( — writes a schema-v0 round document

## Consumes
- 0006-visualize-skill afkv2/skills/visualize/SKILL.md#name: visualize — component guide the rounds follow

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | every `afkv2/skills/grill/**/SKILL.md` has Agent Skills frontmatter (`name`, `description`); `afk-python -m compileall -q afkv2/skills/grill`; `rg -F` each ## Produces anchor | skill files parse; declared symbols present |
| unit | `afk-python -m pytest afkv2/tests/skills/test_grill.py -q` | round document builder output has the SDD §4 required fields; missing-input refusal names file + writer |
| integration | scripted dry run against recorded fakes of the tracker and engine verbs (SDD §3): a ticket fixture with 2 comments and 1 linked ticket gives a round-1 document, a fake ingest answer settles one point by mark and one by note | the skill drives the SDD §3 contracts in the right order |

## Context excerpts
> (PRD §SK-07) | SK-07 | `/afkv2:grill` | reads a ticket with comments and links; optional round 0; requirement rounds on the page; claim ledger; exit gate | K-3, decision 62, 63 |

> (PRD §WE-01) | grill | ticket with 2 comments and 1 linked ticket | GRILL-LOG.md, page document, glossary terms |

> (PRD §AC-002) Each chain skill reads only what earlier skills wrote to disk. A skill run on a spec folder that has the required input succeeds without the earlier skill's session.

> (PRD §AC-003) A skill that is run without its required input stops and names the missing file and the skill that writes it.

> (SDD §4) | Page document | JSON file in the feature spec folder (`pages/<skill>-<session id>.json`) | one file per page session | git, with the spec folder | merges with the change; kept in git history | new value `afkv2.page/N`; the engine keeps a reader for every value it wrote and upgrades in memory | no | no |

> (SDD §7 caption) On Claude the agent keeps v1's tracked background poll; only Codex needs the Stop hook.

> (SDD §3 caption) Each edge is a frozen contract; the producer owns it and the consumer tests against a recorded fake.

## Parent PRD
docs/afk/afkv2/PRD.md

## Parent SDD
docs/afk/afkv2/SDD.md

## Blocked by
- 0006-visualize-skill

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality
during implementation, classify per the decision protocol (`DECISIONS.md`,
workflow plugin root): a two-way-door correction is recorded in
`plan/DECISIONS.md` (this plan folder's `DECISIONS.md`) and implemented; a
one-way door or a tie exits `design_conflict` quoting the SDD section + the
conflict. Never override off the record. Parked conflicts route back to
`/afk:grill-solution` for a superseding ADR.
