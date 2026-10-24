# INV-011 — read-back and upload verbs

feat-small-lane@d346cfb · partial · 8/14 boundaries closed · 1535 nodes · ledger: COVERAGE.json

## Answer

Tracker `none` and forge `none` answer `unsupported` to every verb (`tracker/none/api.py:21`, `forge/none/forge.sh:10`).

| Write | Read-back verb | Returns / match | Works on |
|---|---|---|---|
| tracker create | `tracker_search` | Jira: JQL; summary, status, type, assignee, priority, dates (`jira/api.py:453,512-523`). github-issues: `gh issue list --search`; number, title, state, labels, url; no body, no `--state`, `fields` ignored (`github-issues/api.py:172-179`). Jira create sets no labels (`jira/api.py:563-612`) | jira, github-issues |
| tracker comment | `tracker_get` | Jira: comments only when `fields` includes `comment` (not default, `jira/api.py:451,506-509`); github-issues: comments and body by default (`github-issues/api.py:162-169`) | jira, github-issues |
| tracker transition | Jira `tracker_get fields=status` or `tracker_changelog` (`jira/api.py:535-537`); github-issues `tracker_transitions` (`github-issues/api.py:182-203`) | status field / state marked `current:true` | jira, github-issues |
| attachment upload | `tracker_attachments` | Jira: id, filename, mimeType, size, created, author (`jira/api.py:545-555`), match by filename as `publish_prd.py:285-289`; github-issues: asset URLs in text only, `partial` (`github-issues/api.py:251-265`) | jira; github-issues partial |
| change-create-draft | `change-view {"id":<branch>}` | id, url, state, draft, source, target, head_sha; `missing:true` only when the forge confirms none (github `forge.sh:146-150,281-295`; gitlab `forge.sh:218-220,278-292`); `forge_ledger.py:1831-1840` already looks up by branch | github, gitlab |
| change-comment | `note-list`; `thread-list` for inline | `{notes:[{id,author,body,…}],count}`; GitLab drops system and inline notes (gitlab `forge.sh:554-571`) | github, gitlab |
| change-update-body | `change-fetch` only | body not on stdout; in `files.metadata` mr.json (github `forge.sh:315`; gitlab `forge.sh:324`) | github, gitlab |

**Jira upload:** `Jira.upload_attachment`, `jira/api.py:180-197`; no MCP tool exposes it; reached only via `scripts/tracker_api.py:36-50`. Every file sent as `image/png` (`:189`), type unchecked; `png_size` reads PNG headers only (`:222-231`). Why PNG (inferred): both callers embed inline in the description, which needs media id + width/height (`:199-209`; `publish_prd.py:290-304`; `publish_bug.py:250-265`).

**Other upload paths:** none in github-issues, forge github, forge gitlab (closed B1–B13; B14 frontier).

## Findings

- `github-issues/CONTRACT.md:54-55` says `tracker_attachments` returns a comment it wrote; the code only reads.
- Inferred: `publish_bug.py:92-119` retries a POST after a server error or network failure and can duplicate.
- Inferred: no test covers `tracker_search`, `tracker_attachments`, or `change-view` by branch.

## Unverified

- B3, B5, B6, B7, B10: no pre-pass method; sites read by tracers, merge keeps the worse status.
- Live checks, load-bearing: which change `gh pr view` / `glab mr view` picks when a branch has several or closed changes; whether `gh issue list` shows open issues only by default; shape of Jira `fields=comment`; whether GitLab mr.json names the body `description`.

## Frontier

B14: live forge and tracker APIs; other repositories.

Written by the orchestrator from the investigation's reply; the investigation's own REPORT.md write was refused.
