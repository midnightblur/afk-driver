---
name: review-qa-tests
description: /afkv2:review-qa-tests — reviews the manual test cases of a QA team against the requirements of a feature, and annotates their sheet in place, with missing scenarios as new rows and fixes as threaded comments. Use when the developer shares a QA test-case spreadsheet to find coverage gaps or to improve weak cases.
---

# /afkv2:review-qa-tests

You review the **manual** test cases of a QA team against the requirements of the feature. You give the review back as edits on their own sheet: missing scenarios as new rows, fixes to existing cases as threaded comments.

Two terms apply to all steps:

- **Black box**: the QA reader does not know how the team built the feature. The reader sees requirements and screens, not code. Write each word for a black-box tester.
- **Manual reach**: a case belongs on the sheet only if a black-box tester can, by hand, set up the precondition and see the result. A case that fails this test can be correct, but it does not belong to QA.

## Steps

1. **Read the requirements.** Find and read the source of truth of the feature: the product requirements document (PRD), the specification, the acceptance criteria or the rule catalog of the ticket. The test names alone are not enough. Give the reading to subagents. Take back the list of requirement units (each rule, acceptance criterion, boundary, checkpoint and role), not prose. Then make a **coverage map**: each requirement unit against the scenarios on the sheet, marked `covered`, `partial` or `missing`. Done when each requirement unit has a mark, and each existing case links to the units that it tests.

2. **Classify each case and each gap.** Use the map. Tag each existing case `ok`, `enhance` or `drop`. Plan 1 new case for each missing unit. [Review lenses](#review-lenses) tells what to look for. The [manual reach](#manual-reach) filter tells which case is `drop`. Done when each case has a tag and each missing unit has a planned case.

3. **Settle each uncertainty with the developer first.** A requirement can be unclear, 2 documents can disagree, or you can be unsure whether a behavior is intended. In each of these cases, ask the developer and get a settled fact before you write. You are a member of the team, so do not put a question on the sheet. Never write "confirm with the team". Done when each fact that you will write is settled, and the developer answered each open question.

4. **Write only when all facts are clear.** Do not change the sheet while step 3 has an open question. The annotation is the last step, not a running commentary.

5. **Annotate the sheet.** Make a backup, then edit the sheet in place. Add new cases as rows and enhancements as threaded comments. [Deliverable](#deliverable) gives the format. [EXCEL.md](EXCEL.md) gives the procedure. Done when the sheet is saved, it opens with no repair prompt, and a scan of all text that you wrote finds nothing that [the black-box line](#the-black-box-line) forbids.

## Review lenses

Comment only on the **quality of the test cases**:

- **Coverage**: each requirement unit has a test. A rule can have parallel forms, for example the same check on sibling document types or entities. Write 1 **concrete** case for each form. Never write a note that tells QA to copy another case. A difficult setup is never a reason to skip a case or to change its target. If you see the target, write the case yourself.
- **Both sides of each boundary**: a value at the limit passes, and a value over the limit fails. The endpoints of a window are included. Test each checkpoint where a rule runs, for example at entry and again at approval when the rule checks again. A case that tests only 1 side or 1 checkpoint is `enhance`. Name the missing part.
- **Atomicity**: 1 case tests 1 behavior. A case that puts independent behaviors behind 1 pass or fail result cannot show which behavior failed. Recommend a split.
- **Correctness**: the expected result names the check that actually stops the document. A rule that the system enforces at entry does not first appear at a later step. A case that expects the wrong step records a failure when the feature works.
- **Observable behavior, not status**: when the screens *prevent* an action (a control is absent, an option is not available, a page does not show), test the prevention, not an error code below it.
- **State, not only the message**: for a rejection, "nothing was saved" is a different check from "an error appeared". When the system can save wrong data, tell QA to check the saved state too.

State the gap. Do not criticize the words of QA. "The approval step is missing" is a correct comment. "This sentence says too much" is noise.

## Manual reach

If a black-box manual tester cannot make the precondition or see the result by hand, recommend `drop` and give the reason: the case belongs to automated tests, not to this sheet. Typical failures:

- An unexpected internal error that the tester cannot cause.
- A case that needs more than 1 running instance, or an internal signal that is turned off.
- A true race: timing by hand cannot make 2 saves collide.

Give the reason for each `drop`. Point to the case that already tests the everyday form of the behavior.

## The black-box line

Never put these items in a comment or a case. They mean nothing to QA and break the black box:

- Code identifiers, class, method and file names, specification file names, and decision or acceptance-criterion numbers.
- Bugs, incidents, earlier fixes, iterations and the development process, even when they are true and even to justify a case. Describe the behavior to test, not its history.
- Backend, HTTP or status-code words, when the tester can see the check on a screen.
- "Confirm with the team". Settle the question in step 3.

You may explain the design reason for an *expected behavior*: it helps QA know what to protect. Do not explain the implementation.

## Deliverable

Edit the sheet in place. Make a backup copy first.

- **New case**: add a new row. Fill only the human columns: Test Name, Scenario Objective and Summary. Highlight the row. Leave these columns empty, so QA can fill them and keep the scores as their own: Test ID, priority, preconditions, steps, expected results, and each risk or confidence score. Each Summary states the unit that the case closes and each part that it needs, so QA can run the row as it is.
- **Enhancement or correction**: add a threaded comment on the 1 best cell (Test Name, Scenario Objective or Summary). Use threaded **comments**, not legacy notes. [EXCEL.md](EXCEL.md) gives the procedure and the script.

Follow the layout of the existing sheet. Read its columns and its styles first. Do not assume the layout.
