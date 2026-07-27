# Human sign-off — the human-locked set

Most of the design is settled by argument: recommend, weigh alternatives, lock.
A few aspects are settled by **authority** — they persist data, publish a
contract, or grant access, so a wrong call outlives the feature and costs a
migration, a broken caller, or an access leak to undo. Those are **human-locked**:
the human decides, in their own words, on the record. An agent may recommend and
must grill; it never rules, and the executor never inherits the call.

This file owns the set, the packet the human reviews, and what counts as a
signature.

## The human-locked set

An aspect is **live** when its trigger fires for this feature; otherwise it is
`n/a` with a one-line reason stated in the packet, so the human can object to
the skip. Every live aspect must be settled to its **contract grade** — below
that grade it is not reviewable, so it is not signable.

| id | Aspect | Layer | Trigger | Contract grade | Lands in SDD |
|---|---|---|---|---|---|
| HL-1 | Persistence / entity design | L3 | a persisted entity is added or altered | per entity: every field with type, nullability, default, and unit/precision; identity + uniqueness; every relation with cardinality, owning side, and delete/orphan behaviour; indexes; Envers-audited verdict; retention; migration + backfill of rows that already exist | §4 |
| HL-2 | API surface | L2 | an externally-callable surface (endpoint / controller) is added or changed | per endpoint: method + path, auth + permitted roles, request fields with validation, success envelope, every error envelope with its code and trigger, paging/filtering/sorting, idempotency posture; for a changed endpoint, the verdict on existing callers (compatible / breaking) | §3 |
| HL-3 | Authorization & data scoping | L4 | any protected surface or scoped entity | the L4 authz and scoping matrices complete per this skill's Stop conditions — permitted **and** denied roles, both-side enforcement points, per-entity scoping mechanism | §5 |
| HL-4 | Lifecycle & invariants | L5 | an entity carries a status/state, or a rule the system must refuse to break | the state set, legal transitions, terminal states, who may trigger each; per invariant its guardian and the system's response to a violation | §6 |
| HL-5 | Irreversible & outward side effects | L6 | the feature writes outside its own new state: an external call, a delete/overwrite of existing data, a notification, a posting to a system of record | per effect: trigger, ordering against the local transaction, idempotency key, what a partial failure leaves behind, named recovery | §7 |
| HL-6 | Change to existing behaviour | L9 | a seam row's verdict is `extends` or `reworked` | what existing callers, stored records, and flows see differently; the compatibility posture; the rollback | §14 |

The `Lands in SDD` column is the contract with the synthesis step: a signed
aspect that never reaches its section is design lost between the grill and the
document.

## The packet

Present each live aspect as its own packet — never two aspects in one:

1. **The contract-grade tables themselves, verbatim.** A summary is not a packet;
   the human reviews the fields, not your description of them.
2. The alternatives weighed and why the recommendation won.
3. **Blast radius** — which existing records, callers, and roles this changes.
4. The risks and rough edges you are asking them to accept.

Render per `LAVISH.md` (RP-9, playbook `table`) when a human is present —
mandatory there per that file's Primary-path rule; markdown fallback per the
same file.

## Signing

- **Ask by id, one aspect at a time**, after the packet and before descending.
- A **signature** is the human's direct answer to that aspect's sign-off
  question, affirming it. Silence, an approval given to a different question, a
  nearby favourable remark, and any approval you supply on their behalf are not
  signatures.
- **Changes requested** → record it, rework the aspect, re-packet, re-ask.
- **Void on drift.** A later layer, the L9 walk, or any post-signature change
  touching a signed aspect voids its signature: re-packet the changed rows
  marked as the delta, and re-sign. Never leave a `signed` row describing a
  design that moved.
- **No human, no signature.** Without a human at the keyboard the aspect stays
  `pending` — an unsigned live aspect means the design is not exhausted.
- Record every outcome — `signed` / `changes-requested` / `pending` / `n/a` — in
  the solution grill's `GRILL-LOG.md` section per
  `skills/afk/grill-requirements/GRILL-LOG-FORMAT.md`, at the moment it lands,
  quoting the human's approving words. The log is the register the SDD carries
  forward and the only proof that the call was theirs.
