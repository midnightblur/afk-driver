## Grounding rule — verify claims about existing infra

When the user (or your own draft answer) asserts something about
existing infrastructure — libraries, services, frameworks, datastores,
caches, queues, auth providers, observability stacks, modules, schemas,
build/deploy topology — do **not** accept it into the design. Verify
against the codebase before letting it constrain a downstream decision.
A fictional premise propagates into the SDD, then into ADRs, then into
subtask `## Produces` contracts referencing types that don't exist —
every downstream layer inherits the lie, and no preflight grep can
catch it because the contracts are *internally* consistent with the
fiction.

**Trigger phrases.** When you hear (or are about to write) any of these,
verify before continuing:

- "We use {library/service/framework}" / "we already have {X}"
- "The existing {ClassName/ServiceName/ModuleName}"
- "{X} version {N}.{M} supports {API}" (cross-check `pom.xml` /
  `package.json` / lockfile pin)
- "{X} is configured to {behavior}" (check actual config)
- "Auth is {scheme}" / "we shard by {key}" / "we cache in {store}"
- "There's already a {pattern} for {feature}"

**How to verify, by claim type.**

| Claim about | Verify with |
|---|---|
| Library / dep usage | `ctx_search` `pom.xml`, `build.gradle`, `package.json`, `requirements.txt`. Check the **pinned version**, not just the name. |
| Service / module / class existence | `ctx_search` for the symbol declaration; `ctx_tree` the package. |
| Configuration posture | `ctx_search` `application.yml` / `application.properties` / `*.env*` / framework-specific config files. |
| Schema / table / sharding key | `ctx_search` migration files / changelog / DDL / JPA entity annotations. |
| Existing pattern reuse ("we already use Strategy for X") | `ctx_search` for the named interface / abstract class. |
| Existing behaviour ("the system does X when Y") | Find the code path: `ctx_search` the entry point, read the branch that decides; or run the existing test that pins it. |
| Cross-repo / runtime topology / deploy posture | Often unverifiable from this repo alone — see "external claims" below. |

Run these verifications in `afk-reader` subagents — parallel where the
claims are independent — each returning a cited confirm/refute digest,
per `DELEGATION.md` (plugin root); the grilling session keeps its
context on the interview and acts on the digests.

**How to handle a verification miss.**

1. **Surface the gap explicitly.** Quote what the user said. Quote what
   the search found (or didn't find). No papering over.
2. **Walk the user through three options.** (a) They were mistaken —
   redo the question with the actual posture. (b) They're proposing to
   introduce it as part of this feature — that becomes recorded new
   work (a requirement in a requirements-phase session; an L1/L2/L3
   decision with an ADR in a design-phase session), not a casual
   reference. (c) They confused this service with a different repo /
   module — clarify scope, then verify in the right place.
3. **Re-ask the original question** with the corrected premise. The
   answer changes when the premise changes.

**External claims you cannot verify from this repo** (sibling services
in other repos, multi-region routing, ops-team-owned infra) — say so
plainly: *"I can't verify {claim} from this repo. I'll record it as
'unverified premise: {claim} per user assertion.' Want me to ask for
evidence (link / screenshot / second pair of eyes) or proceed with the
unverified label?"* Letting the user decide whether to chase external
verification is fine; **pretending you verified is not**.

**This rule binds across all 9 layers**, not just L1/L2 where infra
claims are most common — the claim-type table above covers the how; e.g.:

- L1 ("we deploy multi-region") — check ops manifests / Terraform.
- L4 ("we have an idempotency table") — `ctx_search` the schema.
- L6 ("the order saga is implemented via outbox") — verify the
  outbox table + dispatcher.
- L9 ("that service method takes a DTO and handles validation") — read
  the actual signature and its entry path; the seam walk is this rule
  applied per seam.

Verification is cheap (one `ctx_search` / `ctx_read`); a wrong premise
is not. If you find yourself drafting an answer that references
something specific in the codebase, **verify before you write it down**
— this rule applies to your own drafts too, not just the user's
assertions.
