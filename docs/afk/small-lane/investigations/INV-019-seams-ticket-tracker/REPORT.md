# INV-019 — L9 seams: to-ticket bug mode, tracker_attach, config reads

`feat-small-lane@d346cfb · partial · boundaries 0/14 closed · unverified 4 (load-bearing 0)` (ledger `COVERAGE.json`, 4157 nodes, 39 claims; validator accepted before and after stamp). Frontier B14: live Jira/GitHub, user harness allowlists, other repositories. Written by the orchestrator from the run's reply; the run's own write was refused.

B1, B2, B4, B8, B9, B11, B12, B13 partial (alias/wire forms not searched); B3, B5, B6, B7, B10 no method. No `investigation:` block in `.afk/config.yaml` (`CONFIG.md:240`), default patterns only.

## Seam rows (draft)

| Seam | Existing contract | Planned change | Impacted | Verdict |
|---|---|---|---|---|
| S1 to-ticket bug/ad-hoc script | `publish_prd.py:67-75` loads Jira-only symbols at import → exits on github-issues/none (`tracker_api.py:44-49`); `publish_meeting.py:52` inherits it; `Jira` client has no create/transition/versions/retry (`publish_bug.py:92-118` uses `jira._req`); `tracker_create`/`tracker_comment` on Jira wrap text in one plain ADF paragraph (`jira/api.py:495-499,541,574`); GitHub sends markdown via `--body-file -` (`github-issues/api.py:247,314`), `fix_version` → `--milestone` (`:320`); only `server.py:101` calls an adapter `call()` | one new script driving adapter verbs via `tracker_api.load(("call",))`; never imports `publish_prd` | none in production; no test imports `publish_prd`/`publish_meeting` | extends |
| S2 existing modes | PRD mode: refuses no parent (`SKILL.md:25`), wrong type (`publish_prd.py:273`), dry-run (`:279-331`), y/N unless `--yes` (`:333`), replaces `afk-fig` (`:285-289`), `--changes` on re-publish (`:309`), INDEX row (`SKILL.md:53`); meeting mode keyed by expand title (`publish_meeting.py:77-98`), refuses empty body (`:122`); spinoff dedup `filed {KEY}`, human-present (`SKILL.md:95,99`) | bug mode owns a disjoint region or comments only; never touches `afk:prd` or "Meeting Summaries" | `SKILL.md:10,16` text | fits |
| S3 tracker_attach + check E | `upload_attachment` hard-codes `image/png`, no same-name check (`jira/api.py:180-197`; pinned `test_tracker_jira.py:307`); check E substring `adapter_registry_check.py:94` — `tracker_attach` already matches via `tracker_attachments`; exact match: 0 misses on 11 kinds today; caller `skill-registry-gate.sh:201,212`; only positive test `test_skill_registry_gate.py:57` | new verb + exact-match check | edit list below; `FRESHNESS.md:84,86` | extends |
| S4 config reads | nothing reads `jira.transitions`, `jira.issue-types`, fix version (`afk-config.py:109,626-637` validate only); Jira adapter reads no config (`jira/api.py:502,564`); `state-labels` read `github-issues/api.py:84,219,316`, unknown status on create dropped silently | reader resolves name or id against `tracker_transitions`, refuses unconfigured | docs wrong: `jira/CONTRACT.md:26-28`, `adapter.json:22-25`, `server.py:162-163` | extends |

## tracker_attach edit list

`operations` in 3 `adapter.json`; verb list in 3 `CONTRACT.md`; `OPERATIONS` (`jira/api.py:445`, `github-issues/api.py:35`, `none/api.py:12`); `_DISPATCH` + `_op_attach` (`jira/api.py:615`, `github-issues/api.py:341`); one `@mcp.tool` (`server.py:104-175`); "nine" claims `ADAPTERS.md:42,50,51`, `jira/CONTRACT.md:38,49`, `server.py:1,3`, `tracker_api.py:4`, `PARITY.md:148`, `CONFORMANCE.md:95`; `FRESHNESS.md:84` (`.mcp.json`, MANIFEST H2/P1).

## Landmines

- Rich Jira body arrives as raw markdown in one paragraph unless the Jira adapter converts (L8: kind differences stay in adapters).
- Spec-folder re-resolve via notes `resolve` (`adapters/notes/common.sh:56-76,126`); `git mv` only for `notes: repo-files`; obsidian/notion outside repo (`obsidian/notes.sh:11-20`); template without `{workId}`/`{ticket}` never moves (inferred).
- `jira.transitions` values disagree: init template writes a name (`afk-config.py:1032`), sample + test an id (`monorepo-config.yaml:20`, `test_afk_config.py:75`); Jira create matches `status` by name, miss only `status_warning` (`jira/api.py:601-611`); `tracker_transition` takes an id (`:530`).
- State key names: `ready-for-review` (Jira scaffold `afk-config.py:1032`) vs `in-review` (GitHub `:1048`, this repo `.afk/config.yaml:13`) — pick one.
- No fix-version config key; adding one moves `CHILD_KEYS`, `CONFIG.md:119`, `test_afk_config.py:378` together.
- Check E config-key test passes on first segment (`:107-110`); exact would fail 13 keys today — out of scope unless asked.
- Guard `MUTATING` (`protected_branch_guard.py:40,91-95`) has no "attach" → tool judged `allow`; a name with "upload"/"post" + `path` would judge as local write (inferred).
- Local gh 2.92.0 lacks `--attach` — confirms the gh ≥2.99.0 floor (R-4 D-23).
- `github-issues/CONTRACT.md:54` claims a write the code does not make.

## Must-dos the new path could skip

1. Dry-run + y/N before any write (`publish_prd.py:279-336`).
2. Ticket-type check before writing to a key (`:273`).
3. Check fix version against `/project/{key}/versions`; unknown → write nothing (`publish_bug.py:199-206,221,286`; `test_publish_bug.py:247-271`); no tracker verb lists versions; Jira `_op_create` sends `fixVersions` unchecked (`jira/api.py:577-578`).
4. Ask fix version without blocking, then backfill (`bug/SKILL.md:53-55`); backfill via `tracker_edit` (inferred, `jira/api.py:558`).
5. Screenshot failure keeps the ticket, becomes a warning (`publish_bug.py:239-265`).
6. Check each adapter answer — verbs answer `error` with exit 0 (INV-015).
7. Transition id (`publish_bug.py:67`) and type `"Bug"` (`:157`) read from config, not hard-coded.
8. Human present (`SKILL.md:99`, `SPINOFF-TICKET.md:44`).

## Unverified

- `scripts/tests/test_publish_bug.py:25` tracer conflict (terminal vs irrelevant).
- `PARITY.md:148`, `CONFORMANCE.md:95`, `CONFIG.md:119`: first pass breaks, counter-search unchanged.
- Live Jira: non-PNG content type, same-name uploads, unknown `fix_version` on create; `_adf_text` newline rendering (inferred).

## Stale docs once publish_bug is removed

`AGENTS.md:9,195`, `README.md:120`, `GLOSSARY.md:262`, `FRESHNESS.md:79,86`, `MANIFEST.md:66,737,741`, `CAPABILITIES.md:65`, `to-meeting-d/SKILL.md:114`.

## Fold notes (plugin defects)

3751 seed placeholders dropped; blind tracer duplicated 33 ids (its copies dropped, orphaned edges → terminal, `sites` removed from search-closed rows); `validate_coverage.py:355` rejects an `irrelevant` read site that LEDGER-FORMAT allows.
