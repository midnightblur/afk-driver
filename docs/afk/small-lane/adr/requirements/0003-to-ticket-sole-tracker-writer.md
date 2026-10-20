# /afk:to-ticket is the only tracker writer; /afk:bug is removed

> Layer: Requirements
> Context ticket: small-lane

The plugin had 2 tracker writers: `/afk:to-ticket` and the publisher of `/afk:bug`. Now `/afk:to-ticket` gains a bug and ad-hoc mode, which creates or updates a ticket from a diagnosis or a description, applies configured states and posts evidence comments, on Jira and GitHub Issues. It becomes the only tracker writer. `/afk:bug` is removed in a major release with no alias. With one writer, every ticket write has one consent rule and one home.

## Considered Options

- A deprecated alias for one release: rejected.

## Consequences

- The plugin's ADR-0001 (2 tracker writers, no file) no longer holds.
- Tickets filed by the old pipeline are fixed by passing their key to `/afk:fix`; no migration.
