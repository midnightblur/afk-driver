# design-quality — module shape, coupling, change patterns

Design-level. Default `class: design` (baseline items overridden by a documented repo pattern → `pattern-debt` per PRECEDENCE.md). Reads the diff's *shape* — new types, boundaries, who-changes-with-whom — not line-level style.
**Not yours:** symbol naming, duplication, exception discipline → `code-quality`; aggregate/transaction boundaries → `domain-alignment`; endpoint/DTO surface → `api-contract`; timeout/failure stories → `resilience`.

## Reviewer checklist

Module depth:
- **Shallow Module** (APoSD) — new class/interface whose API is as complex as its body (e.g. a service exposing one method per repository call it wraps) → collapse into the caller, or deepen: one simple entry hiding real work.
- **Pass-Through Method** (APoSD) — new method forwards to a near-identical signature adding nothing → cut the layer; caller calls the target.
- **Middle Man** (Fowler) — new class that mostly delegates onward → remove it, call the real target.
- **Same abstraction, adjacent layers** (APoSD) — two new layers speaking the same vocabulary with no transformation between them → merge them.
- **Special-General Mixture** (APoSD) — general-purpose class carrying code that serves exactly one caller → push the special case up into that caller.
- **Overexposure** (APoSD) — common-case callers forced to supply params/config only rare cases need → default the rare case; pull complexity down into the module.

Information & change shape:
- **Information Leakage** (APoSD) — one design decision (format, protocol, field layout) known by ≥2 modules; the diff edits both in lockstep → give the decision one owner module.
- **Temporal Decomposition** (APoSD) — new classes split by execution order (`XxxPreprocessor`/`XxxStep2`) rather than by what each knows → regroup by knowledge.
- **Shotgun Surgery** (Fowler) — one logical change fanned across many files/modules in this diff → gather what changes together into one module.
- **Divergent Change** (Fowler) — one class edited for several unrelated reasons → split so each part changes for one reason.
- **Insider Trading** (Fowler) — new cross-package/module access to another type's internals; two modules trading private detail → move the shared knowledge, or the method, to one side.
- **Conjoined Methods** (APoSD) — new method unreadable without reading its sibling → merge them or redraw the split.
- **Speculative Generality** (Fowler) — hooks, params, interfaces, config for needs no spec names; verify by searching for actual consumers → delete; inline until a real need arrives.

Coupling & inheritance:
- **Control coupling** (CC2) — boolean/enum arg telling the callee which behaviour to run → split into two methods, or polymorphism.
- **Stamp coupling** (CC2) — whole entity/DTO passed where one field is used → pass the field.
- **Grab-bag cohesion** (CC2) — additions to `XxxUtils`/`XxxHelper`/`init()` piles grouped by "when" or "kind of", not by shared data → home each piece with the data it works on.
- **Refused Bequest / LSP break** (Fowler) — new subclass no-ops/throws on inherited behaviour, or strengthens preconditions → drop the inheritance; compose.
- **Inheritance for reuse** (EJ-18) — new `extends` of a class not designed for extension, where substitutability isn't meant → composition + delegation.
- **Concrete reach-through** (Beck) — new `new`/static call into another module's impl class where an injected abstraction exists → inject the seam.

Fewest elements:
- **Lazy Element** (Fowler) — new class/method adding no structure beyond what it wraps → inline it.
- **Unnameable type** (APoSD) — new type needing `Manager`/`Processor`/`Helper`/`Info`/`Data` because nothing sharper fits → if no honest precise name comes, the decomposition is wrong; redraw the boundary before renaming.

## Guardrails (design-time digest)

- Make modules deep: simple interface, powerful implementation. One class per step of your mental plan = temporal decomposition.
- One design decision, one owner module. Two files that must change together mark a wrong boundary.
- Build nothing the spec doesn't need now; delete layers that only forward.
- No flag arguments — split the behaviours.
- `extends` only for true substitutability; otherwise compose.
- No `Utils`/`Helper` grab-bags — home logic with its data.
- Can't give the new type an honest one-word name? Redraw the boundary.
