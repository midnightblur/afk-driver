# forge/gitlab — capability contract

GitLab merge requests through `glab`. Inline comments post as DiffNotes with
the merge request's diff refs.

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
- `gitlab.remote`
- `git.base-branch`

Secrets are never read from a configuration file. The keys above name
environment variables; the values come from the environment or the harness
credential store.

## Documented degradation

None. Every forge verb is supported.
