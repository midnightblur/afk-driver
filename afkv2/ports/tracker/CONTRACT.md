# Tracker port: the command contract

`<python> afkv2/ports/tracker/cli.py <verb> [json-payload]`, or the payload on stdin. `<python>` is the Python in the setup install record (line `python`). `md-to-adf` also needs the package `markdown-it-py` in that Python.

Every answer is one JSON object: `{"ok": true, ...}`, or `{"ok": false, "error": {"code", "reason", ...}}`.
Exit 0 is ok. Exit 1 is a refusal. Exit 2 is unreadable input (`bad-payload`, `unknown-verb`).

## Verbs

| Verb | Payload | Answer | Kind |
|------|---------|--------|------|
| `issue-get` | `key` (Jira: the key; GitHub: `7`, `#7` or `owner/name#7`); optional `fields` (comma string or list), `tracker`, `repo` | Jira: `key, id, fields, description, description_hash, block, site, whole`, `block_range` (`[begin index, end index]` of the block lines) when there is a block, and `block_problem` when the block is broken. `site` is the base URL of the Jira site; `whole` is the `block` summary of the whole description. GitHub: `key` (the bare number, also for `owner/name#7`), the `gh` fields, `description_hash` (of the body), `block`, `length_without_block`, `whole` (the `block` summary of the whole body, family `whole`), and `block_problem` when the block is broken | both |
| `issue-search` | GitHub: optional `query`, `max_results`, `tracker`, `repo`. Jira: `query` (JQL); optional `fields` (comma string or list), `max_results` (default 1000), `tracker` | GitHub: `issues, count`. Jira: `issues, count, truncated`; the port reads every page up to `max_results`, and `truncated` is true when Jira holds more | both |
| `md-to-adf` | `markdown`; optional `figures` `{index: [ADF nodes]}` | `content, figure_token, block_text` | Jira |
| `adf-text` | `adf` (a list of ADF nodes, or a doc) | `block_text` of those nodes | Jira |
| `attachment-list` | `key` | `attachments, count` | Jira |
| `attachment-put` | `key, png, receipt, preview` | `key, attachment_id, media_id, filename, width, height` | Jira |
| `attachment-delete` | `id` | `id, filename, deleted`; when Jira no longer has it, `deleted` is false and `filename` is null | Jira |
| `description-put` | Jira: `key, adf, expect_hash, receipt, preview`; optional `whole` (true: `adf` becomes the whole description, with no block lines). GitHub: `key, markdown, expect_hash, receipt, preview`; optional `whole` (true: `markdown` becomes the whole body, with no block lines), `tracker`, `repo` | `key, replaced, block`; `replaced` is `afkv2`, `v1` (Jira only), or null for a first publish or a `whole` write over a body with no block | both |
| `comment-put` | `key, body, pictures, receipt`; optional `tracker`, `repo` | `comment_id, url, attached, posted`; `posted` is false when a comment with the receipt already exists, and `attached` is then empty | both |
| `block-text` | `markdown` | `block_text`: the GitHub canonical form | GitHub |
| `meeting-comments` | `key`; optional `tracker`, `repo` | `comments`: one `{title, comment_id, comment_hash, own, url, text}` per meeting comment, in the tracker's list order (oldest first) | both |
| `meeting-comment-put` | `key, title, receipt, expect_hash` (may be null) and Jira `adf` (the expand content) or GitHub `markdown`; optional `tracker`, `repo` | `comment_id, url, action, comment_hash`; `action` is `posted`, `edited` or `unchanged` | both |

The port has no create or transition verb. Its comment verbs are `comment-put` (the proof comment) and `meeting-comment-put`.

`issue-get`, `issue-search`, `description-put`, `comment-put`, `meeting-comments` and `meeting-comment-put` take the kind from the payload `tracker`, then from `tracker.kind` in the answer of `afkv2/scripts/afkv2_config.py read`. The kinds are `jira` and `github-issues`. Without a payload `tracker` and `repo`, `repo` comes from `tracker.repo` in the same answer. A GitHub key that names another repository than `repo` refuses `bad-payload`.

## The publish contract

- `preview` is the path of a JSON file with `ticket_key`, `receipt`, `description_hash` and `picture_hashes` (a list: the sha256 hex digest of each picture file).
- `receipt` is the sha256 hex digest (64 lowercase characters) of the UTF-8 bytes of ticket key + `block_text` + the `picture_hashes` joined with no separator, in list order. `description-put` computes it again from `adf` and refuses `bad-receipt` when it differs. It binds the `block_text` content and the picture bytes: a link target and a node type are in the hash, a media id in `adf` is not, and the read-back compares the media ids.
- `block_text` is the canonical JSON (sorted keys, no spaces, UTF-8 not escaped) of the block nodes: each node's `type`, `text`, every mark, the `level` and `language` attributes and its children. A link-only edit changes it. Figure nodes (`mediaSingle`, `mediaGroup`, `media`) stay out, because `picture_hashes` covers them, so `md-to-adf` without `figures` gives the same `block_text` as the later call with `figures`. Other attributes stay out, because Jira can add its own on read. The `text` of a `block` summary is the same form.
- `expect_hash` is the `description_hash` that `issue-get` answered when the preview was built. It must equal the preview's `description_hash`.
- The `png` file name is `afkv2-fig-<receipt 8 chars>-<n>.png`, and the hash of the file must be in `picture_hashes`.
- `adf` is a list of ADF nodes or a doc. It holds only the text between the block lines; the port writes the lines. With `whole` true it is the whole new description: the port writes no block lines, `block` of the answer has the family `whole`, and the read-back compares it with `whole` of the next `issue-get`. A node of `adf` that holds a block line refuses `bad-block` in both modes.
- `figure_token` holds `{}` for the figure index. A paragraph that holds only the token becomes the nodes of `figures[index]`. With `figures`, a token that has no entry refuses `bad-payload`. Without `figures`, the paragraph is left out: use this for the text of the preview.
- `attachment-delete` checks only the file name: it refuses all but an afkv2 or a v1 picture name. It takes no ticket: the caller takes `id` from `attachment-list` of the ticket or from the `attachment-put` answer.

