# Coming back continues the finished page and flags every later document

> Layer: Requirements
> Context ticket: #174

Calling the grill on a ticket whose grill ended takes over the newest finished session and adds a round to its page, instead of starting an empty one. At its new end it names every later document of the ticket that exists, such as the requirements, the design and the plan, as possibly out of date, and lists the settled points that changed.

## Considered Options

- Leave coming back to a spinoff ticket. Rejected by the developer in card i-reentry, because new facts after the end are expected.
- Trace each assumption to the documents that rest on it. Rejected by the developer in card i-stale, because every later skill would have to record which assumption each part rests on.
