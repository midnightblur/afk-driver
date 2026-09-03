# tracker/github-issues — capability contract

GitHub Issues through `gh api`. Workflow states are labels (`github-
issues.state-labels`), a parent is a tracking issue with a task list, and an
attachment is a comment carrying the asset URL.

## Verbs

- `tracker_get`
- `tracker_search`
- `tracker_create`
- `tracker_edit`
- `tracker_comment`
- `tracker_transition`
- `tracker_transitions`
- `tracker_attachments`
- `tracker_changelog`

Every verb takes its arguments as JSON on the command line or on stdin, and
answers with one JSON object on stdout. A verb this adapter does not implement
answers `{"unsupported": true, "reason": "..."}`. A verb whose runtime is
absent answers `{"unavailable": true, "reason": "..."}` — never nothing.

## Configuration keys read

- `tracker`
- `github-issues.repo`
- `github-issues.state-labels`

Secrets are never read from a configuration file. The keys above name
environment variables; the values come from the environment or the harness
credential store.

## Documented degradation

`tracker_attachments` cannot upload a binary: it returns the comment it wrote
and the asset URL it was given. Rich text is Markdown, not ADF.