## The GitHub block

- The block stands in the issue body between the lines `<!-- afkv2:prd:start -->` and `<!-- afkv2:prd:end -->`, each alone on its line. A line inside a code fence holds no block line.
- `description-put` changes only the lines between the block lines. A first publish appends a blank line and the block at the end of the body.
- The block holds the Markdown as is. GitHub draws each Mermaid fence. `media_ids` is always empty, and `picture_hashes` is an empty list.
- `block_text` is the Markdown with LF line ends, no trailing spaces, and no blank lines at the start or the end. The `receipt` covers it.
- With `whole` true the new body is `block_text` of `markdown`, with no block lines. The receipt and the refusals are the same as for a block write. `block` of the answer has the family `whole`; compare it with `whole` of the next `issue-get`.
- `description-put` refuses `bad-block` for a broken or doubled block, or for new text that holds a block line; `stale` when the body hash is not `expect_hash`; `too-large` when the new body passes 65536 characters.

## The comment contract

- `receipt` is 64 lowercase hex characters. The first line of `body` is `afkv2 proof v1 <receipt>`. The caller owns that the receipt is the one the developer marked.
- `pictures` is a list of file paths, possibly empty.
- A comment whose first line equals the first line of `body` makes the post a no-op: nothing is posted, and the answer names that comment.
- Jira: the port attaches each picture as `afkv2-proof-<receipt 8 chars>-<n><suffix>`, then posts 1 ADF comment that shows them. A picture of the same name and size already on the ticket is used again. Limits: the site's upload limit per file, 1,000,000 bytes of comment rich text.
- GitHub: the port runs `gh issue comment --attach` (gh 2.99.0 or later). It takes PNG, JPEG, GIF, WebP, SVG, MP4, MOV and WebM files, 10 MB each, 50 per comment, on github.com only, with push access.

## The meeting comment contract

- A meeting comment has a title that starts with a date `YYYY-MM-DD`. Jira: the body holds exactly 1 top-level `expand` node (empty paragraphs around it do not count), and its `attrs.title` is the title. GitHub: the body (LF line ends, no trailing whitespace) starts with the line `<details><summary>TITLE</summary>` and ends with `</details>`; the inner Markdown is the text between, with no blank lines at the start or the end.
- `comment_hash` is the sha256 hex digest of the `block_text` of the inner content: Jira the form `adf-text` answers, GitHub the form `block-text` answers. `text` is the inner content for a reader: Jira the plain text, one paragraph per line; GitHub the inner Markdown.
- `own` is true when the comment author is the account of the credentials: Jira `GET /rest/api/3/myself`, GitHub `gh api user`. `comment_id` is the Jira comment id, or the GitHub number from `#issuecomment-N`.
- `receipt` is the sha256 hex digest of the UTF-8 bytes of key + title + `block_text` of the new inner content. A difference refuses `bad-receipt`.
- A title without a date, or with a line break, refuses `bad-payload`. Size: Jira 1,000,000 bytes of the comment document, GitHub 65536 characters of body: `too-large`.
- The port finds the meeting comments with exactly this title. 0: post, or `stale` when `expect_hash` is not null. 2 or more: `duplicate-meeting`. 1 of another account: `not-own`. 1 with the new hash: `unchanged`, no write. 1 whose hash is not `expect_hash`: `stale`. Else the port edits that comment in place (Jira `PUT .../comment/{id}`, GitHub `gh api -X PATCH repos/<repo>/issues/comments/<id>`).
- After a post or an edit the port lists again: exactly 1 meeting comment with the title and the new hash, else `read-back-mismatch`.

## The read-back compare

`block` is `{"family", "text", "media_ids"}`. Compare `block` of the `description-put` answer with `block` of the next `issue-get` answer. Equal means the write holds. Delete old pictures only after that.

## Error codes

| Source | Codes |
|--------|-------|
| HTTP status | 400 `bad-request`, 401 `auth`, 403 `forbidden`, 404 `not-found`, 409 `conflict`, 413 `too-large`, 422 `unprocessable`, 429 `rate-limited`, 5xx `server-error`, other `http-error` |
| Input | `bad-payload`, `unknown-verb` |
| Publish | `bad-receipt`, `bad-name`, `bad-block`, `stale`, `not-a-picture`, `no-media-id` (carries `attachment_id`) |
| Meeting comment | `bad-payload` (title), `bad-receipt`, `too-large`, `stale`, `duplicate-meeting` (2 or more comments with the title), `not-own` (the comment of another account), `read-back-mismatch` |
| Comment | `bad-receipt`, `too-large` (a file or the comment is over the tracker's limit), `not-supported` (a GitHub file type outside the list, GitHub Enterprise Server, Jira attachments off), `gh-too-old`, `no-push-access`, `no-media-id` |
| Setup | `no-credentials`, `no-tracker`, `unsupported`, `unavailable`, `missing-dependency` |
| Transport | `network`, `timeout`, `bad-answer`, `cli-failed`, `internal` |
