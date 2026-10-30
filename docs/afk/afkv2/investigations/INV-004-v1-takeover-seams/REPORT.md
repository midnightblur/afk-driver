midnightblur/afk-driver@8e6ef1cfd1bd5f4cc199bc8114bca29cac98bbd1 · closed-with-frontier · boundaries 13/14 · unverified 4 (load-bearing 0) · ledger: docs/afk/afkv2/investigations/INV-004-v1-takeover-seams/COVERAGE.json

## Answer

- Rule block: `<!-- afk:behaviors:start|end -->` (+ legacy plain-language, lavish-sessions, investigation) in `${CLAUDE_CONFIG_DIR:-~/.claude}/CLAUDE.md` and `${CODEX_HOME:-~/.codex}/AGENTS.md` (hooks/lib/providers/claude.sh:46, codex.sh:46). Install replaces the first match, drops the rest, else appends; teardown removes every match; locked, atomic, target-EOL (install_block.py:237-299). Writers: setup H7 fix only (MANIFEST.md:254), teardown (setup SKILL.md:35). Reader: SessionStart drift check (hooks.json:24 -> behavior-drift.sh:21-25 -> behavior_registry.py audit).
- Rule block removed from both files: behavior text stops reaching sessions (adr/0005:8-16). Drift check exits silently, no notice (behavior-drift.sh:24-25; hook-smoke.sh:564). Consent record lost: setup sees "opt-in available" and asks again (MANIFEST.md:223-226). Nothing re-adds it without the human. One file only stripped: next /afk:setup re-adds it without asking (inference, behavior_registry.py:779-780, SKILL.md:116).
- Git stubs: written by install-git-hooks.sh into the common hooks dir (:53-55) at every SessionStart (hooks.json:9, hooks.codex.json:9, --quiet). Grammar: marker line, `# afk-plugin-root:` line, `exec bash <root>/hooks/<gate>` (:88-96). Readers of the grammar: installer (:71,:73), precommit-gates.sh:51-53, background_git_hooks.py:81, MANIFEST.md:112 H5 probe.
- Stubs moved aside: v1 loses the protected-branch backstop, branch-name rule, main-sync retirement (branch-name-gate.sh:54,:68; git-backstop.py:108-110) and all commit gates incl. repo PreCommit handlers (precommit-gates.sh:44-200). Next v1 SessionStart: empty path -> stub silently rewritten (proven in sandbox); foreign hook -> kept, stderr notice, exit 0; foreign hook containing the marker string -> treated as ours: overwritten if the root line differs, kept as-is if it matches (install-git-hooks.sh:71, unanchored grep); core.hooksPath set -> skipped (:47-49).
- PRD block: start = paragraph text startswith `afk:prd:start`, end = exact `afk:prd:end` (publish_prd.py:157-164). Barebone remainder absorbs all; no block -> append after a rule; block -> same position (:213-230). Pictures: delete `^afk-fig\d+\.png$`, upload, then one PUT (:285-304, :337). Other description writers (tracker_edit, publish_meeting.py:150, publish_bug.py:242) ignore the markers.
- Block replaced by `afkv2:prd:*`: v1 re-run finds no block; rich remainder -> second PRD copy appended (:223); barebone -> foreign block absorbed and deleted (:217-219); `--changes` comment dropped (:309). v1 never deletes `afkv2-fig-*` pictures; it does delete any `afk-fig<N>.png`. publish_meeting.py unaffected (:82-98).

## Findings
- install-git-hooks.sh:71 marker check is an unanchored grep: can silently destroy or hide a foreign hook; :26 "Non-destructive" is false for that case. No test.
- publish_prd.py:217 barebone rule can absorb a short Meeting Summaries region today (probe ev-t3); contradicts to-ticket SKILL.md:16, REFERENCE.md:84-85.
- hooks/README.md:99 says the drift check compares both files; code checks only the session's own file (behavior-drift.sh:21).
- No test covers merge, figure lifecycle, or the takeover cases; most breaking sites are unguarded.

## Frontier
- B14: other repositories, live Jira behaviour, harness display of SessionStart stderr (no network, no harness run).

## Unverified
- How Jira renders a media node whose attachment was deleted (no network).
- Whether a disabled v1 plugin's files stay at the root the stub records.
- Whether the human sees the --quiet stderr refusal notice (harness display not checked).
- Orchestrator reconciliation: t4 (blind counter-search) rows for 60 nodes already held by t1-t3 were dropped in favour of the owner's disposition; two t4 nodes set traced->terminal (child held elsewhere). Disagreements adjudicated by reading: publish_prd.py:337 breaks; README.md:107 unchanged.
