---
name: report-issue
description: "Files a GitHub issue about the AFK plugin itself — a plugin defect or feedback — from session evidence, redacted and deduplicated. Use on /afk:report-issue, when a plugin script, hook, or skill contract breaks, or with `publish` to drain queued drafts."
---

> **Language:** read `LANGUAGE.md` (plugin root) first — it binds every word this skill produces.

# afk:report-issue — send a plugin defect upstream

Scripts: `${AFK_PLUGIN_ROOT}/skills/utils/report-issue/scripts/`. Every script documents its arguments and exit codes in its header.

**Scope.** Which signals are issues, and of which kind: `skills/afk/lessons/CAPTURE.md` "A plugin defect is an issue". This skill writes no lesson ledger line.

**Mode.** Human run: the human typed `/afk:report-issue` in this turn. Agent run: every other invocation.

**Approval.** `--approved` on `publish.sh` means the human answered an explicit yes in this conversation to the exact body and target shown. Pass it only then — never in an agent run, never on an inferred yes. One exception: a human run's preview is `--dry-run --approved`, since a dry run sends nothing.

## Argument

- empty or free text → file one issue (steps 1-7); the text is the human's description.
- `publish` → drain the queue (section "Drain").

## Steps

1. **Classify** per the Scope pointer: kind `bug` or `feedback`. Name the owning plugin file: the plugin-relative path whose edit fixes it. No plugin file can own it → stop; it is not a plugin issue.
2. **Gather.** Run `collect_env.sh` (with `--plan-dir <plan dir>` inside a feature run). Collect the plugin-side evidence: the failing command with its exit code and output tail, `OUTCOME:` and other status lines, hook stderr. Product code, product paths, ticket ids, and the consuming repository's name or remotes stay out of every field.
3. **Fingerprint.** `fingerprint.py --kind <kind> --file <owning file> --signature "<first error line, or the feedback in one line>"`.
4. **Draft** the title and body per [ISSUE-TEMPLATE.md](ISSUE-TEMPLATE.md) into a scratch file. Every template section is present; `publish.sh` queues a body missing one.
5. **Redact.** `redact.py --repo-root <git root> --keep-repo <target> -o <redacted file> <draft>`. Exit 1 lists residual hits by line and class. `publish.sh` redacts the title and body again before any send.
6. **Publish** with `publish.sh --body <redacted file> --title <title> --kind <kind> --fp <fp>`:
   - Agent run: call it without `--approved`. The script queues the draft on a residual hit, an incomplete body, an unreadable configuration, `report-issue.auto-publish` not `true` (`CONFIG.md`), no logged-in `gh`, or a failed `gh` call.
   - Any run: exit 3 means queued, with the reason printed; report it with the publish command the script printed.
   - Human run: first run it with `--dry-run --approved` and show the full redacted title, body, and target repository it prints. On an explicit yes, re-run with `--approved`. Exit 4 (residual refused) → show each hit; the human edits the body, or accepts every hit, and the retry adds `--approved --accept-residual`.
7. **Report** per `REPORTING.md` (plugin root): the script's `ISSUE:` line, then one `In plain terms:` sentence. A queued draft also gets the publish command the script printed.

## Drain

`publish` is a human run. `publish.sh --list` names each queued draft. For each one: show its body, its target repository, and `redact.py --check` hits; ask publish, skip, or delete. Publish on an explicit yes → `publish.sh --from-queue <file> --approved` (add `--accept-residual` only when the human accepted every hit). The script deletes the draft once it lands. Delete → remove the file. Report one `ISSUE:` line per draft.
