# Adversary report — 0003-tracker-attach

ADVERSARY: findings — probed=152 crit=0 high=1 med=2 low=4 [report: docs/afk/small-lane/plan/review/0003-tracker-attach-adversary.md]
In plain terms: on Windows, attaching proof to a GitHub issue hangs forever when the text or a file name holds a character such as an arrow or a Chinese letter, and Jira's mismatch list blames the wrong files when Jira lists the uploads in a different order; fix the hang before shipping.

Gate outcome: F1 (high) and F3 fixed in 297ef3c, with regression tests that fail without the fix; the second pass (`0003-tracker-attach-adversary-2.md`) found no critical or high. F2 (pairing by position) waits on the live Jira check in slice 0011, since the part-order answer is unverified. F4-F7 are advisory.

## Setup (decision D-3: no running app)

- Head `dc02009`. Probed by running the runtime surface:
  - `adapters/tracker/jira/api.py` `call(operation, payload)` and its command line (CLI);
  - `adapters/tracker/github-issues/api.py` `call(operation, payload)` and its CLI;
  - `adapters/tracker/none/api.py` `call`;
  - `mcp-servers/tracker/server.py` through a Model Context Protocol (MCP) stdio client: `initialize`, `tools/list`, `tools/call`.
- Interpreter: `afk-python` (CPython 3.14.8, Windows 11). Server launch: environment as the `.mcp.json` registration gives it, with no `PYTHONUTF8` setting.
- Jira stand-in: a local HTTP server on `127.0.0.1:18765` (`JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN` in the environment). It logs each request and parses the multipart parts.
- GitHub stand-in: a fake `gh.exe` first on `PATH`, with the real GitHub CLI folder removed from `PATH`. It logs argv and the raw stdin bytes.
- Configuration: `AFK_CONFIG` pointed at scratch `.afk/config.yaml` files. Jira: `jira.project: ADV`, `jira.transitions: {in-review: Code Review, start: "11"}`. GitHub: `github-issues.repo: adv-owner/adv-repo`, `state-labels: {in-review, todo}`.
- No request left `127.0.0.1`. The real `gh` did not run.
- Diet note: one uncaught exception (finding 3) printed a Python traceback that names one adapter source line. No diff, test, review finding or commit entered context.

## Scenarios probed

| Area | Count | Classes |
|---|---|---|
| Jira `tracker_attach` | 46 | happy, boundary (empty, 0-byte, directory, duplicate, odd and Unicode names, 9 file types), invalid (`files` not a list, empty `ticket_key`, path characters), upload answer short / reordered / empty / not a list / renamed / retyped / without `id` / null fields / HTML / 500, read-back failed / dropped / retyped / malformed, comment failure |
| GitHub Issues `tracker_attach` | 34 | happy, all types, gh 2.98.1 / 2.99.0-rc.1 / 2.100.0 / 3.0.0 / unparseable / failing `--version`, GitHub Enterprise Server by `GH_HOST` and by repo host, permission READ / TRIAGE / WRITE / unreadable, missing file, empty list, directory, comment failure, Unicode text and names |
| `none` `tracker_attach` | 2 | files named per file |
| Refusals and warnings (both kinds) | 41 | transition by key / name / id / lowercase name / target status / unknown / empty / unoffered config key / unreadable list; Jira fix version unknown / known / by id / unreadable project or versions / empty list / list of strings / mixed; Jira `status` unknown / known / unreadable; GitHub `status` unknown / known |
| Markdown to Atlassian Document Format (ADF) | 5 | headings, nested lists, ordered lists, code block with language, links, inline code, bold, italic, table, blockquote, empty text |
| MCP server | 16 | `tools/list` (10 tools, `tracker_attach` schema), 14 tool calls on both kinds |
| CLI payload | 8 | JSON in argv, JSON on stdin, `-`, JSON list |

## What held up

