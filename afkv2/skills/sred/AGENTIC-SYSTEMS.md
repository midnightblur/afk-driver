# Agentic systems reference

## Technology context

Agent software now does more than code completion. Agents run long sessions: they read repositories, call tools, change files and run checks. This capability changes quickly. Practices for control, context, memory, review and recovery are less settled than the practices for conventional applications.

Model Context Protocol is a recent protocol that still changes. Its specification, its software development kits, its authorization model, its transports, its result handling and its support for long-running work are not mature yet. State this context as a source of uncertainty. Do not claim that the whole industry did not know.

## Human-facing interface and agent-facing tool

| Human or developer consumer | Agent consumer | Resulting uncertainty |
|---|---|---|
| A developer reads documentation and writes a fixed client. | A model selects a tool at runtime from names, descriptions and schemas. | Tool boundaries and descriptions change the behavior. |
| A user interface guides the user through fields and states. | An agent sees structured arguments, without the product interface. | Conditional rules need explicit discovery or narrow operations. |
| A human can ask a question and interpret an unclear error. | An agent needs stable results that a machine can read. | The meaning of an error must stay the same through each protocol layer. |
| A human can inspect a large response. | A large response uses context and can distract tool selection. | Results must stay small and keep each necessary state. |
| A developer can know product facts that are not written down. | An agent knows only the loaded context and the tool output. | Local rules need context that arrives in time and stays current. |
| A fixed client calls a known route. | An agent can use tools in an unexpected order. | State guards, authorization, safe repeats and independent checks become necessary. |

## Agentic software development questions

Investigate these questions when they apply:

- How can an agent load repository facts that are not written down, only when the task needs them?
- How can the system balance complete context, token cost and current documents?
- Must facts live in nested instruction files, shared references, retrieval or an external memory system?
- How can research verify facts before a human uses them to select a direction?
- How can a human answer design questions quickly and point feedback to one exact decision?
- How can requirement, solution, prototype and verification work each show different gaps before implementation?
- How can the implementation agent use a plan, and not lose context or skip related work?
- Which work can run autonomously, and which decision needs human judgment?
- How can delegation decrease the context load and keep one shared decision record?
- Which quality rules can deterministic gates enforce?
- Which quality rules still need agent or human judgment?
- How does feedback become a durable rule, so the same mistake does not occur again?
- Where must review decisions live, so that humans and later agents can audit them?
- How does the system verify completion with more than the status report of the agent?

Use these questions to find uncertainty. Show how feedback changed the workflow or its controls. Do not make each agent error into a separate iteration.
