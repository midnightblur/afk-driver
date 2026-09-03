# build-gate/maven — capability contract

Maven gates: compile, format, lock, app-start, mutation. Every parameter comes
from the `maven:` block.

## Verbs

- `gate-discover`
- `gate-run`
- `app-start`

Every verb takes its arguments as JSON on the command line or on stdin, and
answers with one JSON object on stdout. A verb this adapter does not implement
answers `{"unsupported": true, "reason": "..."}`. A verb whose runtime is
absent answers `{"unavailable": true, "reason": "..."}` — never nothing.

## Configuration keys read

- `build-gates`
- `maven.reactor-pom`
- `maven.formatter-config`
- `maven.formatter-plugin`
- `maven.default-module`
- `maven.skip-ui-flag`

Secrets are never read from a configuration file. The keys above name
environment variables; the values come from the environment or the harness
credential store.

## Gates

| Gate | Script | Blocks when |
|---|---|---|
| `java-format` | `java-format-gate.sh` | a changed `.java` file does not match `maven.formatter-config` |
| `maven-compile` | `maven-compile-gate.sh` | a changed module fails `compile` in the `maven.reactor-pom` reactor |

`app-start` is a verb, not a gate: `app-start-gate.sh` packages
`maven.default-module` (or the module given) and waits for the application
context to come up. `mutation-probe.sh` is on-demand only and never blocks.
`maven-lock.sh` is the mutex every Maven-invoking gate wraps its reactor in;
`maven-lib.sh` reads the `maven:` block for all of them.

`gates.sh` is both the CLI entry above and the library the commit runner sources,
so a gate runs inside the runner's process and shares its change set, pass cache
and metrics.

## Documented degradation

Needs a Maven wrapper and a JDK. Absent, `gate-discover` returns no gates.
`maven.reactor-pom` unset, or naming a POM this checkout does not have, makes
every gate in this adapter inert — a repository is never gated by a build it does
not have. `maven.formatter-plugin` or `maven.formatter-config` unset turns off
the format gate alone.
