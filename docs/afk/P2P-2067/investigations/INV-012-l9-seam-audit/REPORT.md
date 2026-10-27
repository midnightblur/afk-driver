# INV-012 — L9 seam and compatibility audit

Verdict: closed-with-frontier. The design resolves every inspected compatibility finding. B14 live-provider and deployment behavior remains a mandatory verification frontier.

## Q1 — What each seam is now

The Existing contract column records the current contract for every inspected seam. Each row cites the source or earlier investigation that established that contract.

## Q2 — What reaches each seam

The Impacted flows column records the direct and indirect callers that pass through each seam. The audit includes configuration, workflow skills, forge operations, parsers, repository access, prompting, adoption, and packaging.

## Q3 — What a change affects

The Planned change, Conventions and landmines, and Verdict columns record the required change and its compatibility impact. The compatibility findings below resolve or explicitly accept every identified impact.

## Locked seam rows

| Seam | Existing contract | Planned change | Impacted flows | Conventions and landmines | Verdict |
|---|---|---|---|---|---|
| AFK configuration | `scripts/afk-config.py` is the only reader; schema 1 rejects unknown keys and layered `load()` includes machine, shared, local, and explicit overlays (`scripts/afk-config.py:1-30,53-59,108-130,332-397,575-637`). | Add an optional manifest pointer and a committed-at-ref read path. | Config docs, views, setup, and focused tests (`scripts/afk-config.py:768-796,1231-1338`; `scripts/tests/test_afk_config.py:119-137,282-310`). | Ordinary effective config is unsafe for AC-035 target-branch controls. Old AFK versions reject the new key. | reworked |
| Requirements and glossary skills | Requirements writes verified terms immediately and commits glossary-only changes; glossary is a vocabulary-only approve-before-write steward (`skills/afk/grill-requirements/SKILL.md:16-34,76-104`; `skills/utils/glossary/SKILL.md:14-24,38-73`). | Call the facade while preserving immediate human verification, caller-owned commits, and vocabulary-only interaction. | Requirements, to-PRD, lessons, and execute. | Consultation must follow the glossary commit; the engine never commits or pushes. | reworked |
| Preflight | Persisted steps end in direct `change-ready`; green rows resume without rerun (`skills/afk/preflight/SKILL.md:34-54,190-238`). | Reconcile before validation, review, and CI; run a read-only Ready gate immediately before `change-ready`. | Manual preflight, autopilot, PLAN and mission-control row readers. | A glossary write after a green row invalidates that proof; glossary parking must not consume the mechanical-fix budget. | extends |
| Settlement | Review ledger closure owns settlement and the skill states it never changes Draft status (`skills/utils/settle-change/SKILL.md:32-56,82-117`). | Add a final glossary settlement gate and permit the named owner-rejection path to return Draft. | Settle-change, settle-mr alias, review-only re-entry, manual settlement. | Preserve review closure and gate the final pushed remote head. | reworked |
| Other glossary consumers | Execute, grill-solution, to-SDD, review, TDD, diagnose, and to-PRD read root, nearest, or direct glossary files through different paths. | Route lifecycle consultation and audit through the facade; plain reads use selected paths returned by it. | Design through settlement. | Updating only four named skills leaves bypasses and divergent vocabulary scope. | reworked |
| Forge registry | Each forge kind declares and documents verbs; the checker validates each kind but not cross-kind parity (`ADAPTERS.md:3-25`; `hooks/lib/adapter_registry_check.py:45-117`). | Add generic `change-approvals` and `change-draft` to GitLab, GitHub, and none plus parity tests. | Every forge-family caller; existing verbs stay unchanged. | All manifests, contracts, scripts, tests, and conformance records move together. | extends |
| Approval read | No approval-read verb exists; current state and Ready operations do not return approval evidence (`adapters/forge/gitlab/forge.sh:350-415`; `adapters/forge/github/forge.sh:361-418`). | Return current head SHA and effective approvals bound to an applicable SHA; stale, dismissed, or unprovable approvals fail closed. | Finalization, owner-chain validation, preflight, settlement, bootstrap. | Actor-only approval lists can count stale approval after a push. | reworked |
| Return to Draft | `change-ready` has no inverse and trusts an optimistic provider result. | Add idempotent `change-draft` with provider read-back; already-Draft is success. | Owner rejection and safety recovery. | Preserve existing Ready behavior and never trust CLI exit alone. | extends |
| Comment transport | `note-list` returns complete oldest-first plain notes with edit evidence; `change-comment` posts plain comments (`ADAPTERS.md:76-85,103-110`). | Use a separate glossary namespace and reconcile uncertain writes by operation ID. | Glossary publication only; review ledger stays separate. | Windows JSON travels through stdin or environment; preserve UTF-8. | fits |
| Append-only reconstruction | Existing replay detects edits and interior gaps, but deleting the newest record and checkpoint restores an older valid prefix (INV-009). | Add a separate strict glossary codec and reducer. | RE-06 through RE-08. | Comment history alone cannot prove deletion of its entire newest suffix. | reworked |
| Glossary Markdown | Current grammar has no stable ID, owner-state, or replacement fields; several consumers parse metadata differently (`skills/utils/glossary/GLOSSARY-FORMAT.md:29-73`; `scripts/lavish/inject.py:77-115`). | Add lifecycle metadata while keeping definitions beside owners and locations in RE-02. | Glossary skill, requirements, Lavish tooltips, strict validation. | Every parser must strip metadata consistently; current parenthetical alias handling can overwrite canonical terms. | reworked |
| Routing | Root `GLOSSARY-MAP.md` currently maps glossary ownership. | Team manifest maps changed paths and domain areas to glossary targets and owner chains. | LC-01, LC-02, bootstrap, glossary, requirements. | Team targets must resolve to map ownership; the two route sets need distinct authority. | extends |
| Git and local evidence | Git common-dir and worktree ownership helpers exist, but no complete repository or evidence adapter exists. | Add pinned-ref repository access and atomic common-dir evidence with fail-closed expiry. | Every LC command and linked worktree. | Handle linked worktrees, NUL paths, unverifiable refs, unknown session ownership, and absolute common-dir resolution. | extends |
| Semantic provider | Existing bounded scanner includes untracked files and returns paths, not ranked snippets (`hooks/lib/bounded_scan.py:193-215`). | Add tracked-text-only ranked candidates with accepted bounds. | LC-02, LC-03, RE-03, RE-04. | Provider failure is an error, not an empty result. | extends |
| RE-07 prompt | Existing Lavish components allow the wrong tokens or free text (`LAVISH-KIT.md`; `scripts/lavish/components.py:466-490,604-634`). | Add a dedicated strict-choice component that accepts only final or reject and has no note field. | Lavish schema, renderer, runtime, tests, owner decision, driven-mode parking. | Markdown fallback cannot count; driven mode parks before render. | extends |
| Bootstrap and adoption | Glossary skills lazily create missing files inside normal work. | Separate bootstrap merge request and explicit migration for repositories with partial legacy state. | Glossary, requirements, LC-01, approvals, setup. | Feature-branch controls cannot authorize their own adoption. | reworked |
| Packaging | Both manifests already register the caller skills; shared scripts need no skill entry. | Add shared scripts and update existing skill prose. | Native plugin tree and changelog. | A new skill would require both manifests and catalogs, but no new skill is designed. | fits |

