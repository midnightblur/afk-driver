# Agentic systems reference

> **Language:** read `LANGUAGE.md` (plugin root) before using this reference.

## Technology context

Agent software moved beyond code completion into longer sessions that read repositories, call tools, change files, and run checks. The capability changes quickly. Practices for control, context, memory, review, and recovery remain less settled than conventional application practices.

Model Context Protocol is a recent and evolving protocol. Its specification, software development kits, authorization model, transports, result handling, and long-running work support continue to mature. State this context as a source of uncertainty. Do not claim universal industry ignorance.

## Human-facing interface and agent-facing tool

| Human or developer consumer | Agent consumer | Resulting uncertainty |
|---|---|---|
| A developer reads documentation and writes a fixed client. | A model selects a tool at runtime from names, descriptions, and schemas. | Tool boundaries and descriptions affect behaviour. |
| A user interface guides the user through fields and states. | An agent sees structured arguments without the product interface. | Conditional rules need explicit discovery or narrow operations. |
| A human can ask for clarification and interpret an ambiguous error. | An agent needs stable, machine-readable results. | Error meaning must survive every protocol layer. |
| A broad response is available for human inspection. | A broad response consumes context and can distract tool selection. | Results must stay small without removing required state. |
| A developer can hold hidden product knowledge. | An agent knows only loaded context and tool output. | Local rules need timely, maintained context. |
| A fixed client calls a known route. | An agent can compose tools in an unexpected order. | State guards, authorization, repeat safety, and independent checks become necessary. |

## Agentic software development questions

Investigate these questions when they apply:

- How can an agent load hidden repository knowledge only when the task needs it?
- How can the system balance context completeness, token cost, and document freshness?
- Should knowledge live in nested instructions, shared references, retrieval, or an external memory system?
- How can research verify facts before a human uses them to choose a direction?
- How can a human answer design questions quickly and point feedback to an exact decision?
- How can requirement, solution, prototype, and verification work expose different gaps before implementation?
- How can the implementation agent use a plan without losing context or skipping related work?
- Which work can run autonomously, and which decision needs human judgment?
- How can delegation reduce context load while preserving a shared decision record?
- Which quality rules can deterministic gates enforce?
- Which quality rules still require agent or human judgment?
- How does feedback become a durable rule so the same mistake does not recur?
- Where must review decisions live so humans and later agents can audit them?
- How does the system verify completion beyond an agent's own status report?

Use these questions to identify uncertainty. Show how feedback changed the workflow or its controls. Do not turn every agent error into a separate iteration.
