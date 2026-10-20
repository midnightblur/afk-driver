# INV-015 — what adding a tracker verb touches

feat-small-lane@d346cfb · partial · ledger: COVERAGE.json (validator: valid)

## Answer

| Site | Edit | What catches a miss |
|---|---|---|
| `adapters/tracker/{jira,github-issues,none}/adapter.json:5-15` | add an `operations[]` entry | nothing |
| `adapters/tracker/*/CONTRACT.md` "## Verbs" | add a verb line | skill-registry-gate check E (`hooks/lib/adapter_registry_check.py:89-98`, called at `skill-registry-gate.sh:201`); **a substring match (`:94`), so a missing `tracker_attach` passes beside `tracker_attachments`** |
| `OPERATIONS` (`jira/api.py:445`, `github-issues/api.py:35`, `none/api.py:12`) | add the name | nothing (`test_tracker_surface.py:71-73` checks only `tracker_get`) |
| `_DISPATCH` and an `_op_*` function (`jira/api.py:615`, `github-issues/api.py:341`) | add both | the verb answers `unsupported` (exit 3) at run time |
| `mcp-servers/tracker/server.py:104-175` | add one `@mcp.tool` | no test (`test_tracker_server.py:28` stubs FastMCP) |
| `.mcp.json`, `adapter.sh`, `tracker_api.py`, `payload.py` | none | — |

- **No consistency check.** No gate compares the server tools, `OPERATIONS`, `_DISPATCH` and `adapter.json`.
- **The MCP server exposes every verb on every kind**, by contract only (`ADAPTERS.md:42-46`, `server.py:3`, `none/api.py:3-5`).
- **Prose that goes stale.** These say "nine verbs" or "upload has no MCP tool": `ADAPTERS.md:42,50,51`, `jira/CONTRACT.md:38-57`, `github-issues/CONTRACT.md:35`, `server.py:1,3`, `tracker_api.py:4`, `providers/PARITY.md:148`, `providers/CONFORMANCE.md:24,95` (inferred: needs a new live proof), `setup/MANIFEST.md:738`, `to-ticket/SKILL.md:29`.
- **Same-commit rows.**
  - `FRESHNESS.md:84`: a change to the server's tool set updates `.mcp.json` and MANIFEST H2/P1.
  - `FRESHNESS.md:40`: CHANGELOG.
  - `AGENTS.md:195`: the Jira writer rule (inferred).
- **Name and the guard.** `protected_branch_guard.py:40-42,91-95` judges an MCP tool by the words in its name. "attach" is not a mutating word; "upload", "add", "put" and "post" are.
- **The write path.** An MCP tool calls `_call`, which drops empty arguments, then `api.call` (`server.py:96-101`).
  - Exit codes: 2 for a bad payload, 3 for unsupported. An `error` answer also exits 0 (`jira/api.py:659-666`, `github-issues/api.py:375-382`).
  - Answer shapes: `comment {ticket_key,text}`; `create {key,id}` on Jira, `{key,url}` on GitHub Issues.
- **Jira upload.** `Jira.upload_attachment(key, filepath)` (`jira/api.py:180-197`):
  - It sends `Content-Type: image/png` hard-coded (`:189`) and returns `arr[0]["id"]`.
  - It has no `try`, and its timeout is 60 s.
  - Callers:
    - `publish_prd.py:284-304`: deletes old figures by name, uploads, then resolves the media id. No retry.
    - `publish_bug.py:250-265`: catches HTTP, URL and runtime errors. Inferred: an OSError ends the run after the Bug exists.
- **The gh helper.** `_gh(*args, stdin=None)` (`github-issues/api.py:91-113`):
  - It answers `unavailable` when `gh` is missing.
  - Timeout 60 s; stdin is DEVNULL unless text is given.
  - The repository comes from `repo`, then `GH_REPO`.
  - Comments are sent with `--body-file -`.

## Correction by the orchestrator

The investigation inferred that the github-issues attach must answer `unsupported`, because local gh 2.92.0 lacks `--attach`. That is superseded: gh 2.99.0 adds `--attach` (docs.github.com/en/github-cli/github-cli/attaching-files-with-github-cli), settled in R-4 D-21 and D-23.

## Findings

- The check E substring defect (above).
- `github-issues/CONTRACT.md:54` claims a write that the code does not make.
- `to-ticket/SKILL.md:96` passes `epic`, which `tracker_create` has no parameter for.
- `ADAPTERS.md:186-188` describes gate checks that do not exist.
- github-issues answers `unavailable` with exit 0, not 4. jira never answers `unavailable`.
- `none/api.py:34` bypasses `payload.py`.
- All 3 CONTRACT.md files (`:17-19`) claim stdin input that no `main` reads.

## Unverified

- How Jira handles a non-PNG file sent as `image/png`.
- Whether FastMCP drops the unknown `epic` argument.
- User harness allowlists that name tracker tools.
- B1 alias forms; B3, B5, B6, B7, B10 have no method.
- Plugin defect: merge_fragments seed placeholders (115 dropped before the fold).

## Frontier

B14: live Jira and GitHub, user harness settings, other repositories.

Written by the orchestrator from the investigation's reply; the investigation's own REPORT.md write was refused.
