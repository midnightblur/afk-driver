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
and the three lists, side by side on a wide window. After round 1, a full-width
"What changed" list above them names each element that the round or its answers
changed, a card by its title with a link to it; the engine builds it from the
`changed` lists. The page shows the banner of the current round; the earlier
banners go into "Earlier banners" at the end, closed. Leave `colour` out and the
engine assigns one; each round has its own colour, and every card carries a
chip in the colour of its round.

## Example

```json fragment=banner
{
  "settled": ["The export holds one file per order."],
  "unlocks": ["The file format", "Who may start an export"],
  "parked": ["Archive retention, waits for the data owner"]
}
```
