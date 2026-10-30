# Forge port: the command contract

`afk-python afkv2/ports/forge/cli.py <verb> [json-payload]`, or the payload on stdin.

The answer envelope and the exit codes are the same as in `afkv2/ports/tracker/CONTRACT.md`. The field lists below are the fields beside `ok`. Both forges answer the same keys.

Every payload can hold `forge` (`github` or `gitlab`) and `repo`. Without `forge`, the kind comes from `forge` in the config reader's answer, then from the host of the `origin` remote.

## Verbs

| Verb | Payload | Answer |
|------|---------|--------|
| `auth-status` | none | `authenticated, user`, or `authenticated: false, reason` |
| `change-view` | `id` | `id, url, title, draft, state, source, target, author, head_sha, base_sha, head_ref, cross_fork, blob_base, pipeline.status` |
| `change-diff` | `id` | `diff, lines, bytes` |
| `change-create-draft` | `title`; optional `body, target, source, reviewer, assignee` | `url, id, draft` |
| `change-update-body` | `id, body` (never blank) | `id, was_draft, draft_restored`; `was_draft` is `"true"`, `"false"` or `"unknown"` |
| `change-ready` | `id` | `id, draft` |
| `change-comment` | `id, text`; for an inline comment `file` or `old_path`/`new_path`, `side` (`new`, `old`, `context`), `line`, `old_line`, `require_inline` | `inline, thread, comment, url`, and `reason` when a position landed as a plain note |
| `note-list` | `id` | `notes[id, author, body, created_at, updated_at, edited], count` |
| `thread-list` | `id` | `threads[id, resolved, file, side, line, old_line, old_path, new_path, url, notes], count` |
| `ci-status` | `id` | `status, url` |
| `ci-wait` | `id`; optional `budget` (default 5400 s), `interval` (default 180 s) | `status, elapsed, id` |

`state` is `opened`, `merged` or `closed`. `status` is a forge word: `success`, `failed`, `canceled`, `running`, or an empty string when the change has no checks.

## `ci-wait`

`ci-wait` exits 0 for every status it can read, `failed` and `canceled` too. The caller routes on `status`. When the budget ends, `status` is `running` and `reason` says so: the checks keep running. 3 reads in a row with no status refuse with `unreadable`, which is no verdict on the change.

## Error codes

The tracker table, plus `no-forge`, `bad-position`, `position-rejected` and `unreadable`.

`position-rejected` means the forge did not place the comment on the line. With `require_inline`, GitLab removes the plain note it wrote: the error holds `cleaned: true`, or `note` with the id of a note the cleanup could not remove.
