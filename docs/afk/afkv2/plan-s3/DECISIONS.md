# Decisions — auto-taken hands-off (protocol + grammar: DECISIONS.md, workflow plugin root). Newest last.

## D-1 — ground diff exit 1 for the INV-004 seams
- 2026-10-30 · decided by execute (0011-setup-skill)
- Options: A — re-run /afk:investigate for both seams vs B — accept the ground as held
- Chosen: B — `git diff 8e6ef1cfd1bd..HEAD` outside `docs/afk/afkv2/` is empty, so no v1 line moved; the reported drift comes from per-subject seeding against a ledger that ran 3 roots together, plus new spec files
- Supersedes: none
- To reverse: run /afk:investigate for the two §14 seams and compare its claims with setup.py

## D-2 — what the hook proof covers before the v1 block goes
- 2026-10-30 · decided by execute (0011-setup-skill)
- Options: A — proof of the current session's provider only vs B — a fired record for every provider that still uses v1, plus the current session's end marker
- Chosen: B — SDD §14 removes the block from both files in one run, and requirement ADR-0004 forbids a session with no rules; an untrusted Codex hook writes no fired record, so B catches it
- Supersedes: none
- To reverse: shrink `required_providers` in setup.py to the current provider

## D-3 — file names in the afkv2 data folder
- 2026-10-30 · decided by execute (0011-setup-skill)
- Options: A — wait for S1 to name the fired record vs B — use `hook-fired-<provider>.txt` and compare its modification time with the install record
- Chosen: B — SDD §4 fixes only "one file per provider, plain text"; the name is one constant in `places.py`, and S4 0016 runs the proof against the real hook
- Supersedes: none
- To reverse: change `Places.fired_record` to the name S1's hook writes

## D-4 — where the expected sha12 comes from
- 2026-10-30 · decided by execute (0011-setup-skill)
- Options: A — recompute SHA-256 over the text between the markers vs B — read the sha12 from the full begin and end lines of the prebuilt files in the plugin tree
- Chosen: B — S1's build check owns the hash and refuses a stale file (SDD §8 "marker hash"); a second hash implementation can disagree on line ends
- Supersedes: none
- To reverse: add a recompute in `expected_sha12s`

## D-5 — where setup stores the Jira values
- 2026-10-30 · decided by execute (0011-setup-skill)
- Options: A — always the environment vs B — the v1 tracker entry in `~/.claude.json` when it exists, else the user environment
- Chosen: B — SDD §5 Secrets: "looked up as v1 does (environment, then the Claude user config's tracker entry, then the Codex config)"; B keeps v1's place when v1 set it up and uses the first lookup source otherwise; afkv2 has no server entry of its own to write
- Supersedes: none
- To reverse: change `store_jira_values` in `jira_values.py`

## D-6 — the `.afkv2` config file setup writes
- 2026-10-30 · decided by execute (0011-setup-skill)
- Options: A — wait for S1's reader format vs B — `.afkv2/config.yaml`, v1's YAML subset, v1 top-level key names for copied blocks, a new `ownership:` block with `own` and `shared` lists
- Chosen: B — the reader (S1 0001) and the copy must agree on one file; v1's names keep the copy a verbatim block move; S4 0016 runs setup against the real reader
- Supersedes: none
- To reverse: change `AFKV2_CONFIG`, `COPIED_KEYS` and `write_ownership` in `repo_config.py`

## D-7 — Codex plugin switch is a config edit
- 2026-10-30 · decided by execute (0011-setup-skill)
- Options: A — a Codex command-line enable/disable vs B — edit `[plugins."<id>"] enabled` in the global `config.toml` with a backup
- Chosen: B — `codex plugin --help` (codex-cli 0.164.0) lists only add, list, marketplace and remove; this answers SDD §13 "Does Codex have a command-line plugin enable/disable?" with no
- Supersedes: none
- To reverse: call the command in `_switch_codex` when Codex adds one

## D-8 — both plugins enabled before the proof
- 2026-10-30 · decided by execute (0011-setup-skill)
- Options: A — turn afkv2 off when the proof fails vs B — leave both on until the proof passes, report it, refuse to finish the takeover with both on
- Chosen: B — the afkv2 hook can fire only while afkv2 is on, so A makes the proof impossible; AC-017's refusal applies to the switch step's read-back
- Supersedes: none
- To reverse: turn afkv2 off in the proof-failed branch of `takeover`

## D-9 — switch-back leaves one plugin on
- 2026-10-30 · decided by execute (0011-setup-skill)
- Options: A — restore every backup byte-identical and stop vs B — restore every backup byte-identical, then turn afkv2 off where the restored state still turns both on
- Chosen: B — the state before setup has both plugins on (D-8), so A leaves two rule sets per session (AC-017, requirement ADR-0004); the integration test checks byte-identity for every file and allows only the afkv2 enable value to differ
- Supersedes: 0011 contract `## Verification` integration row "switch-back → every file byte-identical to before" (the afkv2 enable value is the one difference)
- To reverse: drop `_leave_v1_only` from `switch_back`

## D-10 — switch-back keeps the exclude line and the local settings file
- 2026-10-30 · decided by execute (0011-setup-skill)
- Options: A — also remove the `info/exclude` line and delete the local settings file at switch-back vs B — keep both, with values that leave only v1 on
- Chosen: B — exclude is repository state git needs while `.claude/settings.local.json` exists, and the file must hold `afkv2: false` to keep AC-017 where the restored state turns both plugins on; D-9's "only the afkv2 enable value differs" holds for every file the developer had, and these two are the switch's own carrier
- Supersedes: D-9 phrase "allows only the afkv2 enable value to differ" (adds the exclude line and the local settings file that carry the value)
- To reverse: drop `_ensure_local_ignored` from the switch-back path of `_switch_claude`

