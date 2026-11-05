# Preserve legacy pages

> Layer: Requirements
> Context ticket: #159

Existing page/0 documents keep their current rendering and sidecar tips. Documents with page-owned tips do not read the legacy sidecar. This boundary avoids migration and prevents stale sidecar data from changing a new page.

## Considered Options

- Change page/0 in place. Rejected by the developer in `r1-compatibility`, because page/0 is frozen and existing documents must keep their meaning.
- Merge legacy sidecars into new documents. Rejected by the developer in `r3-sidecar-boundary`, because stale external data could change a new page.
