> **Language:** read `LANGUAGE.md` (plugin root) before writing a diagnosis.

# Diagnosis format — `DIAGNOSIS.md`

One file per bug, in the bug's spec folder, committed with the failing test on the diagnosis branch. It is the only hand-off between the skills that work the bug. `scripts/check_diagnosis.py` accepts or refuses it and derives the bug's state from it. `scripts/outside_writes.py` is the only code that appends to its Outside writes. This file, the check script and the helper change in one commit; the scripts read the tables below, never a copy of them.

## Parts

Each part is a `## {Part}` heading, in this order. A part is empty when its heading has no content line under it.

| Part | Content | Empty allowed | Facts marked | Writer |
|---|---|---|---|---|
| Work id | ticket key, else `bug-{slug}`; unique per spec folder | no | no | diagnose; the bug mode moves the folder when a key arrives |
| Ticket key | the tracker key | yes | no | the bug mode, only while empty; a later different key goes to Outside writes |
| Verdict | one of V-1..V-5, written `V-{n} {name}` | no | no | diagnose; a re-run replaces it |
| Base | the branch the reproduction started from, and its commit id | no | no | diagnose |
| Diagnosis branch | branch name from the branch template, made from the Base tip | no | no | diagnose; never pushed by it |
| Symptom | the behaviour as checked, not as reported | no | yes | diagnose |
| Spec comparison | what the PRD, SDD, verification plan or other specs say, with citations | no | yes | diagnose |
| Reproduction | test path, command and failing output; a light diagnosis gives the reused check or finding | per verdict | yes | diagnose |
| Attempts | each attempt and its result | per verdict | yes | diagnose |
| Root cause | text with file and line | per verdict | yes | diagnose |
| Fix proposal | one option, or labelled options | per verdict | no | diagnose |
| Approval | who; their words or the prior approval; what it covers (code, ticket writes, change); ISO 8601 date | yes | no | `/afk:fix` only; every diagnose rewrite empties it; nothing checks it |
| Outside writes | one entry per outside write that succeeded | yes | no | the outside-writes helper only; append-only |

## Required parts per verdict

The check script refuses a diagnosis whose verdict lacks a part named in its row, and names each missing part. Every verdict needs a reproduction or a recorded attempt.

| Verdict | Name | Required parts |
|---|---|---|
| V-1 | obvious fix | Work id, Verdict, Base, Diagnosis branch, Symptom, Spec comparison, Reproduction, Root cause, Fix proposal |
| V-2 | several fixes | Work id, Verdict, Base, Diagnosis branch, Symptom, Spec comparison, Reproduction, Root cause, Fix proposal |
| V-3 | spec gap | Work id, Verdict, Base, Diagnosis branch, Symptom, Spec comparison, Reproduction, Root cause |
| V-4 | works as specified | Work id, Verdict, Base, Diagnosis branch, Symptom, Spec comparison, Reproduction |
| V-5 | cannot reproduce | Work id, Verdict, Base, Diagnosis branch, Symptom, Spec comparison, Attempts |

## Certainty marks

Every fact carries one mark, which says how sure it is. In a part whose `Facts marked` cell is yes, each fact is a list item that opens with its mark; an indented line or a fenced block under it belongs to that fact. Any other line in a fact part is a fact with no mark, and the check script refuses it.

| Mark | Meaning |
|---|---|
| `[verified]` | observed directly; the item cites its proof (command output, test result, capture) |
| `[inferred]` | concluded from evidence, not observed |
| `[guessed]` | plausible and unchecked |

## Outside writes entries

One list item per write, `- {kind}: {value}`. A re-run skips a write whose entry is listed.

| Kind | Value |
|---|---|
| `ticket` | the ticket key |
| `change` | the change link |
| `evidence` | the evidence marker of the comment |
| `push` | `{feature branch}@{commit id}` |
| `in-review` | the ticket key moved to the in-review state |

## Evidence marker grammar

Each evidence comment, and the body of a ticket the bug mode creates, carries the marker as plain text on a line of its own, so tracker search finds it:

```
afk-evidence {work id} {step}
```

`{step}` is the writing script's named step, matching `[a-z][a-z0-9-]*`. The Outside writes entry for the comment is `- evidence: afk-evidence {work id} {step}`.

## State

The check script derives the state from the file; nothing stores it. The first row that matches wins.

| State | Read from |
|---|---|
| In review | an `in-review` entry in Outside writes |
| Shipped | a `change` entry in Outside writes |
| Landed | a `push` entry in Outside writes |
| Approved | Approval filled |
| Sent to a grill | verdict V-2 or V-3 |
| Stopped | verdict V-4 or V-5 |
| Diagnosed | verdict V-1 |

`/afk:fix` reads the two states the file does not hold: Fixed (fix commits on the diagnosis branch, every tier green) and the return from a grill (a "still small" size-call row in the grill's log).