## D-11 — the plugin switch keeps its settings file out of git
- 2026-10-30 · decided by execute (0011-setup-skill)
- Options: A — add a line to the repository's `info/exclude` when git does not already ignore `.claude/settings.local.json` vs B — write nothing and tell the developer to ignore the file
- Chosen: A — PRD AC-017 and ADR-0008 require the switch in the personal settings file "never the shared one"; an unignored file can be committed by `git add .` and turn the plugin off for the whole team, and B leaves that to memory. The line is the switch's carrier, so it has no backup: setup records that it added the line and removes that exact line at switch-back when the settings file is gone
- Supersedes: D-10 option B where the restored state already has only v1 on (then both the file and the line go)
- To reverse: drop `_ensure_local_ignored` and report the file as not ignored

## D-12 — switch-back keeps what the harness wrote after the takeover
- 2026-10-30 · decided by execute (0011-setup-skill)
- Options: A — overwrite Codex `config.toml` and the local settings with the takeover-time copy vs B — put back only the afk and afkv2 values, and write the backup's bytes when nothing else changed
- Chosen: B — both harnesses keep writing these files (Codex project trust, Claude permission grants), and A deletes those grants without a message; B stays byte-identical in the case the integration row tests. The instruction files already follow this rule through their `appended` branch
- Supersedes: 0011 contract `## Verification` integration row "switch-back → every file byte-identical to before", for a file changed since the takeover
- To reverse: restore the backup bytes in `restore_claude_local` and `_restore_codex_config`

## D-13 — the 0015 contract gets its test paths and the cross-session check input
- 2026-10-30 · decided by the plan author (slicing defect), applied by autopilot
- Options: A — fix the 0015 contract before it starts vs B — let 0015 run with the gap and park on a scope or tier miss
- Chosen: A — the contract named no path for the execute test or its fakes, no check for fresh subagent, TDD order and own commits, and a static glob that does not parse. The `check_plan` input stays an Acceptance bullet and is not a `## Consumes` line, because `validate_plan.py` refuses it: A-UNKNOWN-PRODUCER, 0010 is in plan-s2. The fake contract comes from the 0010 Acceptance (one JSON object, every failure, exit 0/1/2, "SDD §3 envelope"); the SDD §3 table has no row for the check script. The optional 0011 fakes-path line is not applied: 0011 is in review round 2, its fakes are in `afkv2/tests/setup/conftest.py`, and `afkv2/tests/setup/**` is already in its scope
- Supersedes: 0015 `## Verification` static row "every `afkv2/skills/autopilot afkv2/skills/execute/**/SKILL.md`"
- To reverse: revert this commit; 0015 has not started

## D-14 — a settings file whose `enabledPlugins` is not an object stops the takeover
- 2026-10-30 · decided by execute (0011-setup-skill)
- Options: A — read every falsy `enabledPlugins` (`[]`, `""`, `0`, `false`) as empty vs B — accept only an object or null, and refuse every other value
- Chosen: B — the takeover writes this key, and under A it replaces a value it cannot read without a message. Null reads as empty because it holds no value to lose. A refusal stops the takeover before any change and names the file. Unverified: whether Claude itself accepts such values
- Supersedes: none
- To reverse: test `data.get("enabledPlugins") or {}` in `plugins._read_json`

## D-15 — setup keeps its file names although the S1 branch chose others
- 2026-10-30 · decided by execute (0011-setup-skill)
- Options: A — change setup now to the names on the unmerged `feat/afkv2-s1` branch (`fired-<provider>.txt`, `.afkv2/config.json` with a required `spec_folder`) vs B — keep D-3 and D-6, record the mismatch, and reconcile when S1 merges
- Chosen: B — the run rule tests against a recorded fake until the producer's pull request merges, S1 can still change, and a code change now reopens the review at round 9 of 10. The failure of the fired record is safe: setup keeps the v1 block and reports why. The config mismatch has no safe failure: the S1 reader does not see the file setup writes. Unverified: which side yields on the config format; `spec_folder` has no value source in setup.
- Supersedes: none
- To reverse: apply the "To reverse" lines of D-3 and D-6 after S1 merges, before S4 0016 runs

## D-16 — ground diff exit 1 for the INV-002 seam
- 2026-10-30 · decided by execute (0012-forge-tracker-port)
- Options: A — re-run /afk:investigate for the seam vs B — accept the ground as held
- Chosen: B — `git diff 22ab4de0..HEAD` outside `docs/afk/afkv2`, `afkv2` and `.claude` is empty, so no v1 line moved; the drift has the same cause as D-1
- Supersedes: none
- To reverse: run /afk:investigate for the seam and compare its claims with `jira.py`

## D-17 — the receipt check reads a preview file
- 2026-10-30 · decided by execute (0012-forge-tracker-port)
- Options: A — the port only checks that `receipt` has the right form vs B — the payload names a preview JSON file (`ticket_key`, `receipt`, `description_hash`, `picture_hashes`), and the port checks the receipt, the ticket, `expect_hash` and each picture hash against it
- Chosen: B — SDD §5 refuses "without a receipt that matches the preview hash", and the SDD names no carrier. A cannot refuse a made-up receipt. The name of the file is the caller's choice. S2 0008 must write it and pass it: IOU in `.claude/wiring-ious.md`. Unverified: S2's preview format
- Supersedes: none
- To reverse: change `_preview_for` in `jira.py` to the carrier S2 builds

## D-18 — `issue-get` answers the description hash and a block summary
- 2026-10-30 · decided by execute (0012-forge-tracker-port)
- Options: A — the caller hashes and compares the ADF itself vs B — one hash and one summary (`family`, `text`, `media_ids`) in the port, in the answers of `issue-get` and `description-put`
- Chosen: B — a second hash in S2 can disagree with the stale check, and a compare of whole nodes fails on attributes Jira adds on read. The read-back compare is `put.block == read.block`
- Supersedes: none
- To reverse: drop `description_hash` and `block` from `issue_get`

