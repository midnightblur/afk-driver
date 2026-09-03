# build-gate/npm — capability contract

npm gates: lint, run in the nearest workspace of each staged file.

## Verbs

- `gate-discover`
- `gate-run`

Every verb takes its arguments as JSON on the command line or on stdin, and
answers with one JSON object on stdout. A verb this adapter does not implement
answers `{"unsupported": true, "reason": "..."}`. A verb whose runtime is
absent answers `{"unavailable": true, "reason": "..."}` — never nothing.

## Configuration keys read

- `build-gates`
- `npm.lint`
- `npm.workspace-root`

Secrets are never read from a configuration file. The keys above name
environment variables; the values come from the environment or the harness
credential store.

## Documented degradation

Needs node and npm. Absent, `gate-discover` returns no gates.
