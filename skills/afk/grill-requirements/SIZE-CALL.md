> **Language:** read `LANGUAGE.md` (plugin root) before writing a size-call row or a round.

# Size call (G-1)

The size call is the last decision of a grill handed a `DIAGNOSIS.md`: is the bug still small enough for one fix, or does it need the full chain? This file is its one home.

## Taking a diagnosis

- The diagnosis is the grill's input in place of a raw idea or a PRD. Read it per `${AFK_PLUGIN_ROOT}/skills/utils/diagnose/DIAGNOSIS-FORMAT.md`; its Symptom, Spec comparison, Root cause and Fix proposal are settled premises that keep their certainty marks.
- Grill only the open question the verdict names: which fix option for several fixes, what the spec should say for a spec gap. Walk only the layers or branches that question touches; rounds follow `ROUND.md` as usual.
- Write in the grill's own section of the `GRILL-LOG.md` beside the diagnosis (`GRILL-LOG-FORMAT.md`).

## The call

Once the open question is settled, make the call and present it in the final round with your recommendation:

| Call | When |
|---|---|
| still small | the settled answer is one change to existing behaviour that one fix run makes test-first: no new requirement past the settled answer, no new or changed public contract, no persisted-data change, no decision that needs a design record |
| too big | anything else |

Once the call is accepted, write one size-call row (`GRILL-LOG-FORMAT.md` "Size-call row"):

- **still small** → the grill ends; the bug goes back to `/afk:fix` with the diagnosis path.
- **too big** → the bug goes into the full chain, which starts at `/afk:grill-requirements`.
