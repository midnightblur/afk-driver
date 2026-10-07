---
name: sred
description: Write or revise SR&ED technical investigation documents for an audit team.
disable-model-invocation: true
---

> **Language:** read `LANGUAGE.md` (plugin root) first — it binds every word this skill produces.

# sred — technical investigation documents

Produce technical source material for an audit team. The final tax submission belongs to the audit team.

## Inputs

Accept one or more investigation topics. Use these sources when available:

- the technical team's account;
- current and deleted repository files;
- commit history across every repository that held the work;
- architectural decision records, specifications, test records, and review records; and
- primary public sources for claims about an evolving technology.

History review is context-heavy: follow `DELEGATION.md` (plugin root) and give each independent topic its own `afk-reader` child. The main agent keeps the user conversation and cross-document consistency.

Keep a source map beside each document as `<document>.sources.md`. It records the source of each material claim and each research gap. It stays out of the technical document unless the user asks.

For each material claim, distinguish observed behaviour, design analysis, team account, and inference. Check claims that shaped a human decision against the available code or records. If the earlier assessment was incomplete, explain how that changed the next technical direction.

A thesis, observation, or causal link without a source is a research gap. Record it in the source map. Ask the user when the gap changes the narrative. Otherwise, state the limitation or omit that iteration.

## Select the investigation core

Include a technical uncertainty only when all conditions apply:

1. The team had no proven method in its available knowledge at the start.
2. The uncertainty concerned whether or how the objective could be achieved.
3. Analysis or experiment changed the team's technical understanding.
4. The result affected the next technical direction.

A new technology, an immature standard, or an unknown system interaction can create uncertainty. Product novelty and implementation size do not create uncertainty by themselves.

Exclude routine implementation, common defects, known fixes, ordinary integration, formatting, and feature completion. A defect belongs only when it reveals an unknown mechanism and changes the next hypothesis. Group small defects under the larger uncertainty they exposed.

## Reconstruct the investigation

Group work by technical uncertainty, not by commit or ticket. Reorder supported events when this makes the reasoning clear. Preserve cause and effect.

For each iteration, establish:

1. the uncertainty or thesis;
2. the implementation, experiment, or analysis;
3. the observed feedback;
4. the change in technical understanding; and
5. the next direction.

Architectural analysis can reject an option without a runtime experiment. Label it as analysis. A test claim needs a record of the test run.

Success and failure have equal value when they change understanding. Focus on the progression between iterations.

## Add technology context

Explain why the technology space made prediction difficult. Use careful internal claims, such as `we had no proven method in our environment`.

For a recent or evolving technology, verify maturity claims from primary sources. Explain unsettled capabilities or practices that affected the work. Limit claims to the team's knowledge, never to the whole market.

For work involving agents, large language models, agent workflows, or Model Context Protocol, read [AGENTIC-SYSTEMS.md](AGENTIC-SYSTEMS.md).

## Write

[TECHNICAL-DOCUMENT.md](TECHNICAL-DOCUMENT.md) is the output contract: structure, content rules, and exclusions. Write one document per topic, at the path the user names; ask when the user names none. Revise an existing document in place when the user supplies feedback.

Markdown stays the editable source during review. After the user accepts the writing, create one DOCX per topic:

1. Convert: `pandoc <document>.md -o <document>.docx` (`MANIFEST.md · C13`).
2. Render: `soffice --headless --convert-to pdf --outdir <dir> <document>.docx` (`MANIFEST.md · C14`).
3. Inspect every page of the PDF. Fix the Markdown source and repeat from step 1 until every page is correct.

A probe miss on either row stops delivery. Route the user to `/afk:setup`.

## Review

Before completion, verify these conditions:

- Every main iteration addresses a technical uncertainty.
- No iteration exists only to describe a common defect or routine fix.
- Every feedback section changes the understanding or next direction.
- Claims that shaped decisions were checked; unresolved claims have qualified wording.
- Design analysis and runtime experiment remain distinct.
- Technology-maturity context is factual and qualified.
- The document passes every rule in `TECHNICAL-DOCUMENT.md`.
- The final position states progress and remaining uncertainty, not tax eligibility.
- Every DOCX page was inspected, and the Word text matches the accepted source.

When user feedback exposes a gap in this skill's method, follow `${AFK_PLUGIN_ROOT}/skills/afk/lessons/CAPTURE.md`. Topic facts stay in the topic documents.
