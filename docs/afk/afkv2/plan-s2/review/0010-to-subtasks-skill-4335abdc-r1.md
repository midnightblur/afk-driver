# Review 0010-to-subtasks-skill, round 1

Policy: lean. Activated: spec-fidelity, scope-and-impact, test-veracity, logic-correctness (the complexity is complex). Skipped: refactor-safety, api-contract, domain-alignment (no trigger: new files and appended lines only). Deferred: code-quality, agents-md-compliance, design-quality, resilience (to the feature gate). Verified: 0 upheld / 0 downgraded / 0 dropped (no design-level finding at medium or above). Reviewed range: 4335abdc..fb6257a8. No caller investigation ran: the slice changes no earlier public symbol.

Verdict: advisory. Critical 0, high 0, medium 13, low 10.

## r-001 medium spec (spec-fidelity)
`afkv2/skills/to-subtasks/scripts/check_plan.py:383`

A single-segment `./cmd` first word is never read as a check path, so an unowned `./script` passes.

Why: `removeprefix("./")` runs before the `"/" in word` test, so `./mvnw` becomes `mvnw`, which has no slash and sits at index 0. Plan-s3 D-71 leaves path-named commands to this check, so nothing checks them.

Fix: Test for the slash before stripping `./`, or treat a leading `./` word as a path. Add a test whose only path is `./tool`.

Evidence: `word = raw.rstrip(";,").replace("\\", "/").removeprefix("./")` then `if "/" in word or (index and FILE_NAME.fullmatch(word))`.

## r-002 medium spec (spec-fidelity)
`afkv2/skills/to-subtasks/scripts/check_plan.py:443`

A file already on the feature branch is exempt from the Scope-ownership refusal, which the acceptance bullet and SDD §7 do not state.

Why: The bullet and SDD §7 refuse every check path that no Scope in the chain owns; the code adds `and not base.has(path)`. D-59 records this as an executor decision, and the bullet stays unamended. A path under an existing folder also passes, such as `src/**/new.py` when `src` exists.

Fix: Take the exemption to the owner and amend the bullet and SDD §7, or remove it. Add a negative test for an existing unowned file.

Evidence: Code: `if not any(scope_owns(glob, path) for glob in owners) and not base.has(path)`. D-59: passes when the chain owns it or the file is on the feature branch.

## r-003 medium spec (spec-fidelity)
`afkv2/skills/to-subtasks/scripts/check_plan.py:364`

The plan check passes plans that the S3 start gate refuses: unknown `Blocked by` id, wait cycle, tracker with no `Status` column.

Why: The developer can approve the division, and `/afkv2:autopilot` then refuses to start. S3 `contracts_of` reports `unknown-blocker` and `blocked-by-cycle`, and `read_tracker` needs `Subtask` and `Status` columns.

Fix: Add unknown-blocker, cycle and `Status`-column failures to the check, or record why S3 alone owns them.

Evidence: `if not rows or "Subtask" not in rows[0]` in `_tracker_failures`; S3 start_gate.py: `failure("blocked-by-cycle", loop, ...)`.

## r-004 medium spec (spec-fidelity, logic-correctness)
`afkv2/skills/to-subtasks/scripts/plan_files.py:446`

The citation check runs only as a SKILL.md prose step. `division` and `approve` do not run it, so an unresolved plan can be approved.

Why: The script gates before approval call `check_plan` only, and that check holds no citation rule. A skipped step 4 gives an approved plan with unresolved citations.

Fix: Call `citation_failures` in `approve_division` and `build_division_round`, and test that it refuses.

Evidence: `run_top = _run_root(plan)` / `_require_clean_check(plan)` in `approve_division`; D-61.

## r-005 medium correctness (logic-correctness, spec-fidelity)
`afkv2/skills/to-subtasks/scripts/check_plan.py:459`

A plan folder with no contract file passes the check with ok true and an empty subtask list.

Why: A PLAN.md whose tracker has only a header row and no `NNNN-*.md` files gives no failure. `division` then builds a card for 0 subtasks, and `approve` can write the division line.

Fix: Add a failure when read_subtasks returns an empty list, with a test.

Evidence: check_plan(): `return {"ok": True, "subtasks": [subtask.id for subtask in subtasks], ...}` with no non-empty guard.

## r-006 medium correctness (logic-correctness)
`afkv2/skills/to-subtasks/scripts/check_plan.py:63`

check_paths treats `host:port/path` and `file::test` words as repository paths, so valid rows are refused as check-path-unowned.

