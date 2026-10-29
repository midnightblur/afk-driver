# Decisions — auto-taken hands-off (protocol + grammar: DECISIONS.md, workflow plugin root). Newest last.

## D-1 — How to re-take the ground of the safe writer seam
- 2026-10-27 · decided by /afk:execute (0001-safe-writer)
- Options: A — re-run INV-010 whole (its 9 subjects, type Q1, every settings writer) vs B — a fresh Q3 run on the moved names only (`_atomic_write_locked`, `_target_lock`, `write_if_unchanged`, `InstallError`, `update_locked`, `SafeWriteError`)
- Chosen: B — `git diff 2e93489 288b4b3` is empty for `install_block.py`, its tests and its callers (`developer_values.py`, `setup_secrets.py`, `set_instruction_files.py`, `hook-smoke.sh`); the ground diff's drift lies in files other INV-010 subjects hit, which later slices own
- Supersedes: none
- To reverse: run /afk:investigate on the INV-010 question at the branch head and compare its claims with SDD §14 row "safe writer"

## D-2 — Where the adversarial gate probes in a repository that runs no app
- 2026-10-27 · decided by /afk:execute (0001-safe-writer)
- Options: A — report `env_unreachable` and park the slice vs B — probe the shipped module and CLI at runtime with the repository's interpreter in a scratch folder, blind to the diff and tests
- Chosen: B — the slice's promises are behaviour of a library call and a CLI, observable by running them; A parks every slice of a repository that declares no app, which the run's invoker ruled out
- Supersedes: none
- To reverse: re-run Step 10.5 against a provisioned app instance once the repository declares one

## D-3 — What to do with stray copies of other worktrees inside this worktree
- 2026-10-27 · decided by /afk:execute (0001-safe-writer)
- Options: A — stop with `test_fail`, since `test_model_tier_gate.py::test_committed_tree_agrees_with_the_tier_table` scans the ignored `.claude/worktrees/` copies and fails on their old `AGENTS.md` vs B — move those 9 ignored, unregistered copies (962 KB) to the session scratch folder and re-run
- Chosen: B — `git worktree list` registers none of them, git ignores them, no tracked file changes, and the gate passes on the tree without them; the failure is not in the slice's code
- Supersedes: none
- To reverse: move the 9 folders back into this worktree's `.claude/worktrees/`

## D-4 — How to clear the red unit tier that predates the first slice
- 2026-10-27 · decided by /afk:autopilot (run orchestrator)
- Options: A — make the review-id check and the redactor skip `investigations/*/COVERAGE.json` vs B — mask the quoted fixture values (test secrets, one review id) in the five ledgers that quote them vs C — park the whole plan for a human
- Chosen: B — the failures come from this branch's own spec commit, not plugin code; masking changes evidence text only, which the coverage validator checks for presence, and all five ledgers keep their verdicts; A changes two scanners' behaviour and belongs in its own reviewed change
- Supersedes: none
- To reverse: revert the ledger-masking commit on the branch

## D-5 — Correct the caller list D-1 cites
- 2026-10-27 · decided by /afk:execute (0001-safe-writer)
- Options: A — leave D-1's caller list as written vs B — record the real callers and re-check the diff on them
- Chosen: B — `developer_values.py`, `setup_secrets.py` and `set_instruction_files.py` never load `install_block.py`; its real callers are `hooks/tests/hook-smoke.sh`, `skills/afk/setup/SKILL.md`, `skills/afk/setup/MANIFEST.md` (CLI runs) and `scripts/behavior_registry.py` (`REQUIRED_INSTALL_TESTS`); `git diff 2e93489 288b4b3` on them touches no installer call line or required test name, so D-1's choice holds
- Supersedes: D-1 "Chosen" caller list `developer_values.py`, `setup_secrets.py`, `set_instruction_files.py`, `hook-smoke.sh`
- To reverse: none needed; D-1's option B stands on the corrected list

## D-6 — Fix a stale test docstring under the "installer tests unchanged" bullet
- 2026-10-27 · decided by /afk:execute (0001-safe-writer)
- Options: A — keep `scripts/tests/test_install_block.py` byte-identical vs B — update one docstring that names the removed `_LOCK_MAX_ATTEMPTS` constant, no assertion touched
- Chosen: B — the Acceptance bullet guards the installer contract the assertions pin; a docstring that names a constant the slice removed is a stale artifact (`FRESHNESS.md` "no artifact goes stale")
- Supersedes: none
- To reverse: revert the docstring lines in `_run_holder_contender`

## D-7 — Correct INV-023's busy-swap exit code
- 2026-10-27 · decided by /afk:execute (0001-safe-writer)
- Options: A — rewrite INV-023's `REPORT.md` vs B — leave the ledger untouched and record the correction here
- Chosen: B — `/afk:investigate` is the single writer of a ledger; the old `main()` (`git show 288b4b3:skills/afk/setup/scripts/install_block.py`, lines 334 and 359) already caught `OSError`, so a busy swap exited 2 before the slice too; the only caller-visible change is up to 10 retries at 50 ms and the message `target file swap stayed busy: <path>`
- Supersedes: INV-023 `REPORT.md` "instead of a traceback (exit 1)"
- To reverse: none needed; a fresh `/afk:investigate` run would carry the corrected line

## D-8 — Refuse a read-only file at once on Windows
- 2026-10-27 · decided by /afk:execute (0001-safe-writer)
- Options: A — treat a denied replace onto a read-only file as a busy swap (10 retries, "file swap stayed busy") vs B — refuse it at once as "is read-only", naming the file
- Chosen: B — SDD §7's retry row covers a busy swap; a read-only file is a permanent denial no retry clears, and A gave the user the wrong cause; the error type, the unchanged file and the installer's exit code stay as SDD §7 and ADR-0005 state
- Supersedes: none (narrows SDD §7 "file swap busy on Windows" to busy files)
- To reverse: drop the `os.access` check in `_swap` of `scripts/safe_write.py`

## D-9 — Keep INV-013 and INV-004 as the ground for 0002-settings-reader
- 2026-10-27 · decided by /afk:execute (0002-settings-reader)
- Options: A — re-run `/afk:investigate` on both seams vs B — keep both ledgers after reading the ground diff
- Chosen: B — the ground diff since the ledgers touches no line of `scripts/afk-config.py` or `hooks/precommit-gates.sh`; its one new node is a machine-file test fixture, which reads the same `load()` the ledgers trace (D-1 precedent)
- Supersedes: none
- To reverse: run `/afk:investigate` on INV-013 and INV-004 and re-check the slice against the new ledgers

## D-10 — Read rules for the two files catalog S does not name
- 2026-10-27 · decided by /afk:execute (0002-settings-reader)
- Options: A — filter `.afk/config.local.yaml` and `$AFK_CONFIG` like the committed file vs B — the local overlay follows the repository personal file's rules, `$AFK_CONFIG` is not filtered except that removed keys are dropped; a team value in the machine file is ignored
- Chosen: B — both are the developer's own files, so a personal value must stay readable there; `$AFK_CONFIG` is an explicit file a person or test names on purpose; catalog S reads a team setting only from the committed file or the repository personal file, so the machine file holds no team value
- Supersedes: none
- To reverse: edit `_READS` in `scripts/afk-config.py` and the "Setting owners" section of `CONFIG.md`

## D-11 — Root every file-backed notes kind at the checkout
- 2026-10-27 · decided by /afk:execute (0002-settings-reader)
- Options: A — keep each kind's `notes_root` (the vault for obsidian) vs B — `adapters/notes/common.sh` renders `repo-files.spec-dir` under the checkout's top folder for every kind
- Chosen: B — ADR-0003 (requirements) puts every agent working file in the repository's spec folder whatever app is chosen; the kinds' `notes_root` functions become unused and their headers stale, which the out-of-scope files carry until a later slice edits them
- Supersedes: none
- To reverse: restore the `notes_root` call in `notes_main` of `adapters/notes/common.sh`

## D-12 — Keep init's machine-file TODO and say the value is not read
- 2026-10-27 · decided by /afk:execute (0002-settings-reader)
- Options: A — filter the machine file in `_machine_layer`, so `init` stops offering the machine file's tracker or forge vs B — keep the commented `TODO` line and change its text and `CONFIG.md` "init" to say a team setting is not read from the machine file, so the developer uncomments it to pin it
- Chosen: B — SDD §4 Migration ignores a team value in the machine file; B keeps the developer's hint with no new behavior, and 0009-settings-writer reworks `init` from the personal file
- Supersedes: none
- To reverse: restore the old `_inherited_line` text in `scripts/afk-config.py` and the "init" paragraph in `CONFIG.md`

