# GLOSSARY.md Format

## Structure

```md
# {Service Name}

{One or two sentence description of what this service is and why it exists.}

## Language

**Order**:
{A one or two sentence description of the term}
_Avoid_: Purchase, transaction

**Invoice**:
A request for payment sent to a customer after delivery.
_Avoid_: Bill, payment request

**Customer**:
A person or organization that places orders.
_Avoid_: Client, buyer, account
```

## Rules

- **Be opinionated.** When multiple words exist for the same concept, pick the best one and list the others under `_Avoid_`.
- **Keep definitions tight.** One or two sentences max. Define what it IS, not what it does.
- **Only include terms specific to this service's context.** General programming concepts (timeouts, error types, utility patterns) don't belong even if the service uses them extensively. Before adding a term, ask: is this a concept unique to this context, or a general programming concept? Only the former belongs.
- **Group terms under subheadings** when natural clusters emerge. If all terms belong to a single cohesive area, a flat list is fine.
- **One owner per term.** A term shared across services is defined once — in the service that owns it, or in the root `GLOSSARY.md` if it is genuinely system-wide. Other services reference it via the map's Relationships section rather than redefining it. Never let the same term carry two definitions.

## Multi-context layout

This repo is always multi-context. A `GLOSSARY-MAP.md` at the root indexes the
per-service glossaries and records how the services relate:

```md
# Glossary Map

## Glossaries

- [Payable](./11700-payable/GLOSSARY.md) — owns posting runs and payable invoices
- [SAP Posting Bot](./11024-sap-posting-bot/GLOSSARY.md) — pushes posting runs to SAP
- [SAP Sync Bot](./11022-sap-sync-bot/GLOSSARY.md) — reconciles SAP master data

## Relationships

- **Payable → SAP Posting Bot**: SAP Posting Bot references Payable's `PostingRun`; it does not redefine it
- **SAP Sync Bot ↔ Payable**: shared system-wide terms `CompanyCode`, `Money` live in the root `GLOSSARY.md`
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
