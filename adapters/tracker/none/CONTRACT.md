# tracker/none — capability contract

No tracker. Every verb returns `{"unsupported": true}` with the reason.

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

Secrets are never read from a configuration file. The keys above name
environment variables; the values come from the environment or the harness
credential store.

## Documented degradation

Everything. A skill that needs a tracker writes the same payload through the
`notes` adapter and says so.