## D-19 — the picture guards
- 2026-10-30 · decided by execute (0012-forge-tracker-port)
- Options: A — `attachment-put` takes a target name and `attachment-delete` deletes any id vs B — `attachment-put` takes the name of the file and refuses a name outside the pattern (`bad-name`); `attachment-delete` reads the attachment first and refuses a file that is not an afkv2 or v1 picture (`not-a-picture`)
- Chosen: B — PRD access row: the agent writes "one ticket's block and diagram pictures". A file a person attached stays out of reach, and an already deleted attachment answers `deleted: false`
- Supersedes: none
- To reverse: drop the name checks in `attachment_put` and `attachment_delete`

## D-20 — `ci-wait` exits 0 for every status it can read
- 2026-10-30 · decided by execute (0012-forge-tracker-port)
- Options: A — keep the v1 four-value exit code vs B — exit 0 with `status` in the answer; only 3 reads in a row with no status refuse (`unreadable`, exit 1)
- Chosen: B — SDD §3 fixes exit 0, 1 and 2 for every forge command, where 2 is unreadable input and v1's exit 2 and 3 have no place. A failed run is a readable answer, and the caller routes on `status`
- Supersedes: v1 `ci-wait` exit codes 0, 1, 2, 3 (ADR-0007 "v1 JSON answers": the answer stays, the exit code goes)
- To reverse: return `exit_code` from `status` in `common.ci_wait`

## D-21 — the forge verb list
- 2026-10-30 · decided by execute (0012-forge-tracker-port)
- Options: A — all 18 v1 commands vs B — 11: `auth-status, change-view, change-diff, change-create-draft, change-update-body, change-ready, change-comment, note-list, thread-list, ci-status, ci-wait`
- Chosen: B — ADR-0007 keeps only the commands the chain calls. 0013 posts findings, 0014 and 0015 open and update the change and read CI. No contract in plan-s3 replies to or resolves a thread. `change-fetch, change-state, change-reviewers, change-close, thread-reply, thread-resolve, commit-changes` answer `unknown-verb`. Unverified: a later slice can still need one
- Supersedes: none
- To reverse: port the verb into `github.py` and `gitlab.py` (ADR-0007 follow-up)

## D-22 — how the forge port finds its kind
- 2026-10-30 · decided by execute (0012-forge-tracker-port)
- Options: A — only the config reader vs B — payload `forge`, then `forge` in the reader's answer, then the host of the `origin` remote
- Chosen: B — the S1 reader on the unmerged branch answers no `forge` key, and SDD §8 says the forge port reads the config. `origin` is the same fact v1's checkout-derived call used. A host that names neither forge refuses `no-forge`. v1's `github.remote` key is gone: the payload `repo` replaces it. IOU to the reader in `.claude/wiring-ious.md`
- Supersedes: none
- To reverse: remove `_from_origin` in `forge/cli.py`

## D-23 — the same answer on both forges over the v1 literal shape
- 2026-10-30 · decided by execute (0012-forge-tracker-port)
- Options: A — copy each v1 answer as it was vs B — GitHub `change-view` answers `opened` (not `open`), GitHub `change-update-body` answers `was_draft` and `draft_restored`, a missing change is the code `not-found` (not `missing: true`)
- Chosen: B — PRD AC-066 asks for the same behaviour on both forges, and the SDD envelope replaces v1's error fields
- Supersedes: ADR-0007 "v1 JSON answers" at these 3 points
- To reverse: change `STATES` and `change_update_body` in `github.py`

## D-24 — the credential lookup reads only the `tracker` entry
- 2026-10-30 · decided by execute (0012-forge-tracker-port)
- Options: A — also read a `jira` entry when v1 wrote it vs B — only `tracker`
- Chosen: B — SDD §8 row "tracker port": own credential lookup; §5: "the Claude user config's tracker entry". v1's test for its own entry needs v1's setup code, which afkv2 does not load. The v1 test "own legacy entry is read" is dropped; the other v1 credential tests are ported
- Supersedes: none
- To reverse: add the legacy name to `_walk_for_jira_env`

## D-25 — `markdown-it-py` is imported only by `md-to-adf`
- 2026-10-30 · decided by execute (0012-forge-tracker-port)
- Options: A — import at the top of the module, as v1 does vs B — import in the function and refuse `missing-dependency` with the install command
- Chosen: B — every other verb works without the package, and the setup skill does not install it. A refusal names the fix. Unverified: which Python a developer's machine runs and whether it holds the package. IOU for setup in `.claude/wiring-ious.md`
- Supersedes: none
- To reverse: move the import to the top of `adf.py`

## D-26 — the forge port imports the envelope from the tracker folder
- 2026-10-30 · decided by execute (0012-forge-tracker-port)
- Options: A — a shared folder under `afkv2/ports` vs B — `tracker/envelope.py` and `tracker/shell.py` are the one home, and forge imports them
- Chosen: B — the contract's Scope is `afkv2/ports/tracker/**` and `afkv2/ports/forge/**`; a shared folder is outside it, and a copy breaks "one answer envelope with the tracker port" (ADR-0007)
- Supersedes: none
- To reverse: move both files to a shared folder and change the imports

## D-27 — v1 block lines and picture names live in one file
- 2026-10-30 · decided by execute (0012-forge-tracker-port)
- Options: A — keep the literals in `jira.py` vs B — `tracker/v1_facts.py`, as the setup skill keeps its v1 names
- Chosen: B — one place for the only v1 strings the port must know. S1's `plugin_check.check_no_v1_names` on the unmerged branch flags any such name in code and has no exemption, so it flags this file as it flags setup's. S4 0016 must add the exemption. A v1 begin line with another note text is plain text, so a block with it refuses `bad-block`, which is safe. Unverified: whether an older v1 release wrote another note text
- Supersedes: none
- To reverse: inline the constants in `jira.py`

