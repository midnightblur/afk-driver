---
name: review-qa-tests
description: Review a QA team's manual test cases against a feature's requirements and annotate their sheet in place — missing scenarios as new rows, fixes as threaded comments. Use when the user shares a QA test-case spreadsheet wanting coverage gaps found or weak cases sharpened.
---

# review-qa-tests

Review a QA team's **manual** test cases against the feature's requirements and hand the review back as edits on their own sheet: missing scenarios as new rows, fixes to existing cases as threaded comments.

Two ideas run through everything:

- **black-box** — the QA reader knows nothing about how the feature was built. They see requirements and screens, not code. Every word you write is for a black-box tester.
- **manual reach** — a case only belongs on their sheet if a black-box tester can, by hand, both set up the precondition and observe the result. What fails this test is real to verify but not theirs.

## Steps

1. **Ground in the requirements.** Find and read the feature's source of truth — the PRD / spec / acceptance criteria / rule catalog for the ticket, not the test names alone. Delegate the reading to subagents; you want the enumerated requirement units (every rule, AC, boundary, checkpoint, role), not prose. Then build a **coverage map**: each requirement unit against the scenarios present, marked covered / partial / missing. _Completion: every requirement unit in the map carries a verdict, and every existing case is traced to the units it exercises._

2. **Classify every case and every gap.** Against the map, tag each existing case `ok` / `enhance` / `drop`, and give each missing unit a planned new case. What to look for is in [Review lenses](#review-lenses); what makes a case `drop` is the **manual reach** filter. _Completion: no case untagged, no missing unit without a planned case._

3. **Settle uncertainties with the user first.** Wherever the requirement is ambiguous, or two documents disagree, or you are unsure whether behaviour is intended — bring it to the user and resolve it to a **settled fact** before writing anything. You are on the team; the sheet is not where you park a question. Never write "confirm with the team." _Completion: every fact you are about to write is settled; the user has ruled on each open question._

3.5 **Write only when everything is clear.** Do not touch the sheet until step 3 leaves no open question. This gate is deliberate — annotations are the last step, not a running commentary.

4. **Annotate the sheet.** Back it up, then edit in place. New cases as rows, enhancements as threaded comments — format and mechanics in [Deliverable](#deliverable) and the Excel recipe it points to. _Completion: sheet saved, reopens with no repair prompt, and a leak scan of everything you wrote is clean against [The black-box line](#the-black-box-line)._

## Review lenses

Comment on the **quality of the test cases** and nothing else:

- **Coverage** — every requirement unit tested. A rule that exists in several parallel forms (the same check across sibling document types or entities) gets one **concrete** case per form — never a note telling QA to mirror another case. Awkward setup is never a reason to skip or re-target: if you spot the target, you write the case yourself.
- **Both sides of every boundary** — at-limit passes and over-limit fails; window endpoints inclusive; each checkpoint a rule fires at (entry, and again at approval where it re-checks). A case covering one side or one checkpoint is `enhance`, with the missing leg named.
- **Atomicity** — one case, one behaviour. A case bundling independent behaviours behind a single pass/fail can't say which broke; recommend splitting.
- **Correctness** — the expected result names the gate that actually stops the document. A rule enforced at entry won't first surface at a later step; a case asserting the wrong point gets recorded as a failure while the feature works.
- **Observable behaviour over status** — when the screens *prevent* an action (a control absent, an option unofferable, a page not shown), test that prevention, not an error code underneath it.
- **State, not just message** — for a rejection, "nothing was saved" is a different assertion from "an error appeared." Where a wrong-but-committed write is possible, say to check the stored state too.

Say the gap, not a critique of QA's wording. "The approval leg is missing" is the comment; "this sentence overstates it" is noise.

## Manual reach

If a black-box manual tester cannot produce the precondition or see the outcome by hand, recommend **dropping** the case with the reason — it belongs to automated testing, not their sheet. Classic failures:

- An unexpected internal error the tester has no lever to trigger.
- Anything needing more than one running instance, or a suppressed internal signal.
- A genuine race — hand timing can't make two saves collide.

Drop with rationale; point to where the everyday version of the behaviour is already covered.

## The black-box line

Never let any of this reach a comment or a case — it means nothing to QA and breaks the black-box frame:

- Code identifiers, class/method/file names, spec filenames, decision or AC numbers.
- Bugs, incidents, past fixes, iterations, dev process — even when true, even to justify a case. Reframe as the behaviour to test, not the history behind it.
- Backend/HTTP/status-code vocabulary when the check is observable on screen.
- "Confirm with the team" — resolve it in step 3 instead.

Design rationale for *expected behaviour* is welcome (it helps QA understand what to protect); implementation rationale is not.

## Deliverable

Edit the sheet in place; keep a `.BACKUP` copy first.

- **New case** → a new row. Fill only the human columns — Test Name, Scenario Objective, Summary — and highlight the row. Leave Test ID, priority, preconditions, steps, expected results, and every risk/confidence score blank so QA assigns them and the scoring stays theirs. Each Summary states the unit it closes and every leg it needs, so the row is ready to run as-is.
- **Enhancement / correction** → a threaded comment on the single most fitting cell (Test Name, Scenario Objective, or Summary). Threaded **comments**, not legacy notes — mechanics and a ready script in [`EXCEL.md`](EXCEL.md).

Match the existing sheet: read its columns and styling first; don't assume this file's layout.
