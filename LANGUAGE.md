# LANGUAGE.md — one language across the chain

Binding on every skill, agent, and script that produces words — the conversation
with the human (replies, questions, option lists, status lines) **and** every
artifact written to disk or published (specs, plans, contracts, reports,
steering notes, tickets, HTML pages, notifications), whether a human or another
agent reads it. Two rules: write **Simplified Technical English**, use the
**vocabulary the glossaries own**. Root docs are not auto-loaded, so every
`SKILL.md` and agent definition carries a one-line pointer here — never a
restatement (gate: `hooks/skill-registry-gate.sh` check D).

## 1. Simplified Technical English (ASD-STE100 spirit)

- Short sentences, one point each (aim ≤ 20 words); one instruction per sentence.
- Active voice, present tense: "run the build", not "the build should be run".
- One term, one meaning — and one meaning, one term. Never rotate synonyms for variety.
- Prefer the common word. Expand every abbreviation at first use, per report or artifact.
- No idioms, no metaphors, no filler, no rhetorical questions.
- Numbers, not adjectives: "3 of 9 subtasks parked", never "most subtasks parked".

## 2. Ubiquitous language

- Workflow terms (stages, modes, states, verdicts, artifact names) come from `GLOSSARY.md` (plugin root), spelled as defined there.
- Domain terms come from the target repo's glossaries (start at its `GLOSSARY-MAP.md`).
- Never coin a synonym for a term a glossary owns; never redefine one inline — point at its home.
- A recurring domain term with no entry is a gap: name it once, consistently, and route it to the glossary steward (`/afk:glossary`).
- Jargon stays out of the reader-facing plain-terms sentence — that sentence must stand alone without any glossary (`REPORTING.md`).

## Scope, exceptions, neighbours

- Prose only. Code, code comments, commit messages, and test names keep their own conventions.
- Verbatim identifiers — paths, commands, flags, field names, env vars, error strings — are never reworded to fit rule 1.
- A user-invoked compression mode overrides sentence shape while active; rule 2 still binds.
- `CONCISION.md` governs **how much** to write; this file governs **which words**. Specialized bars own only their deltas.
