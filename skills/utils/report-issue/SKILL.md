---
name: report-issue
description: "Proposes a GitHub issue when an observed problem may come from AFK, then files approved evidence as a new issue or a comment on an existing issue. Use for AFK hook or script failures, workflow inefficiency or slowness, unexpected agent behavior under AFK instructions, plugin contract failures, a review of reportable session signals, /afk:report-issue, or `publish` to drain queued drafts."
---

> **Language:** read `LANGUAGE.md` (plugin root) first — it binds every word this skill produces.

# afk:report-issue — propose a plugin issue

Scripts: `${AFK_PLUGIN_ROOT}/skills/utils/report-issue/scripts/`. Every script documents its arguments and exit codes in its header.

**Scope.** Which signals are issues, and of which kind: `skills/afk/lessons/CAPTURE.md` "A plugin defect is an issue". This skill writes no lesson ledger line.

**Approval.** `--approved` on `publish.sh` means the human answered an explicit yes in this conversation to the exact redacted body, target repository, and shown action. Pass it only after that answer. A preview needs no approval and performs no write.

## Argument

- empty or free text → file one issue (steps 1-7); the text is the human's description.
- `publish` → drain the queue (section "Drain").

## Steps

1. **Sweep session evidence.** Before answering whether anything qualifies, enumerate every plugin or harness signal in the current conversation and tool output: a hook, script, command, or gate that failed, timed out, crashed, retried, needed a workaround, returned an unexpected status, or ran unusually slowly. Recovery does not erase the signal. Give each one a disposition: `plugin-owned`, `not plugin-owned`, or `unverified: <reason>`.
2. **Investigate.** For every `plugin-owned` or `unverified` signal, prove the caller, input, and reachable failing path before classifying it. Include workflow inefficiency, performance, and unexpected agent behavior when an AFK file can own the correction. No plugin file can own it → continue the current task and do not propose an issue.
3. **Classify** per the Scope pointer: kind `bug` or `feedback`. Name the owning plugin file: the plugin-relative path whose edit fixes it. State uncertainty as `unverified: <reason>`; uncertainty does not become a defect claim.
4. **Gather.** Run `collect_env.sh` (with `--plan-dir <plan dir>` inside a feature run). Collect all relevant plugin-side evidence from the current context: the failing command with its exit code and output tail, the active skill and step, `OUTCOME:` and other status lines, hook stderr, the observed cost or delay, and the investigation result. Product code, product paths, ticket ids, and the consuming repository's name or remotes stay out of every field.
5. **Fingerprint.** `fingerprint.py --kind <kind> --file <owning file> --signature "<first error line, or the feedback in one line>"`.
6. **Draft** the title and body per [ISSUE-TEMPLATE.md](ISSUE-TEMPLATE.md) into a scratch file. Every template section is present; `publish.sh` queues a body missing one.
7. **Redact.** `redact.py --repo-root <git root> --keep-repo <target> -o <redacted file> <draft>`. Exit 1 lists residual hits by line and class. `publish.sh` redacts the title and body again before any send.
8. **Find an existing issue.** Search the target by fingerprint, owning file, and symptom. A matching cause and scope is the same issue, including a closed issue. Record its number as `<existing>`; a keyword match alone is not enough.
9. **Preview.** Run `publish.sh --body <redacted file> --title <title> --kind <kind> --fp <fp> --dry-run [--existing <existing>]`. Show the full output. It names the target and whether approval will create an issue or add the current context to an existing issue. A preview with `preview-unverified` is incomplete; fix its lookup blocker before asking.
10. **Ask once.** Suggest the issue in one sentence, then ask for approval of the shown action and body. A decline ends this route. Silence or an inferred yes is not approval.
11. **Publish.** After an explicit yes, repeat the preview command without `--dry-run` and add `--approved`. Exit 4 (residual refused) → show each hit; the human edits the body, or accepts every hit, and the retry adds `--accept-residual`. Exit 3 means queued; report the reason and the publish command the script printed.
12. **Report** per `REPORTING.md` (plugin root): the script's `ISSUE:` line, then one `In plain terms:` sentence.

## Drain

`publish` is a human run. `publish.sh --list` names each queued draft. For each one, preview it with `publish.sh --from-queue <file> --dry-run`. Show its body, target, action, and `redact.py --check` hits. Ask publish, skip, or delete. Publish on an explicit yes → `publish.sh --from-queue <file> --approved` (add `--accept-residual` only when the human accepted every hit). The script deletes the draft once it lands. Delete → remove the file. Report one `ISSUE:` line per draft.
