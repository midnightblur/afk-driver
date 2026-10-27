# INV-010 — L7 module seams

Verdict: closed-with-frontier.

## Closed premises

- Shared executable behavior belongs under the plugin `scripts/` layer; skills invoke it through `AFK_PLUGIN_ROOT`. The Lavish renderer already uses a small command entry point over separately testable schema and page modules (`scripts/lavish_render.py:33,120-150`, `scripts/lavish/schema.py:476`, `scripts/lavish/page.py:139`).
- Shared stateful code uses explicit dependency passing, not a dependency-injection container. The forge ledger constructs its real adapter at the command boundary and tests the same seam with `FakeAdapter` (`skills/afk/review/scripts/forge_ledger.py:743-787,2415-2427`, `scripts/tests/test_forge_ledger.py:36-92,235`).
- The forge family is the provider boundary. `note-list` returns normalized oldest-first notes and `change-comment` posts normalized comments (`ADAPTERS.md:3-25,76-85,103-110`).
- The configuration reader is the only owner of `.afk/config.yaml`; callers consume its normalized result (`scripts/afk-config.py:1-34,53-59,100-130`; INV-005).
- Requirements, glossary, preflight, and settlement already have distinct workflow responsibilities. A shared synchronous JSON command is the stable seam between those skills and one glossary engine (`skills/afk/grill-requirements/SKILL.md:20-34,76-82`, `skills/utils/glossary/SKILL.md:14-24,28-73`, `skills/afk/preflight/SKILL.md:190-215,273-280`, `skills/utils/settle-change/SKILL.md:32-38,96-98`).
- The forge family has no normalized approval-read operation and no operation that returns a change to Draft. Existing `change-state` is read-only and `change-ready` moves only toward Ready (`adapters/forge/gitlab/forge.sh:350-415`, `adapters/forge/github/forge.sh:361-418`).

## Counter-search

- Searched skill calls, script imports, adapter manifests and contracts, configuration consumers, tests, and both provider scripts.
- No dependency-injection framework or long-lived service container exists in the applicable plugin paths.
- No existing approval-read or return-to-Draft forge verb was found under alternate provider terms.
- B1-B5, B7-B8, and B12-B13 are closed. B6, B9-B11 are not applicable to this synchronous local package.

## Frontier

- B14: the two required forge operations do not exist, so live GitLab and GitHub behavior for them is unverified. The already signed L4 contract requires live conformance tests before shipment.