Why: NOT_A_PATH skips `://` URLs but not `localhost:8080/health` or `tests/test_x.py::test_a`. Both hold a `/`, so check_paths returns them, and the remedy it names does not help.

Fix: Skip words with `host:port/`, `::` or an image-tag shape; cut a trailing `::...` before the path test; add tests.

Evidence: NOT_A_PATH = re.compile(r"^[-/~]|^[A-Za-z]:|^origin/|://|[\"'<>{}$%=|&]").

## r-007 medium correctness (test-veracity, scope-and-impact, logic-correctness)
`afkv2/skills/to-subtasks/scripts/check_plan.py:52`

The check accepts a division line with an impossible calendar date, and S3 refuses it.

Why: `APPROVAL` matches `\d{4}-\d{2}-\d{2}` only, so `2026-13-45` gives approved true. S3 `approval_failures` runs `date.fromisoformat` and answers `bad-approval`. `approve` writes today's date, so only a hand edit reaches this.

Fix: Validate the date with `date.fromisoformat` in `division_of`, and add one test.

Evidence: check_plan.py: `APPROVAL = re.compile(re.escape(APPROVAL_TEXT) + r"(\d{4}-\d{2}-\d{2})\s*")`.

## r-008 medium scope (scope-and-impact)
`afkv2/skills/to-subtasks/scripts/plan_files.py:89`

plan_files.py depends on underscore-private symbols of three other skills, and no `## Consumes` line declares them.

Why: A rename in `design_files`, `grill_start` or `round_document` breaks to-subtasks, and check (a) does not see the dependency.

Fix: Ask the owning skills for public names, or declare the consumed symbols in `## Consumes`.

Evidence: `design_files._open_question_problems(sdd_text)`; `grill_start._raw_pending(raw_file, doc)`; `rd._drop_unanswered_round(doc)`; `cp._app_of(...)`.

## r-009 medium test (test-veracity)
`afkv2/tests/skills/test_to_subtasks.py:339`

Two Scope-owner cases never reach `scope_owns`: the path `src` is never extracted from the check cell.

Why: `check_paths` takes a word as a path only with a `/` or a file name after the first word, so `ok is True` holds for any Scope. The folder-around-Scope rule goes untested.

Fix: Call `cp.scope_owns(scope, path)` directly for these cases, or use `src/`.

Evidence: ("src/**", "src", True) and ("src/a/**", "src", True) run `python -m pytest src -q`.

## r-010 medium test (test-veracity)
`afkv2/tests/skills/test_to_subtasks.py:874`

The `bad-approval` rule has no test: a duplicate `> Division:` line or a malformed one.

Why: `division_of` fails closed on 2 lines or a bad form, but every test uses the absent line or one well-formed line.

Fix: Add cases: 2 `> Division:` lines, `> Division: approved` with no date, `> Division: pending`.

Evidence: The rule is `if len(lines) > 1 or not match: ... failure("bad-approval", ...)`, and no test names `bad-approval`.

## r-011 medium test (test-veracity)
`afkv2/tests/skills/test_to_subtasks.py:172`

The anchor checks (b) have no test at their boundaries: length 11 and 12, and an anchor found once in the base.

Why: Only `class` and `short` test `len(anchor) < MIN_ANCHOR`, and only an anchor found twice tests `text.count(anchor) >= 2`.

Fix: Add a 12-character anchor that passes, an 11-character one that fails, and an anchor found once that passes.

Evidence: `if len(anchor) < MIN_ANCHOR` and `text.count(anchor) >= 2`.

## r-012 medium test (test-veracity)
`afkv2/tests/skills/test_to_subtasks.py:719`

The `("tree", folder)` branch of `Base`, a plan in an ordinary work tree, has no test.

Why: Every git-backed test runs on a `-run` branch, and the unit tests run outside a git repository.

Fix: Add a test with a plan in a repository whose branch does not end in `-run`.

Evidence: `return bool(kind and literal) and (Path(where) / literal).exists()`.

## r-013 medium test (test-veracity)
`afkv2/tests/skills/test_to_subtasks.py:1068`

The lockstep test with the S3 start gate pins 3 of the 8 copies the module docstring lists.

Why: Drift in `SPAN`, `PROGRAM`, `_programs`, `RUN_SUFFIX` and the division line stays silent after the merge.

Fix: Assert the patterns, `RUN_SUFFIX`, the `_programs` output for sample cells, and `APPROVAL` on a few lines.

Evidence: `assert gate.NOT_APPLICABLE == cp.NOT_APPLICABLE and set(gate.LIVE_TIERS) == cp.LIVE_TIERS`.

