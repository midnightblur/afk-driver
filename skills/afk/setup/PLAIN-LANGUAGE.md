# PLAIN-LANGUAGE.md — the opt-in reply standard

One home for the block `MANIFEST.md · H7` installs into the user-global
steering file(s) — targets + copy command live in that entry. Everything
between the sentinel lines lands verbatim; edit here. The sentence rules are
a synchronized copy of `LANGUAGE.md` §1, and the two coined-term rules a
synchronized copy of `LANGUAGE.md` §2 (the owner of both) — a change to §1, or
to §2's coinage/gloss rules, updates this block in the same commit.

<!-- afk:plain-language:start -->
## Reply standard: Simplified Technical English

All human-facing prose — replies, summaries, reports, questions — follows the
ASD-STE100 spirit:

- Short sentences, one point each (aim ≤ 20 words); one instruction per sentence.
- Active voice, present tense: "run the build", not "the build should be run".
- One term, one meaning — and one meaning, one term. Never rotate synonyms.
- Prefer the common word; expand every abbreviation at first use.
- Noun clusters: 3 words maximum. Unstack with a preposition or a verb — "the handler that sets task-queue priority", never "the agent task queue priority handler".
- No idioms, no metaphors, no filler, no rhetorical questions.
- Numbers, not adjectives: "3 of 9 tests fail", never "most tests fail".

Coined terms — a multi-word compound naming a concept is a term:

- Do not invent one and start using it. Write the concept out as a phrase, or state the definition and keep the name.
- Gloss a named compound at first use in **every** reply that uses it — 3-5 words, in brackets: "mergebase (the commit the branch forked from)". Repeating the gloss is not redundancy; a novel compound costs a full re-parse at every encounter.

Scope: conversation output only — code, comments, commit messages, and written
artifacts keep their own style rules.
<!-- afk:plain-language:end -->
