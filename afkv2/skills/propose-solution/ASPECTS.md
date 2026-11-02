# Critical aspects

Ask these before the draft, in this order. The build refuses any other order. `design_round.py` reads this table, so the table is the one copy of the order.

| # | Key | Aspect | Ask | Picture of the current state |
|---|-----|--------|-----|------------------------------|
| 1 | `entities` | Entities | Which things does the feature store or change? | `table` of the current entities and fields |
| 2 | `relations` | Relations | How do those things link, in which number, and which side owns the link? | `graph` of the entities and their links |
| 3 | `keys` | Keys | What identifies each thing? Which foreign keys and unique keys exist? | `table` of the current keys |
| 4 | `constraints` | Constraints | Which rules must the data never break, and where is each rule enforced? | `table` of the current constraints, with sample rows |
| 5 | `cascade` | Cascade | What happens to linked data on a delete or an orphan? | `graph` or `table` of what a delete reaches today |
| 6 | `api` | API contract and compatibility | Which callable surfaces change, and do existing callers keep working? | `sequence` of today's call, or `table` of the current surfaces |
| 7 | `migration` | Data migration | What happens to the rows that exist, and can the change go back? | `table` of the existing rows, with sample data |
| 8 | `authorization` | Authorization | Who may do each action, who may not, and where is the guard? | `table` of surfaces and roles today |
| 9 | `lifecycle` | Entity life cycle and states | Which states exist, which moves are legal, and who may trigger each? | `graph` of the current states, or `run-strip` of today's run |
| 10 | `other-teams` | Other teams' modules | Which modules outside the ownership config does this touch? | `graph` of the code area, with the owner of each module |
| 11 | `large-data` | Large data | Which tables or lists can grow large, and what does each read or write cost? | `table` of the current sizes |

## How to ask

- Read the code first, and show what you found. Each aspect gets at least one card. The picture is the card's body root, and the question is in its `children`: the human reacts to the picture.
- Mark what the question would change with chips (`kept`, `removed`, `new`, `proposed`). The guide's section "Picture before a critical-aspect question" says which picture fits.
- Use a `confirm` card when your reading is safe by default. Use a fork when 2 or more live options remain.
- An aspect the feature does not touch gets a `confirm` card that says so, with a picture of what you checked. Silence never skips an aspect.
- One round may hold several aspects, in this order. An aspect that depends on an open answer waits for the next round, or says "holds if <id> = <option>".
- A question outside this list is an ordinary card with no `aspect` field.
