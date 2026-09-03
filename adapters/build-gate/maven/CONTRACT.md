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

## Documented degradation

Needs a Maven wrapper and a JDK. Absent, `gate-discover` returns no gates.
