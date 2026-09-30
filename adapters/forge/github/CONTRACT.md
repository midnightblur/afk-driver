# forge/github — capability contract

GitHub pull requests through `gh`.

## Verbs

- `change-view`, `change-diff`, `change-fetch`, `change-state`
- `change-create-draft`, `change-ready`, `change-reviewers`, `change-update-body`,
  `change-comment`, `change-close`
- `thread-list`, `thread-reply`, `thread-resolve`
- `note-list`, `commit-changes`
- `ci-status`, `ci-wait`
- `auth-status`
- `branch-protection`


Every verb takes its arguments as JSON on the command line or on stdin, and
answers with one JSON object on stdout. A verb this adapter does not implement
answers `{"unsupported": true, "reason": "..."}`. A verb whose runtime is
absent answers `{"unavailable": true, "reason": "..."}` — never nothing.

## Configuration keys read

- `forge`
- `github.remote`
- `git.base-branch`

No credential is configured for this kind: authentication is whatever the forge
CLI already established, and no configuration file holds a token.

## Notes that bite

The adapter tests use a stub command-line tool. They do not contact GitHub.

- A paginated read (`gh api --paginate`) prints one JSON document per page, not
  one document holding every page. `thread-list` decodes the documents in order
  and joins the arrays; a caller driving `gh` directly does the same, or it sees
  only page 1 — or, worse, reports the whole answer unreadable.
- `ci-wait` prints its result object on stdout for EVERY terminal status,
  including budget exhausted (exit 2) and unreadable (exit 3); stderr carries
  the human line only. A caller routes on the object, and an exit code alone
  does not say which checks, or for how long.
- A payload handed to this script as a command-line argument from a NATIVE
  Windows process (not from a shell) loses its quotes: the shell's runtime
  re-parses the command line, and the adapter then reads an unreadable payload
  and uses its defaults. Such a caller puts the payload in the environment and
  lets the shell expand it.
- `change-comment` uses the issue-comment API for a plain note. It uses the
  review-comment API for an exact line.
- `side: old` sends `LEFT`, `old_path`, and `old_line`. `new` and `context`
  send `RIGHT`, `new_path`, and `line`.
- `thread-list` groups REST review comments by their root identifier. It joins
  the real resolution state from paginated GraphQL review threads.
- `thread-resolve` maps the REST root identifier to the GraphQL node. An
  unmapped root returns an error and changes nothing.
- `note-list` reads paginated issue comments. It returns plain notes only, each
  with `edited` from GraphQL `lastEditedAt` (keyed by `databaseId`). A failed
  query, or a comment the query does not answer, is an error.
- `thread-list` carries `edited` on every note from the same GraphQL review-thread
  query that gives the resolution state; a comment missing from the answer is an error.
- `commit-changes` reads the pull requests that contain one commit (`sha`), paginated. A merged request reports `merged`; an open one reports `opened`. A failing `gh`, a non-list answer, or an entry with no number is an error.
- `change-view` answers `missing: true` in its error only when `gh` says no pull request exists for the reference.
- `change-view` and `change-fetch` return the metadata in `ADAPTERS.md`.
- `blob_base` names the source repository. It is empty when that repository is
  unavailable.
- "Pipeline status" is the rollup of the head commit's checks, mapped into the
  same words the GitLab adapter answers with, so one caller compares one
  vocabulary.

## Documented degradation

`change-reviewers` needs push access to the head repository; on a fork it
returns `unsupported` with that reason.
