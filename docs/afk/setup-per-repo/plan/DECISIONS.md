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
