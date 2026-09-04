# GLOSSARY.md Format

## Structure

```md
# {Service Name}

{One or two sentence description of what this service is and why it exists.}

## Language

**Order**:
A customer's request to buy goods — the commitment that reserves stock and, once
confirmed, becomes the basis for an Invoice; distinct from a quote, which reserves nothing.
`Code:` `OrderService.place` · `Related:` Invoice, Customer · `Avoid:` purchase, transaction

**Invoice**:
A request for payment owed after delivery, carrying the amount, due date, and the Order
it settles; it can only be issued once the Order ships, and going unpaid past its due
date is what flips a Customer to delinquent.
`Code:` `Invoice` (entity) · `Related:` Order, Customer · `Avoid:` bill, payment request

**Customer**:
A person or organization that places Orders and owes against Invoices; delinquency (an
overdue Invoice) blocks new Orders until cleared.
`Code:` `Customer` (entity) · `Related:` Order, Invoice · `Avoid:` client, buyer, account
```

## Rules

- **Be opinionated.** When multiple words exist for one concept, pick the best and list the others under `_Avoid_`.
- **Answer like a Product Owner would.** A definition states the term's business meaning, behavior, constraints, nature, workflow, and implications — with a touch of code-level insight (senior-developer voice for technical terms). Correct-but-shallow fails the bar; depth is worth the tokens.
- **Three sentences max, every word earning its place.** Cut filler ruthlessly. Do **not** relist enum values the code already shows — explain what distinguishes the variants and what they imply instead.
- **Carry the optional metadata line** where it helps a future agent: `Code:` one anchor (file path or class) for lazy exploration, `Related:` sibling terms, `_Avoid_:`/aka synonyms seen in code, UI, or legacy naming. Cross-reference other glossary terms freely inside a definition.
- **Declare a legitimate shorter spelling under `_Also_:`** (comma-separated; a parenthetical may say why). Prose often writes a term's distinctive part and lets the sentence carry the rest — `one-live-fixer` inside a list of invariants — and that is correct usage, not drift. `_Also_:` is the opposite of `_Avoid_:`: one records what readers *do* write, the other what they should not. Both matter to the plugin's own term-usage check (`scripts/glossary_usage.py`), which accepts an `_Also_:` spelling as a consumer and never accepts an `_Avoid_:` one.
- **Only terms specific to this service's context.** General programming concepts (timeouts, error types, utility patterns) don't belong even if the service uses them extensively. Before adding, ask: unique to this context, or general programming concept? Only the former belongs.
- **Group terms under subheadings** when natural clusters emerge. All terms in one cohesive area → flat list is fine.
- **One owner per term.** A term shared across services is defined once — in the service that owns it, or in root `GLOSSARY.md` if genuinely system-wide. Other services reference it via the map's Relationships section rather than redefining. Never let the same term carry two definitions.

## Multi-context layout

Always multi-context. A root `GLOSSARY-MAP.md` indexes the
per-service glossaries and records how services relate:

```md
# Glossary Map

## Glossaries

- [Billing](./10001-billing/GLOSSARY.md) — owns billing runs and invoices (hypothetical)
- [Export Bot](./10002-export-bot/GLOSSARY.md) — pushes billing runs to the ERP (hypothetical)

## Relationships

- **Billing → Export Bot**: Export Bot references Billing's `BillingRun`; it does not redefine it
- **Export Bot ↔ Billing**: shared system-wide terms `CompanyCode`, `Money` live in the root `GLOSSARY.md`
```

The layout:

- **Root `GLOSSARY-MAP.md`** — mandatory. The single entry point; read it first.
- **Root `GLOSSARY.md`** — optional. System-wide / shared terms only.
- **`{service}/GLOSSARY.md`** — terms owned by that service. Exactly one per
  service, exactly one level below the root, never nested deeper.

How to use it:

- Read `GLOSSARY-MAP.md` first; it routes you to the right service glossary.
- Route by the **known target service** (from the ticket / spec path), not by
  guessing from the topic. Only infer or ask when the target is ambiguous or the
  work spans several services.
- When you create or locate a service `GLOSSARY.md`, ensure its row exists in
  `GLOSSARY-MAP.md` — an unlisted glossary is invisible to the next session.
