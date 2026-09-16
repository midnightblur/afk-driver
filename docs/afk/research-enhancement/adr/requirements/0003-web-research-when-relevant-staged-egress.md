# Web research: relevance-gated, sanitized, staged evidence, single-provider advisory

> Status: Accepted
> Audited: 2026-09-11
> Layer: Requirements
> Context ticket: research-enhancement

Public web research runs at `research.public: when_relevant` by default: only for a question an authorized local tool cannot settle, with queries rejected when they carry internal terms, ticket ids, code or customer identifiers (PRD AC-007, AC-008). Participants see staged, approved evidence in a scratch directory; whole-repository access needs an explicit `allowed_paths` grant (AC-030, AC-031). A consultation with exactly one healthy participant runs advisory under `unavailable: single` and is refused under `unavailable: block`, the mode for high-impact routes (AC-019). Source: `MERGED-PLAN.md` §6 D-3.
