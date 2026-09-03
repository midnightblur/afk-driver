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

## Gates

| Gate | Script | Blocks when |
|---|---|---|
| `ui-lint` | `ui-lint-gate.sh` | a changed `.js/.cjs/.mjs/.ts/.vue` file fails `npm.lint` |

The lint workspace is the nearest ancestor of a changed file holding a lint
configuration; with none, `npm.workspace-root` is used when it is an ancestor.
`npm.lint` is a command and its fixed arguments, split on whitespace, with the
changed files appended; it defaults to
`npx --no-install eslint --no-error-on-unmatched-pattern`.

`gates.sh` is both the CLI entry above and the library the commit runner sources.

## Documented degradation

Needs node and npm. Absent, `gate-discover` returns no gates. A workspace whose
lint command cannot be resolved is skipped and NOT recorded as a pass — missing
lint infrastructure is not the committer's failure, and it must not cache green.
