# Patterns are reusable team shapes, not stage settings

> Status: Accepted
> Audited: 2026-09-28
> Layer: Requirements
> Context ticket: agent-team-topology

A pattern knows nothing of the workflow. It carries a description of how and when it is useful; the contact agent reads the descriptions, proposes patterns for the task, possibly several combined, and the human picks. The plugin ships built-in patterns but no stage map; the human's own configuration may still map a stage to a pattern. A reader expects a workflow plugin to wire a team to each of its stages. The human rejected that, because one shape, such as a debate, serves many stages, and binding it to one would force the same shape to be written again for each.

## Considered Options

- Ship a map giving each stage one pattern, with combined patterns for stages that write then audit. Rejected: it attaches patterns to the workflow.
- Let a map entry hold an ordered list of patterns. Rejected for the same reason, and it needs its own order and failure rules.

## Consequences

Patterns combine: a step may use another pattern, and a role may run as a debate on different models. The combination becomes one team before any agent starts, so it adds no nested team; nested teams stay deferred (issue 25).
