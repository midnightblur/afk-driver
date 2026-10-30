# Forge port: the command contract

`<python> afkv2/ports/forge/cli.py <verb> [json-payload]`, or the payload on stdin. `<python>` is the Python in the setup install record (line `python`).

The answer envelope and the exit codes are the same as in `afkv2/ports/tracker/CONTRACT.md`. The field lists below are the fields beside `ok`. Both forges answer the same keys.

Every payload can hold `forge` (`github` or `gitlab`) and `repo`. Without `forge`, the kind comes from `forge` in the config reader's answer, then from the host of the `origin` remote: exactly one of `github` and `gitlab` must be a part of the host, where a dot or a dash ends a part. Any other host refuses `no-forge`.

## Verbs

| Verb | Payload | Answer |
|------|---------|--------|
| `auth-status` | none | `authenticated, user`, or `authenticated: false, reason` |
| `change-view` | `id` | `id, url, title, draft, state, source, target, author, head_sha, base_sha, head_ref, cross_fork, blob_base, pipeline.status` |
| `change-diff` | `id` | `diff, lines, bytes` |
| `change-create-draft` | `title`; optional `body, target, source, reviewer, assignee` (`reviewer` and `assignee`: a word or a list) | `url, id, draft` |
| `change-update-body` | `id, body` (never blank) | `id, was_draft, draft_restored`; `was_draft` is `"true"` or `"false"`. A failed read of the flag refuses, and nothing is written |
| `change-ready` | `id` | `id, draft` |
| `change-comment` | `id, text`; for an inline comment `file` or `old_path`/`new_path`, `side` (`new` by default, `old`, `context`), `line` (for `new`, `context`), `old_line` (for `old`, `context`), `require_inline` | `inline, thread, comment, url`, and `reason` when a position landed as a plain note |
| `note-list` | `id` | `notes[id, author, body, created_at, updated_at, edited], count`. Every note that is not on a line and not from the system, replies too |
| `thread-list` | `id` | `threads[id, resolved, file, side, line, old_line, old_path, new_path, url, notes[id, author, type, body, created_at, updated_at, edited]], count`. Line comments only. A thread note `id` is a number, and `type` is the forge's own word |
| `ci-status` | `id` | `status, url` |
| `ci-wait` | `id`; optional `budget` (default 5400 s), `interval` (default 180 s) | `status, elapsed, id` |

`state` is `opened`, `merged` or `closed`. `status` is one of these words on both forges: `success`, `failed`, `canceled`, `running`, or an empty string when the change has no checks. A status that is not final, and a pipeline or check that waits for a human (GitLab `manual`, GitHub `ACTION_REQUIRED`), reads `running`. A skipped run reads `success`. A check with an error or a stale result reads `failed`.

## `change-comment`

A position the forge rejects: with `require_inline`, the verb refuses `position-rejected` and leaves no comment. Without it, the text lands as a plain note and the answer holds `inline: false` and `reason`.

## `ci-wait`

`ci-wait` exits 0 for every status it can read, `failed` and `canceled` too. The caller routes on `status`. It reads at least once, and once more when the budget ends. After a last read that gives a status that is not final, `status` is `running` and `reason` says so: the checks keep running. 3 reads in a row with no status, or a last read with no status, refuse with `unreadable`, which is no verdict on the change.

## Error codes

The tracker table, plus `no-forge`, `bad-position`, `position-rejected`, `unreadable` and `draft-lost`.

`draft-lost` means `change-update-body` wrote the body on GitLab, `glab` cleared the draft flag, and the port could not set it again. The change is open for review until a human sets it: `reason` names the command. A retry does not set it, because the flag then reads as off.

`position-rejected` means the forge did not place the comment on the line. With `require_inline`, GitLab removes the plain note it wrote: the error holds `cleaned: true`, or `note` with the id of a note the cleanup could not remove.
