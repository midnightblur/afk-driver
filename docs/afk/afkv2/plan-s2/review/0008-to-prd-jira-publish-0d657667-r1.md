# Review 0008-to-prd-jira-publish, round 1

Policy: lean. Activated: spec-fidelity, scope-and-impact, test-veracity, logic-correctness (the slice has a consumer). Skipped: refactor-safety, domain-alignment, api-contract (no trigger). Deferred to the feature gate: code-quality, agents-md-compliance, design-quality, resilience.

Verdict: blocking. Critical 0, high 1, medium 9, low 9.

## r-001 high correctness (logic-correctness)
`afkv2/skills/to-prd/scripts/publish.py:239`

When uploads.json holds nothing for this receipt, _already_published passes on text, picture count and file names alone. The publish then deletes the picture the live block still uses.

Why: Nothing ties the block's media ids to the named files on the ticket. If run/uploads.json is missing or was overwritten by another receipt, `not uploads` makes the test pass, and _remove_unused (keep_ids empty, keep by name) deletes the old in-use afkv2/v1 picture.

Fix: Return False when `names` is non-empty and `uploads` is empty, so the normal upload, write, read-back path runs; or tie each media id to an attachment before trusting it.

Evidence: return not uploads or media == [uploads[name]["media_id"] for name in names if name in uploads]  /  if str(item.get("id")) in keep_ids or (not keep_ids and name in keep_names): continue. Failing input: the ticket holds an afkv2 block B with old picture afkv2-fig-aaaaaaaa-1.png. A publish of receipt R2 (same text, new diagram) uploads afkv2-fig-bbbbbbbb-1.png, then its description-put fails. A later publish of receipt R3 overwrites run/uploads.json. The PRD returns to the R2 diagram. Preview then answers already_published:true. Publish then deletes aaaaaaaa-1.png, which B still shows, and writes nothing. The same happens when run/ is wiped or the PRD is published from another clone.

## r-002 medium test (test-veracity)
`afkv2/tests/skills/fakes/fake_jira_port.py:79`

The fake md-to-adf only knows headings, paragraphs and code fences. The fixture PRD has no list, table or inline mark, so the AC-055 id check and the block_text compare never meet the real converter's output on those node types.

Why: The PRD format asks for tables and the AC lines are '- [ ]' list items, so the real converter may give a different block_text for them. The skipped real-port tests use the same plain PRD.

Fix: Add a list item with an AC id, a table row and an inline-code span to the fixture PRD. Make the fake convert lists and tables as the contract's block_text rule says, or make the real-port test run them.

Evidence: elif line.startswith("#"): ... elif line.strip(): nodes.append(paragraph(line.strip())) // fixture: "- [ ] AC-001 The basket shows the total." // contract: "block_text is the text of the top-level nodes that hold text, one per line"

## r-003 medium test (test-veracity)
`afkv2/tests/skills/test_to_prd.py:328`

The only test of the yes gate checks that the substring 'ask' appears between step=preview and step=publish in SKILL.md.

Why: 'ask' also matches 'task' or 'do not ask', so the test passes with the gate removed or reversed. The publish verb takes no proof of a yes.

Fix: Assert the specific gate text, for example 'A yes is the developer's own message', and that step 8 comes before step 9. Or assert that the skill tells the agent to end its turn after the preview.

Evidence: assert "ask" in text[text.index("step=preview"):text.index("step=publish")].lower()

## r-004 medium test (test-veracity)
`afkv2/tests/skills/test_to_prd.py:565`

bad-block is tested only at preview. The description going bad between preview and publish is untested, though publish_after_yes has its own _refuse_bad_block call (publish.py:380).

Why: With that call deleted, the publish would upload pictures first and only then fail at description-put. 'Nothing is written' would break and no test would fail.

Fix: Add a test: preview on a good ticket, then set a ticket with a begin line only, publish, and assert exit 1, code bad-block, and no attachment-put or description-put in the call log.

Evidence: error = world.preview(expect=1)["error"]  // every bad-block case calls preview, none calls publish after a ticket change

## r-005 medium correctness (logic-correctness)
`afkv2/skills/to-prd/scripts/publish.py:397`

The publish re-converts block.md from disk. Only its text is compared to the preview; link targets, node types and picture positions are not.

Why: block.md is not in the receipt or in any digest in preview.json, and the port's receipt covers visible text and picture bytes only, so a changed block.md (or a different converter version) sends different links or figure positions than the page the developer approved.

