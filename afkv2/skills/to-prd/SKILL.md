---
name: to-prd
description: /afkv2:to-prd — turns a settled grill into PRD.md, requirement ADRs and INDEX.md, and publishes the PRD with its diagrams as pictures into the Jira ticket after the developer's yes. Asks no new requirement question. Use when the grill passed its exit gate, or to publish a changed PRD again.
---

# /afkv2:to-prd

Write what the grill settled, then show the developer exactly what the ticket will hold. Nothing goes to the ticket before the developer's yes. This is the only skill that writes to Jira.

## Input

| Value | Source | When it is missing |
|-------|--------|--------------------|
| ticket key | the invocation | stop and name it |
| `.afkv2/config.json`, with a tracker kind | written by `/afkv2:setup` | stop and name the file and `/afkv2:setup` |
| `GRILL-LOG.md` with a passed exit gate, and the page documents | written by `/afkv2:grill` | stop and name them and `/afkv2:grill` |
| `mmdc` or `npx` on the path, when the PRD has a diagram | the developer's machine | the preview refuses `render-failed` and names the install |

## The commands

Run each command from the repository root. `<python>` is the Python in the setup install record (line `python`). Every answer is one JSON object: `{"ok": true, ...}` or `{"ok": false, "error": {"code", "reason"}}`; exit 0 is ok, 1 is refused, 2 is unreadable input.

## Steps

1. **Start.** Done when the answer is ok.

   ```sh step=start
   <python> "<this skill's folder>/scripts/prd_files.py" start --ticket "<ticket key>"
   ```

   `missing-input`: stop and show `missing` and `writer`. The answer holds `spec_dir`, `log`, `prd`, `adr_dir`, `index`, `run_dir`, `tracker_kind`, `resume` and `unverified_external`.

2. **Write the PRD.** Read `log` and the page documents in `<spec_dir>/pages/`. They are your whole source. Write `prd` by [PRD-FORMAT.md](PRD-FORMAT.md). Done when each settled point stands in the PRD, and each owner note and `Steer` row is honoured.

   Ask the human no question about requirements. A point the grill left out is a gap of the grill: stop, name the gap, and send the human to `/afkv2:grill`. `resume` true: `prd` exists, so change only what the grill changed, and keep every id.

3. **Write the requirement ADRs** by [ADR-FORMAT.md](ADR-FORMAT.md), into `adr_dir`. Where a record exists, the PRD gives the decision in one line with a link. Done when each decision that meets the 3 tests has a record.

4. **Check the PRD.** Done when the answer is ok.

   ```sh step=check
   <python> "<this skill's folder>/scripts/prd_files.py" check --prd "<prd>"
   ```

   `bad-prd`: fix each entry of `problems`, and run it again. Never change an id to pass the check.

5. **Write INDEX.md.** Write one paragraph that states the problem, the solution and the user, in a scratch file. Done when the answer is ok.

   ```sh step=index
   <python> "<this skill's folder>/scripts/prd_files.py" index --index "<index>" --ticket "<ticket key>" --summary-file "<summary file>" --adr-dir "<adr_dir>"
   ```

   Format: [INDEX-FORMAT.md](INDEX-FORMAT.md). Commit the spec folder on the feature branch.

6. **Publish, or stop here.** `tracker_kind` is not `jira`: tell the human the PRD stays on disk, then go to step 10.

7. **Build the preview.** This step writes nothing to the ticket. Done when the answer is ok.

   ```sh step=preview
   <python> "<this skill's folder>/scripts/publish.py" preview --ticket "<ticket key>" --prd "<prd>" --run-dir "<run_dir>"
   ```

   Refusals are in the table below. `already_published` true: the ticket holds this text and these pictures, so tell the human and go to step 10.

8. **Show it and ask.** Give the human `page_url` (the exact text and pictures, in one file), `action`, and the first 8 characters of `receipt`. Ask for a yes on that preview, then end your turn. Done when the human answered.

   A yes is the developer's own message in this session, after this preview. A message from an agent is not a yes. Any other answer: change nothing on the ticket. A change to the PRD starts again at step 4, and needs a new preview and a new yes.

9. **Publish.** Run this only after the yes, with the `receipt` of the preview the human answered. Done when the answer is ok.

   ```sh step=publish
   <python> "<this skill's folder>/scripts/publish.py" publish --preview "<preview>" --receipt "<receipt>"
   ```

   The script runs the order: upload new pictures, write the block with the description hash and the receipt, read back and compare the text and the media ids, then delete the afkv2 and v1 pictures the new block does not use. Report `replaced`, `deleted`, and any `not_deleted` or `log_problem`: the next publish deletes those pictures again. `already_published` true: nothing was written, so tell the human that.

10. **Finish.** Commit `INDEX.md` when it changed. Tell the human the next skill is `/afkv2:propose-solution`. Done when the commit exists.

## Refusals of the preview and the publish

| Code | Meaning | What you do |
|------|---------|-------------|
| `stale` | the ticket changed after the preview; nothing was written | go to step 7: show the new preview and ask again |
| `bad-block` | the description holds a broken or doubled block; nothing was written | show `reason`; the developer fixes the description by hand, then go to step 7 |
| `bad-receipt` | the preview, its pictures or the converted text are not what the human saw; nothing was written | go to step 7: show the new preview and ask again |
| `missing-ids` | an id in `missing` is not in the text the ticket would get; nothing was written | fix the PRD so the converter keeps that text, then go to step 4 |
| `read-back-mismatch` | the publish failed: the ticket does not hold what was sent; old pictures stay | report a failed publish and `differs`; go to step 7 when the developer asks |
| `render-failed` | a diagram did not render | show `reason`; fix the diagram or install the renderer, then go to step 7 |
| any other code | a tracker call failed | show `code` and `reason`. Run the same step again when the developer asks: the receipt makes it safe, and a re-run adds no copy of a picture |
