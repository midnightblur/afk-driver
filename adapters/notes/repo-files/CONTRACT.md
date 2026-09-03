# notes/repo-files — capability contract

Markdown files inside the consuming repository, under the path `repo-
files.spec-dir` renders for the work item.

## Verbs

- `note-create`
- `note-read`
- `note-update`
- `note-delete`
- `note-link`
- `resolve`

Every verb takes its arguments as JSON on the command line or on stdin, and
answers with one JSON object on stdout. A verb this adapter does not implement
answers `{"unsupported": true, "reason": "..."}`. A verb whose runtime is
absent answers `{"unavailable": true, "reason": "..."}` — never nothing.

## Configuration keys read

- `notes`
- `repo-files.spec-dir`

Secrets are never read from a configuration file. The keys above name
environment variables; the values come from the environment or the harness
credential store.

## Documented degradation

None. This is the canonical store; every other notes adapter mirrors it.