## Compatibility findings

1. Accepted limitation: comment history cannot detect deletion of its complete newest suffix. The ledger fails on detectable edits and interior gaps; an audit-event store would be required to close this proof gap.
2. Resolved: approval evidence binds the effective approval to the current head SHA and provider evidence identifier or fails closed.
3. Resolved: target-branch controls use committed-at-ref reads, not ordinary layered effective configuration.
4. Resolved: preflight reconciles before validation, review, and CI, then runs a read-only gate immediately before Ready.
5. Resolved: settlement permits only the named owner-rejection path to return the change to Draft.
6. Resolved: required `ID` and optional `Replaces` live on the definition metadata line; every parser migrates together.
7. Resolved by prerequisite: partial legacy glossary state requires a separate adoption change before lifecycle controls apply.
8. Resolved: a strict Lavish control accepts only `final` or `reject`; Markdown fallback is not owner evidence.
9. Resolved: a new tracked-text-only provider returns ranked bounded snippets; the existing scanner remains unchanged.
10. Resolved: absent manifest preserves vocabulary-only behavior; lifecycle gates require a compatible committed target-branch pointer.

## Boundary and frontier record

- B1-B5, B8, and B12-B13 are closed for the inspected seams. Applicable UI and packaging boundaries are also closed.
- B6-B7 and B9-B11 are not applicable except for generated Lavish HTML and expiry invocation, which are called out above.
- B14 remains an acknowledged external frontier for live GitLab/GitHub approval and Draft behavior, semantic-provider behavior, live strict-choice prompting, and external repository deployment order. Mandatory contract, conformance, and end-to-end tests must pass before shipment.
