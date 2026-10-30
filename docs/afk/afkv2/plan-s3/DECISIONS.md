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
