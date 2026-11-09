---
name: sred
description: /afkv2:sred — writes or revises SR&ED (Scientific Research and Experimental Development) technical investigation documents for an audit team, first as Markdown, then as DOCX. Use when the developer asks for SR&ED source material on one or more investigation topics.
disable-model-invocation: true
---

# /afkv2:sred — technical investigation documents

You write technical source material for an audit team. The audit team owns the final tax submission.

## Inputs

The developer gives 1 or more investigation topics. Use these sources when they are available:

- the account of the technical team;
- current and deleted repository files;
- the commit history of each repository that held the work;
- architectural decision records (ADRs), specifications, test records and review records;
- primary public sources for each claim about a technology that still changes.

Give each independent topic its own subagent for the history review. You keep the conversation with the developer and the consistency between the documents.

Keep a source map next to each document, as `<document>.sources.md`. It records the source of each material claim and each research gap. The source map stays out of the technical document, unless the developer asks for it.

For each material claim, tell apart 4 kinds: observed behavior, design analysis, team account and inference. Check each claim that shaped a human decision against the code or the records. If the earlier assessment was incomplete, explain how this changed the next technical direction.

A thesis, observation or causal link without a source is a research gap. Record it in the source map. Ask the developer when the gap changes the narrative. Otherwise, state the limit or omit that iteration.

## Select the investigation core

Include a technical uncertainty only when all 4 conditions are true:

1. At the start, the available knowledge of the team held no proven method.
2. The uncertainty was about whether or how the team could reach the objective.
3. Analysis or experiment changed the technical understanding of the team.
4. The result changed the next technical direction.

A new technology, an immature standard or an unknown system interaction can cause uncertainty. Product novelty and implementation size do not cause uncertainty by themselves.

Exclude routine implementation, common defects, known fixes, ordinary integration, formatting and feature completion. Include a defect only when it shows an unknown mechanism and changes the next thesis. Put small defects under the larger uncertainty that they showed.

## Reconstruct the investigation

Group the work by technical uncertainty, not by commit or ticket. You may change the order of supported events when this makes the reasoning clear. Keep each cause before its effect.

For each iteration, find:

1. the uncertainty or thesis;
2. the implementation, experiment or analysis;
3. the observed feedback;
4. the change in technical understanding;
5. the next direction.

Architectural analysis can reject an option without a runtime experiment. Label it as analysis. A test claim needs a record of the test run.

A success and a failure have the same value when they change the understanding. Put the focus on the progress from one iteration to the next.

## Add technology context

Explain why the technology made the result difficult to predict. Use careful claims about the team, for example `we had no proven method in our environment`.

For a recent technology, or one that still changes, verify each maturity claim against a primary source. Explain the capabilities or practices that were not settled and that affected the work. Make claims only about the knowledge of the team, never about the whole market.

For work with agents, large language models, agent workflows or Model Context Protocol, read [AGENTIC-SYSTEMS.md](AGENTIC-SYSTEMS.md).

## Write

[TECHNICAL-DOCUMENT.md](TECHNICAL-DOCUMENT.md) is the output contract: the structure, the content rules and the exclusions. Write 1 document for each topic, at the path that the developer gives. If the developer gives no path, ask. When the developer gives feedback, revise the existing document in place.

The Markdown file is the source that you edit during the review. After the developer accepts the text, make 1 DOCX file for each topic:

1. Check the 2 tools: `pandoc --version` and `soffice --version`. If a tool is missing, tell the developer which tool to install, and stop before the DOCX step.
2. Convert: `pandoc <document>.md -o <document>.docx`.
3. Render: `soffice --headless --convert-to pdf --outdir <folder> <document>.docx`.
4. Look at each page of the PDF. If a page is wrong, fix the Markdown source and start again at step 2.

## Review

Before you finish, verify each of these conditions:

- Each main iteration addresses a technical uncertainty.
- No iteration only describes a common defect or a routine fix.
- Each feedback section changes the understanding or the next direction.
- You checked each claim that shaped a decision. Each claim that you could not resolve has qualified words.
- Design analysis and runtime experiment stay separate.
- The technology maturity context is factual and qualified.
- The document obeys each rule in `TECHNICAL-DOCUMENT.md`.
- The final position states progress and the remaining uncertainty, not tax eligibility.
- You looked at each page of the DOCX output, and the Word text agrees with the accepted source.
