---
name: summarize-meetings
description: /afkv2:summarize-meetings — turns 1 meeting transcript or notes into 1 comment per ticket the meeting concerns, and applies its decisions to each ticket description, after the developer's sign on 1 page. A re-run of the same meeting edits its comments in place. Use when asked to summarize a meeting, or to post a meeting to its tickets.
---

# /afkv2:summarize-meetings

Write what 1 meeting settled onto each ticket it concerns: 1 comment per ticket, and a current description. Nothing goes to a ticket before the developer's sign.

## Input

| Value | Source | When it is missing |
|-------|--------|--------------------|
| the transcript or the notes | the invocation: a file or pasted text | stop and ask for it |
| the meeting date and title | the invocation, else the transcript | ask |
| the ticket keys | the invocation, the keys the transcript names, and step 3 | ask for 1 key at least |
| recordings and documents | the invocation | write "Transcript only, no recording link given" and "-" |
| `.afkv2/config.json`, with a tracker kind | `/afkv2:setup` | stop and name `/afkv2:setup` |

## The commands

Run each command from the repository root. `<python>` is the Python in the setup install record (line `python`). Every answer is 1 JSON object: `{"ok": true, ...}` or `{"ok": false, "error": {"code", "reason"}}`; exit 0 is ok, 1 is refused, 2 is unreadable input.

## Steps

1. **Start.** Done when the answer is ok.

   ```sh step=start
   <python> "<this skill's folder>/scripts/meetings.py" start --date "<YYYY-MM-DD>" --title "<meeting title>"
   ```

   Keep `title` (the title of each comment) and `run_dir` (a private folder outside the repository: the meeting is customer content).

2. **Read.** Read the transcript. Give a transcript of more than about 2000 lines to 1 subagent, and take back a digest that cites transcript line numbers. Read each named ticket and its linked tickets. Done when you know each topic and the ticket it belongs to.

3. **Route.** For each ticket, list its topics with their transcript lines. A ticket gets a summary when the meeting decides, confirms or changes something of it, even when the meeting names it only once, and also when the talk on a linked ticket changes its scope. A ticket with no real content gets none. A topic settled under another ticket gets 1 line "See KEY for topic". Done when each topic has its tickets.

4. **Summarize.** For each routed ticket, write `<run_dir>/<ticket key>/summary.md` by [SUMMARY-FORMAT.md](SUMMARY-FORMAT.md). Done when each decision of the routing stands in the summary of each ticket it concerns.

5. **Update the descriptions.** For each ticket whose current scope the meeting changes, run the to-prd outline:

   ```sh step=outline
   <python> "<this skill's folder>/scripts/meetings.py" outline --run-dir "<run_dir>" --ticket "<ticket key>"
   ```

   Read `outline` (each live node of the description, with its `index`) and `meetings` (the ticket's meeting comments, oldest first). Then write `<run_dir>/<ticket key>/TICKET.md` by [../to-prd/TICKET-FORMAT.md](../to-prd/TICKET-FORMAT.md), the one home for how a description reads. Done when each decision and new fact of the meeting stands in the description, and the description contradicts no meeting in `meetings.md` that is more recent.

6. **Preview.** This step writes nothing to a ticket. Done when the answer is ok.

   ```sh step=preview
   <python> "<this skill's folder>/scripts/meetings.py" preview --run-dir "<run_dir>"
   ```

   `round_input` holds 1 card per ticket (the exact comment, and the description preview when it changes) and the sign-off card `i-publish`. Add before `i-publish` 1 info card with the routing (ticket, topic, transcript lines), and 1 debate card with a recommendation for each "(unclear in transcript)" point and each routing you are not sure of.

7. **Show it and ask.** Show the round by `/afkv2:use-lavish` ([../use-lavish/SKILL.md](../use-lavish/SKILL.md)): `page_home.py start` with `--topic "<title>"` and `--private`, then `round_document.py build` with `--round-input` set to `round_input` and `--private`, then `present`, `wait` and `ingest`. Done when the developer answered.

   A yes is the developer's sign mark on `i-publish` of this page. A message from an agent is not a yes. A note or any other mark: change the files it asks for, then go to step 6; each change needs a new preview and a new sign.

8. **Post.** Run this only after the sign, with the `receipt` of the preview. Done when the answer is ok.

   ```sh step=post
   <python> "<this skill's folder>/scripts/meetings.py" post --run-dir "<run_dir>" --receipt "<receipt>" --doc "<page document>"
   ```

   Per ticket it writes the description first (stale check, read-back), then the comment: a description that fails leaves the comment unwritten. Report per ticket `description`, `comment` (`posted`, `edited` or `unchanged`) and `url`, and each `error`. A ticket in `failed`: show its `error`, fix it, and go to step 5 or 6 for that ticket.

## Refusals

| Code | Meaning | What you do |
|------|---------|-------------|
| `no-summary` | no `<ticket key>/summary.md` in the run folder | step 4 |
| `duplicate-meeting` | the ticket holds 2 comments with this title | tell the developer to merge them by hand, then go to step 6 |
| `not-own` | the comment with this title has another author | tell the developer; it stays as it is |
| `no-sign` | `i-publish` holds no sign mark; nothing was written | step 7 |
| `bad-receipt` | a summary, a description or the preview changed after the sign; nothing was written | step 6 |
| `stale` | a comment or a description changed after the preview | step 5 for a description, step 6 for a comment |
| the to-prd preview and publish codes | see [../to-prd/SKILL.md](../to-prd/SKILL.md) "Refusals" | as that table says |
