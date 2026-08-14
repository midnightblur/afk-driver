# Baseline precedence — pasted with every checklist

Rules binding every checklist item marked as **baseline** (book-derived catalog items, cited `(Fowler)`, `(APoSD)`, `(EJ-nn)`, `(CC2)`, `(DDD)`, `(Nygard)`, `(Newman)`, `(PoEAA)`, `(Meszaros)`, `(Bloch-API)`, `(Beck)`). Documented-rule checks (CLAUDE.md chain, spec, scope) are NOT baseline — these rules don't soften them.

1. **The repo overrides — but report the conflict.** A documented standard in the target repo's CLAUDE.md chain / `STAPLES.md` / ADRs wins where it endorses what a baseline item would flag. Don't suppress silently: emit the finding as `class: pattern-debt`, severity `low`, quoting BOTH the baseline item and the overriding repo rule. `pattern-debt` never blocks; it feeds the debt ledger. Net-new modules with no established local pattern get the baseline at full strength — no override applies.
2. **Baseline findings are judgment calls.** Hedge the headline ("possible Feature Envy"), severity ≤ `medium`. Only documented-standard breaches, spec violations, and demonstrable correctness bugs may be `high`/`critical`.
3. **Skip what tooling enforces.** Formatter, ESLint, compile gates own style, length limits, magic-number mechanics, import order. Never report their territory.
4. **One owner per smell.** Report only items on YOUR checklist. Adjacent smells named under your checklist's "Not yours" line belong to another reviewer — skip them even when obvious.
5. **The open question.** After the checklist pass, add at most ONE finding answering: what is the most important problem in this diff that no checklist item covers? Mark it `concern: <yours>`, evidence-cited like any other; none is a fine answer.

Source-tag legend: Fowler = *Refactoring* 2nd ed. ch.3 · APoSD = Ousterhout, *A Philosophy of Software Design* · EJ = Bloch, *Effective Java* 3rd ed. item · CC2 = McConnell, *Code Complete 2* · DDD = Evans · Nygard = *Release It!* 2nd ed. · Newman = *Building Microservices* 2nd ed. · PoEAA = Fowler, *Patterns of Enterprise Application Architecture* · Meszaros = *xUnit Test Patterns* · Bloch-API = "How to Design a Good API" · Beck = four rules of simple design / *Tidy First?*
