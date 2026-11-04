# Page documents own feature tips

> Status: Decided by agent
> Audited: 2026-11-04
> Layer: Requirements
> Context ticket: #159

The page document carries feature-term definitions and ID-to-title mappings. A separate feature-tip file remains a legacy input only. This choice gives each page one durable source for its feature-specific meanings.

## Considered Options

- Keep feature-specific tips in an adjacent file. Rejected by the agent in `r1-data-boundary`, because the accepted requirement makes the page authoritative and the old file has no authoring path.
