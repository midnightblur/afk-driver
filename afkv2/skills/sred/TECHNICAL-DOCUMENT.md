# Technical document contract

Write 1 technical investigation document for each topic.

## Required structure

```markdown
# <Topic>: technical investigation

## Technology context
<Why the technology or the application made the result difficult to predict.>

## Technical objective
<The capability that the team wanted, and the constraints that the team could not give up.>

## Starting capability and knowledge
<What the team could do, and what the team did not know.>

## Technical uncertainties
<The connected questions that needed analysis or experiment.>

## Investigation sequence

### Iteration <n>: <uncertainty or approach>

#### Thesis
<What the team expected, and why.>

#### Work performed
<Implementation, runtime experiment or design analysis. Name the correct type.>

#### Observed feedback
<What the team learned. Include an unexpected result when it changed the direction.>

#### Change to the next direction
<What changed in the model, the design or the next thesis.>

## How the investigation changed the design
| Earlier model | Feedback | Revised direction |
|---|---|---|

## Technical understanding gained
<The knowledge that the linked iterations gave.>

## Remaining uncertainties
<The questions that the work did not resolve.>

## Current technical position
<The present direction and its limits. Do not show completion as proof.>
```

## Content rules

- Write for an audit team that has no specialist knowledge. Give enough detail to show why each result changed the next direction.
- Explain why known methods did not give the answer.
- Give a precise detail only when it explains the uncertainty or the feedback.
- Qualify each result with the scope that the team tested or analyzed.
- Omit an iteration when its thesis, its feedback or its causal link has no support.
- Keep routine development out of the investigation narrative.

## Exclusions

The document contains none of these items, unless the developer asks:

- education about the tax program, or eligibility conclusions;
- claim-form sections or filing instructions;
- narration of the research method, or notes about how the document was made;
- citations, evidence appendices, evidence tables, commit hashes or repository history;
- placeholders for business, cost, time or claimant data;
- dates, version numbers or counts that change and do not explain an uncertainty;
- statements that bind the document to a writing standard.
