## Goal
Give the tracker adapters and the tracker MCP server a tenth verb, `tracker_attach`, on Jira, GitHub Issues and `none`; make Jira create and comment send formatted text (markdown → Atlassian Document Format) and upload files with their real content type, read back after upload; check the in-review key against the tracker's transitions and refuse an unknown fix version before any write; match verb names whole in registry check E; and record the gh 2.99.0 floor.

## Complexity
complex

## Design refs
- SDD: SDD.md#§3 L2 — Service Boundaries & Integration — adapter family table, tracker rows
- SDD: SDD.md#§9b External Seams & Failure Affordance — rows "GitHub Issues attach", "Jira attachment upload", "Jira rich text", "Field truth"
- SDD: SDD.md#§8 L7 — Module Decomposition — row "tracker adapters + MCP server"
- SDD: SDD.md#§10 NFRs — row "Minimum gh version for inline images on GitHub Issues"
- ADR: adr/design/0004-proof-on-the-ticket-through-tracker-attach.md — new verb, real content type, read-back, registry exact match
- ADR: adr/design/0009-bug-mode-drives-tracker-adapter-verbs.md — kind differences live inside each adapter

## Scope
- adapters/tracker/*/api.py
- adapters/tracker/*/CONTRACT.md
- adapters/tracker/*/adapter.json
- adapters/tracker/payload.py
- mcp-servers/tracker/server.py
- ADAPTERS.md
- hooks/lib/adapter_registry_check.py
- scripts/afk-config.py
- skills/afk/setup/MANIFEST.md
- skills/afk/setup/SKILL.md
- providers/CONFORMANCE.md
- scripts/tests/test_tracker_*.py
- scripts/tests/test_skill_registry_gate.py
- scripts/tests/test_plugin_source_gates.py
- .mcp.json
- skills/afk/to-ticket/scripts/publish_prd.py
- skills/afk/bug/scripts/publish_bug.py
- CHANGELOG.md

## Seams
- implement: tracker adapters: `tracker_create`, `upload_attachment`, `fixVersions`, `state-labels` — §9b boundaries "GitHub Issues attach", "Jira attachment upload", "Jira rich text" and "Field truth"; owns their seam-tests (INV-024)
- implement: registry check E: `adapter_registry_check` — whole-name verb match (INV-024)

## Acceptance
- [ ] `tracker_attach` exists on the Jira, GitHub Issues and `none` adapters and on the tracker MCP server, and every home that counts or lists the tracker verbs names ten (SDD §14 row "tracker adapters: `tracker_create`, `upload_attachment`, `fixVersions`, `state-labels`")
- [ ] On GitHub Issues, `tracker_attach` posts one comment carrying one `--attach` per image or video file; another file type, GitHub Enterprise Server, gh older than 2.99.0 and kind `none` answer unsupported for that file, and the file is named in the comment (SDD §9b row "GitHub Issues attach")
- [ ] On Jira, the upload sends each file's real content type instead of `image/png`, then reads back each stored name and type and reports a mismatch (SDD §9b row "Jira attachment upload")
- [ ] Jira create and comment convert markdown headings, lists, code and links into the matching Atlassian Document Format nodes instead of one plain paragraph (SDD §9b row "Jira rich text")
- [ ] The in-review key, read from `jira.transitions` or `github-issues.state-labels`, is matched by name or id against the tracker's transitions; an unknown key is refused before any write (SDD §9b row "Field truth")
- [ ] On Jira, an unknown fix version is refused before any write (SDD §9b row "Field truth")
- [ ] The config scaffold's Jira in-review key is renamed so both trackers use one in-review key (SDD §4)
- [ ] Registry check E matches a verb name whole: `tracker_attach` does not satisfy `tracker_attachments`, nor the reverse (SDD §14 row "registry check E: `adapter_registry_check`")
- [ ] The dependency register carries a gh ≥ 2.99.0 floor row and `/afk:setup` probes it (SDD §10)
- [ ] Existing tests stay green: the `.png` upload in `test_tracker_jira.py` and the single create request in `test_tracker_create_assignee.py` (SDD §14 row "tracker adapters: `tracker_create`, `upload_attachment`, `fixVersions`, `state-labels`")
- [ ] Seam-tests assert on the real outgoing call: the stub gh argv, the multipart content type of the stub HTTP request, and the ADF document structure, not our intermediate objects (SDD §9b)
- [ ] Implements the public interface of SDD §8 row "tracker adapters + MCP server" unmodified (SDD §8)
- [ ] Conforms to ADR-0004 and ADR-0009 design — the bug-mode caller sees one verb set (design ADR-0004)

## Produces
- mcp-servers/tracker/server.py#def tracker_attach( — the tenth MCP tool
- adapters/tracker/jira/api.py#"tracker_attach": — Jira op: real content type, read-back of stored name and type
- adapters/tracker/github-issues/api.py#"tracker_attach": — GitHub Issues op: one comment, one `--attach` per supported file
- adapters/tracker/none/api.py#"tracker_attach", — `none` lists the verb and answers unsupported
- skills/afk/setup/MANIFEST.md#gh ≥ 2.99.0 floor — the dependency floor row

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `bash hooks/plugin-source-gates.sh --staged`; grep each ## Produces anchor | gates pass, incl. registry check E; declared symbols present |
| unit | `afk-python -m pytest scripts/tests/test_tracker_jira.py scripts/tests/test_tracker_surface.py scripts/tests/test_tracker_server.py scripts/tests/test_tracker_registration.py scripts/tests/test_tracker_create_assignee.py scripts/tests/test_skill_registry_gate.py -q` | verb present on every adapter and the server; in-review and fix-version refusals before any write; whole-name registry match |
| integration | seam-tests in `scripts/tests/test_tracker_attach.py`: stub-gh argv carries one `--attach` per supported file and none for others; stub-HTTP multipart content type equals the file's type; ADF structure for headings, lists, code, links | the outside tools receive the real values (§9b) |
| integration | `afk-python -m pytest scripts/tests -q` and `bash hooks/tests/hook-smoke.sh`, on Windows and WSL | nothing else broke |

## Context excerpts
> (SDD §9b) | GitHub Issues attach | gh ≥ 2.99.0 `gh issue comment --attach` (docs.github.com "Attaching files with GitHub CLI"; github.blog changelog 2026-09-01) | uploads image/video files and embeds them inline in the comment body | older gh, GitHub Enterprise Server, other types, no push access → unsupported per file, file named in the comment | stub-gh test asserting the argv carries one `--attach` per supported file and none for others; live run before release |
> (SDD §9b) | Jira attachment upload | Jira Cloud REST attachments endpoint | stores the file; the stored type and same-name handling are undocumented (INV-024) | today hard-coded `image/png`; after upload the bug mode reads back each file's stored name and type and names a mismatch; proof names are unique per diagnosis | stub-HTTP test asserting the multipart content type equals the file's type; live run before release |
> (SDD §9b) | Jira rich text | Atlassian Document Format | renders our markdown | today one plain paragraph (INV-024) | test asserting the ADF document structure for headings, lists, code, links |
> (SDD §9b) | Field truth | ticket key: tracker; in-review state: `jira.transitions` / `github-issues.state-labels` checked against tracker transitions; fix version: Jira project versions | — | unknown → refused before any write | stub-tracker tests per refusal |
> (SDD §3) | tracker | `tracker_attach` (new, tenth verb) | bug mode, for proof files | Jira: upload with the file's real content type, media embedded; each file's stored name and type read back after upload, a mismatch named in the comment. GitHub Issues: one comment with each image or video inline through `gh issue comment --attach`; another file type, GitHub Enterprise Server, gh older than 2.99.0, and kind `none` answer unsupported for that file |
> (SDD §3) | tracker | get, create, edit, transition, comment | bug mode; get also by diagnose and fix | Jira create/comment send formatted text (markdown → Atlassian Document Format) |
> (SDD §14 row "tracker adapters: …") INV-024: create/comment flatten to one ADF paragraph (`jira/api.py:495-499`); upload hard-codes `image/png` (`:180-197`); nothing reads `jira.transitions` | `tracker_attach`; markdown → ADF; in-review key as name or id checked against transitions; unknown fix version refused; scaffold key renamed | INV-024: `tracker_attach` edit list: 3 adapters (`none/api.py:4`, `github-issues/api.py:4`), MCP server (`server.py:138`), `ADAPTERS.md:51,58`, `MANIFEST.md:737-738`, `CONFORMANCE.md:96`, "nine verbs" claims; `test_tracker_jira.py:307` uploads a `.png` and stays green | live Jira checks before release; an unparseable `github-issues/adapter.json` silently disables the comment gate (`comment_gate.py:518-523`)
> (SDD §14 row "registry check E: `adapter_registry_check`") INV-024: substring match (`adapter_registry_check.py:94`) | whole-name match | INV-024: `skill-registry-gate.sh:201,212`; `test_skill_registry_gate.py:59`; `test_plugin_source_gates.py:263,423,477`; CI `tests.yml:85,99` | config-key prefix match left as is
> (SDD §10) | Minimum gh version for inline images on GitHub Issues | 2.99.0 | `/afk:setup` probe, dependency register | `/afk:setup` |

## Parent PRD
docs/afk/small-lane/PRD.md

## Parent SDD
docs/afk/small-lane/SDD.md

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
