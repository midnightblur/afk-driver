# build-gate/npm — capability contract

npm gates: lint, run in the nearest workspace of each staged file, plus
worktree provisioning.

## Verbs

- `gate-discover`
- `gate-run`
- `worktree-provision`

Every verb takes its arguments as JSON on the command line or on stdin, and
answers with one JSON object on stdout. A verb this adapter does not implement
answers `{"unsupported": true, "reason": "..."}`. A verb whose runtime is
absent answers `{"unavailable": true, "reason": "..."}` — never nothing.

## Configuration keys read

- `build-gates`
- `npm.lint`
- `npm.workspace-root`
- `npm.worktree-install`
- `npm.worktree-command`

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

## worktree-provision

A fresh worktree has no `node_modules`, so every UI command in it fails until
something restores the dependencies. `worktree-provision.sh` runs the
repository's own install command in `npm.workspace-root`, and only when there is
a lockfile there to install from.

| Key | Values | Effect |
|---|---|---|
| `npm.worktree-install` | `ci` (default), `none` | `none` installs nothing |
| `npm.worktree-command` | argv words, default `npm ci` | the command that restores the dependencies |
| `npm.workspace-root` | path, default the worktree root | where the lockfile and the install live |

Already-current dependencies are adopted, not reinstalled: npm writes
`node_modules/.package-lock.json` after an install, so a copy of it no older than
the lockfile is npm's own statement that the tree matches.

Answers `{"kind":"npm","status":…,"fingerprint":…,"done":[…],"skipped":[…],"warnings":[…]}`.
`status` is `provisioned`, `adopted`, or `skipped`. Exit 0 for all of those, 2 for
an invalid payload, 4 when the install command failed — the worktree is still a
usable checkout, so that is a warning with the command to re-run, not a failure.

`gates.sh` is both the CLI entry above and the library the commit runner sources.

## Documented degradation

Needs node and npm. Absent, `gate-discover` returns no gates. A workspace whose
lint command cannot be resolved is skipped and NOT recorded as a pass — missing
lint infrastructure is not the committer's failure, and it must not cache green.
