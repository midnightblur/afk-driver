---
name: to-prd
description: /afkv2:to-prd — turns a settled grill into PRD.md, requirement ADRs and INDEX.md, and publishes the ticket description into the Jira ticket, written to the ticket description standard with the owner's pictures kept (diagrams as pictures), or the PRD into the GitHub issue (Markdown as is) after the developer's yes. Asks no new requirement question. Use when the grill passed its exit gate, or to publish a changed PRD again.
---

# /afkv2:to-prd

Write what the grill settled, then show the developer exactly what the ticket will hold. Nothing goes to the ticket before the developer's yes. This is the only skill that writes a PRD to Jira or to a GitHub issue. It makes the first ticket write. The second is the ship proof comment, which `/afkv2:create-change-request` posts at ship.

## Input

| Value | Source | When it is missing |
|-------|--------|--------------------|
| ticket key | the invocation | stop and name it |
| `.afkv2/config.json`, with a tracker kind | written by `/afkv2:setup` | stop and name the file and `/afkv2:setup` |
| `GRILL-LOG.md` with a passed exit gate, and the page documents | written by `/afkv2:grill-requirements` | stop and name them and `/afkv2:grill-requirements` |
| `mmdc` on the path and `%LOCALAPPDATA%\afkv2\puppeteer-config.json`, when the PRD has a diagram | `/afkv2:setup` | the preview refuses `no-renderer` and names `setup`; a publish downloads nothing |

## The commands

Run each command from the repository root. `<python>` is the Python in the setup install record (line `python`). Every answer is one JSON object: `{"ok": true, ...}` or `{"ok": false, "error": {"code", "reason"}}`; exit 0 is ok, 1 is refused, 2 is unreadable input.

## Steps

1. **Start.** Done when the answer is ok.

   ```sh step=start
   <python> "<this skill's folder>/scripts/prd_files.py" start --ticket "<ticket key>"
   ```

   `missing-input`: stop and show `missing` and `writer`. The answer holds `spec_dir`, `log`, `prd`, `adr_dir`, `index`, `run_dir`, `tracker_kind`, `resume`, `unverified_external` and `assumed`.

2. **Write the PRD.** Read `log` and the page documents in `<spec_dir>/pages/`. They are your whole source. Write `prd` by [PRD-FORMAT.md](PRD-FORMAT.md). Done when each settled point stands in the PRD, and each owner note and `Steer` row is honoured.

   Ask the human no question about requirements. A point the grill left out is a gap of the grill: stop, name the gap, and send the human to `/afkv2:grill-requirements`. `resume` true: `prd` exists, so change only what the grill changed, and keep every id.

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

6. **Publish, or stop here.** `tracker_kind` is not `jira` or `github-issues`: tell the human the PRD stays on disk, then go to step 10. A GitHub issue gets the PRD Markdown as is between 2 HTML-comment lines; GitHub draws each Mermaid diagram, so no picture is rendered or uploaded: go to step 7.

   A Jira ticket gets a new whole description, written to the standard. Read the live description. Done when the answer is ok.

   ```sh step=outline
   <python> "<this skill's folder>/scripts/publish.py" outline --ticket "<ticket key>" --run-dir "<run_dir>"
   ```

   Read `outline` (each top-level node with its `index`, `text`, `media` and `in_block`). Write `<spec_dir>/TICKET.md` by [TICKET-FORMAT.md](TICKET-FORMAT.md). Done when each settled point of the PRD that the reader needs stands in it, and each node of the product owner is kept or changed on purpose.

7. **Build the preview.** This step writes nothing to the ticket. Done when the answer is ok. A GitHub issue:

   ```sh step=preview
   <python> "<this skill's folder>/scripts/publish.py" preview --ticket "<ticket key>" --prd "<prd>" --run-dir "<run_dir>"
   ```

   A Jira ticket, with `<ticket file>` the `TICKET.md` of step 6:

   ```sh step=preview-ticket
   <python> "<this skill's folder>/scripts/publish.py" preview --ticket "<ticket key>" --prd "<prd>" --ticket-file "<ticket file>" --run-dir "<run_dir>"
   ```

   Refusals are in the table below. Check `dropped`: each live node the new description leaves out. `already_published` true: the ticket holds this text and these pictures, so tell the human and go to step 10.

