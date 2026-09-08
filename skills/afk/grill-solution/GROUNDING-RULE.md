## Grounding rule — verify claims about existing infra

When the user (or your own draft answer) asserts something about
existing infrastructure — libraries, services, frameworks, datastores,
caches, queues, auth providers, observability stacks, modules, schemas,
build/deploy topology — do **not** accept it into the design. Verify
against the codebase before letting it constrain a downstream decision.
A fictional premise propagates into the SDD, then ADRs, then
subtask `## Produces` contracts referencing types that don't exist —
every downstream layer inherits the lie, and no preflight grep
catches it because the contracts are *internally* consistent with the
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

**How to verify.** One `/afk:investigate` run per claim, `--design-phase`,
its question type read off the claim by
`${AFK_PLUGIN_ROOT}/INVESTIGATION.md` § "Question types" — with one addition
that file does not carry:

| Claim about | Question type |
|---|---|
| Cross-repo / runtime topology / deploy posture | Q5 — usually answered `frontier`; see "external claims" below |

Pass what you know as `--alias FORM=VALUE` and as declared paths, and let the
run close the boundaries. The completion contract is
`${AFK_PLUGIN_ROOT}/INVESTIGATION.md`; a run whose verdict is `partial`
has not verified the claim.

Spawn the runs in the background — parallel where the claims are
independent — per `DELEGATION.md` (plugin root; its think-time overlap
rule applies — spawn before yielding the turn); the grilling session keeps
its context on the interview and acts on the ledgers.

**How to handle a verification miss.**

1. **Surface the gap explicitly.** Quote what the user said. Quote what
   the search found (or didn't find). No papering over.
2. **Walk the user through three options.** (a) Mistaken —
   redo the question with the actual posture. (b) Proposing to
   introduce it as part of this feature — recorded new
   work (a requirement in a requirements-phase session; an L1/L2/L3
   decision with an ADR in a design-phase session), not a casual
   reference. (c) Confused this service with a different repo /
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
claims are most common. A deployment-topology claim, a schema claim, a
workflow claim, and a signature claim are all claims; the table above
picks the question type for each. The L9 seam walk is this rule applied
per seam.

**A derived finding is a claim too.** A conflict, hole, or violation inferred
from several facts is only as verified as its least-verified leg. Before
presenting one to the human — in chat, a poll reply, or a rendered card —
verify every leg, or present it as a hypothesis naming the unverified leg.

A wrong premise is expensive. Drafting an answer that references
something specific in the codebase — **verify before you write it down.**
