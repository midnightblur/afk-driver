# Open questions for others block the end of the grill

> Layer: Requirements
> Context ticket: #174

The grill's end check fails while a question for others is open. A question closes when it is answered, dropped with a reason, or assumed after the developer accepts a written assumption; an assumed answer goes into the requirements as a risk naming who must confirm it. The developer chose "Block, allow assumption".

## Considered Options

- Block always, with no assumption. Rejected by the developer, because a stakeholder away for days would stall the grill.
- Warn only. Rejected by the developer, because a guess would reach the requirements unmarked.