## r-014 low scope (scope-and-impact)
`.claude/wiring-ious.md:22`

Three wiring lines are added in `.claude/wiring-ious.md`, which no `## Scope` glob covers.

Why: The contract Scope does not list it; D-65 records the exception only in the ledger.

Fix: Keep the lines, because the user's wiring rule requires them; the planner can widen Scope.

Evidence: D-65: add them, outside `## Scope`, as 0007, 0008 and 0009 did.

## r-015 low spec (spec-fidelity)
`afkv2/skills/to-subtasks/scripts/plan_files.py:40`

The spec-file denylist is incomplete, so other spec-folder artifacts pass `commit` under `plan/`.

Why: INDEX-FORMAT.md also lists PROTOTYPE.md, DESIGN-REVIEW-PLAN.md, DEMO-PLAN.md and `understanding/`.

Fix: List each artifact, or allow only an explicit run-file set under `plan/`.

Evidence: `SPEC_FILES = {"PRD.md", "SDD.md", "GRILL-LOG.md", "INDEX.md", "VERIFICATION-PLAN.md", "DESIGN-BRIEF.md"}`.

## r-016 low correctness (logic-correctness)
`afkv2/skills/to-subtasks/scripts/plan_files.py:179`

A PRD citation with a bare number resolves against any matching token in the PRD text.

Why: `PRD §3` passes when a standalone `3` appears anywhere in PRD.md. `PLAN.md decision D-S-1` also matches `D-S-10` as a substring.

Fix: Resolve PRD ids against the ids the PRD defines; match decision ids with a word boundary.

Evidence: `re.search(rf"(?<![\w-]){re.escape(item)}(?![\w-])", self.prd)`; `plan_part.group(1) in self.plan`.

## r-017 low correctness (logic-correctness)
`afkv2/skills/to-subtasks/scripts/plan_files.py:238`

A `## Design refs` bullet that matches neither the SDD form nor the ADR form is skipped without a failure.

Why: A malformed binding reference reaches autopilot unchecked.

Fix: Add an else branch with a C-UNRESOLVED failure, and a test.

Evidence: `if sdd: ... elif adr: ...` with no else.

## r-018 low test (test-veracity)
`afkv2/tests/skills/test_to_subtasks.py:736`

The citation resolver is tested only on failures for the `PLAN.md decision` form and the quoted-row form.

Why: A resolver that always refuses those forms passes every test.

Fix: Add one passing case each.

Evidence: The `D-404` case and the `row "no such row"` case.

## r-019 low test (test-veracity)
`afkv2/tests/skills/test_to_subtasks.py:358`

`test_each_path_form_is_read_from_a_check_cell` asserts that some path is unowned, not which path was read.

Why: A wrong extraction is also unowned, so the 5 forms cannot tell right from wrong.

Fix: Assert the failure `reason` names the expected path.

Evidence: assert "check-path-unowned" in codes_of(answer)

## r-020 low test (test-veracity)
`afkv2/tests/skills/test_to_subtasks.py:1035`

`test_the_conflict_procedure_heading_stands_once` is the same test as `test_the_format_file_holds_the_conflict_anchor_once`.

Why: The 2 bodies are identical.

Fix: Delete one.

Evidence: `(SKILL_DIR / "SUBTASK-CONTRACT.md").read_text("utf-8").count("## Conflict procedure") == 1`

## r-021 low test (test-veracity)
`afkv2/tests/skills/test_to_subtasks.py:999`

The design-session test hard-codes the session name, not the name `_new_session` makes.

Why: D-57 relies on the `s-` prefix sorting after `division-`, and a copy of that name does not follow a rename.

Fix: Build the name with `design_files._new_session(pages)`.

Evidence: `(pages / f"{design_files.DOC_PREFIX}s-20200101-000000.json").write_text("{}", "utf-8")`

## r-022 low test (test-veracity)
`afkv2/tests/skills/test_to_subtasks.py:93`

The autouse fixture replaces `shutil.which` on the shared stdlib module for every test in the file.

Why: The patch reaches all in-process code, not only `check_plan`.

Fix: Add a module-level seam in `check_plan`, or patch a namespace.

Evidence: monkeypatch.setattr(cp.shutil, "which", lambda name: None if name.startswith("no-such") else name)

## r-023 low test (test-veracity)
`afkv2/tests/skills/test_to_subtasks.py:839`

3 tests compare the approval date with `date.today()` read after the run.

Why: A run that crosses midnight writes one day and expects the next.

Fix: Read the date back from the answer.

Evidence: `day = date.today().isoformat()` after `answer = world.approve(started)`.