- `tools/list` answers exactly ten tools. The `tracker_attach` schema needs `ticket_key` and `files`, with optional `text`.
- Jira upload sends each file's real content type. Verified in the multipart parts for PNG, MP4, TXT, PDF, JPG, GIF, WEBM, MOV, SVG, JSON, LOG and a file without an extension. Non-ASCII and space names travel intact.
- Jira answer shape on success: `attached` items carry `file`, `id`, `filename` and `mimeType`; `mismatches`, `unsupported_files` and `read_back` are present.
- Mismatch reasons `stored differently`, `not in the upload answer` and `not in the read-back` (with `stored: null`) appear when the answer keeps the sent order.
- A failed read-back (HTTP 500) answers `read_back: false`, an empty `mismatches` list and null `filename` and `mimeType`. The comment says the files were not checked.
- A comment failure after upload answers `error`, `comment_error` and the `attached` list.
- A missing file, a directory, an empty `files` list, an absent `files` and a string `files` give `error` + `refused: true`. No request reaches the stand-in (Jira and GitHub).
- Jira transition: an unknown name, an empty value, an unknown id and a config key mapped to a transition the issue does not offer are all refused. Each refusal names the offered transitions and sends no POST. A key, a name (any case) or an id resolves to the correct id.
- Jira fix version: an unknown version on `tracker_create` (also with `status` set) and on `tracker_edit` (by name, by id, as a string, mixed with a known one) is refused before any write. An unreadable project or version list writes and adds `fix_version_warning`.
- Jira `tracker_create` with an unknown `status` creates the issue, sends no transition, and answers `status_warning`. When the transition list is unreadable, it also answers `status_warning`.
- GitHub `tracker_create` with an unknown `status` and `tracker_transition` with an unknown state are refused before any `gh` write.
- GitHub `tracker_attach` sends one `gh issue comment` with one `--attach` per image or video and none for other files. Each other file goes in `unsupported_files` and is named in the comment. gh older than 2.99.0, an unparseable version, GitHub Enterprise Server (by `GH_HOST` or by repo host) and READ or TRIAGE permission give unsupported for each file. Version 2.100.0 and 3.0.0 are compared as numbers.
- `none` answers `unsupported` with one `unsupported_files` entry per file.
- ADF output: headings, bullet and ordered lists (nested), code blocks with language, links, inline code, bold, italic, tables and blockquotes become the matching nodes. Images and videos are embedded with `mediaSingle`; other files become a `mediaGroup`.

## Findings

| # | Severity | Class | Finding |
|---|---|---|---|
| 1 | high | robustness | GitHub Issues `tracker_attach` on Windows writes the comment body to `gh` in the Windows code page. A character outside that code page hangs the call with no end. Other non-ASCII characters reach GitHub as invalid UTF-8. |
| 2 | medium | correctness | Jira `tracker_attach` pairs files with the upload answer by position, not by name. A reordered, front-short or padded answer gives wrong `attached` entries and false `mismatches`, and the comment carries these wrong claims. |
| 3 | medium | robustness | A malformed Jira answer after the upload raises an uncaught exception. The files are on the ticket, no comment is posted, and the caller gets no `attached` list. |
| 4 | low | robustness | Upload answer entries without `id` become the string `"None"`. Two files pair with one read-back entry, and null stored fields print as `None (None)` in the ticket comment. |
| 5 | low | correctness | The type comparison is exact text. `image/PNG` or `text/plain; charset=UTF-8` is reported `stored differently`. |
| 6 | low | robustness | Jira `tracker_attach` does not check or URL-encode `ticket_key`. An empty key is sent; a key with `/` and `?` sends the upload to another endpoint and answers `ok: true`. |
| 7 | low | spec | Both CLIs ignore a JSON payload on stdin, but `adapters/tracker/jira/CONTRACT.md` "Verbs" says the verbs take JSON "on the command line or on stdin". |

### 1 — Windows: body not sent as UTF-8; non-code-page character hangs `tracker_attach` (high, robustness)

Promise: ADAPTERS.md "## tracker": `tracker_attach` "posts one comment carrying them"; contract Acceptance bullet 2: "the file is named in the comment" (SDD §9b row "GitHub Issues attach").

Repro A (hang), kind `github-issues`, Windows, gh fake reports 2.99.0 and WRITE permission:

```
call("tracker_attach", {"ticket_key": "7", "files": ["<dir>/a.png"], "text": "fix → ✓ 日本"})
```

- Expected: one `gh issue comment` that gets the body and an answer `ok: true`.
- Actual: `gh issue comment 7 --repo adv-owner/adv-repo --body-file - --attach <dir>/a.png` starts. In the adapter, stderr shows `UnicodeEncodeError: 'charmap' codec can't encode character '→'` in the stdin writer thread. Stdin is never closed, `gh` waits for end of input, and `call` does not return in 190 s.
- Through the MCP server, `tools/call tracker_attach` with the same arguments gets no answer in 30 s.
- The same hang happens with ASCII `text: "proof"` when a non-image file named `日本.txt` must be listed in the comment (no answer in 30 s).

Repro B (invalid UTF-8): with `files: ["<dir>/a.png", "<dir>/c.txt"], text: "proof"`, the bytes on `gh` stdin are `proof\r\n\r\n**Not attached \x97 add these files by hand:**…`. Byte `0x97` is the code-page dash, which is not valid UTF-8. `text: "café"` arrives as byte `0xE9`. This affects every Windows call that lists an unsupported file, because the heading written by the adapter holds that dash.