8. **Show it and ask.** `over_jira_limit` true (visible text over about 30000 characters): shorten `TICKET.md` before you ask. `over_github_limit` true: say that GitHub may refuse this text as too long, and offer to shorten the PRD. Done when the human answered.

   By default, show the preview on a page by `/afkv2:use-lavish` ([../use-lavish/SKILL.md](../use-lavish/SKILL.md)): run its `page_home.py start` with `--topic "<ticket key> ticket preview"`, `--ticket` and `--private`, then `round_document.py build` with `--round-input` set to `round_input` of the preview, `--ticket` and `--private`, then `present`, `wait` and `ingest`. The round holds 1 card with the exact text and pictures, and the sign-off card `i-publish`. In chat, give `action`, each entry of `dropped`, and the first 8 characters of `receipt`.

   The developer asks for no page, or `present` refuses on `show`: give `page_url` (the same text in one file), `action`, each entry of `dropped`, and the first 8 characters of `receipt` in chat, ask for a yes, and end your turn.

   A yes is the developer's sign mark on `i-publish` of this preview's page, or, with no page, the developer's own message in this session, after this preview. A message from an agent is not a yes. Any other answer: change nothing on the ticket. A change to the PRD starts again at step 4, a change to `TICKET.md` at step 7; each needs a new preview and a new yes.

9. **Publish.** Run this only after the yes, with the `receipt` of the preview the human answered. Done when the answer is ok.

   ```sh step=publish
   <python> "<this skill's folder>/scripts/publish.py" publish --preview "<preview>" --receipt "<receipt>"
   ```

   The script runs the order: upload new pictures, write the description (Jira) or the block (GitHub) with the description hash and the receipt, read back and compare the text and the media ids, then delete the afkv2 and v1 pictures the new text does not use. A GitHub issue has no pictures: the script writes the block and reads it back. Report `replaced`, `deleted`, and any `not_deleted` or `log_problem`: the next publish deletes those pictures again. `already_published` true: nothing was written, so tell the human that.

10. **Finish.** Commit `INDEX.md` when it changed. Tell the human the next skill is `/afkv2:propose-solution`. Done when the commit exists.

## Refusals of the preview and the publish

| Code | Meaning | What you do |
|------|---------|-------------|
| `stale` | the ticket changed after the outline or the preview; nothing was written | go to step 6: run `outline` again, check each keep line, then show a new preview |
| `no-outline` | the preview of a ticket file found no `outline.json` | go to step 6 |
| `bad-ticket` | a keep line names no node, or a node twice | fix `TICKET.md`, then go to step 7 |
| `keeps-block` | a keep line names a node of an old block | write that content anew in `TICKET.md`, then go to step 7 |
| `drops-media` | a node in `nodes` holds a picture of the product owner and is not kept | keep it in `TICKET.md`, then go to step 7 |
| `dated-section` | a heading of the new description is dated, or an update, history or meeting-summary section | apply its content to the text it changes, then go to step 7 |
| `wiki-link` | `TICKET.md` holds wiki link text, which Jira shows as raw text | write the bare key or a Markdown link, then go to step 7 |
| `bad-block` | the description or issue body holds a broken or doubled block; nothing was written | show `reason`; the developer fixes the description by hand, then go to step 7 |
| `bad-receipt` | the preview, its pictures or the converted text, link targets included, are not what the human saw; nothing was written | go to step 7: show the new preview and ask again |
| `missing-ids` | an id in `missing` is not in the text the ticket would get; nothing was written | fix the PRD so the converter keeps that text, then go to step 4 |
| `read-back-mismatch` | the publish failed: the ticket does not hold what was sent; old pictures stay | report a failed publish and `differs`; go to step 7 when the developer asks |
| `no-renderer` | `mmdc` is not on the path or its config file is missing; nothing went to the ticket | show `reason`; run `/afkv2:setup`, then go to step 7 |
| `render-failed` | a diagram did not render | show `reason`; fix the diagram, then go to step 7 |
| `too-large` | the issue body would pass the GitHub limit of 65536 characters; nothing was written | shorten the PRD with the developer, then go to step 4 |
| `bad-request` with `CONTENT_LIMIT_EXCEEDED` in `reason` | Jira refused the length; the description did not change, and an uploaded picture stays until the next publish | shorten `TICKET.md` with the developer, then go to step 7 |
| any other code | a tracker call failed | show `code` and `reason`. Run the same step again when the developer asks: the receipt makes it safe, and a re-run adds no copy of a picture |
