# An ad-hoc page lives in the spec folder only with a ticket and shareable content

> Layer: Requirements
> Context ticket: #163

Any agent may write a page at any time, and an ad-hoc page often has no ticket. With a ticket, an ad-hoc page lives in the ticket's spec folder and is committed. With no ticket, or with content the repository's readers may not see, it lives outside the repository and is not committed. A committed page is read by every reader of a public repository, and that cannot be undone.

## Considered Options

- Always the spec folder. Rejected by the owner in i-adhoc-home, because every ad-hoc page would need a ticket.
- Always outside the repository. Rejected by the owner in i-adhoc-home, because a page about a ticket would leave no record.
