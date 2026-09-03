# forge/github — capability contract

GitHub pull requests through `gh`.

## Verbs

- `change-view`
- `change-diff`
- `change-create-draft`
- `change-ready`
- `change-reviewers`
- `change-update-body`
- `change-comment`
- `change-state`
- `change-close`
- `change-fetch`
- `ci-status`
- `ci-wait`
- `auth-status`

Every verb takes its arguments as JSON on the command line or on stdin, and
answers with one JSON object on stdout. A verb this adapter does not implement
answers `{"unsupported": true, "reason": "..."}`. A verb whose runtime is
absent answers `{"unavailable": true, "reason": "..."}` — never nothing.

## Configuration keys read

- `forge`
- `github.remote`
- `git.base-branch`

Secrets are never read from a configuration file. The keys above name
environment variables; the values come from the environment or the harness
credential store.

## Documented degradation

`change-reviewers` needs push access to the head repository; on a fork it
returns `unsupported` with that reason.