## D-13 — Write a marker under the list's lock with the safe writer's unlocked replace
- 2026-10-27 · decided by /afk:execute (0003-repository-list)
- Options: A — write the marker with `update_locked`, which puts `.afk-repository.afk.lock` in the short name's folder vs B — call `safe_write._replace_if_unchanged` (compare, temp file, one replace, no lock of its own) from inside the list's `update_locked` transform vs C — add a public unlocked write to `scripts/safe_write.py`, outside this slice's Scope
- Chosen: B — ADR-0005 (design) and SDD §4 require the marker written under the list's lock with no lock file under the root; A breaks that, C needs a re-slice; B keeps the safe writer's change refusal and temp-file cleanup
- Supersedes: none (SDD §8 row "safe writer": "one call" stays the only public interface)
- To reverse: add a public unlocked write to `scripts/safe_write.py` and call it from `_claim_folder` in `scripts/repo_list.py`

## D-14 — An empty short-name folder counts as absent
- 2026-10-27 · decided by /afk:execute (0003-repository-list)
- Options: A — refuse any existing folder without a marker vs B — claim an empty folder; refuse a folder that holds anything and has no marker of this path
- Chosen: B — an empty folder holds nothing setup could damage, and a run stopped between making the folder and writing the marker leaves one; catalog R R-06 guards a folder made for another repository, which holds a marker or content
- Supersedes: PRD catalog R R-06 "the short name's folder under the root is absent" — narrowed to "absent or empty"
- To reverse: drop the empty-folder clause in `_claim_folder` of `scripts/repo_list.py`

