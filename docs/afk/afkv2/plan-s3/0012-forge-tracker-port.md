# 0012-forge-tracker-port

## Goal
Port the forge and tracker code. Forge: a Python rewrite of only the commands
the chain calls, on GitHub (gh) and GitLab (glab), with v1 command names and v1
JSON answers inside the afkv2 envelope. Tracker: the ported v1 Jira REST client
(issue-get, md-to-adf, attachment-list, attachment-put, attachment-delete,
description-put) and the GitHub-issue reads (issue-get, issue-search).

## Complexity
complex

## Design refs
- SDD: SDD.md#§3 L2 — Service Boundaries & Integration — tracker and forge rows, publish sequence
- SDD: SDD.md#§5 L4 — Cross-Cutting & Quality Attributes — authz, retry + timeout, secrets
- SDD: SDD.md#§7 L6 — Process & Coordination — v1 defect table
- SDD: SDD.md#§9b External Seams & Failure Affordance — row Jira REST
- SDD: SDD.md#§14 L9 — Implementation Seams & Change Impact — row "v1 PRD block written by build_description"
- ADR: adr/design/0003-jira-through-the-v1-rest-client.md
- ADR: adr/design/0007-forge-port-python-rewrite.md

## Scope
- afkv2/ports/tracker/**
- afkv2/ports/forge/**
- afkv2/tests/ports/**

## Seams
- implement: v1 PRD block written by build_description — description-put writes between the full `afkv2:prd:start/end` lines, replaces a v1 `afk:prd` block, refuses a broken or doubled block (INV-002)

## Acceptance
- [ ] Every tracker and forge command answers one JSON object: `{"ok": true, ...}` or `{"ok": false, "error": {"code", "reason"}}`, exit 0, 1 or 2; error codes come from an HTTP-status table; v1's `error: true` at exit 0 is gone (SDD §3)
- [ ] Jira calls go through the ported v1 REST client; credentials are looked up as v1 does; no acli (ADR-0003 design)
- [ ] The tracker port has no create, transition or comment verb (SDD §5 AuthZ row "create ticket, change status, comment")
- [ ] description-put and attachment-put refuse without a receipt that matches the preview hash (`bad-receipt`); description-put reads the description just before the write and refuses `stale` when its hash differs from expect_hash (SDD §5; ADR-0004 design)
- [ ] description-put finds a block only by full begin and end lines (`afkv2:prd:start/end`, or v1 `afk:prd` lines to replace); begin without end, end without begin, or 2 or more blocks → `bad-block`, nothing written; no block → append at the end (PRD §AC-058, §AC-053)
- [ ] description-put changes only the text between the block lines; a description with a short section before and after the block keeps both byte-identical (PRD §AC-059, §AC-052)
- [ ] attachment-put returns the attachment id and the media id; picture names follow `afkv2-fig-<receipt 8 chars>-<n>.png` (SDD §8 row "tracker port")
- [ ] Jira REST: one attempt, no retry, timeout 60 s (SDD §5 Retry + timeout)
- [ ] Forge: only the commands the chain calls, v1 names and JSON answers, the same on GitHub and GitLab (PRD §AC-066; ADR-0007 design)
- [ ] The ported v1 tests pass under afkv2 names; one live round-trip on a real pull request: this session's own Draft pull request (PRD Testing Decisions)
- [ ] Seam-test on Jira REST: the read-back compare on text and media ids runs against recorded Jira responses here; the live run on the D-4 test project is in 0016 (SDD §9b row "Jira REST")
- [ ] Implements the public interfaces in SDD §8 rows "tracker port" and "forge port" unmodified (SDD §8)

## Produces
- afkv2/ports/tracker/jira.py#def description_put( — stale-checked managed-block write
- afkv2/ports/tracker/jira.py#def attachment_put( — picture upload, returns attachment id + media id
- afkv2/ports/tracker/jira.py#def find_managed_block( — full-line block finder, bad-block refusal
- afkv2/ports/tracker/github_issues.py#def issue_search( — GitHub-issue reads
- afkv2/ports/tracker/cli.py#def tracker_main( — tracker command entry
- afkv2/ports/forge/forge_cli.py#def forge_main( — forge command entry

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `afk-python -m compileall -q afkv2/ports` + `rg -F` each ## Produces anchor in its file (exactly 1 hit) | code builds; declared symbols present |
| unit | `afk-python -m pytest afkv2/tests/ports -q` | ported v1 tests; envelope; block finder cases; stale; bad-receipt; no create/transition/comment verb |
| integration | live forge round-trip on this session's own Draft pull request (read the change, post and read one comment, read CI); Jira read-back compare against recorded Jira responses | the forge seam on real output; the Jira compare logic |

## Context excerpts
> (SDD §3 rows) | Jira tracker | issue-get, md-to-adf, attachment-list, attachment-put, attachment-delete, description-put | one JSON payload | `{"ok": true, ...}`; attachment-put returns attachment id + media id | same shape; codes from an HTTP-status table; description-put refuses `stale`, `bad-receipt` and `bad-block` | 0 · 1 · 2 |
> | GitHub issue tracker | issue-get, issue-search | one JSON payload | `{"ok": true, ...}` | same shape | 0 · 1 · 2 |
> | forge (GitHub, GitLab) | the commands the chain calls, v1 names and v1 JSON answers (ADR-0007) | v1 arguments | v1 JSON answer inside `{"ok": true, ...}` | same shape (replaces v1's `error: true` at exit 0) | 0 · 1 · 2 |

> (SDD §8 ported vs new) | tracker port | v1 Jira client (INV-002) | extends | answer envelope; create, transition and comment removed; own credential lookup; markers `afkv2:prd:start/end`; pictures `afkv2-fig-<receipt 8 chars>-<n>.png` |
> | forge port | v1 forge adapters (INV-002) | reworked | Python rewrite of the chain's commands (ADR-0007) |

> (SDD §5 AuthZ) | publish PRD (description block + pictures) | agent in `/afkv2:to-prd`, after the developer's yes | agent in every other skill | to-prd shows the preview and asks | description-put and attachment-put refuse without a receipt that matches the preview hash |

> (SDD §7 v1 defect table) | the near-empty rule deletes a short section of the description that is not the PRD block | the Jira port removes text only between the full AFK block lines; no rule removes text by its content or size | AC-059 test ticket |

> (SDD §14 row) | v1 PRD block written by build_description | (INV-002), (INV-004) | the first afkv2 publish replaces a v1 `afk:prd` block with the afkv2 block and deletes v1 pictures after the read-back | (INV-002), (INV-004): v1 finds its block by the `afk:prd:start` prefix only and never deletes `afkv2-fig-*` pictures | text outside the block stays unchanged | reworked |

> (SDD §9b) | Jira REST | Jira Cloud REST v3 | stores ADF; returns media id via the attachment redirect | 4xx/5xx mapped to error codes; ADF normalised on read (unverified) | read-back compare on text and media ids, on the D-4 test project |

> (PRD Testing Decisions) Forge and tracker port: the ported v1 tests, plus one live round-trip on a real pull request before merge. Stubs alone missed a live bug in v1.

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
