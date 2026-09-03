# forge/none — capability contract

No forge. Every verb prints `{"unsupported": true, "reason": "forge: none —
set forge: gitlab|github in .afk/config.yaml"}` and exits 3.

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

No credential and no runtime: this kind talks to nothing.

## Documented degradation

Everything. A skill that reaches a forge verb stops and shows that reason; it
never guesses a forge.
