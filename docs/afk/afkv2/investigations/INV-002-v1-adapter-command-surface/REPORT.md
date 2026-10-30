midnightblur/afk-driver@22ab4de0ff03d9b3b79425494df03938b56d0899 · closed-with-frontier · boundaries 13/14 · unverified 0 (load-bearing 0) · ledger: docs/afk/afkv2/investigations/INV-002-v1-adapter-command-surface/COVERAGE.json

## Answer

- Forge: `afk_adapter forge <verb> '<json>'` (hooks/lib/adapter.sh:73-114). The kind comes from `AFK_CFG_FORGE` (:29-35). The entry is `runner.entry` in adapter.json, run as `afk-python` for `*.py`, else `bash` (:108-113). The caller gets the entry's stdout and exit code unchanged. Dispatch exits 2 when the kind is unresolved (:40-49, :103-106).
- Forge answer: one JSON object. Failure is `{error:true,verb,reason}` with exit 0 (github/forge.sh:402-406). Unknown verb exits 3 (:745-747). Missing CLI is `unavailable`, exit 4 (:77-82). `ci-wait` exits 0, 1, 2 or 3. ADAPTERS.md:27-38 does not list the error object.
- Tracker: `api.py <op> [json]` reads the payload from argv[1] only (jira/api.py:645-666). Exit 3 means unsupported, exit 2 a bad payload (payload.py:16-40), every other result exits 0. CONTRACT.md:18-21 promises stdin and `unavailable`; the code has neither.
- Tracker answers are not normalized across kinds. Jira returns raw REST JSON; github-issues returns gh JSON (inference, c-3f9f2252).
- Skills reach the tracker through the MCP server (mcp-servers/tracker/server.py:66-179). Publishers reach it through scripts/tracker_api.py:36-50.
- Jira adapter: REST v3 over urllib with Basic auth, no acli (jira/api.py:139-153). Credentials: env, then ~/.claude.json `tracker` env, then ~/.codex/config.toml (:74-136).
- publish_prd.py:
  - Block markers `afk:prd:start` and `afk:prd:end` (:83-89, :157-182).
  - Barebone description: the block replaces all of it. First publish: the block is appended after a rule. Re-publish: the block goes back to its old position (:185-230).
  - Figures: mermaid is rendered by mmdc. The script deletes old `afk-fig*.png`, uploads the new ones, then reads the media UUID from the Location header of a GET (:285-304; api.py:173-216).
  - Then one PUT of the description (api.py:159-164), with no read-back.
- Does anything check that the ticket changed since the preview? No (c-f5776c3c). The publish run GETs the ticket afresh (:271) and does no If-Match, version or hash compare.

## Findings
- The figure deletes and uploads run before the confirm prompt (:285-304 vs :333). Answering "no" breaks the images (inference).
- `tracker_edit`, publish_meeting.py:150 and publish_bug.py:242 also write the description without a guard.
- Nothing tests strip_managed_block, is_barebone, build_description or the mermaid render.

## Frontier
- B14: other repositories and the live Jira behaviour (no network).

## Unverified
- Whether Jira honours If-Match on description PUT: not checked (no network).
- Orchestrator reconciliation: in t2, node B1:scripts/tracker_api.py:36 changed traced→terminal and the B8:33 parent was aligned with t1 so the fold accepts both.
