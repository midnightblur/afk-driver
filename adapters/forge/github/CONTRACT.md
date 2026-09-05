# forge/github — capability contract

GitHub pull requests through `gh`.

## Verbs

- `change-view`, `change-diff`, `change-fetch`, `change-state`
- `change-create-draft`, `change-ready`, `change-reviewers`, `change-update-body`,
  `change-comment`, `change-close`
- `thread-list`, `thread-reply`, `thread-resolve`
- `ci-status`, `ci-wait`
- `auth-status`


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

The paginated read and every `ci-wait` exit are pinned offline, against a stub command-line tool, by `scripts/tests/test_forge_adapters.py`.

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
- GitHub has no discussion object: a thread is a root review comment plus the
  comments whose `in_reply_to_id` points at it, so `thread-list` does that
  grouping and reports `resolved: null` — resolution lives on a GraphQL review
  thread these REST ids are not.
- `thread-resolve` therefore answers `unsupported`. Leaving a thread open is
  visible; resolving the wrong one silently hides a finding.
- "Pipeline status" is the rollup of the head commit's checks, mapped into the
  same words the GitLab adapter answers with, so one caller compares one
  vocabulary.

## Documented degradation

`change-reviewers` needs push access to the head repository; on a fork it
returns `unsupported` with that reason.