## D-28 — the recorded Jira answers are hand-built
- 2026-10-30 · decided by execute (0012-forge-tracker-port)
- Options: A — park until the D-4 test project exists vs B — hand-built answers with a `_source` field, marked unverified
- Chosen: B — PLAN.md Inputs: the project is named by day 4, and the 0012 contract moves the live run to 0016. The answers follow the REST v3 issue shape and the ADF attributes the documentation lists. Unverified until 0016: how Jira normalises ADF on read
- Supersedes: none
- To reverse: replace `afkv2/tests/ports/recorded/*.json` from the live run

## D-29 — the port computes the receipt again from the text it writes
- 2026-10-30 · decided by execute (0012-forge-tracker-port)
- Options: A — compare only `receipt` with the preview file vs B — also compute the sha256 digest of key + block text + picture hashes from `adf`, and refuse a difference
- Chosen: B — with A, a valid preview and other `adf` writes text the developer never saw. `block_text` is defined by the port and answered by `md-to-adf`, so the skill and the port hash the same text. Figure nodes hold no text, so the preview text (no `figures`) equals the write text. Unverified: S2's preview code, which does not exist yet
- Supersedes: SDD §3 "description-put {key, adf, expect_hash, receipt}" and "attachment-put {key, png}": both also take `preview`, the path of the file D-17 names. Also D-17 "Supersedes: none"
- To reverse: remove `_check_text_is_previewed` in `jira.py`

## D-30 — the CI status is one closed word set on both forges
- 2026-10-30 · decided by execute (0012-forge-tracker-port)
- Options: A — pass the forge's own word vs B — map to `success`, `failed`, `canceled`, `running`, or empty
- Chosen: B — only named words read green. GitHub: `ERROR` and `STALE` read `failed`, every word not listed reads `running`. GitLab: `skipped` reads `success`, as GitHub `SKIPPED` does; `manual` and every word not final reads `running`, so `ci-wait` ends at its budget on a pipeline that waits for a human. A v1 defect on the ship path, not copied: v1 answered `success` for `ERROR`
- Supersedes: ADR-0007 "v1's ... JSON answers" for `status`
- To reverse: `_rollup` in `github.py`, `_ci_word` in `gitlab.py`

## D-31 — one rule for a rejected position
- 2026-10-30 · decided by execute (0012-forge-tracker-port)
- Options: A — keep v1, where GitHub refuses and GitLab can land a plain note vs B — with `require_inline` both refuse `position-rejected` and leave no comment; without it both land a plain note with `reason`
- Chosen: B — PRD AC-066 asks for the same behaviour. The GitLab status for a bad position (400) is from memory of its API: unverified live. The port treats 400 and 422 on that post as a rejected position
- Supersedes: ADR-0007 "v1's ... JSON answers" for `change-comment`
- To reverse: `change_comment` in `github.py` and `gitlab.py`

## D-32 — a lost draft flag on GitLab is a refusal
- 2026-10-30 · decided by execute (0012-forge-tracker-port)
- Options: A — v1: exit 0 with `draft_restored: false` vs B — refuse `draft-lost`
- Chosen: B — with A the same answer means "flag kept" and "the change is now open for review", and PRD AC-064 keeps the change Draft until ship
- Supersedes: ADR-0007 "v1's ... JSON answers" for this one failure
- To reverse: `change_update_body` in `gitlab.py`

## D-33 — the Jira answers are hand-built until the live run
- 2026-10-30 · decided by execute (0012-forge-tracker-port)
- Options: A — keep the word "recorded" vs B — name them hand-built: folder `afkv2/tests/ports/hand_built`, fixture `fake_jira`
- Chosen: B — no answer was recorded from Jira (D-28), and the name must not read as proof. An IOU sends the replacement to 0016, which has the D-4 test project
- Supersedes: 0012 Acceptance "runs against recorded Jira responses here": hand-built answers here, recorded answers in 0016. Also D-28 "Supersedes: none"
- To reverse: rename the folder after the live run

## D-34 — push is git, and GitLab has no live proof yet
- 2026-10-30 · decided by execute (0012-forge-tracker-port)
- Options: A — add a push verb vs B — no push verb: the 0015 Consumes line "push and change commands" reads as change commands from the port and a push through git
- Chosen: B — v1 had no push verb, and git is the same on both forges. Separately: `forge_round_trip.py` runs on GitHub only, because this repository has no GitLab change. All GitLab answers rest on fakes: unverified live. An IOU sends a GitLab round trip to the owner's run in 0016
- Supersedes: none
- To reverse: add the verb to both `VERBS` tables

## D-35 — the plugin check and the v1 strings
- 2026-10-30 · decided by execute (0012-forge-tracker-port)
- Options: A — hide the v1 strings from `check_no_v1_names` vs B — keep them in files named `v1_facts.py`, and the check exempts that file name
- Chosen: B — the first publish must recognise the v1 block (SDD §14), and hiding the strings defeats the check. The S1 check flags only `ports/tracker/v1_facts.py` of the port now, as read from `origin/feat/afkv2-s1`; `afkv2/skills/setup/scripts/v1_facts.py` has the same need. The tests pin the strings by digest, so they hold no v1 word; the digests were computed from the constants in v1's publish script. The exemption lives in `plugin_check.py`, which is outside the 0012 Scope and the 0016 Scope: an IOU names it
- Supersedes: none
- To reverse: inline the strings and remove the exemption

