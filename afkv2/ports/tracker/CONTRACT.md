# Tracker port: the command contract

`<python> afkv2/ports/tracker/cli.py <verb> [json-payload]`, or the payload on stdin. `<python>` is the Python in the setup install record (line `python`). `md-to-adf` also needs the package `markdown-it-py` in that Python.

Every answer is one JSON object: `{"ok": true, ...}`, or `{"ok": false, "error": {"code", "reason", ...}}`.
Exit 0 is ok. Exit 1 is a refusal. Exit 2 is unreadable input (`bad-payload`, `unknown-verb`).

## Verbs

| Verb | Payload | Answer | Kind |
|------|---------|--------|------|
| `issue-get` | `key` (Jira: the key; GitHub: `7`, `#7` or `owner/name#7`); optional `fields` (comma string or list), `tracker`, `repo` | Jira: `key, id, fields, description, description_hash, block`, and `block_problem` when the block is broken. GitHub: `key` (the bare number, also for `owner/name#7`) and the `gh` fields | both |
| `issue-search` | GitHub: optional `query`, `max_results`, `tracker`, `repo`. Jira: `query` (JQL); optional `fields` (comma string or list), `max_results` (default 1000), `tracker` | GitHub: `issues, count`. Jira: `issues, count, truncated`; the port reads every page up to `max_results`, and `truncated` is true when Jira holds more | both |
| `md-to-adf` | `markdown`; optional `figures` `{index: [ADF nodes]}` | `content, figure_token, block_text` | Jira |
| `attachment-list` | `key` | `attachments, count` | Jira |
| `attachment-put` | `key, png, receipt, preview` | `key, attachment_id, media_id, filename, width, height` | Jira |
| `attachment-delete` | `id` | `id, filename, deleted`; when Jira no longer has it, `deleted` is false and `filename` is null | Jira |
| `description-put` | `key, adf, expect_hash, receipt, preview` | `key, replaced, block`; `replaced` is `afkv2`, `v1`, or null for a first publish | Jira |
| `comment-put` | `key, body, pictures, receipt`; optional `tracker`, `repo` | `comment_id, url, attached, posted`; `posted` is false when a comment with the receipt already exists, and `attached` is then empty | both |

The port has no create or transition verb. `comment-put` is its one comment verb.

`issue-get`, `issue-search` and `comment-put` take the kind from the payload `tracker`, then from `tracker.kind` in the answer of `afkv2/scripts/afkv2_config.py read`. The kinds are `jira` and `github-issues`. Without a payload `tracker` and `repo`, `repo` comes from `tracker.repo` in the same answer. A GitHub key that names another repository than `repo` refuses `bad-payload`.

## The publish contract

- `preview` is the path of a JSON file with `ticket_key`, `receipt`, `description_hash` and `picture_hashes` (a list: the sha256 hex digest of each picture file).
- `receipt` is the sha256 hex digest (64 lowercase characters) of the UTF-8 bytes of ticket key + `block_text` + the `picture_hashes` joined with no separator, in list order. `description-put` computes it again from `adf` and refuses `bad-receipt` when it differs. It binds the `block_text` content and the picture bytes: a link target and a node type are in the hash, a media id in `adf` is not, and the read-back compares the media ids.
- `block_text` is the canonical JSON (sorted keys, no spaces, UTF-8 not escaped) of the block nodes: each node's `type`, `text`, every mark, the `level` and `language` attributes and its children. A link-only edit changes it. Figure nodes (`mediaSingle`, `mediaGroup`, `media`) stay out, because `picture_hashes` covers them, so `md-to-adf` without `figures` gives the same `block_text` as the later call with `figures`. Other attributes stay out, because Jira can add its own on read. The `text` of a `block` summary is the same form.
- `expect_hash` is the `description_hash` that `issue-get` answered when the preview was built. It must equal the preview's `description_hash`.
- The `png` file name is `afkv2-fig-<receipt 8 chars>-<n>.png`, and the hash of the file must be in `picture_hashes`.
- `adf` is a list of ADF nodes or a doc. It holds only the text between the block lines; the port writes the lines.
- `figure_token` holds `{}` for the figure index. A paragraph that holds only the token becomes the nodes of `figures[index]`. With `figures`, a token that has no entry refuses `bad-payload`. Without `figures`, the paragraph is left out: use this for the text of the preview.
- `attachment-delete` checks only the file name: it refuses all but an afkv2 or a v1 picture name. It takes no ticket: the caller takes `id` from `attachment-list` of the ticket or from the `attachment-put` answer.

## The comment contract

- `receipt` is 64 lowercase hex characters. The first line of `body` is `afkv2 proof v1 <receipt>`. The caller owns that the receipt is the one the developer marked.
- `pictures` is a list of file paths, possibly empty.
- A comment whose first line equals the first line of `body` makes the post a no-op: nothing is posted, and the answer names that comment.
- Jira: the port attaches each picture as `afkv2-proof-<receipt 8 chars>-<n><suffix>`, then posts 1 ADF comment that shows them. A picture of the same name and size already on the ticket is used again. Limits: the site's upload limit per file, 1,000,000 bytes of comment rich text.
- GitHub: the port runs `gh issue comment --attach` (gh 2.99.0 or later). It takes PNG, JPEG, GIF, WebP, SVG, MP4, MOV and WebM files, 10 MB each, 50 per comment, on github.com only, with push access.

## The read-back compare

`block` is `{"family", "text", "media_ids"}`. Compare `block` of the `description-put` answer with `block` of the next `issue-get` answer. Equal means the write holds. Delete old pictures only after that.

## Error codes

| Source | Codes |
|--------|-------|
| HTTP status | 400 `bad-request`, 401 `auth`, 403 `forbidden`, 404 `not-found`, 409 `conflict`, 413 `too-large`, 422 `unprocessable`, 429 `rate-limited`, 5xx `server-error`, other `http-error` |
| Input | `bad-payload`, `unknown-verb` |
| Publish | `bad-receipt`, `bad-name`, `bad-block`, `stale`, `not-a-picture`, `no-media-id` (carries `attachment_id`) |
| Comment | `bad-receipt`, `too-large` (a file or the comment is over the tracker's limit), `not-supported` (a GitHub file type outside the list, GitHub Enterprise Server, Jira attachments off), `gh-too-old`, `no-push-access`, `no-media-id` |
| Setup | `no-credentials`, `no-tracker`, `unsupported`, `unavailable`, `missing-dependency` |
| Transport | `network`, `timeout`, `bad-answer`, `cli-failed`, `internal` |
