# Round banner

## Holds

The round number, the round colour, what settled in the round before, what the
settled points unlock, and the parked items. Fields: `rounds[].n`,
`rounds[].colour` and `rounds[].banner` with three lists of text: `settled`,
`unlocks`, `parked`.

## Use it when

Every round has one. Write its banner when you open the round: `settled` lists
what the last round settled, `unlocks` what this round can now ask, `parked`
what waits for a later round or a human outside the session. An empty list is
correct for round 1.

## How it looks

A band across the top of the page in the round colour, with the round number
and the three lists. Leave `colour` out and the engine assigns one; each round
has its own colour, and a round chip in that colour marks every item that needs
the human in that round.

## Example

```json fragment=banner
{
  "settled": ["The export holds one file per order."],
  "unlocks": ["The file format", "Who may start an export"],
  "parked": ["Archive retention, waits for the data owner"]
}
```
