# Tracker port: the command contract

`afk-python afkv2/ports/tracker/cli.py <verb> [json-payload]`, or the payload on stdin.

Every answer is one JSON object: `{"ok": true, ...}`, or `{"ok": false, "error": {"code", "reason", ...}}`.
Exit 0 is ok. Exit 1 is a refusal. Exit 2 is unreadable input (`bad-payload`, `unknown-verb`).

## Verbs

| Verb | Payload | Answer | Kind |
|------|---------|--------|------|
| `issue-get` | `key`; optional `fields` (comma string or list), `tracker`, `repo` | Jira: `key, id, fields, description, description_hash, block`, and `block_problem` when the block is broken. GitHub: `key` and the `gh` fields | both |
| `issue-search` | optional `query`, `max_results`, `tracker`, `repo` | `issues, count` | GitHub issues |
| `md-to-adf` | `markdown`; optional `figures` `{index: [ADF nodes]}` | `content, figure_token` | Jira |
| `attachment-list` | `key` | `attachments, count` | Jira |
| `attachment-put` | `key, png, receipt, preview` | `key, attachment_id, media_id, filename, width, height` | Jira |
| `attachment-delete` | `id` | `id, filename, deleted`; `deleted` is false when Jira no longer has it | Jira |
| `description-put` | `key, adf, expect_hash, receipt, preview` | `key, replaced, description_hash, block` | Jira |

The port has no create, transition or comment verb.

`issue-get` and `issue-search` take the kind from the payload `tracker`, then from `tracker.kind` in the answer of `afkv2/scripts/afkv2_config.py read`. The kinds are `jira` and `github-issues`.

## The publish contract

- `preview` is the path of a JSON file with `ticket_key`, `receipt` (64 lowercase hex characters), `description_hash` and `picture_hashes` (the sha256 hex digest of each picture file).
- `expect_hash` is the `description_hash` that `issue-get` answered when the preview was built. It must equal the preview's `description_hash`.
- The `png` file name is `afkv2-fig-<receipt 8 chars>-<n>.png`, and the hash of the file must be in `picture_hashes`.
- `adf` is a list of ADF nodes or a doc. It holds only the text between the block lines; the port writes the lines.
- `figure_token` holds `{}` for the figure index. A paragraph that holds only the token becomes the nodes of `figures[index]`.
- `attachment-delete` removes only an afkv2 or a v1 picture of a published block.

## The read-back compare

`block` is `{"family", "text", "media_ids"}`. Compare `block` of the `description-put` answer with `block` of the next `issue-get` answer. Equal means the write holds. Delete old pictures only after that.

## Error codes

| Source | Codes |
|--------|-------|
| HTTP status | 400 `bad-request`, 401 `auth`, 403 `forbidden`, 404 `not-found`, 409 `conflict`, 413 `too-large`, 422 `unprocessable`, 429 `rate-limited`, 5xx `server-error`, other `http-error` |
| Input | `bad-payload`, `unknown-verb` |
| Publish | `bad-receipt`, `bad-name`, `bad-block`, `stale`, `not-a-picture`, `no-media-id` (carries `attachment_id`) |
| Setup | `no-credentials`, `no-tracker`, `unsupported`, `unavailable`, `missing-dependency` |
| Transport | `network`, `timeout`, `bad-answer`, `cli-failed`, `internal` |