Scope: the same hang shows on the GitHub Issues `tracker_comment` (text `café → 日本`) and `tracker_create` (description `日本`). unverified: whether those two paths predate this slice (the diet bars git history).

### 2 — Jira upload answer matched by position (medium, correctness)

Promise: `adapters/tracker/jira/CONTRACT.md` row `tracker_attach`: "Each stored name and type is read back, and a difference is listed in `mismatches`"; contract Acceptance bullet 3.

Repro A (reordered): `files: [a.png, c.txt, d.pdf]`. The stand-in answers the upload with the same three entries in reverse order. The read-back agrees with it.

- Expected: no mismatches; each `attached` entry carries its own file's id.
- Actual: `attached[0] = {file: a.png, id: "1002", filename: "d.pdf", mimeType: "application/pdf"}`. `mismatches` claims `a.png … stored as d.pdf (application/pdf)` and `d.pdf … stored as a.png (image/png)`. The posted comment repeats both false claims under "Check these files:".

Repro B (front-short): the upload answer lists only `c.txt` (id 2) and `d.pdf` (id 3).

- Expected: `a.png` → `not in the upload answer`.
- Actual: `d.pdf` → `not in the upload answer`; `a.png` → `stored differently` as `c.txt`; `c.txt` → `stored differently` as `d.pdf`.

Repro C (extra entry): `files: [a.png]`. The upload answer is `[{id 9, other.png}, {id 1, a.png}]`. Actual: `a.png` is reported `stored differently` as `other.png`.

Effect: the media node for an image is built from another file's id, so the inline embed can show the wrong file.

### 3 — malformed Jira answer after upload crashes (medium, robustness)

Promise: CONTRACT.md: "a failed read-back answers `read_back: false` and checks nothing". ADAPTERS.md: when Jira stores the files but the comment fails, the answer carries `attached` "so the caller knows the files are on the ticket".

Repro A: the read-back `GET /rest/api/3/issue/ADV-1?fields=attachment` answers `200 {"key":"ADV-1","fields":{"attachment":"oops"}}`.

- `call` raises `AttributeError: 'str' object has no attribute 'get'` after `POST …/attachments` succeeded.
- MCP: `{"isError": true, "content": [{"text": "Error executing tool tracker_attach: 'str' object has no attribute 'get'"}]}`.
- No comment is posted.

Repro B: the upload answer is `200 ["a.png"]` (items are not objects). Same exception.

Expected: `read_back: false` (or `error` with `attached`), never a bare exception after a write. A caller that retries uploads the files a second time.

### 4 — upload entry without `id`; `None` in the ticket comment (low, robustness)

- Repro A: the upload answer entries lack `id`. Actual: `attached` and `mismatches` carry `"id": "None"`, not `null`. The adapter requests `GET /rest/api/3/attachment/content/None` twice. `a.png` is paired with the `c.txt` read-back entry and reported `stored as c.txt (text/plain)`.
- Repro B: the upload answer has `filename: null, mimeType: null`. Actual: the comment says `a.png was sent as image/png and is stored as None (None)`.

### 5 — exact-text type comparison (low, correctness)

Repro: the read-back gives `mimeType: "image/PNG"` for `a.png` and `"text/plain; charset=UTF-8"` for `c.txt`. Actual: both are in `mismatches` as `stored differently`, and both are named in the comment. Expected: no mismatch, because the types are the same with letter case and parameters ignored. unverified: whether Jira Cloud returns the type with a charset parameter (no live Jira).

### 6 — `ticket_key` not checked or encoded (low, robustness)

- Repro A: `ticket_key: ""`. Actual: `POST /rest/api/3/issue//attachments` is sent (a write attempt); the answer is the 404 error.
- Repro B: `ticket_key: "ADV-1/comment?x="`. Actual: the multipart upload is sent to `POST /rest/api/3/issue/ADV-1/comment?x=/attachments`. The answer is `ok: true` with an empty `attached` list.
- Expected: a refusal before any write.

### 7 — CLI ignores a stdin payload (low, spec)

Repro: `afk-python adapters/tracker/jira/api.py tracker_attach` with `{"ticket_key":"ADV-1","files":["<dir>/a.png"]}` on stdin.

- Actual: `{"error": true, "reason": "missing required argument 'ticket_key'"}`, exit 0. The same happens on `github-issues/api.py`.
- With argument `-`: `"the payload is not JSON"`, exit 2.
- The same JSON passed as argv works.

Promise: CONTRACT.md "Verbs": "takes its arguments as JSON on the command line or on stdin". unverified: whether this predates the slice.