## D-36 — small changes to the port answers after review
- 2026-10-30 · decided by execute (0012-forge-tracker-port)
- Options: A — keep the answers vs B — `description-put` answers no `description_hash`, because it hashes the document as sent and is no `expect_hash`; `attachment-delete` answers `filename: null` when the file is gone; a GitHub key `owner/name#7` reads that repository, and a key that names another repository than `repo` refuses `bad-payload`; a `forge` or `tracker` value that is not a word is `bad-payload`; `attachment-delete` stays id-only (D-19), and the contract says that it checks only the file name
- Chosen: B — all are in the contracts now, before a consumer exists
- Supersedes: none
- To reverse: `jira.py`, `github_issues.py`, both `cli.py`

## D-37 — changes to the port after the second review pass
- 2026-10-30 · decided by execute (0012-forge-tracker-port)
- Options: A — keep the answers vs B — (1) GitHub `ACTION_REQUIRED` reads `running`, as GitLab `manual` does; (2) a failed first read of the draft flag refuses and writes nothing, on both forges, so `was_draft` has no `"unknown"`; (3) a failed read after the GitLab write sets the flag again; (4) a last `ci-wait` read with no status refuses `unreadable`; (5) GitLab `note-list` holds every note that is not on a line and not from the system, so a reply on a plain note is in `note-list`, and `thread-list` holds line comments only, as on GitHub; (6) a dash also ends a part of the host, and a host that names both forges refuses `no-forge`; (7) a GitHub key needs a number of digits
- Chosen: B — (1) ends a wait that a human can still end. (2) and (3) close the hole D-32 left open. (5) no comment is lost between the two verbs: the `DiscussionNote` type is from memory of the GitLab API, unverified live. The receipt binds visible text and picture bytes, as the SDD formula says: a link target, a node type or a media id is not in the hash, so D-29's "other `adf`" means other text
- Supersedes: ADR-0007 "v1's ... JSON answers" for items 1, 2, 4 and 5. D-30 for `ACTION_REQUIRED`. D-18 "in the answers of `issue-get` and `description-put`": `description-put` has answered no `description_hash` since D-36. Also D-36 "Supersedes: none"
- To reverse: `_rollup` and `change_update_body` in `github.py`; `change_update_body`, `note_list`, `_on_a_line` in `gitlab.py`; `ci_wait` in `common.py`; `_from_origin` in `cli.py`; `_repo_and_number` in `github_issues.py`

## D-38 — limits of the port after the third review pass
- 2026-10-30 · decided by execute (0012-forge-tracker-port)
- Options: A — GitHub reads the draft flag as best effort, because `gh pr edit` does not clear it vs B — one rule on both forges: a failed first read refuses and writes nothing. Separately: A — `ci-wait` refuses when the last read gave no status vs B — only when no read gave a status
- Chosen: B and B — the cost of the first is one refused body write on a GitHub read failure, and a retry fixes it: the same answer on both forges is what PRD AC-066 asks. The second keeps the evidence of a long wait when one read fails at the end. Known limit: the receipt does not bind a link target: the SDD formula sets what it binds, and S2 builds the same formula. A wider hash is an SDD change and an S2 change
- Supersedes: D-37 item 4
- To reverse: `change_update_body` in `github.py`; `ci_wait` in `common.py`

## D-39 — what round 3 does with a critical or high finding
- 2026-10-30 · decided by execute (0013-code-review-skill)
- Options: A — post every finding of round 3 and fix nothing vs B — fix as in every round, then stop; `finish` reports a fix of round 3 as `reviewed: false`, and posts each finding left unfixed
- Chosen: B — PRD AC-063: "Critical and high findings are fixed", and a finding it leaves is reported, so a reader sees what no reviewer read
- Supersedes: none
- To reverse: `_stop_reason` and `_report` in `review_rounds.py`

## D-40 — a new round exists only to review a fix of the last round
- 2026-10-30 · decided by execute (0013-code-review-skill)
- Options: A — always 3 rounds vs B — `begin` refuses `no-fix-to-review` when the last round made no fix
- Chosen: B — 3 is a cap (decision 46). A round with no new code has nothing new to read
- Supersedes: none
- To reverse: drop the `no-fix-to-review` check in `_new_round`

## D-41 — the review script imports the envelope from the tracker folder
- 2026-10-30 · decided by execute (0013-code-review-skill)
- Options: A — a second copy of the answer code in the skill vs B — `tracker/envelope.py`, the home D-26 names
- Chosen: B — SDD §3 fixes one answer shape, and SDD §8 lets a skill depend on a port. The skill calls the forge through its published command, not by import
- Supersedes: none
- To reverse: copy `serve` into `review_rounds.py`

## D-42 — one finding across rounds is the file plus its headline
- 2026-10-30 · decided by execute (0013-code-review-skill)
- Options: A — also the line vs B — file and the `finding` text, without case and extra spaces
- Chosen: B — a fix moves lines, and a repost on every round is noise on the change. Known limit: a reworded finding is a new finding and gets a second comment
- Supersedes: none
- To reverse: `_key` in `review_rounds.py`

## D-43 — the review needs a change before it starts
- 2026-10-30 · decided by execute (0013-code-review-skill)
- Options: A — review without a change and hold the posts vs B — `change` is a required input of `begin`
- Chosen: B — PRD SK-12 pushes to one Draft change per run, and 0015 opens it before it runs this skill; the PRD flow picture draws review before the change, and the catalog rows win. The caller also passes the plan folder and the base commit: IOU in `.claude/wiring-ious.md`
- Supersedes: PRD flow picture order "code-review" before "Draft change"
- To reverse: hold posts in the state until a `change` arrives

## D-44 — the same text at another line of one round is another defect
- 2026-10-30 · decided by execute (0013-code-review-skill)
- Options: A — add the line to the key vs B — keep D-42's key and add the rank of the line among the lines of that text in this round
- Chosen: B — a later round keeps one defect when its line moves, and 2 defects with the same words stay apart. Known limit: when 2 defects share their words and a later round finds only the second, it matches the first entry
- Supersedes: D-42 "file and the `finding` text" as the whole key
- To reverse: `_with_keys` in `review_rounds.py`

