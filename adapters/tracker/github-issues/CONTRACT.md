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
- `tracker_attach`

Every verb takes its arguments as JSON on the command line or on stdin, and
answers with one JSON object on stdout. A verb this adapter does not implement
answers `{"unsupported": true, "reason": "..."}`. A verb whose runtime is
absent answers `{"unavailable": true, "reason": "..."}` — never nothing.

## Configuration keys read

- `tracker`
- `github-issues.repo`
- `github-issues.state-labels`

No credential is configured for this kind: it runs `gh`, so authentication is
whatever `gh auth login` established.

## What is modelled, not mapped

GitHub Issues has no workflow engine and no attachment API, so four operations
answer in a shape this contract fixes rather than pretending a field exists:

| Operation | Shape here |
|---|---|
| `tracker_transitions` | `open` and `closed` always, marked `native`, plus the states in `github-issues.state-labels`; the transition id IS the state name |
| `tracker_transition` | `open`/`closed` (and the aliases `reopen`/`close`) move GitHub's own issue state. Any other id adds that state's label and removes every other state label, so an issue is never in two states. An id that is not a state is refused before any write |
| `tracker_attachments` | the asset URLs referenced in the issue body and its comments, with `"partial": true` — a file never referenced in text cannot be listed |
| `tracker_attach` | one `gh issue comment` with one `--attach` per image or video file (`.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`, `.svg`, `.mp4`, `.mov`, `.webm`), shown inline. Any other file type, a host other than github.com (GitHub Enterprise Server), gh older than 2.99.0 (register row C3c) and a login without write access leave that file in `unsupported_files` with the reason, and the comment names it |

`tracker_create` writes the work-item type and the opening state as labels, and
a `parent` becomes a task-list line on the parent issue. A `status` that is
neither `open` nor a key of `github-issues.state-labels` is refused before any
write. `tracker_edit` writes
title, body, milestone, labels and assignees; any other field is reported back
in `ignored_fields` and NOT written.

This kind does not carry the ADF publishing machinery, so the Jira publishing
scripts stop with the missing names when `tracker: github-issues` is selected.

## Documented degradation

`tracker_attach` uploads images and videos only; every other file is named in
the comment for the developer to add by hand. Rich text is Markdown, not ADF.

A label has to exist in the repository before an issue can carry it, so
`tracker_edit` with an unknown label answers `error` naming that label and
writes nothing. This adapter never creates a label: that would change the
repository's settings on a caller's behalf.

A payload that is not one JSON object is answered with the family's error object and exit 2, never a traceback; the shared reader is `adapters/tracker/payload.py` and `scripts/tests/test_tracker_surface.py` pins it for both tracker kinds.
