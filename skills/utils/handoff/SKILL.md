---
name: handoff
description: Compact the current conversation into a handoff document for another agent to pick up.
argument-hint: "What will the next session be used for?"
---

Write a handoff document summarising the current conversation so a fresh agent can continue the work. Save to a path from `mktemp -t handoff-XXXXXX.md` (read the file before writing to it).

Required sections: **goal** · **current state** · **next steps** · **artifact pointers** (paths/URLs to everything the next agent touches). Bar: a fresh agent needs no other context to take the next step — anything a next step depends on that only this conversation knows goes in the doc.

Suggest the skills the next session should use, if any.

Don't duplicate content already in other artifacts (PRDs, plans, ADRs, issues, commits, diffs). Reference them by path or URL instead.

If the user passed arguments, treat them as what the next session will focus on and tailor the doc accordingly.

End by printing the saved doc path as the final line.