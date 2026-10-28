# Adversary report — 0003-tracker-attach, second pass

Verdict: findings — crit=0 high=0 med=4 low=5 (status lines at the end).

- Head: 297ef3c. Surface (decision D-3 in `plan/DECISIONS.md`): `call(operation, payload)` and the command line of `adapters/tracker/{jira,github-issues,none}/api.py`, and the `tracker` MCP server (`mcp-servers/tracker/server.py`) over stdio.
- Diet: contract `plan/0003-tracker-attach.md`, `ADAPTERS.md` "## tracker", `adapters/tracker/jira/CONTRACT.md`, tool and module docstrings, entry signatures. No diff, test, review file or commit read. Two runtime tracebacks (finding 3) printed 2 source lines of `md_to_adf_content`. This is runtime output, not a diet breach.
- Fakes, all local: a fake Jira on `http://127.0.0.1:18765`; a compiled `gh.exe` first on PATH, real GitHub CLI folder removed from PATH. The fake `gh.exe` logs argv and raw stdin bytes. No real Jira, GitHub or `gh` was contacted. Adapter and server processes ran without `PYTHONUTF8`. Scripts: `<scratchpad>/adversary-0003b/src/` (`harness.py`, `p1.py`–`p17.py`).

Gate outcome: no critical or high, so the gate passes. F1 (pairing by position) waits on the live Jira check in slice 0011. F3 and F4 need a non-string `text`, which the MCP tool schema refuses; they reach only a direct `call()` or command-line run. F2 and the low findings are advisory.

## Scenarios probed

| Area | Scenarios | Result |
|---|---|---|
| GitHub Issues attach, non-ASCII | arrows, Chinese/Japanese text, accents, emoji in `text` and in file names; `;`, `&`, `%`, spaces, upper-case extension; 1.8 MB body | held |
| GitHub Issues comment/create, non-ASCII | same text through `tracker_comment`, `tracker_create` (title + description) | held |
| gh stdout, non-ASCII | comment URL, `issue view` JSON, 400 000-character title | held |
| gh version floor | 2.98.9, 2.99.0, 2.100.0, 3.0.0, 2.99.0-rc.1, unparseable | finding 9 |
| GitHub access | permission READ/TRIAGE/WRITE/MAINTAIN/ADMIN/empty; permission call fails, non-JSON, a list; `GH_HOST` and a host in `github-issues.repo` | held |
| Refusals | missing file, folder, `files` string/empty/absent/non-string items, missing `ticket_key`, `#7` key, duplicate file, relative path | held |
| Wrong-typed `text` | dict, int, None on `call()`, command line, MCP | findings 3, 4 |
| Jira attach happy path | 10 files, non-ASCII names, real content types (png, mp4, webm, pdf, txt, log, no extension) | held |
| Jira upload answer malformed | object, string, null, int, non-object items, wrong field types, empty list, extra item, reordered, HTML 200, empty 200, 500 | findings 1, 2, 7 |
| Jira read-back malformed | `attachment` object/string/null, `fields` string/absent, body list/string, non-object items, wrong field types, HTML, 500, 404, stored differently, file absent | finding 8; rest held |
| Jira comment after upload | 400, 500 HTML, 201 non-JSON, 201 list | held |
| Jira media lookup | 303 without id, 200, 500 | finding 6 |
| Jira ADF (Atlassian Document Format) | heading, bullet + ordered list, code block with language, link, inline code, bold; non-ASCII | held |
| Jira field truth | unknown fix version on create, unknown transition, `in-review` key | held |
| Command line | payload in argv; payload on stdin; `-` | finding 5 |
| MCP server | 10 tools listed; `tracker_attach` schema; GitHub, Jira, `none` kinds; refusal; HTML upload answer | finding 2; rest held |
| `none` kind | attach, attach of a missing file | held |

## What held up

- Every gh stdin body reached `gh.exe` as valid UTF-8 for `tracker_attach`, `tracker_comment` and `tracker_create`, up to 1.8 MB, with no hang. Every non-ASCII argv reached `gh.exe` unchanged.
- One `gh issue comment` per attach, one `--attach` per image or video file, none for other types. Each other file is named in the comment with its reason. Older gh, unparseable version, READ/TRIAGE access and a non-github.com host each answer unsupported for every file.
- Jira multipart parts carry each file's real content type and its UTF-8 name. A file stored under another name or type is listed in `mismatches` with `sent` and `stored`, and named in the comment.
- Every malformed upload answer that is valid JSON, and every malformed read-back, answers without an exception. A read-back that cannot be read answers `read_back: false` with empty `mismatches`.
- Comment failure after upload answers `error`, `reason`, `comment_error` and `attached`.
- Each refusal answers `error: true` + `refused: true`, with 0 gh calls and 0 HTTP requests.
- MCP tool schema rejects a non-string `text` and a string `files` before the adapter runs.
- Observation, no promise broken: the body that reaches `gh.exe` has every LF changed to CRLF (1 740 000 bytes sent as 1 800 000).