## D-45 — a later round matches a finding to the nearest line
- 2026-10-30 · decided by execute (0013-code-review-skill)
- Options: A — keep D-44's rank of the line vs B — one key for the text, and the entry with the nearest line wins; an entry seen in this round at another line does not match
- Chosen: B — with A, a later round that finds only the second of 2 defects reopens the first. Known limit: 2 defects with the same words on lines that a fix moves far apart can still swap
- Supersedes: D-44 "the rank of the line among the lines of that text in this round", and D-44's known limit
- To reverse: `_entry_of` in `review_rounds.py`

## D-46 — what "review settled" reads
- 2026-10-30 · decided by execute (0014-change-request-ci-watch)
- Options: A — read each `<plan>/review/<subtask>.rounds.json` vs B — run the code review's `finish` command for each contract in the plan folder
- Chosen: B — `finish` is the review's public report (`afkv2/skills/code-review/SKILL.md` "The result"), and the state file is that script's own. Settled: `finish` answers ok on this change, `left.blocking` is empty, `left.not_posted` is empty. A subtask with no review blocks Ready, so a parked subtask blocks ship. Cost: `finish` at ship stops a review that owes no more work, and it posts what is left. The PRD does not define "settled"
- Supersedes: none
- To reverse: `_why_open` in `ci_watch.py`

## D-47 — the watch is a process of its own, and its result is a record
- 2026-10-30 · decided by execute (0014-change-request-ci-watch)
- Options: A — the agent runs a blocking command as a background shell of the harness vs B — `start` starts a process and returns; the process writes one record per change in the git folder of the worktree; `status` reads it; a blocking `watch` remains for the wait at ship
- Chosen: B — A leaves "without blocking work" to each harness, and no test can prove it. The record goes with the worktree and is never a tracked file. A newer `start` takes over: the older process stops within 600 s and writes nothing. Unverified: the Codex background shell behind the `ci-running` row, and whether a harness job that refuses breakaway ends the process with the session
- Supersedes: none
- To reverse: `_spawn` and the `start` verb in `ci_watch.py`

## D-48 — every red CI, and no checks, refuse Ready
- 2026-10-30 · decided by execute (0014-change-request-ci-watch)
- Options: A — let a failure in code outside our ownership pass the gate vs B — the gate refuses `failed`, `canceled`, `running` and no checks; the developer marks Ready in those cases
- Chosen: B — PRD AC-064 needs "CI green" and AC-065 says "Ship is refused while CI is red". The port answers one word for the whole change, so the script cannot see which check failed or who owns it. A manual job reads `running`, and the port has no verb to start one, so the developer starts it
- Supersedes: issue #153 decision 28 "Failures outside our ownership do not block", at the Ready gate only; the skill still routes such a failure to a check of the target branch
- To reverse: pass a per-check answer from the port and read ownership in `mark_ready_if_green`

## D-49 — `open` replaces the whole description
- 2026-10-30 · decided by execute (0014-change-request-ci-watch)
- Options: A — add `body` to the port's `change-view` and keep text outside a marker block vs B — `open` writes the whole description; the title and the people are set only at creation
- Chosen: B — `afkv2/ports/forge/**` is outside this slice's Scope, `change-view` answers no body, and the port has no verb that sets reviewers on an open change. Known limit: a person's edit of the description is lost at the next `open`, without a message, so the skill sends notes to a comment. A person added later sees only the mention in the text. `open` runs at most twice per run in the planned flow: first commits and ship
- Supersedes: none
- To reverse: add `body` to `change-view` in `github.py` and `gitlab.py`, then merge in `open_change`

## D-50 — what "mergeability case" and "one self-critique" hold
- 2026-10-30 · decided by execute (0014-change-request-ci-watch)
- Options: A — free text only vs B — `merge-facts` gives git's answer (`git merge-tree`, ahead, behind, a fresh fetch), and the agent writes the case from it: facts, what it can break, how to undo. One self-critique is one pass and one text field
- Chosen: B — the PRD names both and defines neither (inferred meaning). A merge claim with no git read is a guess. The gate does not read `merge-facts`: PRD AC-064 sets the Ready conditions. A list in `self_critique` is refused
- Supersedes: issue #153 decision 31 "self-critique loop": PRD SK-14 says "one self-critique"
- To reverse: `merge_facts` and `_text` in `change_request.py`

## D-51 — 2 checks the PRD does not name
- 2026-10-30 · decided by execute (0014-change-request-ci-watch)
- Options: A — only review and CI vs B — also refuse `head-differs` at Ready, and `not-draft` after a create
- Chosen: B — a green CI on the forge says nothing about a local commit that was never pushed. The port answers `draft: true` from the flag it sent, so the read-back is the only proof of AC-064 "opens as Draft". Each is one call and refuses safe: the developer can still mark Ready
- Supersedes: none
- To reverse: the `head-differs` check in `mark_ready_if_green`; the read-back in `_create`

## D-52 — the order of the Ready gate, and who clears an open review
- 2026-10-30 · decided by execute (0014-change-request-ci-watch)
- Options: A — reviews first vs B — change state and head, then reviews, then CI vs C — CI before the reviews
- Chosen: B — `finish` stops a review, so a wrong id, a closed change or a head that differs must refuse first. The CI read stays last, because it must be the freshest read before `change-ready`. A review that a red CI stops loses nothing: `begin` already refuses a round with no new fix. Each entry of a `review-open` refusal now has `next`: `run-review`, `mark-again` (a failed post, which `finish` tries again) or `developer` (a review that has stopped and cannot clear)
- Supersedes: none
- To reverse: the order in `mark_ready_if_green`; `_why_open`

