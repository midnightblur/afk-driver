# Every change request needs proof lines before Ready, in every lane

> Layer: Requirements
> Context ticket: 185

The entry skills own the workflow and are the main path. The ship step of the change request also refuses Ready when a changed user-visible behavior has no proof line, in every lane and for a plain chat request. In the incident the verify step existed as text and was skipped; this check is the one an agent meets after it skips the entry skill, and it costs 1 line per behavior.

## Considered Options

- Entry skills only, with no check at ship. Rejected in i-ship6 after the devil's-advocate pass, because a plain chat request that starts no skill then meets no check.
- A core-behavior instruction line. Rejected by the developer in i-chat3: the trigger descriptions route the request, and an instruction alone already failed once.
