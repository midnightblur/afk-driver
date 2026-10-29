# Jira write boundary: the whole PRD, in one managed block, after a yes

> Status: Accepted
> Audited: 2026-10-29
> Layer: Requirements
> Context ticket: GitHub #153

The agent writes to Jira only through `/afkv2:to-prd`, and only into one ticket. It writes the whole PRD inside the AFK-managed block of the description, and it uploads and replaces the PRD's diagram pictures. Every write follows the human's yes on the exact preview. All text outside the block stays unchanged. The publish is refused when the ticket changed after the preview, or when an acceptance-criterion id or a worked-example id is missing. Creating tickets, changing their status and commenting stay denied in the beta. Why: the product owner and QA read requirements in the ticket, and the owner chose the whole PRD with pictures (GRILL-LOG J-1, J-2, J-4, Y-1, Y-3). The managed block keeps other people's text.

## Considered Options

- A requirements-level summary (the v1 ticket form). Rejected by the owner in Y-1.
- No Jira write in the beta. Rejected by the owner in J-1.
