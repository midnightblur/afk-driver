## External-seam rule — the boundary with code you don't control

The Grounding rule proves things *exist*. It won't catch a design that's
wrong at the seam with a framework, a UI contract, or another layer's
enforcement — the grill is sharp on seams between *our* modules and blind
where our code meets things we don't own. Before locking any decision that
crosses such a seam, **verify (don't assume)** the four things that pass
existence checks and still ship broken — like Grounding-rule
verifications, these reads run in `afk-reader` subagents returning cited
confirm/refute digests, per `DELEGATION.md` (plugin root):

1. **Framework runtime behavior** — not the API signature, what it *does*
   at the pinned version: how it serializes your output, generates the
   input schema from your types, which annotations it honors, how it
   surfaces errors. (Classic misses: a Jackson-2 value serialized by
   Jackson 3; a `@NotNull` that moves no schema.) A test on your own
   object can't cover this — only one asserting on the framework's real
   output can; flag that test so `/afk:to-sdd` binds it.
2. **Contract source of truth** — required / immutable / constraint come
   from the canonical source, not a proxy. Here: UI vuelidate `*Form.vue`
   (required) and edit-mode `:readonly` (immutable), not DB `NOT NULL`.
   Name it and read it.
3. **Where it's enforced — both directions.** A guard must hold on *both* sides
   of the UI seam, and each side is blind to the other's hole:
   - *Below the UI* — "the UI prevents X" ≠ "the system prevents X." A new
     API/MCP caller bypasses the UI; verify the guard lives below it (controller
     / service), or design one that does.
   - *At the UI* — the converse, and the one that ships silently: a guard that
     lives **only** below the UI leaves the surface itself ungated (menu shown,
     route reachable, control visible to a role that should never see it), and no
     API test catches it because the backend correctly returns `403`. Verify (or
     design) the guard at the **UI surface**
     too — route guard, menu visibility, control visibility per role tier.

   Both sides feed the §9b seam and become required `/afk:grill-verification`
   rows (a denied-tier UI row **and** a `403` API row) — neither alone is "done."
4. **Failure affordance** — design the error contract, not just the happy
   path: per violation class, what the consumer gets, and whether a
   business refusal is distinguishable from a server fault (including the
   framework's own signal, e.g. MCP `isError`). State the **real** response
   shape an API/MCP caller sees on each edge (a missing entity may return an
   empty-success envelope rather than 404, a denial a coded 403 — the
   harness's actual envelope conventions live in
   `11700-payable/verification/api/AUTHORING.md`) — this is exactly what `/afk:to-sdd` records in
   the §3 API contract table and what `/afk:grill-verification` later turns
   into assertable API scenarios; a hand-wave here leaves the endpoint
   un-verifiable.
