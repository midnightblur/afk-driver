# summary.md format

`<run_dir>/<ticket key>/summary.md` is the comment 1 ticket gets for 1 meeting, in Markdown. The comment title is the meeting key that `start` answered; do not write it in the file.

## Shape

```markdown
<1 line: what this meeting was, seen from this ticket>

**Recordings:**
- [<label>](<url>)   or: Transcript only, no recording link given

In Attendance: <names, from the transcript speakers>

Documents: <links, or ->

---

# Summary

## 1. Decisions / Confirmations
- <a decision or confirmation for this ticket>

## 2. Open questions / Action items
- **[<owner>]** <an action or open question>

## 3. Meeting notes
- <a clarification worth keeping>
- See <OTHER-KEY> for <topic>.
```

## Rules

- Word each summary for its ticket. Content that concerns 2 tickets goes into both, worded for each.
- Write only what the transcript supports. A suggestion is not a decision. Mark unclear audio "(unclear in transcript)" and each inference "(inferred)".
- An owner is a named person, or "unassigned".
- A topic settled under another ticket gets 1 line in Meeting notes: "See <KEY> for <topic>."
- Write a ticket key bare, such as `ABC-12`: the Jira comment makes each key of the ticket's projects a link.