Fix: Store a sha256 of block.md (or of the preview's ADF) in preview.json, include it in the receipt, and check it in _load_preview.

Evidence: markdown = (run_dir / "block.md").read_text("utf-8") ... if final["block_text"] != preview["block_text"]: raise Refusal("bad-receipt", ...). Failing input: change https://a.example to https://b.example in run/block.md after the yes. block_text is equal, so the publish writes the new link.

## r-006 medium correctness (logic-correctness)
`afkv2/skills/to-prd/scripts/publish.py:407`

_note_published can raise after the ticket write and read-back succeeded. Then _remove_unused never runs, and a retry in the already_published branch hits the same raise.

Why: The log write is guarded (_record returns text), but set_row is not: a locked INDEX.md on Windows (os.replace PermissionError, an OSError) or an INDEX.md with no table (bad-index) reports a failed publish for a ticket that was updated.

Fix: Catch Refusal and OSError around _note_published, return the problem as text like log_problem, and run _remove_unused regardless.

Evidence: problem = _record(log_path, key, receipt, now, only_if_new=False)
    _note_published(preview, now)
    keep_ids = ...
    deleted, not_deleted = _remove_unused(...)  (same order at line 387)

## r-007 medium correctness (logic-correctness)
`afkv2/skills/to-prd/scripts/prd_files.py:190`

The `index` verb sets the PRD row to `draft` on every run, including a resume after a publish. When the preview then answers already_published, SKILL.md step 7 jumps to step 10, so the row is never set to `published`.

Why: INDEX.md is the read-first dashboard and ends up saying draft for a PRD that is on the ticket, because only publish.py _note_published writes the published state.

Fix: Leave the PRD row alone when it already reads `published to Jira ...` and the PRD is unchanged, or have step 7's already_published path run `prd_files.py row` for it.

Evidence: set_row(path, "PRD", "PRD.md", "draft")  /  SKILL.md step 7: "`already_published` true: ... go to step 10."

## r-008 medium spec (spec-fidelity)
`afkv2/skills/to-prd/scripts/publish.py:122`

When mmdc is missing, the publish runs `npx -y @mermaid-js/mermaid-cli`, which downloads and runs a package at publish time.

Why: The accepted grill seam row (docs/afk/afkv2/GRILL-LOG.md:152) says setup installs the diagram renderer and nothing is downloaded at publish. D-39 says no SDD row or setup contract covers this, and it never cites that row.

Fix: Drop the npx branch and refuse `render-failed` naming the install. Or record a superseding decision that cites GRILL-LOG.md:152.

Evidence: command = [mmdc] if mmdc else [npx, "-y", "@mermaid-js/mermaid-cli"] if npx else None

## r-009 medium spec (spec-fidelity)
`afkv2/skills/to-prd/scripts/publish.py:180`

The preview page shows a link only as underlined text with the target in a hover tooltip. Other marks and unknown node kinds are dropped. The receipt does not cover link targets, so the developer says yes to something they cannot fully read.

Why: The developer approves text that goes to the ticket, but the link target they approve is visible only on hover.

Fix: Print the link target in the page text, for example `text (href)`. Also list any node or mark type the page does not render.

Evidence: text = f'<u title="{html.escape(str((mark.get("attrs") or {}).get("href")), quote=True)}">{text}</u>'

## r-010 medium correctness (spec-fidelity)
`afkv2/skills/to-prd/scripts/publish.py:233`

`_already_published` compares only block text and media ids. A PRD edit that changes only a link target or a mark (bold, code) gives the same receipt and an equal text. The preview then says `already_published` and the ticket never gets the edit.

Why: The developer sees 'nothing to publish' while the ticket still holds the old formatting or link. This is consistent with the receipt rule in CONTRACT.md, but the skill does not warn about it.

Fix: Compare the sent ADF content with the ticket description, or have the preview say that only visible text and pictures are compared.

Evidence: if not block or block.get("family") != "afkv2" or block.get("text") != preview["block_text"]:

## r-011 low test (test-veracity)
`afkv2/tests/skills/test_to_prd.py:569`

The bad-block cases assert words from the fake's own reason strings ('without an end', 'doubled'). The two port-error tests (573, 607) have the fake return a code and assert the same code back.

Why: These show that a port refusal is passed through. They do not show the real port's wording or its block-line rules, which could differ from the fake's.

Fix: Assert only the code and that nothing was written. Leave the wording check to the real-port test.

Evidence: ("[x, BEGIN, y]", "without an end") // fake: raise Refused("bad-block", "a begin line without an end line")

## r-012 low test (test-veracity)
`afkv2/tests/skills/test_to_prd.py:271`

The renumber cases cover AC removal, an AC swap and WE removal. No case renumbers or swaps two WE ids, or reuses a WE gap.

Why: AC-050 names both AC and WE ids as never renumbered, and a WE-only bug in renumber_problems would pass.

Fix: Add a case that swaps WE-01 and WE-02, and one that adds a WE id below the highest.

Evidence: (lambda text: text.replace("### WE-01 ", "### WE-02 "), "WE-01 is gone")

## r-013 low test (test-veracity)
`afkv2/tests/skills/fakes/fake_jira_port.py:160`

attachment-put never answers `no-media-id` (with attachment_id), though the contract lists it. The upload-failure test uses a generic server-error. A re-run after `no-media-id` is untested.

Why: This is a real failure that leaves an uploaded picture with no media id on the ticket. The kinder fake skips it.

Fix: Add FAKE_JIRA_FAIL=attachment-put:no-media-id with an attachment_id extra. Assert that a re-run adds no copy.

Evidence: return {"key": key, "attachment_id": str(number), "media_id": f"media-{number}", ...}  // contract Publish codes: `no-media-id` (carries `attachment_id`)

## r-014 low test (test-veracity)
`afkv2/tests/skills/test_to_prd.py:648`

`world.writes() == []` after a preview is always true, since preview never calls a write verb. The post-preview id-loss test checks only that description-put is absent. Pictures are uploaded before the id check (publish.py:393-399) and the test does not say whether that is allowed.

Why: AC-055 says the publish is refused, and the test does not pin whether any write happens first.

Fix: Drop the trivial assert. In the publish case, assert the intended attachment-put behaviour and the ticket state.

Evidence: error = world.preview(expect=1)["error"] ... assert world.writes() == []  // and line 656: assert "description-put" not in world.verbs()

## r-015 low test (test-veracity)
`afkv2/tests/skills/test_to_prd.py:627`

The 'short sections stay unchanged' and v1-replace tests run through the fake's own splice code (fake_jira_port.py:204-206). The real-port equivalents (838, 863) skip when ports/tracker/jira.py is absent, as on this branch.

Why: On this branch nothing runs the real splice, so AC-059 and the v1 replace are proven only against the fake until the real-port tests run.

Fix: Keep the skip but make the skip reason visible in the slice's verification record. Make sure the real-port tests run once S3 merges.

Evidence: if not (tree / "jira.py").is_file(): pytest.skip("the tracker port is not on this branch yet")

## r-016 low correctness (logic-correctness)
`afkv2/skills/to-prd/scripts/publish.py:35`

FENCE accepts only a bare info word. A fence such as ```` ```js title=x ```` is not seen as a fence, so its closing line is read as an opening one. Fence parity flips and a later ```` ```mermaid ```` fence stays a code block instead of becoming a picture.

Why: Markdown-it treats the whole info string as one fence, so extract_mermaid and the converter disagree on where fences start. The diagram silently goes to the ticket as code.

Fix: Match any info string (`(.*)`) and compare only its first word to `mermaid`.

Evidence: FENCE = re.compile(r"^ *(`{3,}|~{3,})[ \t]*(\S*)[ \t]*$"). Failing input: "```js title=x\ncode\n```\n\n```mermaid\ngraph TD\n```" gives sources == [] and the mermaid fence stays in the text.

## r-017 low correctness (logic-correctness)
`afkv2/skills/to-prd/scripts/publish.py:302`

An upload that reaches Jira but is not recorded in uploads.json leaves a copy, so a re-run adds another one. This covers `no-media-id` (the answer carries attachment_id, but nothing stores it), a crash before write_json, and a tracker timeout after the upload.

Why: SKILL.md promises a re-run adds no copy of a picture. The extra copies are removed only by a later successful publish, never if the developer stops.

Fix: On Refusal `no-media-id`, save its attachment_id in uploads.json (or delete it at once); correct the SKILL.md sentence.

Evidence: answer = tracker("attachment-put", {...})
        uploads[name] = {...}
        write_json(...)  /  SKILL.md: "a re-run adds no copy of a picture"

## r-018 low spec (spec-fidelity)
`afkv2/skills/to-prd/scripts/prd_files.py:127`

The id check compares with the last commit only. Ids renumbered in an earlier commit pass. `publish.py preview` never runs `check`, so the guard depends on the agent following SKILL step 4.

Why: AC-050 is only partly enforced, because the published text is not part of the comparison.

Fix: Have `preview` call `id_problems` and `renumber_problems`, or compare with the first commit that holds the PRD.

Evidence: run = subprocess.run(["git", "-C", str(prd.parent), "show", f"HEAD:./{prd.name}"],

## r-019 low spec (spec-fidelity)
`afkv2/skills/to-prd/scripts/publish.py:387`

In the `already_published` branch, `_note_published` rewrites the INDEX.md PRD row with today's date, though nothing was published. A failure in it (`bad-index` from `set_row`) would also fail a publish whose ticket write already succeeded, in the normal branch at line 407, before the deletes.

Why: A no-op re-run changes a file, and an INDEX.md fault can skip the picture clean-up after a good write.

Fix: Skip the INDEX.md update when `already_published`. Catch `Refusal` from `_note_published` and return it as `log_problem`, as `_record` does.

Evidence: _note_published(preview, now)
        return _publish_answer(preview, published=False, already_published=True,
