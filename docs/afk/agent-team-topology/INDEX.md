# agent-team-topology — start here

A run today is one agent on one model, so work that needs independent thinking gets a single opinion nobody can check, a single provider's usage limit can halt it, and nothing records what the run started — a failed run can leave processes alive on the machine. This feature lets a run optionally use a team of agents, shaped by a pattern that says which roles exist, which model fills each, how long each lives and which roles may talk directly. One contact agent is the only one the person talks to and the only one that starts and stops the others; everything started is written to a manifest so cleanup can kill it; and roles may run on models from different providers, so one provider's limit moves work rather than stopping it. Patterns are reusable team shapes that the contact agent proposes and may combine; five ship with the plugin, including a lighter one for bug fixes. Every pattern keeps duties apart, has work checked independently, looks at a problem from several angles and runs without the person wherever it can. A role's result goes to the agent the pattern names, by default the one that asked, and the contact agent keeps only a copy of each message that says an agent finished, parked or exited, for its records. Every pattern that starts agents carries a charter, a pattern part and one part per role, which each agent reads before its brief, is given again when it resumes, and is pointed back at after a compaction where the tool reports one; each role reports progress to its report target, which may send it answers and data back, never a new duty. Team topology and multi-model are independent switches. Turning both off does not turn off pane agents: a run behaves as before only when one more key switches role agents back to subagents, or when no multiplexer is found. A session without the plugin enabled is unchanged. Wherever the plugin is enabled and a multiplexer is found, every agent that writes work or returns a verdict runs in its own visible pane, in tabs apart from the contact agent, named for its goal, role, model and effort. Each agent closes when its job ends, and one that dies is resumed before it is replaced. Plain subagents are only helpers those agents start for themselves.

## Artifacts

| Artifact | Where | State |
|---|---|---|
| PRD | PRD.md | draft |
| Requirement ADRs | adr/requirements/ | 20 records (0002 superseded by 0018, 0003 by 0010; 0010, 0012 and 0014 in part by 0020) |
| Prototype | PROTOTYPE.md | — |
| SDD | SDD.md | draft |
| Design ADRs | adr/design/ | 16 records |
| Design brief | DESIGN-BRIEF.md | — |
| Verification plan | VERIFICATION-PLAN.md | — |
| Plan | plan/PLAN.md | — |
| Smoke gate | plan/PLAN.md | — |
| Understanding | understanding/index.html | — |
| Design review plan | DESIGN-REVIEW-PLAN.md | — |
| Demo plan | DEMO-PLAN.md | — |

## Reading order

1. This file.
2. DESIGN-BRIEF.md if present — the 1–2 page digest; else PRD.md's Problem Statement + User Stories.
3. SDD.md §0 (locked vs free) + §1 (why this design) — full document only if implementing or reviewing design.
4. plan/PLAN.md — solution map + live progress tracker.
5. plan/JOURNAL.md (tail) — what happened lately, in order.
6. plan/review/INDEX.md — what the quality gates found.
7. understanding/index.html — the interactive explainer of what was actually built, once generated.
8. Later: plan/TRACE.md (which commit satisfied which criterion), adr/ (why it's shaped this way).
