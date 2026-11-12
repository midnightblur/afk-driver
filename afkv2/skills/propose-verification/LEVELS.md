# Test levels

The `level` of a plan row. Tier low runs per subtask; tier high runs once for the whole chain, at the end gate.

| Level | Tier | Proves | Good when | A smell |
|-------|------|--------|-----------|---------|
| `static` | low | a whole class of defect is absent, without a run | blocks only real defects; says how to fix | a new suppress comment; lint cited as proof of a behavior |
| `unit` | low | logic, edge cases and branches, in milliseconds | public interface only; asserts state; doubles only for external systems | an expected value copied from the code; a double of the unit itself |
| `integration` | low | the code and a real boundary agree: database, file, queue | the engine of the production type; reads the effect back; owns its data | the database is a double; fails when run alone |
| `contract` | low | 2 services agree on their messages, with no shared environment | the real client makes the call; only the fields the consumer reads | raw HTTP in place of the client; never verified by the provider |
| `api` | high | the wired app, with real configuration, routing and authentication, answers as specified | status, body and effect; error and permission paths; polls, never sleeps | a status-only assert; fixed sleeps |
| `ui-e2e` | high | a user journey through the real screen and backend | asserts what the user sees; role or label locators; waiting assertions | sleeps; structural selectors; a screenshot nobody asserts |
| `acceptance` | high | the feature does what was meant, in business words | a few key examples; each outcome bound to its own evidence | a click script as the spec; a vague outcome |

**Highest-value level**: the lowest level where the outcome of a behavior exists with fidelity. Each behavior has 1 authoritative row there. Cheaper rows below add cases; a few rows above cover wiring, configuration, the browser or a journey.
