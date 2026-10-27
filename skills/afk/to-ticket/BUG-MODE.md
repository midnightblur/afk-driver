> **Language:** read `LANGUAGE.md` (plugin root) first — it binds every word this file produces.

# Bug and ad-hoc mode — file a ticket from a diagnosis or a description

Creates or updates one ticket on the configured tracker (Jira or GitHub Issues) from a `DIAGNOSIS.md`, or from a description written to a file in the spec folder first. Engine: [`scripts/publish_bug_mode.py`](./scripts/publish_bug_mode.py). Diagnosis parts, the Outside writes entries and the evidence marker: `${AFK_PLUGIN_ROOT}/skills/utils/diagnose/DIAGNOSIS-FORMAT.md`.

## Rules (binding)

- **Consent.** Run a write only with a person present (`--consent person`) or under a prior approval that covers ticket writes (`--consent prior`). Neither → do not run it; the script refuses too.
- **Description only on a ticket this mode creates.** On an existing ticket it only comments; it never edits the description, so the PRD block and the Meeting Summaries region stay as they are.
- **Ticket key.** The diagnosis's Ticket key is set only while empty. A different key given later is listed in Outside writes, and the recorded key stays.
- **Spec folder.** After it creates a ticket from a diagnosis, the script re-resolves the spec folder with the new key and moves the folder when the path differs; the key becomes the work id.
- **Assignee.** A created ticket takes `trackerAssignee` (`CONFIG.md` "Developer settings (K1–K5)"). Unset → the ticket is filed unassigned and the output names the key.

## How to run

1. **Input.** A diagnosis path the diagnosis check accepts, or a description file (`--description`). Optional: `--type bug|enhancement` (default `bug`, applied to a created ticket), `--key` for an existing ticket, `--summary` for a created ticket's title, `--proof P-n=PATH` per proof file, `--in-review`.
2. **Fix version (Jira).** With a person present, ask which fix version the ticket takes and pass `--fix-version`; no answer → leave it out. Hands-off → leave it out. GitHub Issues → do not ask.
3. **Dry run** — every check, no write; prints the payloads:

   ```
   afk-python ${AFK_PLUGIN_ROOT}/skills/afk/to-ticket/scripts/publish_bug_mode.py --diagnosis <path> [options] --dry-run
   ```

   With a person present, show the plan and get a go-ahead.
4. **Publish** — same command without `--dry-run`, with `--consent person|prior` and `--yes`.

**Done when:** the script prints `TICKET: <key> <link>` and exits 0. Exit 1 → refused, nothing written: report the `REFUSED:` line. Exit 2 → a write failed after its retries and no write followed it: report the `FAILED:` line; a re-run resumes.

## Refusals, before any write

Tracker kind `none` or a tracker with no bug mode; no consent; the diagnosis check refuses the file; the in-review key is not configured (`jira.transitions.in-review`, `github-issues.state-labels.in-review`); `--in-review` on a ticket that offers no transition matching it by name or id; a given or recorded key the tracker does not return; an unknown type (Jira issue type, or a GitHub label that does not exist); an unknown Jira fix version, or any fix version on GitHub Issues; a missing proof file or a proof kind outside P-1, P-2, P-3; a description file that is empty; no confirmation.

## Write order

Steps run in this order and stop at the first failure:

| Step | Write | Outside writes entry |
|---|---|---|
| ticket | create, the summary as the description with the marker; skipped when a key exists | `ticket: <key>` |
| fix-version | Jira, existing ticket: add the version to those set | none; read from the ticket |
| evidence | one comment: the diagnosis parts and the change link from Outside writes, with the marker; a description input comments only on an existing ticket | `evidence: <marker>` |
| proof | `tracker_attach`: files named `{work id}-{kind}-proof-{file name}` and a comment listing them with the marker; a file the tracker would not take is named in the comment and in a `NOTE:` line | `evidence: <marker>` |
| in-review | move to the configured in-review state | `in-review: <key>` |

A listed step is skipped. Every other write is read back first, by its marker or the ticket's state; a failed write is retried at most twice, each after a read-back shows it left nothing. A refusal or a 4xx answer is shown and never retried; a 5xx or network failure is retried.
