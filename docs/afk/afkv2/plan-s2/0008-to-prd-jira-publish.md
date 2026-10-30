# 0008-to-prd-jira-publish

## Goal
Write `/afkv2:to-prd`: PRD + requirement ADRs + INDEX.md from the settled grill,
no new questions, AC-NNN and WE-NN ids that are never renumbered, and the Jira
publish: preview with pictures and receipt, the developer's yes, picture upload,
stale-checked block write, read-back, and removal of unused afkv2 and v1
pictures, all through the tracker verbs.

## Complexity
complex

## Design refs
- SDD: SDD.md#§3 L2 — Service Boundaries & Integration — tracker verbs, publish sequence
- SDD: SDD.md#§5 L4 — Cross-Cutting & Quality Attributes — Jira authz (signed HL-3), idempotency
- SDD: SDD.md#§7 L6 — Process & Coordination — publish use case, failure matrix, v1 defect table (signed HL-5)
- SDD: SDD.md#§14 L9 — Implementation Seams & Change Impact — row "v1 PRD block written by build_description"
- ADR: adr/design/0004-jira-publish-order-and-stale-check.md
- ADR: adr/requirements/0005-jira-write-boundary.md

## Scope
- afkv2/skills/to-prd/**
- afkv2/tests/skills/test_to_prd.py
- afkv2/tests/skills/fakes/*

## Seams
- use: v1 PRD block written by build_description — the first afkv2 publish replaces a v1 `afk:prd` block through description-put and deletes v1 pictures after the read-back (INV-002)

## Acceptance
- [ ] to-prd writes PRD.md, requirement ADRs and INDEX.md from the settled grill and asks no new question (PRD §SK-08)
- [ ] Every acceptance criterion and worked example has a stable id (AC-NNN, WE-NN) that is never renumbered (PRD §AC-050)
- [ ] The preview shows the exact text and pictures; nothing is written to Jira before the developer's yes (PRD §AC-051)
- [ ] The publish is refused when an AC id or a WE id of the PRD is missing from the published text (PRD §AC-055)
- [ ] Receipt = SHA-256 of ticket key + block text + picture hashes; new pictures are named `afkv2-fig-<receipt 8 chars>-<n>.png`; a re-run after success finds an equal read-back and writes nothing (SDD §5 Idempotency; SDD §8 row "tracker port")
- [ ] Order: issue-get → preview + receipt → yes → attachment-put → description-put with expect_hash and receipt → issue-get read-back → compare text and media ids → attachment-delete of afkv2 and v1 pictures the new block does not use (ADR-0004 design)
- [ ] `stale` → new preview and a new yes; `bad-block` → the problem is named and nothing is written; a read-back mismatch is reported as a failed publish and old pictures stay (PRD §AC-056, §AC-057, §AC-058)
- [ ] The first publish to a ticket with no afkv2 and no v1 block appends the block at the end and keeps the rest; a v1 `afk:prd` block is replaced (PRD §AC-053; PRD §WE-04)
- [ ] The publish never removes ticket text because of its content or size: a fixture with a short section before and after the block keeps both unchanged (PRD §AC-059)
- [ ] Each PRD diagram appears as a picture; a re-publish replaces the pictures and adds no copies (PRD §AC-054)
- [ ] Each successful publish appends one line `<ISO-8601 UTC> <ticket key> <receipt 8 chars>` to `%LOCALAPPDATA%\afkv2\published-tickets.txt` (PLAN.md decision D-S-3; read by setup switch-back)
- [ ] Jira writes happen only in this skill (SDD §5 AuthZ row "publish PRD")

## Produces
- afkv2/skills/to-prd/SKILL.md#name: to-prd — the to-prd skill
- afkv2/skills/to-prd/scripts/publish.py#def build_preview( — block, pictures, receipt
- afkv2/skills/to-prd/scripts/publish.py#def check_ids_present( — AC-055 id check
- afkv2/skills/to-prd/scripts/publish.py#def publish_after_yes( — the ordered write sequence

## Consumes
- 0007-grill-skill afkv2/skills/grill/SKILL.md#name: grill — the settled grill output to-prd reads

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | every `afkv2/skills/to-prd/**/SKILL.md` has Agent Skills frontmatter (`name`, `description`); `afk-python -m compileall -q afkv2/skills/to-prd`; `rg -F` each ## Produces anchor | skill files parse; declared symbols present |
| unit | `afk-python -m pytest afkv2/tests/skills/test_to_prd.py -q` | id check, receipt, picture names, block build, published-tickets line |
| integration | publish sequence against a recorded fake of the SDD §3 tracker verbs: first publish (append), v1 block replaced, re-publish (no copies), `stale`, `bad-block`, `bad-receipt`, read-back mismatch, short sections around the block unchanged. The live publish on the D-4 test ticket runs in 0016 | the ADR-0004 order and every failure row of SDD §7 |

## Context excerpts
> (SDD §3 tracker row) | Jira tracker | issue-get, md-to-adf, attachment-list, attachment-put, attachment-delete, description-put | one JSON payload | `{"ok": true, ...}`; attachment-put returns attachment id + media id | same shape; codes from an HTTP-status table; description-put refuses `stale`, `bad-receipt` and `bad-block` | 0 · 1 · 2 |

> (SDD §3 caption) S2 owns what is written (block, pictures, id check, preview, receipt); S3 owns how it reaches Jira.

> (ADR-0004 design) Preview (read the ticket, build the block with picture placeholders, render pictures, write the receipt) → developer yes → upload new pictures under receipt-carrying names → description-put compares a hash of the current description with the preview's, read just before the write, then writes only the managed block → read-back compares text and media ids → delete afkv2 and v1 pictures the new block does not use. The receipt is the idempotency key. A v1 `afk:prd` block is replaced on the first afkv2 publish.

> (SDD §5 Idempotency) | Jira publish | receipt = SHA-256 of ticket key + block text + picture hashes | until the next publish | a re-run after success finds an equal read-back and writes nothing |

> (SDD §7 v1 defect table) | no block found by prefix → a second PRD is appended, and the change comment is lost | append happens only when the description has no afkv2 block and no v1 block (AC-053); a broken or doubled block is refused with `bad-block` (AC-058); the port has no comment step, so the publish result goes to the developer | AC-053, AC-058 tests |

> (SDD §14 row) | v1 PRD block written by build_description | (INV-002), (INV-004) | the first afkv2 publish replaces a v1 `afk:prd` block with the afkv2 block and deletes v1 pictures after the read-back | (INV-002), (INV-004): v1 finds its block by the `afk:prd:start` prefix only and never deletes `afkv2-fig-*` pictures | text outside the block stays unchanged | reworked |

> (PRD §AC-058) The publish finds the AFK block only by its full begin and end lines. A begin line without an end line, an end line without a begin line, or 2 or more blocks makes the publish refuse with nothing written, and the agent names the problem.

> (PRD §AC-059) The publish never removes ticket text because of its content or its size. A test ticket with a short section before and after the block keeps both sections unchanged.

## Parent PRD
docs/afk/afkv2/PRD.md

## Parent SDD
docs/afk/afkv2/SDD.md

## Blocked by
- 0007-grill-skill

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality
during implementation, classify per the decision protocol (`DECISIONS.md`,
workflow plugin root): a two-way-door correction is recorded in
`plan/DECISIONS.md` (this plan folder's `DECISIONS.md`) and implemented; a
one-way door or a tie exits `design_conflict` quoting the SDD section + the
conflict. Never override off the record. Parked conflicts route back to
`/afk:grill-solution` for a superseding ADR.