## D-53 — limits of "settled" and of the watch that stay
- 2026-10-30 · decided by execute (0014-change-request-ci-watch)
- Options: A — bind settled to a commit in the review state vs B — state the limit and show it to the developer
- Chosen: B — the review state names no commit, and the review command is in another subtask's Scope. A commit pushed after a review stopped gets no round: `begin` refuses `review-over`. The skill tells the agent to list each such commit in `proofs`. Unverified: how often this happens in a real run. Also accepted: a watch can pass its token check and then overwrite the record of a `start` that lands between the check and the write. The window is narrow, and the next push starts a new watch; a lock file costs more than this risk
- Supersedes: D-47 "the older process writes nothing", for this narrow window
- To reverse: add the commit to the review state and compare it in `_why_open`; add a lock around `_write_record`

## D-54 — the CI answer names no commit
- 2026-10-30 · decided by execute (0014-change-request-ci-watch)
- Options: A — add the commit to the port's `ci-status` and `ci-wait` answers in this slice vs B — record the limit, and route it to the feature gate
- Chosen: B — the forge port is outside this slice's Scope, and another session calls its contract. GitHub reads the rollup of the last commit. GitLab reads `head_pipeline`, which keeps the older pipeline until a new one exists (read from GitLab source by the verify pass; not tested live). So on GitLab, a mark just after a push can read the green result of an older commit. The "Wait" step of the skill narrows this, and it does not close it. The ledger key stays open for the feature gate
- Supersedes: none
- To reverse: add the commit to the port's answers and compare it with the head in `mark_ready_if_green` and `_end`

## D-55 — the 0015 contract names the skill, not the watch verbs
- 2026-10-30 · decided by execute (0014-change-request-ci-watch)
- Options: A — edit the 0015 contract vs B — leave the contract, state the gap in the IOU and the report
- Chosen: B — the plan's contracts belong to its author, and an execute run owns only its tracker cell. The skill's own sections call `start`, `status`, `watch` and `mark-ready`, so an agent that follows the skill runs them. 0015 Acceptance does not test this: the executor of 0015 must add the check, or the watch can stay unrun
- Supersedes: none
- To reverse: name the verbs in the 0015 Acceptance

## D-56 — the Ready gate reads the change before and after the reviews
- 2026-10-30 · decided by execute (0014-change-request-ci-watch)
- Options: A — one read of the change, as in D-52 vs B — read the change and its head before and after `finish`, and CI last vs C — also read CI before `finish`
- Chosen: B — the reviews can take minutes, so the head and the draft flag must be read again just before the CI read and `change-ready`. The cost is 1 more forge read at ship. C gives nothing: the verify pass read each review state `finish` can stop, and `begin` refuses a next round in each. So a CI fix has no round in either order (D-53)
- Supersedes: none; it adds to D-52
- To reverse: the second `_head_view` in `mark_ready_if_green`

## D-57 — a capped review with a fix no round read counts as settled
- 2026-10-30 · decided by execute (0014-change-request-ci-watch)
- Options: A — refuse Ready on `fixed[].reviewed: false` vs B — keep the D-46 reading: `left.blocking` and `left.not_posted` are empty
- Chosen: B — the review's cap is its own rule, and its report shows the unread fix to the developer. A refusal here has no route to clear: `begin` refuses `round-cap` and `review-over`
- Supersedes: none
- To reverse: read `fixed[].reviewed` in `_why_open`

## D-58 — the watch waits until the forge shows the pushed commit
- 2026-10-30 · decided by execute (0014-change-request-ci-watch)
- Options: A — take the first final status vs B — while the forge shows another commit, wait and read again, for at most 5 minutes
- Chosen: B — seen live on change 156: 2 `start` runs right after a push each ended in seconds with the status and the head of the last commit, so the new commit had no watch. After 5 minutes the watch ends with the commit the forge shows and `current_head: false`, so that a `start` with no push does not wait for its whole budget. Not closed: GitLab's `head_pipeline` can hold an older pipeline with the head correct (D-54)
- Supersedes: none
- To reverse: `_forge_behind` and `HEAD_GRACE` in `ci_watch.py`

## D-59 — owner ruling R-1: no adversarial gate on afkv2
- 2026-10-30 · decided by the owner (R-1, session brief)
- Options: A — run execute Step 10.5 vs B — skip it
- Chosen: B — owner: "Skip for afkv2". There is no running app to attack. Each slice records `adversary: skipped (owner ruling R-1)` in the journal
- Supersedes: execute "Driven mode" "adversarial gate included"
- To reverse: the owner withdraws R-1

## D-60 — owner ruling R-2: review loop has at most 3 rounds, and fixes only critical and high
- 2026-10-30 · decided by the owner (R-2, session brief)
- Options: A — settle up to 10 rounds and fix or dispute every finding vs B — at most 3 rounds per slice; medium and low findings stay on the pull request as advisory, with no fix and no dispute round
- Chosen: B — owner ruling. After round 3, an open critical or high finding parks the slice; otherwise the gate passes. Applies to 0013, 0014 and 0015. 0011 and 0012 settled before this ruling
- Supersedes: SETTLEMENT.md round cap of 10 and its fix-or-dispute rule for medium and low findings
- To reverse: the owner withdraws R-2

## D-61 — owner ruling R-3: a note that changes sign-off wording sends the card back
- 2026-10-30 · decided by the owner (R-3, session brief)
- Options: A — a wording note keeps the sign mark vs B — the card goes back for a sign mark
- Chosen: B — owner ruling; it closes S2 D-15 / f074. No plan-s3 contract names HL-4, so no S3 slice changes (grep on plan-s3 contracts, setup, code-review and ports)
- Supersedes: none in plan-s3
- To reverse: the owner withdraws R-3