## Findings

| # | Severity | Class | Finding |
|---|---|---|---|
| 1 | medium | correctness | Jira pairs the upload answer with the sent files by position. A reordered answer gives false `stored differently` mismatches, posts them on the ticket and puts the media in the wrong slots |
| 2 | medium | robustness | Jira upload that answers 2xx with a non-JSON body: the answer is a bare `error` with no `attached`, no read-back and no comment, though Jira took the files. Reproduces through MCP |
| 3 | medium | robustness | Jira `tracker_attach` with non-string `text` through `call()` or the command line raises `TypeError` after the upload and read-back. No answer object; the command line exits 1 with a traceback |
| 4 | medium | robustness | GitHub Issues `tracker_attach`, `tracker_comment`, `tracker_create` with a non-string `text` / `description` through `call()` or the command line never return, after gh has exited |
| 5 | low | spec | Command line ignores a payload on stdin on both kinds. `-` is parsed as the payload itself |
| 6 | low | correctness | Jira media lookup failure: the answer is `ok: true` with no field for it. The comment gives `(RuntimeError)` as the reason |
| 7 | low | robustness | Jira upload answer with wrong-typed ids: `id` becomes the strings `"None"` and `"{'x': 1}"`, and the adapter sends `GET /rest/api/3/attachment/content/None`. Wrong-typed read-back `filename` / `mimeType` (5, `{"a": 1}`) are copied into `attached` |
| 8 | low | correctness | Jira read-back with `fields.attachment: null` answers `read_back: true` and lists every file `not in the read-back`. An object or string there answers `read_back: false` |
| 9 | low | spec | gh `2.99.0-rc.1` passes the 2.99.0 floor. Under Semantic Versioning a pre-release of 2.99.0 is older than 2.99.0. Unverified whether that pre-release carries `--attach` |

## Repros

Common setup: `AFK_CONFIG` names a scratch config (`tracker: jira`, `jira.project: ADV`, `jira.transitions.in-review: In Review`; or `tracker: github-issues`, `github-issues.repo: acme/widgets`). Set `JIRA_BASE_URL=http://127.0.0.1:<port>`, `JIRA_EMAIL`, `JIRA_API_TOKEN`. Put a stub `gh` first on PATH that logs argv and stdin. Each repro states the stub replies, the request and the observed vs expected answer, in the stub-gh / stub-HTTP form the contract's `## Verification` integration tier names.

### 1 — upload answer paired by position

- Files: `证据截图.png`, `notes.txt`. Stub `POST /rest/api/3/issue/ADV-1/attachments` → 200 `[{"id":"2","filename":"notes.txt","mimeType":"text/plain"},{"id":"1","filename":"证据截图.png","mimeType":"image/png"}]`. Read-back `GET /rest/api/3/issue/ADV-1?fields=attachment` lists id 1 = `证据截图.png` image/png and id 2 = `notes.txt` text/plain.
- `call("tracker_attach", {"ticket_key":"ADV-1","files":[<证据截图.png>,<notes.txt>],"text":"t"})`.
- Actual: `attached[0]` = `{"file":"…证据截图.png","id":"2","filename":"notes.txt","mimeType":"text/plain"}`. 2 `stored differently` mismatches. The comment says "`证据截图.png` was sent as image/png and is stored as `notes.txt` (text/plain)". The media lookup for the inline image slot requests id 2 (`notes.txt`).
- Expected: pairing by stored name (or by read-back), `mismatches: []`, the PNG embedded inline. Breaks `adapters/tracker/jira/CONTRACT.md` row `tracker_attach` and SDD §9b row "Jira attachment upload".

### 2 — 2xx upload with non-JSON body

- Stub upload → 200, `Content-Type: text/html`, body `<html>proxy</html>` (also: empty body). Read-back and comment stubs answer normally.
- MCP `tracker_attach {"ticket_key":"ADV-1","files":[<plain.png>],"text":"t"}`.
- Actual: `{"error": true, "operation": "tracker_attach", "reason": "JSONDecodeError: Expecting value: line 1 column 1 (char 0)"}`. Requests: only the upload. No read-back, no comment.
- Expected: the files are on the ticket, so the answer says so — read back the attachment list and report `attached`, or carry an explicit "upload answer unreadable" error with the sent files. A caller that retries on this answer uploads the files twice. Breaks `ADAPTERS.md` "## tracker" ("… so the caller knows the files are on the ticket").

