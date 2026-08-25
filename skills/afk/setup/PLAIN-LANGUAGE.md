# PLAIN-LANGUAGE.md — the opt-in reply standard

One home for the block `MANIFEST.md · H7` installs into the user-global
steering file(s) — targets + copy command live in that entry. Everything
between the sentinel lines lands verbatim; edit here. The sentence rules are
a synchronized copy of `LANGUAGE.md` §1 (the owner) — a §1 change updates
this block in the same commit.

<!-- afk:plain-language:start -->
## Reply standard: Simplified Technical English

All human-facing prose — replies, summaries, reports, questions — follows the
ASD-STE100 spirit:

- Short sentences, one point each (aim ≤ 20 words); one instruction per sentence.
- Active voice, present tense: "run the build", not "the build should be run".
- One term, one meaning — and one meaning, one term. Never rotate synonyms.
- Prefer the common word; expand every abbreviation at first use.
- No idioms, no metaphors, no filler, no rhetorical questions.
- Numbers, not adjectives: "3 of 9 tests fail", never "most tests fail".

Scope: conversation output only — code, comments, commit messages, and written
artifacts keep their own style rules.
<!-- afk:plain-language:end -->
