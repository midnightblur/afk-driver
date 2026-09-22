# Technical document contract

> **Language:** read `LANGUAGE.md` (plugin root) before writing the document.

One technical investigation document per topic.

## Required structure

```markdown
# <Topic>: technical investigation

## Technology context
<Why the technology or application space made prediction difficult.>

## Technical objective
<Capability sought and constraints that could not be traded away.>

## Starting capability and knowledge
<What the team could do and what remained unknown.>

## Technical uncertainties
<The connected questions that required analysis or experiment.>

## Investigation sequence

### Iteration <n>: <uncertainty or approach>

#### Thesis
<What the team expected and why.>

#### Work performed
<Implementation, runtime experiment, or design analysis. Name the type accurately.>

#### Observed feedback
<What the team learned. Include an unexpected result when it changed the direction.>

#### Change to the next direction
<What changed in the model, design, or next hypothesis.>

## How the investigation changed the design
| Earlier model | Feedback | Revised direction |
|---|---|---|

## Technical understanding gained
<Knowledge gained from the linked iterations.>

## Remaining uncertainties
<Questions that the work did not resolve.>

## Current technical position
<Present direction and its limits. Do not frame completion as proof.>
```

## Content rules

- Write for a non-specialist audit team. Keep enough detail to show why each result changed the next direction.
- Explain why known methods did not determine the answer.
- State only precise details that explain the uncertainty or feedback.
- Qualify results with the tested or analysed scope.
- Omit an iteration when its thesis, feedback, or causal link is unsupported.
- Keep routine development out of the investigation narrative.

## Exclusions

The document contains none of these unless the user asks:

- tax-program education or eligibility conclusions;
- claim-form sections or filing instructions;
- research-method narration or document-production notes;
- citations, evidence appendices, evidence tables, commit hashes, or repository history;
- business, cost, time, or claimant placeholders;
- volatile dates, version numbers, or counts that do not explain an uncertainty; or
- statements that bind the document to a writing standard.