### 3 — Jira, non-string `text`

- Normal stubs. `call("tracker_attach", {"ticket_key":"ADV-1","files":[<plain.png>],"text":{"a":1}})`.
- Actual: `TypeError: Input data should be a string, not <class 'dict'>` raised from `call()`. Requests already sent: upload, read-back, media lookup. No comment. Command line `api.py tracker_attach '<same JSON>'`: exit 1, traceback on stderr, empty stdout. `tracker_comment` with `text` `{"a":1}` raises the same, before any request.
- Expected: one JSON answer object — a refusal before the upload, or `error` with `attached` after it. Breaks `adapters/tracker/jira/CONTRACT.md` "answers with one JSON object on stdout". MCP is not affected: its schema refuses the call.

### 4 — GitHub Issues, non-string `text` never returns

- Stub `gh` that answers at once and exits 0 (single process). `call("tracker_attach", {"ticket_key":"7","files":[<plain.png>],"text":{"a":1}})`; also `text` 5; `tracker_comment` `text` `{"a":1}`; `tracker_create` `description` `["x"]`.
- Actual: stub `gh issue comment … --body-file -` (or `gh issue create …`) runs, reads an empty stdin and exits. `call()` does not return in 25 s or 60 s. Same through the command line. `text: null` returns normally.
- Expected: one JSON answer object, a refusal before the gh call. MCP is not affected: its schema refuses the call.

### 5 — command-line payload on stdin

- `echo {"ticket_key":"7","text":"ascii only"} | api.py tracker_comment` (both kinds).
- Actual: `{"error": true, "operation": "tracker_comment", "reason": "missing required argument 'ticket_key'"}`. With argv `-`: exit 2, "the payload is not JSON: Expecting value: line 1 column 1 (char 0)".
- Expected: stdin payload accepted. Breaks `adapters/tracker/jira/CONTRACT.md` "takes its arguments as JSON on the command line or on stdin". Unverified whether this predates the slice; it is not specific to `tracker_attach`.

### 6 — media lookup failure is silent in the answer

- Stub `GET /rest/api/3/attachment/content/<id>` → 303 with `Location: http://127.0.0.1:<port>/elsewhere` (also 200, 500).
- Actual: `{"ok": true, …, "mismatches": [], "unsupported_files": []}`. Comment: "`证据截图.png` is attached but not embedded (RuntimeError)".
- Expected: the answer names each file not embedded, with a reason a reader can act on. `adapters/tracker/jira/CONTRACT.md` row `tracker_attach`: "Images and videos are embedded inline".

### 7 — wrong-typed ids and fields copied

- Stub upload → `[{"id":{"x":1},"filename":5,"mimeType":["image/png"]},{"id":null,"filename":null,"mimeType":null}]`.
- Actual: `attached[].id` = `"{'x': 1}"` and `"None"`; request `GET /rest/api/3/attachment/content/None` sent. With a read-back item `{"id":"1","filename":5,"mimeType":{"a":1}}`: `attached[0].filename` = `5`, `mimeType` = `{"a":1}`.
- Expected: a non-string id is treated as absent (`not in the upload answer`), no request for it; `filename` / `mimeType` are strings or null (`ADAPTERS.md` "## tracker").

### 8 — `attachment: null` read as an empty list

- Read-back → 200 `{"fields":{"attachment":null}}`.
- Actual: `read_back: true`, 2 mismatches `not in the read-back`, named in the comment.
- Expected: `read_back: false`, as for an object or string in that field (`ADAPTERS.md`: "`read_back` (false when the stored names could not be read, so none was checked)").

### 9 — pre-release passes the floor

- Stub `gh --version` → `gh version 2.99.0-rc.1 (2026-09-01)`.
- Actual: `--attach` passed for `plain.png`, `attached` lists it.
- Expected: treated as older than 2.99.0, file answered unsupported (contract `## Acceptance` bullet 2, "gh older than 2.99.0").

```
ADVERSARY: findings — probed=113 crit=0 high=0 med=4 low=5 report: docs/afk/small-lane/plan/review/0003-tracker-attach-adversary-2.md
In plain terms: the attach tool works for every normal case, including non-English file names and text on Windows, but four uncommon replies or inputs make it mislabel files, hide that files were uploaded, crash after uploading, or freeze.
```
