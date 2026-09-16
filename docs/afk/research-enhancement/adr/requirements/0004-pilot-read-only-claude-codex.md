# Pilot scope: read-only roles, Claude and Codex, resumable jobs

> Status: Accepted
> Audited: 2026-09-11
> Layer: Requirements
> Context ticket: research-enhancement

The pilot dispatches only read-only jobs to Claude Code and Codex CLI. Gemini CLI is excluded while billing is subscription-only; Antigravity and Grok wait for a recorded live conformance probe (PRD catalog C3). Unfinished read-only jobs resume on another host from `state.json` (AC-028); executor and write-role hops are out of scope and recorded as an IOU on that file. Source: `MERGED-PLAN.md` §1 A13 (:35), §2 D3 (:50), §3 step 5 (:79), §6 D-4 (:122).

Change note (2026-09-15): amended after ADR-AUDIT.md; the edit removes text the plan never decided and leaves the user's decision unchanged.