## D-15 — Re-take the safe writer seam's ground with a fresh question on the moved call
- 2026-10-27 · decided by /afk:execute (0003-repository-list)
- Options: A — diff against INV-010, whose subject `_atomic_write_locked` no longer exists in code vs B — diff against INV-023 (the move's ledger, D-1 and D-5), and on drift run one fresh Q1 on `update_locked` and `SafeWriteError` at the branch head
- Chosen: B — INV-023's ground moved (review fixes in `scripts/safe_write.py`, `scripts/tests/test_safe_write.py`, `scripts/tests/test_install_block.py`); the fresh run at f53fef5 is `closed-with-frontier`, and no claim it makes contradicts SDD §8 row "safe writer" or ADR-0005 (design); its claim that `update_locked` puts a lock file beside every file it writes is the ground of D-13. Its ledger stays in the run's scratch folder (named in the slice's outcome report): the native contract gate's check K matches a provider helper's file name inside the name of that helper's unit test, which the seed map lists as a site, and refuses the ledger
- Supersedes: the `## Seams` row of `plan/0003-repository-list.md` citing INV-010 — this slice stands on the fresh run
- To reverse: run `/afk:investigate` on the INV-010 question at the branch head and publish it in the spec folder once check K skips ledger text

## D-16 — Find an entry by path text alone; a caller resolves a far worktree first
- 2026-10-27 · decided by /afk:execute (0003-repository-list)
- Options: A — `find_entry` reads a worktree's `.git` pointer to reach its main checkout vs B — `find_entry` matches path text against the list file alone (the main checkout, or `<root>/<shortName>` when the root is passed); a worktree elsewhere finds nothing until the caller passes `main_checkout(path)`
- Chosen: B — the Acceptance bullet "Finding the entry for a path reads only the list file" (PRD §Session scope AC-080) forbids reading a pointer file; worktrees setup makes sit under `<root>/<shortName>`, and ADR-0002 (design) lets placement start git for an unusual layout
- Supersedes: the Goal of `plan/0003-repository-list.md` "finds the entry for any path (main checkout, worktree, subfolder)" — narrowed to worktrees inside the main checkout or under `<root>/<shortName>`
- To reverse: resolve a worktree's `.git` pointer in `find_entry` of `scripts/repo_list.py` and drop the list-file-only test

## D-17 — Refuse a trailing dot and a device name as a short name on Windows only
- 2026-10-27 · decided by /afk:execute (0003-repository-list)
- Options: A — keep SDD §4's set alone (letters, digits, dot, dash, underscore) vs B — also refuse, on Windows only, a name ending in a dot and a device name (`CON`, `NUL`, `COM1`, ...), and refuse `.` and `..` everywhere
- Chosen: B — Windows drops a trailing dot from a folder name and opens a device for a device name, so the marker would land in another folder or fail; `.` and `..` name no new folder
- Supersedes: SDD §4 `entry.shortName` "one folder name: letters, digits, dot, dash, underscore" — narrowed on Windows
- To reverse: drop the trailing-dot and device-name checks in `_check_short_name` of `scripts/repo_list.py`

## D-18 — Take a submodule's working folder as its main checkout
- 2026-10-27 · decided by /afk:execute (0003-repository-list)
- Options: A — store the folder `git worktree list` names first, which is the git folder (`.git/modules/<name>`) for a submodule and for a clone made with a separate git folder vs B — when that folder holds no `.git`, take its `core.worktree`, else the top level of the path's own checkout when the path is that checkout, else refuse
- Chosen: B — A stores a git folder as a main checkout, against the Acceptance bullet "a path to a worktree or a subfolder adds that worktree's main checkout"; git cannot name the main checkout of a separate git folder from its linked worktree, so that one case is refused with its reason
- Supersedes: none
- To reverse: drop `_apart_main` from `scripts/repo_list.py`

## D-19 — A failed folder release leaves the marker, and a later remove deletes it
- 2026-10-27 · decided by /afk:execute (0003-repository-list)
- Options: A — raise when the release after the list write fails, though the entry is already gone vs B — return `folder_deleted` false and let a later `remove_repository` of that short name delete a marker that holds a path no entry lists, when the folder holds only the marker
- Chosen: B — the list write is the remove; the release cannot share its lock (`update_locked` has no step after the write), and B gives the left marker a way out through the same call instead of blocking the short name until a hand delete
- Supersedes: SDD §4 relation "list entry → marker" "empty folder and marker deleted" — narrowed to "deleted by this remove, or by a later remove of the short name when the deletion failed"
- To reverse: drop `_left_marker` and widen the release `except` in `remove_repository` of `scripts/repo_list.py`

## D-20 — Name what D-16 and D-18 narrow
- 2026-10-27 · decided by /afk:execute (0003-repository-list)
- Options: A — leave D-16 pointing callers at `main_checkout` and D-18 at "Supersedes: none" vs B — D-16 names no list-module call for a worktree outside the main checkout and `<root>/<shortName>` (placement starts its own git for such a layout, ADR-0002 (design)); D-18 narrows AC-003 and the `GLOSSARY.md` "main checkout" reading for a separate git folder
- Chosen: B — `main_checkout` is in neither the slice's Produces nor 0004's Consumes, and the two narrowings belong on the record
- Supersedes: D-16 "until the caller passes `main_checkout(path)`" — dropped; the Acceptance bullet of `plan/0003-repository-list.md` "a path to a worktree or a subfolder adds that worktree's main checkout" — narrowed: a linked worktree of a clone with a separate git folder and no `core.worktree` is refused; `GLOSSARY.md` "Main checkout" as the first entry of `git worktree list` — for a submodule or a separate git folder it is that folder's working folder
- To reverse: restore the `main_checkout(path)` sentence in the module docstring of `scripts/repo_list.py`

## D-21 — A short name longer than 255 characters is refused
- 2026-10-27 · decided by /afk:execute (0003-repository-list)
- Options: A — let the file system refuse the folder, which reads as an unreadable marker on Linux and a raw path error on Windows vs B — refuse a short name longer than 255 characters as not valid, on every system
- Chosen: B — 255 is the common folder-name limit on Windows, macOS and Linux file systems, and setup then asks for another name with one reason everywhere
- Supersedes: none — PRD catalog R R-05 sets no length; this adds a limit
- To reverse: drop the length check in `_check_short_name` of `scripts/repo_list.py`

## D-22 — Report the two new developer keys in the setup status without asking for them
- 2026-10-27 · decided by /afk:execute (0002-settings-reader)
- Options: A — add `worktreeRoot` and `forgeAccount` to `ORDER` alone, which makes `status` fail with a missing-key error vs B — add them to `ORDER` and give both the need `n/a` and no suggestion in `status`, so setup reports their value and source but never asks for them
- Chosen: B — the Acceptance bullet needs `ORDER` to cover both keys, and `status` reads one need and one suggestion per key in `ORDER`; `n/a` keeps the setup walk unchanged until 0004-placement, 0007-forge-account and 0010-setup-walk give each key its question; `set` accepts both keys as for every key in `ORDER`, and 0009-settings-writer makes it refuse a key sent to a file its owner does not read
- Supersedes: the Scope note "skills/afk/setup/scripts/developer_values.py — key order only" of `plan/0002-settings-reader.md` — widened to the two `status` table rows the key order needs
- To reverse: drop the `worktreeRoot` and `forgeAccount` rows from `ORDER`, `need` and `suggest` in `skills/afk/setup/scripts/developer_values.py`

## D-23 — Without Python, stop reading the machine file for repo-hooks and leave the rest of the narrowing to the human
- 2026-10-27 · decided by /afk:execute (0002-settings-reader)
- Options: A — make the no-Python commit check read only the files the owner rule reads for a team setting, which breaks `test_without_the_launcher_a_repo_hooks_key_in_the_local_layer_blocks` in `scripts/tests/test_precommit_order.py`, outside Scope vs B — drop only the machine file from that check, so it still blocks on a local overlay or personal file beside a committed file, and carry the rest of review key f002
- Chosen: B — the Scope hard rule forbids editing the out-of-scope test; B can only block more often than the reader would, never let a declared hook go unrun
- Supersedes: none
- To reverse: put `"${HOME:-/nonexistent}/.afk/config.yaml"` back in the layer loop of the no-launcher branch of `hooks/precommit-gates.sh`

## D-24 — Report a developer value's source only from a file the owner rule reads
- 2026-10-27 · decided by /afk:execute (0002-settings-reader)
- Options: A — leave `status` naming the first file that holds the key, even when the reader ignored it there vs B — name the source by the new `layer_reads` of `scripts/afk-config.py`, which `_owner_filter` also uses
- Chosen: B — review key f011 found `status` naming a file whose value the reader dropped; B keeps one statement of which owners each file is read for
- Supersedes: the Scope note "skills/afk/setup/scripts/developer_values.py — key order only" of `plan/0002-settings-reader.md`, already widened by D-22 — widened again to the source lookup in `status`
- To reverse: restore the label-only `files` list and the source lookup in `status` of `skills/afk/setup/scripts/developer_values.py`

## D-25 — Leave the dependency register's obsidian row to 0010-setup-walk
- 2026-10-27 · decided by /afk:execute (0002-settings-reader)
- Options: A — park the slice again, because `skills/afk/setup/MANIFEST.md` still names `adapters/notes/obsidian/notes.sh` as the reader of `AFK_CFG_OBSIDIAN_VAULT` after this slice deletes that read vs B — delete the dead read inside Scope and leave that one register row to 0010-setup-walk, whose Scope lists `skills/afk/setup/MANIFEST.md`
- Chosen: B — the row is one table cell in a file a later slice of this plan already edits; a third park for it costs more than the stale cell, and the reader still exports the variable, so no caller breaks
- Supersedes: `FRESHNESS.md` same-commit rule for the `AFK_CFG_OBSIDIAN_VAULT` row of `skills/afk/setup/MANIFEST.md` — deferred to 0010-setup-walk
- To reverse: edit that row (drop the obsidian consumer, or delete the row) in the commit that removes the read

## D-26 — The carried narrowing and the dead notes roots are done; D-23 and D-11 describe the state before them
- 2026-10-28 · decided by /afk:execute (0002-settings-reader)
- Options: A — leave D-23 and D-11 as they read vs B — record that the re-slice let this slice finish what they carried
- Chosen: B — review key f025: the no-launcher branch of `hooks/precommit-gates.sh` now reads only `$AFK_CONFIG` and the committed file, else the local overlay and the repository personal file, and both kinds' `notes_root` functions are deleted
- Supersedes: D-23 choice B and its reverse recipe — the whole narrowing landed (option A, with the out-of-scope test replaced after the re-slice); D-11 "their headers stale, which the out-of-scope files carry until a later slice edits them" — the functions are deleted and the headers rewritten
- To reverse: restore the layer loop of D-23 option B in `hooks/precommit-gates.sh`, and the `notes_root` functions in `adapters/notes/obsidian/notes.sh` and `adapters/notes/repo-files/notes.sh`

## D-27 — Keep `layer_reads` public beside the SDD §8 reader answers
- 2026-10-28 · decided by /afk:execute (0002-settings-reader)
- Options: A — make it private, so `skills/afk/setup/scripts/developer_values.py` either imports a private name or restates which owners each file is read for vs B — keep the one public function both `_owner_filter` and `status` call
- Chosen: B — review key f020: one statement of the read rule is the reason D-24 gave; the name is plugin-internal, so renaming it later is cheap
- Supersedes: the Acceptance bullet "Implements the public interface in SDD §8 row \"settings reader (changed)\" unmodified" of `plan/0002-settings-reader.md` — widened by `layer_reads(kind, committed)`
- To reverse: rename it `_layer_reads` and give `status` its own copy of the read rule

## D-28 — 0010-setup-walk also rewords the dependency register's commit-gate sentence; no IOU carries either edit
- 2026-10-28 · decided by /afk:execute (0002-settings-reader)
- Options: A — park the slice a third time for two sentences of `skills/afk/setup/MANIFEST.md`, outside Scope vs B — leave both to 0010-setup-walk, which every executor reaches through this ledger, and drop the IOU line, which the wiring gate never matches for an existing file
- Chosen: B — review keys f027 and f030; executors read `plan/DECISIONS.md` before working a slice (root `DECISIONS.md`), so this entry is where 0010-setup-walk meets the duty
- For 0010-setup-walk: in `skills/afk/setup/MANIFEST.md`, drop `adapters/notes/obsidian/notes.sh` from the `AFK_CFG_OBSIDIAN_VAULT` row (or delete the row), and reword P1's "any configuration layer mentions `repo-hooks`" to the files `CONFIG.md` names: the `$AFK_CONFIG` file, and the committed file, else the repository personal file and the local overlay
- Supersedes: D-25's carrier — the IOU of review key f018 is withdrawn; `FRESHNESS.md` same-commit rule for P1 of `skills/afk/setup/MANIFEST.md` — deferred to 0010-setup-walk
- To reverse: edit both sentences in the commit that narrows the check, and drop this entry's duty

## D-29 — `jira.site` stays scheme plus host
- 2026-10-28 · decided by /afk:execute (0002-settings-reader)
- Options: A — accept a context path such as `https://host/jira` vs B — accept only scheme plus host, with an optional trailing slash
- Chosen: B — review key f028: INV-016 records that the sign-in load hands Jira a base of scheme plus host, and ADR-0004 (design) derives the per-site key from the host, so two paths on one host would share one sign-in; a context path is a non-goal of this feature
- Supersedes: the fix of review key f021, which allowed a path
- To reverse: allow `(/\S*)?` in the `jira.site` check of `scripts/afk-config.py` and define the per-site key for a path in ADR-0004

## D-30 — Re-take the reader seam's ground with a fresh question on the one call this slice uses
- 2026-10-28 · decided by /afk:execute (0004-placement)
- Options: A — re-run INV-013 whole (its Q3 question on the owner-rule change, 7 subjects) vs B — one fresh Q1 run on `parse_single_file`, the only reader call placement makes
- Chosen: B — `ground_diff.py` against INV-013 exits 1 (4297 places; 0002-settings-reader built the change INV-013 studied), and the contract's `## Seams` row binds placement to the single-file parse, never the merge; INV-024 at cc6bff8 is `closed-with-frontier` and no claim in it contradicts SDD §8 row "settings reader (changed)" (D-15 precedent)
- Supersedes: the `## Seams` row of `plan/0004-placement.md` citing INV-013 — this slice stands on INV-024
- To reverse: run `/afk:investigate` on the INV-013 question at the branch head and re-check placement against its claims

## D-31 — The short-name marker counts as part of the repository list placement reads
- 2026-10-28 · decided by /afk:execute (0004-placement)
- Options: A — read only the machine file and the list file, and skip R-06 on a check vs B — also read the marker in `<root>/<short name>` on every check
- Chosen: B — R-06 asks whether setup made the folder for that repository, which only the marker answers, and R-07 checks on every read; SDD §4 relation "list entry → marker" sets its fetch posture to "read per add, remove, placement check"
- Supersedes: the `## Verification` row of `plan/0004-placement.md` "assert only the machine file and the list file are read" — widened to the marker of the checked entry's short name
- To reverse: drop `_short_name_folder` from `ROOT_RULES` in `scripts/placement.py` and narrow the read-count test

## D-32 — R-04 warns on every root with a space; the caller says whether a listed repository builds with Maven
- 2026-10-28 · decided by /afk:execute (0004-placement)
- Options: A — placement reads each listed repository's build gates to warn only for Maven vs B — placement returns the R-04 warning for any space, and setup words it for the repositories that build with Maven
- Chosen: B — A breaks the Acceptance bullet "Placement reads only the machine file and the repository list", and PRD catalog R gives the R-04 outcome to setup ("setup accepts it and warns")
- Supersedes: none — narrows the Acceptance bullet "R-04 a space in the path (a warning when a listed repository builds with Maven)" of `plan/0004-placement.md` to "a warning; the caller decides the Maven case"
- To reverse: give `_no_space` in `scripts/placement.py` the repository's build gates

## D-33 — A failing old base value refuses; a passing one is the root with state suggested
- 2026-10-28 · decided by /afk:execute (0004-placement)
- Options: A — a failing machine `developer.worktreeBasePath` falls through to the suggestion vs B — it refuses with its rule, and a passing one has state suggested, source `developer.worktreeBasePath`
- Chosen: B — PRD AC-043 "If it fails, agents refuse to create a worktree until setup is answered"; the SDD §6 root state diagram keeps the old base value in NotConfirmed, which the developer leaves only by answering the root question
- Supersedes: none — reads the Acceptance bullet "else the old machine `developer.worktreeBasePath` when it passes catalog R; else the suggestion" as "else the suggestion when no old base value is set"
- To reverse: in `_candidate` of `scripts/placement.py`, try the suggestion when the old base value fails

## D-34 — R-05 finds a clash through the entry lookup; the earlier entry keeps the short name
- 2026-10-28 · decided by /afk:execute (0004-placement)
- Options: A — read every entry with `all_entries` to find a clash vs B — check the short name is one valid folder name, then ask `find_entry` for `<root>/<short name>`; an earlier entry holding it refuses the later one with R-05
- Chosen: B — SDD §8 row "repository list (new)" keeps "all entries" for setup only and SDD §5 says the read-all call is used only by setup; the list module refuses a clash at add, so a clash comes only from a hand edit
- Supersedes: none
- To reverse: read `all_entries` in `_short_name_free` of `scripts/placement.py` and refuse both clashing entries

## D-35 — A repository git cannot map to a main checkout counts as not listed
- 2026-10-28 · decided by /afk:execute (0004-placement)
- Options: A — refuse a target when git names a repository whose main checkout placement cannot work out vs B — answer not listed
- Chosen: B — PRD AC-055 leaves an unlisted repository unchecked, and the cases are a bare repository (the list refuses one) and a linked worktree of a separate git folder without `core.worktree`, whose main checkout git does not name (D-18); A would refuse agents in repositories no entry lists
- Supersedes: none
- To reverse: return a refusal from `_entry_for` in `scripts/placement.py` when `_main_by_git` answers None for a folder inside a repository

## D-36 — Placement calls the list module's private short-name check and marker read
- 2026-10-28 · decided by /afk:execute (0004-placement)
- Options: A — copy the short-name check and the marker read into placement vs B — call `_check_short_name` and `_marker_holder` of `scripts/repo_list.py` vs C — make both public in the list module
- Chosen: B — the list module stays the one owner of both formats, and C edits `scripts/repo_list.py`, outside this slice's Scope; the feature review owns the public form (review key 0004-placement/f004)
- Supersedes: none
- To reverse: give `scripts/repo_list.py` public names for both and switch the two calls in `_short_name_free` and `_short_name_folder` of `scripts/placement.py`

## D-37 — An unlisted `--branch --dir` without `--parent` goes to the sibling `<main>-worktrees`; a set old base value no longer moves it
- 2026-10-28 · decided by /afk:execute (0005-worktree-creator)
- Options: A — keep a `developer.worktreeBasePath` from any layer as the flat parent of an unlisted repository's `--dir` worktree vs B — the derived sibling `<main-checkout-name>-worktrees`, else `~/repo-worktrees` when git names no main checkout
- Chosen: B — the contract removes `resolve worktreeBasePath`, and placement already reads the old machine value as a root candidate (D-33), so A gives one key two meanings; SDD §3 row "`create-worktree --branch <b> --dir <d> [--parent <p>]`" declares the change "breaking … for a set worktree base value"
- Supersedes: none
- To reverse: in `ask_placement` dir mode of `scripts/create-worktree`, use `developer_value(config, "worktreeBasePath")` for a not listed answer

## D-38 — A `~` or relative `--parent` is made absolute against the caller's folder, and one inside the main checkout is refused, for every caller
- 2026-10-28 · decided by /afk:execute (0005-worktree-creator)
- Options: A — make it absolute and refuse it only in an agent session vs B — for every caller, with exit 3 and the line `ERROR=parent <path> is inside the main checkout <main> - pass an absolute --parent outside it (… was relative)`
- Chosen: B — PRD AC-051 "A relative or `~` path never lands a worktree inside the main checkout" names no actor; a developer keeps "anywhere" (AC-056) for an absolute `--parent` and for a relative one outside the checkout
- Supersedes: none
- To reverse: test `agent` before the relative check in `ask_placement` parent mode of `scripts/create-worktree`

## D-39 — A placement read failure exits 1 with `ERROR=placement: <reason>`; every catalog R refusal takes the root line
- 2026-10-28 · decided by /afk:execute (0005-worktree-creator)
- Options: A — exit 3 for any problem placement reports vs B — exit 3 only for a refused rule (R-01..R-03, R-05, R-06), exit 1 for an unreadable machine file or list file or a failed git call
- Chosen: B — SDD §3 row "`create-worktree --name <name>`": exit 3 when the "root fails a rule", "every other failure: exit 1, `ERROR=<reason>`"; R-05 and R-06 are catalog R rules, so they print `ERROR=worktree root: <rule> <reason> - run /afk:setup`
- Supersedes: none
- To reverse: call `refuse_exit` for the `error` state in `place` of `scripts/create-worktree`

## D-40 — `resolve worktreeBasePath` exits 2 and names `resolve worktreeRoot`; the derived value stays for setup's report
- 2026-10-28 · decided by /afk:execute (0005-worktree-creator)
- Options: A — drop the key from `resolve` so it fails as any unknown key vs B — refuse it with exit 2 and name the replacement vs C — B, and remove the derived value from `developer_value`
- Chosen: B — the contract says `resolve worktreeBasePath` "is gone", and a named replacement tells a stale caller what to run; C breaks the H6 status of `skills/afk/setup/scripts/developer_values.py`, which 0009-settings-writer owns
- Supersedes: none
- To reverse: delete the `worktreeBasePath` branch before `load(root)` in `main` of `scripts/afk-config.py`

## D-41 — The creator asks placement for the folder and reads `resolve worktreeRoot` only for its note
- 2026-10-28 · decided by /afk:execute (0005-worktree-creator)
- Options: A — read the root through `resolve worktreeRoot` and join `<root>/<short name>/<name>` in the creator vs B — take the folder from placement's `target_for`, then print `Worktree folder: <folder> (worktree root: <resolve answer>)` on stderr
- Chosen: B — ADR-0002 (design) "the creator asks placement and computes no folder itself"; the Produces anchor `resolve worktreeRoot` stays live as the developer-facing note
- Supersedes: none
- To reverse: drop the `root_note` call in `scripts/create-worktree`

## D-42 — The move helper starts nothing when placement refuses
- 2026-10-28 · decided by /afk:execute (0005-worktree-creator)
- Options: A — fall back to the old path for the hint vs B — return the refusal as the plan's error, with no marker and no detached creation
- Chosen: B — the creator exits 3 for the same name, so a started move fails after the pane was told where to go; the contract requires the hint to equal the creator's path
- Supersedes: none
- To reverse: return the old `root / folder / name` from `target` in `hooks/lib/h2_move.py` on a refusal

## D-43 — The plugin-root `CONFIG.md` sentence on resolving `worktreeBasePath` waits for 0010-setup-walk
- 2026-10-28 · decided by /afk:execute (0005-worktree-creator)
- Options: A — edit `CONFIG.md` here, outside Scope vs B — leave it to 0010-setup-walk, which has `CONFIG.md` and `CHANGELOG.md` in Scope, as D-28 did
- Chosen: B — executors read this ledger before working a slice (root `DECISIONS.md`)
- For 0010-setup-walk: in the `developer` row of `CONFIG.md`, replace "Resolve with `afk-config.py resolve <key>`, which applies the developer value, then (for `worktreeBasePath` alone) a derived one" with `resolve worktreeRoot` (placement's root, checked on each read; exit 1 names the failed rule) and drop the derived value; add the `resolve worktreeBasePath` removal to the changelog
- Supersedes: `FRESHNESS.md` same-commit rule for that sentence — deferred to 0010-setup-walk
- To reverse: edit the sentence in this slice's commit and drop this entry's duty

## D-44 — The plugin's worktree-path readers for AC-060, and the ones no sandbox can run
- 2026-10-28 · decided by /afk:execute (0005-worktree-creator)
- Options: A — test only the creator, the move helper and cleanup vs B — every reader found in the code, one case each in `scripts/tests/test_existing_worktree_outside_root.py`, run on a worktree cut outside the root and one inside it
- Chosen: B — the contract's Acceptance bullet asks for every hook, gate and script that reads a worktree path
- The list: every case id of that test file names its member. Hooks: `worktree-create.sh`, `worktree-remove.sh`, `worktree-prune.sh`, `protected-branch-occupancy.py` (+ `hooks/lib/occupancy.py`), `protected-branch-guard.py` (+ `hooks/lib/protected_branch_guard.py`, `shell_mutations.py`, `read_only.py`, `main_sync.py`), `run-hook.py repo-list`, `nested-steering.sh`, `install-git-hooks.sh`, `agents-md-config-check.sh`, `branch-name-gate.sh`, `git-backstop.py`, `precommit-gates.sh`, `gate-context.sh`, `gate-cache.sh`, `gate-metrics.sh`, `comment-gate.sh`, `plugin-source-gates.sh` and its four gates, `wiring-gate.sh`, `hooks/lib/provider.sh`, `lesson-append.sh`, `lesson-digest.sh`, `stall-watchdog.sh`. Adapters: maven `gates.sh`, `maven-lock.sh`, `worktree-provision.sh`; npm `gates.sh`, `worktree-provision.sh`; `notes/common.sh`; the tracker server with tracker `none`. Scripts: `create-worktree`, `worktree-provision`, `worktree_owner.py`, `remove-worktree.py`, `afk-move.py`, `afk-launch.py`, `placement.py`, `repo_list.py`, `protected-lookup.py`, `afk-config.py`, `tracker_api.py`, `lavish/inject.py`. Skill scripts: setup `ancestor_instruction_files.py`, `background_git_hooks.py`, `setup_secrets.py`, `developer_values.py`; `gc-check.sh`; `verify-contract.sh`; `mission_control.py` + `mc/sections/understanding.py`; `validate_plan.py`; `forge_ledger.py`; `write_report.py`; `seed_map.py`; report-issue `publish.sh --list`
- Exclusions (no sandbox can run them): `maven-compile-gate.sh`, `java-format-gate.sh`, `app-start-gate.sh`, `mutation-probe.sh` (need `mvnw`, a JDK and a Maven project); npm `ui-lint-gate.sh` lint (needs eslint and `node_modules`); npm `worktree-provision.sh` install (`npm ci` downloads); the typing part of `afk-move.py` (needs the `herdr` binary); `forge_ledger.py` forge calls and `publish.sh` publish (a forge CLI over the network); the `jira` and `github-issues` tracker adapters (remote APIs)
- Supersedes: none
- To reverse: delete the test file and this entry

## D-45 — The base checks run before the creator prunes or makes the parent folder
- 2026-10-28 · decided by /afk:execute (0005-worktree-creator)
- Options: A — keep the base checks beside `git worktree add`, after `git worktree prune` and `mkdir -p <parent>` vs B — run them first, so the only things before them are read-only git calls and, for `--name`, the creation lock, which the exit releases
- Chosen: B — INV-025 found the write steps ran before the base checks at HEAD; ADR-0002 (design) "the creator runs every check before anything is made"; the `--name` taken-name and branch checks stay under the lock, which makes them race-free
- Supersedes: none
- To reverse: move the two base checks in `scripts/create-worktree` back into the `else` branch before `git worktree add`

## D-46 — Setup's H6 probe and its K3 sentences move to `worktreeRoot` in 0010-setup-walk; the K3 need in `developer_values.py` in 0009-settings-writer
- 2026-10-28 · decided by /afk:execute (0005-worktree-creator)
- Options: A — keep `resolve worktreeBasePath` answering until 0010 lands (reverse D-40) vs B — keep D-40 and hand the two readers to the slices whose Scope holds them
- Chosen: B — the contract says `resolve worktreeBasePath` "is gone"; `skills/afk/setup/MANIFEST.md` is in 0010's Scope and `developer_values.py` in 0009's; the branch ships as one change, so the interim H6 miss never reaches a developer
- For 0010-setup-walk: in `skills/afk/setup/MANIFEST.md` H6, replace `worktreeBasePath` in the probe's `keys` with `worktreeRoot`, and rewrite the K3 sentences (the machine `worktreeBasePath` derived-value step, the `--machine` refusal, and "`worktreeBasePath` normally resolves without anyone setting it … a bare clone") to the root: one machine value, checked by catalog R, no derived value
- For 0009-settings-writer: in `developer_values.py`, `need` makes `worktreeRoot` required and `worktreeBasePath` n/a, and the `derived` field goes with it
- Supersedes: none
- To reverse: restore the derived answer for `worktreeBasePath` in `main` of `scripts/afk-config.py` and drop these duties

## D-47 — A `--dir` that climbs out of the short-name folder is refused with exit 3
- 2026-10-28 · decided by /afk:execute (0005-worktree-creator)
- Options: A — check `--dir` with the `--name` rule (1-64 safe characters) vs B — act on placement's `outside` verdict: exit 3 with `worktree folder: <reason> - pass a plain folder name as --dir`
- Chosen: B — placement already judges the target (ADR-0002); A would also narrow `--dir` for unlisted repositories, which keep today's behaviour
- Supersedes: none
- To reverse: drop the `refused` check after `place` in the name/dir branch of `scripts/create-worktree`

## D-48 — A short-name folder removed by hand is made again with its marker
- 2026-10-28 · decided by /afk:execute (0005-worktree-creator)
- Options: A — refuse with `run /afk:setup` when the folder is missing vs B — make the folder through the repository list's own claim, under its lock, then cut the worktree
- Chosen: B — R-06 lets an absent folder pass (PRD §Catalog R), and a plain `mkdir` left an unmarked folder that R-06 refused on the next creation; at HEAD nothing outside `scripts/repo_list.py` claims a folder (grep of `skills`, `scripts`, `hooks`), so no setup step remakes it
- Supersedes: none
- To reverse: drop `claim_short_name_folder` and its call in `scripts/create-worktree`
- Debt: the creator calls `repo_list`'s private `_parse`, `_claim_folder` and `_update_list`, as placement does (feature-gate design review)

## D-49 — Any existing file at the destination stops the creator, not only a folder
- 2026-10-28 · decided by /afk:execute (0005-worktree-creator)
- Options: A — keep the `-d` test vs B — `-e`, so a plain file stops the run before `git worktree prune` and `mkdir`
- Chosen: B — ADR-0002 (design) "the creator runs every check before anything is made"; git refuses that path anyway, but only after the write steps
- Supersedes: none
- To reverse: put `-d` back in the destination check of `scripts/create-worktree`

## D-50 — `hooks/genericity-allow.txt` takes `INV-025` outside Scope
- 2026-10-28 · decided by /afk:execute (0005-worktree-creator)
- Options: A — leave the investigation id out of committed prose vs B — allow it, as INV-001 to INV-024 already are
- Chosen: B — the Seams rows must name the investigation that closed each seam, and the genericity gate refuses an unlisted id
- Supersedes: none
- To reverse: delete the `INV-025` line from `hooks/genericity-allow.txt`

## D-51 — INV-025's B1 exclusion of `docs/afk/*/investigations/**` is an accepted frontier
- 2026-10-28 · decided by /afk:execute (0005-worktree-creator)
- Options: A — re-run B1 over a partitioned universe vs B — accept the exclusion
- Chosen: B — the 52 excluded files are 26 `.json` and 26 `.md` ledgers and reports (`git ls-files 'docs/afk/*/investigations/**'`), which no code runs; a mention there cannot call the creator; the review re-checked the live callers by hand and found none broken
- Supersedes: none
- To reverse: run `/afk:investigate` again with B1 partitioned over that folder

## D-52 — Only an agent's `--dir` that climbs out of the short-name folder is refused
- 2026-10-28 · decided by /afk:execute (0005-worktree-creator)
- Options: A — refuse it for every caller vs B — refuse it in an agent session; a developer's lands where it points, with a note naming the folder it leaves
- Chosen: B — ADR-0004 (requirements) binds the guard to agents only, and AC-056 keeps the developer free to create a worktree anywhere; `--parent` already splits the same way
- Supersedes: D-47, for developer sessions
- To reverse: make the refusal after `place` in the name/dir branch of `scripts/create-worktree` unconditional again

## D-53 — Every placement under the root makes sure the short-name folder carries its marker
- 2026-10-28 · decided by /afk:execute (0005-worktree-creator)
- Options: A — claim only a missing folder in the name/dir modes vs B — claim whenever placement answers inside, in every mode, when the marker does not name this repository; the claim is skipped without the lock when it does
- Chosen: B — R-06 also lets an empty unmarked folder pass, and an agent's `--parent` inside the folder made it with plain `mkdir`; both left a folder the next creation refused
- Supersedes: D-48's "removed by hand" scope
- To reverse: claim only when `$WORKTREE_PARENT` is missing, as D-48 first did

## D-54 — Where the folder claim learns the repository's short name
- 2026-10-28 · decided by /afk:execute (0005-worktree-creator)
- Options: A — keep `repo_list.all_entries()` in the claim and widen its "setup only" rule in the 0003 and 0010 contracts and the module header vs B — look the repository up with `find_entry` and build the folder as `<root>/<short name>` from `root_state`, not from placement's resolved folder
- Chosen: B — the seam rule stays as two contracts already state it, and a folder reached through a link keeps the listed short name instead of the link target's basename
- Supersedes: none
- To reverse: restore the `all_entries()` scan in `claim_short_name_folder` and amend the "setup only" lines in `scripts/repo_list.py`, `plan/0003-repository-list.md` and `plan/0010-setup-walk.md`

## D-55 — The folder claim keeps calling the repository list's private helpers
- 2026-10-28 · decided by /afk:execute (0005-worktree-creator)
- Options: A — add a public claim call to `scripts/repo_list.py` (0003's module) and move the creator onto it vs B — keep the creator's calls to `_parse`, `_claim_folder`, `_update_list`, `_marker_holder` and `_key`, and widen D-48's debt to all five
- Chosen: B — a public claim changes a done slice's seam surface that 0010's setup walk also consumes; the five calls run under the list's own lock, as placement's do
- Supersedes: D-48's Debt line (it named three of the five calls)
- To reverse: add a public `claim_folder` to `scripts/repo_list.py` and call it from `claim_short_name_folder` in `scripts/create-worktree`
- Debt: the creator calls five private `repo_list` helpers (feature-gate design review)

## D-56 — Setup's H6 probe stops resolving `worktreeBasePath` in this slice
- 2026-10-28 · decided by /afk:execute (0005-worktree-creator)
- Options: A — leave the probe to 0010-setup-walk, as D-46 did, with `scripts/tests/test_setup_h6_probe.py` red (8 of 12) until then vs B — drop `worktreeBasePath` from the probe's `keys` here, so the probe checks no root until 0010 adds `worktreeRoot` vs C — keep `resolve worktreeBasePath` answering until 0010
- Chosen: B — SDD §3 says the callers of `resolve` move in the same commit, and A leaves a red suite for every slice before 0010; C breaks this contract's "`resolve worktreeBasePath` is gone"; the key only ever failed on a bare clone, so B loses no check a developer saw
- Supersedes: D-46's H6 `keys` duty for 0010-setup-walk, which becomes "add `worktreeRoot` to the probe's `keys`" (its K3-sentence duty stands)
- To reverse: restore `keys="worktreeBasePath"` in `skills/afk/setup/MANIFEST.md` H6 and hand the test file to 0010-setup-walk

## D-57 — The creator is a second writer of short-name markers
- 2026-10-28 · decided by /afk:execute (0005-worktree-creator)
- Options: A — keep SDD §2's "setup is the only writer" and move the folder claim into setup vs B — let the creator claim a missing or empty short-name folder under the list lock (D-48, D-53) and record that the single-writer rule no longer holds for markers
- Chosen: B — the claim writes only the marker of a repository already in the list, under the list's own lock, and the list itself keeps setup as its only writer
- Supersedes: SDD §2 row "Repository list and short-name markers" ("setup is the only writer") and plan/0003-repository-list.md's "written when setup takes the short name", for markers only
- To reverse: drop `claim_short_name_folder` from `scripts/create-worktree` and refuse a missing or unmarked folder with `run /afk:setup`

## D-58 — A test's probe word quoted in a review record is masked
- 2026-10-28 · decided by /afk:execute (0005-worktree-creator)
- Options: A — rename the probe word in `scripts/tests/test_existing_worktree_outside_root.py` vs B — mask the word in `plan/review/0005-worktree-creator-98a0a12-r3.findings.json`, as D-4 masked quoted fixture values
- Chosen: B — the report-issue redactor reads every tracked `.json` outside `tests/` as plugin vocabulary, so the quoted word made two `test_report_issue.py` tests fail on the full Linux run; a new word would break the same way the next time a record quotes it, and the record is telemetry no gate reads
- Supersedes: none
- To reverse: restore the word in that findings file's r-007 evidence

## D-59 — The spec passages this slice's placement calls override stay in the ledger
- 2026-10-28 · decided by /afk:execute (0005-worktree-creator)
- Options: A — amend `SDD.md` and `VERIFICATION-PLAN.md` in this slice, outside its Scope vs B — quote each overridden passage here, since a `Supersedes:` line overrides the exact passage it quotes (root `DECISIONS.md` "Before working a slice")
- Chosen: B — the specs are outside every slice's Scope and the ledger is the protocol's home for an override; A would put a second scope exception on top of D-60's
- Supersedes: SDD §4 `path` row "written when setup takes the short name" (D-57's "SDD §2 row" is the §3 row "Repository list and short-name markers") and `VERIFICATION-PLAN.md` A18/A19 "setup-only writer", for short-name markers only (as D-57); SDD §3 `create-worktree --name` row "every other failure: exit 1" and `--branch --dir` row's exit-3 cell, which also cover any catalog R refusal (D-39) and an agent's `--dir` that climbs out of the short-name folder (D-47, D-52)
- To reverse: amend those SDD and verification-plan passages and drop this entry's Supersedes line

## D-60 — This slice edits three files outside its Scope
- 2026-10-28 · decided by /afk:execute (0005-worktree-creator)
- Options: A — edit them here vs B — hand each to the slice whose Scope lists it (0010-setup-walk for `skills/afk/setup/MANIFEST.md`, 0006-worktree-guard for `scripts/tests/test_protected_branch_acceptance.py` and `scripts/tests/test_protected_branch_guard.py`)
- Chosen: A — each edit follows from this slice's own change: the H6 probe called the removed `resolve worktreeBasePath` (D-56) and its prose and `AFK_WORKTREE_FOLDER` row describe the old placement; the two test files run the creator and the move helper, which now read `~/.afk` through placement, so they get the same empty sandbox home as this slice's own tests; B leaves suites red or reading the real home until those slices run
- Supersedes: 0005-worktree-creator `## Scope`, for these three files only; 0010-setup-walk still owns the rest of H6, including adding `worktreeRoot` to the probe's `keys` (D-56)
- To reverse: revert this slice's hunks in those three files

## D-61 — Only the out-of-Scope edits a binding rule forces stay; the test fixtures go to 0006-worktree-guard
- 2026-10-28 · decided by /afk:execute (0005-worktree-creator)
- Options: A — keep D-60's three edits vs B — withdraw the sandbox-home fixtures from `scripts/tests/test_protected_branch_acceptance.py` and `scripts/tests/test_protected_branch_guard.py` and keep only the edits a binding rule forces vs C — park every out-of-Scope edit for the human
- Chosen: B — root `DECISIONS.md` condition 3 puts Scope reshaping outside agent authority, so an edit stays only where a rule leaves no option: the `skills/afk/setup/MANIFEST.md` hunks follow `FRESHNESS.md` rule 1 ("a commit that adds, removes, or changes how any skill/script/hook invokes an external tool, MCP server, env var, secret, or sibling path updates `skills/afk/setup/MANIFEST.md` in the same commit") and this contract's "every caller (the creator, skills/afk/bug) moved in the same commit"; D-50's `hooks/genericity-allow.txt` line follows the genericity gate, which refuses the `INV-025` id the Seams rows must name; no rule forces the fixtures, and 0006-worktree-guard's Scope lists both files. The final report names the kept edits for the human. Duty for 0006-worktree-guard: give both test files an empty sandbox home per test, because the creator and the move helper now read `~/.afk` through placement
- Supersedes: D-60, whole; and, adding to D-59, SDD §3 `create-worktree --branch <b> --dir <d> [--parent <p>]` row's cell "`--parent` outside the folder for an agent: exit 3, `ERROR=parent <path> is outside <root>/<short name>` plus the fixing command", which also covers an agent's `--dir` that climbs out of the short-name folder (D-47, D-52)
- To reverse: re-apply round 6's `sandbox_home` fixtures in the two test files

## D-62 — Three earlier entries are corrected by quotation, since the ledger is append-only
- 2026-10-28 · decided by /afk:execute (0005-worktree-creator)
- Options: A — edit D-44, D-55 and D-59 in place vs B — quote and correct each here
- Chosen: B — root `DECISIONS.md` makes the ledger append-only, and a later entry's Supersedes line is how an earlier one changes
- Supersedes: D-44's list item "`plugin-source-gates.sh` and its four gates" — the dispatcher stays a case, and `skill-registry-gate.sh`, `native-contract-gate.sh`, `genericity-gate.sh` and `behavior-registry-gate.sh` join its Exclusions: they judge only the plugin's own repository and return at once in any other; D-55's "the five calls run under the list's own lock" — `_parse`, `_claim_folder` and `_update_list` run under the lock, while the marker read (`_marker_holder`, `_key`) is the lock-free check that skips the claim (D-53); D-59's `VERIFICATION-PLAN.md` "A18/A19" — A19 (repository list module) only, since A18 is the settings writer
- To reverse: drop this entry; the three earlier wordings stand

## D-63 — The review ledger runs from a scratch copy of the plugin whose GitHub thread listing reads its review-thread JSON from a file
- 2026-10-28 · decided by /afk:execute (0005-worktree-creator)
- Options: A — edit `adapters/forge/github/forge.sh` on the branch vs B — park `needs_decision` vs C — run `forge_ledger.py` from `C:/t/p5judge` (a `git archive` of 1551d586) whose `thread-list` passes the review-thread JSON as a file path instead of an argument
- Chosen: C — change #145 now has enough review threads that `thread-list` exceeds the Windows command-line limit ("Argument list too long"), so every gate call fails; A edits a file outside Scope that no binding rule forces (D-61), B stops the slice over a transport defect, while C changes nothing on the branch and only how the same JSON reaches the same code; the defect goes to the report as a plugin issue candidate
- To reverse: drop the scratch copy and run the ledger from the worktree again; nothing on the branch changes

## D-64 — Four more ledger corrections by quotation, and two more test files for 0006-worktree-guard
- 2026-10-28 · decided by /afk:execute (0005-worktree-creator)
- Options: A — edit the earlier entries and the verification plan in place vs B — quote and correct each here
- Chosen: B — root `DECISIONS.md` makes the ledger append-only, and the verification plan sits outside Scope (D-61)
- Supersedes: D-62's "the marker read (`_marker_holder`, `_key`) is the lock-free check that skips the claim" — the lock-free part is `_marker_holder` and the first `_key` comparison; `claim` calls `_key` again under the list lock; D-50's reason "the Seams rows must name the investigation that closed each seam" — the contract's Seams rows cite INV-014 and INV-019 only; the line is forced because `DECISIONS.md` and `JOURNAL.md` already carry `INV-025` in added lines, which the append-only rule keeps and the genericity gate refuses without it; `VERIFICATION-PLAN.md` A3 cell "other failure exit 1" — any placement refusal exits 3, the root rules, a catalog R refusal (D-39) and an agent's `--dir` that climbs out of the short-name folder (D-47, D-52), and every other failure exits 1; A4 cell "agent parent outside root/short name exit 3" and the scenario line "agent outside (any form, after being made absolute): exit 3" — an agent's climbing `--dir` exits 3 the same way; D-61's duty for 0006-worktree-guard — `scripts/tests/test_main_sync.py` and `scripts/tests/test_lavish_direct.py` run the guard with `AFK_MOVE_SPAWN=0` and no sandbox home too, so the sandbox-home duty covers them as well
- To reverse: drop this entry; the earlier wordings stand

## D-65 — The contract's exit-code bullets and the SDD §14 creator row are corrected by quotation
- 2026-10-28 · decided by /afk:execute (0005-worktree-creator)
- Options: A — edit the contract and the SDD vs B — quote and correct each here
- Chosen: B — a two-way door reshapes no plan structure (root `DECISIONS.md`), and D-59 and D-64 already correct the same claim in SDD §3 and the verification plan
- Supersedes: this contract's Acceptance bullet "every other failure exits 1 with `ERROR=<reason>`" and its Context excerpt's "every other failure: exit 1, `ERROR=<reason>`" — any placement refusal exits 3, the root rules, a catalog R refusal (D-39) and an agent's `--dir` that climbs out of the short-name folder (D-47, D-52); every other failure exits 1; the Acceptance bullet "with `<p>` outside `<root>/<short name>` exits 3" and its excerpt's "`--parent` outside the folder for an agent: exit 3" — an agent's climbing `--dir` exits 3 the same way; SDD §14 row "`create-worktree` `--name`, `--branch`, `--dir`, `--parent`" cell "refusal exit 3 through its own exit path; an agent `--parent` outside the folder refused" (also quoted in this contract's Context excerpts) — any placement refusal exits 3, and an agent `--parent` or climbing `--dir` outside the folder is refused
- To reverse: drop this entry; the contract and SDD wordings stand

## D-66 — The worktree placement rule binds only an agent, and its variable half binds in every repository
- 2026-10-28 · decided by /afk:execute (0006-worktree-guard)
- Options: A — run the rule for every guard call vs B — run it only when the agent detector is on (provider facts present), first in the shell branch of `decide`, the variable refusal in every repository and the worktree refusal only for a listed one
- Chosen: B — VERIFICATION-PLAN A6-A8 pass "the detector off" and name the developer as the detector switched off; SDD §3 row "Δ command guard on inline variables" names "an agent command" with no listed-repository condition; `main()` still returns before `decide` on the launch flag, so the flag lifts both halves (SDD §14)
- Supersedes: none
- To reverse: drop the `facts` condition in `decide`, or add a listed-repository check to `variable_refusal`

## D-67 — No guard test pins "a plain add passes"; the reversed and kept pins are new guard tests
- 2026-10-28 · decided by /afk:execute (0006-worktree-guard)
- Options: A — edit the two module-level pins vs B — keep them and pin the guard verdict in the new test file
- Chosen: B — INV-026 found no test feeding the guard `git worktree add`; `scripts/tests/test_shell_mutations.py:33,44` pin the parser (outside Scope, still true) and `scripts/tests/test_protected_branch_acceptance.py:1035` runs git against the backstop; `test_a_listed_repository_reverses_the_plain_add_pin` and `test_an_unlisted_repository_keeps_a_plain_add_passing` in `scripts/tests/test_worktree_placement_guard.py` are the guard-level pair
- Supersedes: this contract's Acceptance bullet "The two existing tests pinning "a plain `git worktree add` passes the guard" are reversed for listed repositories and kept for unlisted ones", and the same claim at PRD.md:200, SDD.md:132 and :711, `adr/design/0002-one-placement-guardian.md`:43 and VERIFICATION-PLAN.md:211 — no guard test pinned it; the pair is new
- To reverse: drop the two new tests

## D-68 — Refusal wording for a target the guard cannot work out, a root-rule failure and a placement error
- 2026-10-28 · decided by /afk:execute (0006-worktree-guard)
- Options: A — one fixed text for every refusal vs B — the contract's exact text for an outside target, and the same head and Move with a different Cause otherwise
- Chosen: B — the contract fixes only the outside text; an unknown target (a variable, a word that splits, an opaque `-C` folder, an unknown or ambiguous option, an opaque subcommand, a `-c alias.*` naming worktree, an opaque program before `worktree add|move`) says "the guard cannot work out this command's worktree target, so it may be outside <root>/<short name>"; a root or short-name rule says "worktree root: <rule> <reason>" with "run /afk:setup"; a `PlacementError` says "placement has no answer (<error>)". An unknown folder falls back to the segment's folder, then the envelope's. A quoted variable as a branch name is no path and passes
- Supersedes: none
- To reverse: change the texts in `hooks/lib/worktree_placement_rule.py` `_verdict`

## D-69 — "0 new file reads" counts what the rule itself opens or starts
- 2026-10-28 · decided by /afk:execute (0006-worktree-guard)
- Options: A — count every file open of the guard process vs B — count the opens and process starts made inside `worktree_placement_rule.py`, plus any load of `scripts/placement.py`
- Chosen: B — the existing protected-branch lookup reads `~/.afk/config.yaml` on every mutation (a pre-existing read, not new); loading the guard's own rule module is code loading, as for `lavish_direct.py`; the rule's text test (`concerns`) reads nothing, so a command naming no worktree and neither variable makes no read and starts no process
- Supersedes: none
- To reverse: compare whole-process open counts against a guard run without the rule

## D-70 — The setter forms reuse `lavish_direct.py` by import and a name-parametrized copy
- 2026-10-28 · decided by /afk:execute (0006-worktree-guard)
- Options: A — generalize `lavish_direct._sets_host` to take the name vs B — import `_nested`, `DECLARE`, `PRINT_ONLY` and `MAX_DEPTH` and copy the setter test for the two names
- Chosen: B — `hooks/lib/lavish_direct.py` is outside Scope and no binding rule forces an edit; recorded as debt: a later change folds `_sets` and `_sets_host` into one name-parametrized check. Added forms beyond the lavish rule: `[Environment]::SetEnvironmentVariable` naming either variable, cmd's `set NAME=`, and backslash-escaped names after `export`-style words
- Supersedes: none
- To reverse: generalize `lavish_direct._sets_host` and call it for each name

## D-71 — Freshness-forced edits outside Scope, and the ones left
- 2026-10-28 · decided by /afk:execute (0006-worktree-guard)
- Options: A — leave every document for 0010 and 0013 vs B — make the edits `FRESHNESS.md` rows 58 and 70 force in this commit, one sentence each
- Chosen: B — the same-commit rule binds a verdict-rule change: `hooks/README.md` (guard bullet), `SAFETY.md` "Worktree per session", `AGENTS.md` Reference hooks bullet, `docs/afk/protected-branch-guard/PRD.md` A-5, the `FRESHNESS.md` row 58 file list (the new module), and `hooks/genericity-allow.txt` `INV-026` (D-50's reason); left: `PROVIDERS.md` (its "lifts every worktree-protection refusal" stays true), `CAPABILITIES.md` and the `BEHAVIORS.md` row (no stated rule changes), ADR-0014 (an accepted decision record; this feature's ADR-0002 supersedes its creator line), `README.md` (makes no claim the rule falsifies)
- Supersedes: none
- To reverse: revert those hunks; 0010 and 0013 own the documents

## D-72 — f128 confirmed, outside Scope; the guard suites run under a temporary home
- 2026-10-28 · decided by /afk:execute (0006-worktree-guard)
- Options: A — edit `hooks/tests/hook-smoke.sh` vs B — report it
- Chosen: B — INV-026 confirms `hook-smoke.sh:348-365` runs the H-2 refusal with the real home and no `AFK_MOVE_SPAWN=0`, so under codex `h2_move.plan` reads the real `~/.afk` and can start `afk-move.py` detached; the file is outside Scope and the rule does not change its verdict. D-61's fixture duty is met: both protected-branch test files carry `sandbox_home` again; `test_main_sync.py` and `test_lavish_direct.py` (outside Scope, D-64) run with HOME and USERPROFILE set to a temporary folder for the whole pytest process
- Supersedes: none
- To reverse: none needed; the smoke file stays as it was

## D-73 — Review round 1 widens the freshness edits; the contract's Scope list counts them
- 2026-10-28 · decided by /afk:execute (0006-worktree-guard)
- Options: A — leave `AGENTS.md` line 201, `PROVIDERS.md` "Protected-branch guard" and the `SAFETY.md` outside-Git line for 0010 and 0013 vs B — make the one-clause edits now and count every D-71 and D-73 path as in Scope for this slice
- Chosen: B — each line states a guard verdict the rule changed, so the same-commit rule (`FRESHNESS.md`) binds them; the contract's `## Scope` list is superseded for these doc paths only: `hooks/README.md`, `SAFETY.md`, `AGENTS.md`, `PROVIDERS.md`, `docs/afk/protected-branch-guard/PRD.md`, `FRESHNESS.md`, `hooks/genericity-allow.txt`; D-71's "left: `PROVIDERS.md`" no longer holds
- Supersedes: D-71 (its `PROVIDERS.md` clause only)
- To reverse: revert those hunks; 0010 and 0013 own the documents

## D-74 — Review round 4: the variable rule refuses prose that names the .NET call and a rule variable
- 2026-10-29 · decided by /afk:execute (0006-worktree-guard)
- Options: A — keep round 3's `[Environment]` anchor so prose passes vs B — drop the anchor; refuse when the command calls `SetEnvironmentVariable` with a computed first argument, by `.Invoke`, or by reflection and names a rule variable
- Chosen: B — round 4 showed the type name can be built from parts, so no text anchor separates a real call from prose; a refused commit message or search costs one rewording, a missed set lifts the guard. Prose without call punctuation (`document SetEnvironmentVariable and NAME`) still passes; this reverses f044's fix
- Supersedes: none
- To reverse: restore `ENV_TYPE` in `hooks/lib/worktree_placement_rule.py` and move the three prose rows back to the passing list

## D-75 — Review round 5: any mention of the .NET call beside a rule variable is refused
- 2026-10-29 · decided by /afk:execute (0006-worktree-guard)
- Options: A — tell a call from prose by the punctuation after `SetEnvironmentVariable` vs B — refuse a command that names `SetEnvironmentVariable` and a rule variable, unless every mention is a direct call whose first argument is another plain name
- Chosen: B — round 5 showed one direct call hides an indirect one beside it, and a regex search such as `SetEnvironmentVariable.*NAME` reads like a call; counting mentions against direct calls closes both without parsing PowerShell. A commit message or search naming both is refused and needs rewording (`document SetEnvironmentVariable and NAME` included)
- Supersedes: D-74 (its "prose without call punctuation still passes" clause)
- To reverse: restore the `SET_ENV_INDIRECT` test in `hooks/lib/worktree_placement_rule.py` and move the prose rows back to the passing list

## D-76 — Review round 6: a PowerShell item writer beside a rule variable is refused, reads included
- 2026-10-29 · decided by /afk:execute (0006-worktree-guard)
- Options: A — keep judging the written operand of `Set-Content`, `New-Item`, `Copy-Item`… by position, arrays and `@(…)`/`$(…)` operands vs B — refuse a command whose segment runs an item writer (or its alias) when the command names a rule variable anywhere
- Chosen: B — rounds 3 to 6 each found a new operand spelling (arrays, parentheses, `;` and newline lists, `env:` location) that writes the variable past the positional reading; the parser splits those spellings into other segments, so no positional rule is complete. A command that only reads the variable through a writer (`Set-Content out.txt $env:NAME`) is refused and needs rewording; this reverses the read exemptions of f043, f049, f054 and f058
- Supersedes: none
- To reverse: restore `_item_sets`, `_operands`, `_arrays` and `_parts` in `hooks/lib/worktree_placement_rule.py` from 8b8cad05 and move the read rows back to the passing list

## D-77 — Review round 7: a PowerShell writer named anywhere beside a rule variable is refused
- 2026-10-29 · decided by /afk:execute (0006-worktree-guard)
- Options: A — find the writer among each segment's words (after `$x =`, `return`, a pipeline) vs B — search the command text for a writer name, as D-74 and D-75 do for the .NET call
- Chosen: B — round 7 showed an assignment or `return` in front of the writer hides it from a word-position test; a text search has no position to miss. The cmdlet names (`Set-Item`… `Rename-Item`) and the provider and `PSVariable` calls count in any shell; their short aliases (`sc`, `cp`, `mv`…) count only when PowerShell reads the command or the text names `pwsh`/`powershell`, so a Bash `cp` or `mv` beside a rule-variable name passes
- Supersedes: D-76 (its "as a segment's program" clause)
- To reverse: restore the `writer` test on `program[0]` in `hooks/lib/worktree_placement_rule.py` from 8cfc8d8c

## D-78 — Review round 8: the `env:` drive spelling of a rule variable is refused in PowerShell text, reads included
- 2026-10-29 · decided by /afk:execute (0006-worktree-guard)
- Options: A — keep telling an `env:` read from a write by the words around it (assignment operators, `++`, list targets) vs B — refuse a command PowerShell reads (the PowerShell tool, or text that names `pwsh`/`powershell`) whose text names a rule variable on the `env:` drive (`$env:NAME`, `${env:NAME}`, `env:NAME`, any case) in any position
- Chosen: B — round 8 showed a cast (`[int]$env:NAME=1`), a list target written either way round (`$b,$env:NAME = 1,2`) and a `foreach` variable all set the variable past the word test, and the parser splits none of them; no agent step needs to read the developer's variables. `Write-Output $env:NAME`, `Get-Content env:NAME` and `Remove-Item env:NAME` are refused and need rewording; `[Environment]::GetEnvironmentVariable('NAME')`, a longer name (`$env:NAME_OLD`) and Bash text such as `grep 'env:NAME'` still pass. The PowerShell name test now keeps folder marks and takes `pwsh-preview`, so `C:\...\pwsh.exe` counts and `pwsh-notes.md` does not. Correction to D-77: its Supersedes line quotes a phrase D-76 lacks; the D-76 passage it supersedes is "refuse a command whose segment runs an item writer (or its alias)"
- Supersedes: D-77 (its Supersedes line, corrected above)
- To reverse: restore `ASSIGNS`, `_env_ref` and its loop in `_sets` in `hooks/lib/worktree_placement_rule.py` from c278c604 and move the read rows back to the passing list
