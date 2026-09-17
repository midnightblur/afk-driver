# Same-provider participant runs as a native subagent

> Status: Accepted
> Audited: 2026-09-11
> Layer: Requirements
> Context ticket: research-enhancement

When the participant's provider is the host harness, the participant is a native subagent: no subprocess and no billing gate. The participant remains subject to staged evidence and explicit `allowed_paths` grants. `claude -p` is used only when another host calls Claude, and Codex is likewise called headless only from a non-Codex host. The tension between Anthropic's developer-key guidance and its subscription-use statement for `claude -p` is an accepted policy risk (PRD Further Notes). The risk record names the verified sentence from support.claude.com article 13189465: "If you're building a product, application, or tool for others, use API key authentication through Claude Console or a supported cloud provider." The plugin is a tool, and the route runs it under the user's own login. Source: `MERGED-PLAN.md` §1 A9 (:31), §6 D-3 (:121), D-6 (:124-126). Recorded, audited conditions of that risk (user decision A, 2026-09-15): (a) only the unmodified `claude` binary under the user's own login, never an extracted token; (b) `ANTHROPIC_API_KEY` stripped from the child environment, never `--bare`; (c) the `subscription_only` route requires a declared `usage_credits: disabled` or it blocks; (d) the cross-provider `claude -p` route is opt-in and off by default, behind one config switch so that decision B (written Anthropic guidance required before enabling) would change one key only.

Change note (2026-09-15): amended after ADR-AUDIT.md and the user's #5 decision (A with 4 conditions); the conditions record the accepted policy risk and leave the decision unchanged.
