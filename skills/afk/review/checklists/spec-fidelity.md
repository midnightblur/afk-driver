# spec-fidelity — is it truly done?

Default `class: spec`.

Walk every `## Acceptance` bullet and find the diff line(s) that satisfy it; an unsatisfied or partially-satisfied bullet is a finding (severity by how load-bearing). In cited mode, every SDD §9b seam this subtask `implement:`s must be present and assert on the framework's real output. Every `## Produces` `{grep-anchor}` must resolve in the diff. Flag silent scope-shrink: an acceptance bullet "handled" by a stub, a `TODO`, or a swallowed branch is **not** done. Any acceptance bullet tracing to an **accepted staple** (`{service}/STAPLES.md`) gets the scrutiny its registry **Obligation** demands: a matching staple silently dropped, stubbed, or half-enforced against that Obligation is a finding, class `spec`.
