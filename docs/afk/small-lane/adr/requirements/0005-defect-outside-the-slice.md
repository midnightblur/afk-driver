# A defect outside the slice gets its own ticket and diagnosis

> Layer: Requirements
> Context ticket: small-lane

An agent can find a defect in code that its slice did not write. A reader who never saw the feature will read the ticket for that defect, so it must stand alone. Each such defect gets a diagnosis before its ticket is filed: a light diagnosis when the run already holds a reproduction, else a full one. The ticket carries the evidence and the proof. When the defect blocks the slice, the agent fixes it on its own branch off the base branch with its own merge request, linked to the ticket. The agent also puts the same fix on the feature branch, and the feature's merge request names the separate one as a dependency. The human merges both. When the defect does not block the slice, it gets the ticket only. Starting a hands-off run is the prior approval for these ticket writes and merge requests. The run stays autonomous, and the human keeps every merge decision.

## Considered Options

- Put the feature branch on top of the fix branch: rejected. The feature could not merge before the fix, and every rebase would move both branches.
- Fix it only inside the feature's merge request: rejected, because it hides an unrelated fix inside a feature review.
- File the ticket with no diagnosis: rejected, because the ticket would not stand alone.
