# Review 0008-to-prd-jira-publish, round 2

Policy: lean. Delta round. Activated: delta-sweep, logic-correctness (it owned the high fixed in round 1), test-veracity (the delta touches test code). Deferred to the feature gate: code-quality, agents-md-compliance, design-quality, resilience.

Verdict: advisory. Critical 0, high 0, medium 1, low 2.

## r-001 medium test (test-veracity)
`afkv2/tests/skills/test_to_prd.py:696`

The new test uses a one-picture PRD with the upload record fully missing. It never tests a record that lists only some of the pictures. It also never tests a record whose media ids differ from the block's.

Why: Changing `all(name in uploads for name in names)` to `any(...)` leaves this test green, because with one picture `all` and `any` give the same answer. A record with only some pictures would then count as published with no test failing.

Fix: Add a case with 2 diagrams where uploads.json is edited to keep only the first picture. Assert `already_published` is False. Add one case where the recorded media id differs from the block's media id.

Evidence: return all(name in uploads for name in names) and media == [uploads[name]["media_id"] for name in names]   /   (world.run_dir / "uploads.json").unlink()

## r-002 low correctness (logic-correctness)
`afkv2/skills/to-prd/scripts/publish.py:239`

`_already_published` checks that each picture NAME is on the ticket (line 237), not that the recorded `attachment_id` is. If the recorded attachment was deleted by hand and a same-named copy exists, the check can return True. The live block then points at a dead media id, and the cleanup deletes the surviving copy.

Why: This needs a same-named duplicate and a hand-deleted recorded attachment. A sequence of publish tool calls cannot produce it, because `_upload_pictures` rewrites `uploads.json` whenever it re-uploads. So it is not load-bearing.

Fix: Also require `{str(uploads[n]['attachment_id']) for n in names} <= {str(a.get('id')) for a in attachments}` before returning True.

Evidence: return all(name in uploads for name in names) and media == [uploads[name]["media_id"] for name in names]

## r-003 low test (test-veracity)
`afkv2/tests/skills/test_to_prd.py:714`

After the second publish the test asserts only that the media ids differ from the old ones. It does not assert the block holds the media id of the picture kept on the ticket.

Why: Any wrong media id would pass this, so a block that points at a different or deleted picture could still pass as long as the id is not the old one.

Fix: Assert `_block_media(world)` equals the media id of the attachment now on the ticket. In the fake that is `media-<attachment id>`.

Evidence: assert _block_media(world) != old_media