## D-62 — owner ruling R-4: pre-commit gates may be skipped on afkv2 commits
- 2026-10-30 · decided by the owner (R-4, session brief)
- Options: A — skip only for spec-folder commits and v1-layout refusals vs B — skip all pre-commit gates on afkv2 commits
- Chosen: B — owner ruling for this build. Pull-request CI catches the rest, and the ship gate must be green. Skipped commits stay listed in the journal
- Supersedes: session brief rule that a skip needs a v1-layout refusal
- To reverse: the owner withdraws R-4

## D-63 — round 3 of 0014 ends by D-60, with no clean marker
- 2026-10-30 · decided by execute (0014-change-request-ci-watch)
- Options: A — write `clean=true` at the fix head so that `gate --phase closure` passes vs B — write the round 3 summary with `clean=false` at the head that round read, and take the gate result from D-60
- Chosen: B — no review round read the fix of the 2 high findings, and a clean marker would say that one did. Their proof is 2 new tests, each seen to fail on the old behaviour. The 9 medium and low findings of round 3 stay open on the change as `deferred gate=advisory`, so that no later gate reads them as owed. `gate --phase closure` refuses this state, as expected; D-60 replaces it for this slice
- Supersedes: none
- To reverse: run another review round on the tip and write a clean summary

## D-64 — 3 wrong record comments of 0013 were deleted outside the ledger verbs
- 2026-10-30 · decided by execute (0013-code-review-skill)
- Options: A — keep the 3 `fixed` records with sha d0e07482 vs B — delete them with `gh api -X DELETE` and write them again with sha 50d44790
- Chosen: B — the earlier agent of this slice took this action and did not record it; this entry records it after the fact. It wrote the 3 records on change 156 for f013, f014 and f015 with a telemetry commit that has no `Settles:` trailer. `fixed` is terminal, so closure could never pass. It deleted only those 3 comments, its own (ids 4423544149, 4423551306, 4423558267), and `reconstruct` now shows the 3 keys `fixed` at 50d44790. Source: that agent's transcript. The deleted bodies were not read in this run (unverified)
- Supersedes: none
- To reverse: write no new record; the earlier comments cannot be restored, and their content is in the transcript

## D-65 — round 3 of 0013 is recorded at the head it read, and passes by D-60
- 2026-10-30 · decided by execute (0013-code-review-skill)
- Options: A — write `clean=true` at the current tip so that `gate --phase closure` passes vs B — run the round again vs C — write `clean=true` at d0e07482, the head that the round read, and take the gate result from D-60
- Chosen: C — round 3 did run: its 2 reviewers (delta-sweep, test-veracity) read d0e07482 and both returned an empty list, but the stopped agent wrote no record of it. A new run would be a 4th round, which D-60 forbids. A marker at the tip would name a head that no round read. No file of this slice changed from d0e07482 to the tip. `gate --phase closure` refuses, as expected: "summary does not describe the requested final head and round". All 15 keys are `fixed` with resolved threads, and no critical or high finding is open, so D-60 passes the gate
- Supersedes: none
- To reverse: run another review round on the tip and write a clean summary

## D-66 — 0013 and 0015 get the new SDD §7 v1-defect bullets
- 2026-10-30 · decided by the plan author (SDD commit 05ef43e8), applied by autopilot
- Options: A — add the Acceptance bullets now vs B — leave the contracts and test the rows only in S4 0016
- Chosen: A — the rows name "0013 test" and "0015 start-gate test" as their checks. 0013 is in its re-run: `test_next_round_stops_after_round_3`, `test_route_sends_critical_and_high_to_fix_and_medium_and_low_to_post` and `test_record_routes_each_severity_and_posts_only_medium_and_low` already cover its bullet (read by name; run by its executor). 0015 has not started; its unit row and excerpts also carry the rule
- Supersedes: none
- To reverse: revert this commit

## D-67 — the SDD §7 bullet of 0013 needs no new test
- 2026-10-30 · decided by execute (0013-code-review-skill)
- Options: A — add a test for the bullet of D-66 vs B — keep the tests that exist
- Chosen: B — each clause has a test, and each test failed when the rule was changed in memory. Round cap: `test_next_round_stops_after_round_3` and `test_round_4_is_refused_whatever_is_left` fail at a cap of 2 and of 4. Only critical and high are fixed: `test_route_sends_critical_and_high_to_fix_and_medium_and_low_to_post` and `test_record_routes_each_severity_and_posts_only_medium_and_low` fail when every severity goes to fix, and when only critical does. The rest stay as advice: the same 2 tests fail when no finding is posted; the record test also proves that the only forge calls are 2 `change-comment` calls, so no thread is resolved; `outcome` refuses a medium finding (`no-such-finding`); and `test_finish_after_a_round_with_nothing_to_fix_stops_clean` reports a low finding under `left.posted` with `stopped_by` `clean`. Not proved: the comment text does not say the word "advice" and no test asks for it (the severity label and `left.posted` carry that meaning). No code changed, so no review round is owed and D-65 still holds
- Supersedes: none
- To reverse: add the test to `afkv2/tests/skills/test_code_review.py`

## D-68 — 0015 chooses how a plan names a gate not applicable
- 2026-10-30 · decided by autopilot (orchestrator ruling, this one fork)
- Options: A — 0015 parks until the owner or S2 names the format vs B — 0015 chooses one format, records it, and leaves an IOU for S2 0010 to emit it
- Chosen: B — SDD §7 says "the plan names it not applicable" and defines no form. 0010 is pending on `feat/afkv2-s2`, and a grep of its branch finds no such form, so no caller exists to break. The form is one edit in 0015 and one in 0010. Any other fork that 0015 parks on needs a new ruling
- Supersedes: none
- To reverse: change the parser in `start_gate.py` to the form S2 builds
